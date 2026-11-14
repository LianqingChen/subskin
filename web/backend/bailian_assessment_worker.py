"""Run one allowlisted Bailian job at a time in a bounded child process."""

import argparse
import json
import logging
from datetime import datetime
from time import sleep, time

from web.backend.database.database import SessionLocal
from web.backend.database.models import AuditLog, User
from web.backend.exceptions import RGBSegmentationError
from web.backend.models.rgb_segmentation import RGBSegmentationJob
from web.backend.services.consent import health_data_consent_missing
from web.backend.services.rgb_segmentation import artifacts, bailian_consent as consent
from web.backend.services.rgb_segmentation.jobs import claim_job

logger = logging.getLogger("bailian_preview")
HEARTBEAT = consent.HEARTBEAT


def run_job(job_id, lease):
    from web.backend.services.rgb_segmentation.bailian_inference import run
    from web.backend.services.rgb_segmentation.pipeline import process_job

    def infer(rgb, source):
        key = consent.provider_key()
        if not key:
            raise RGBSegmentationError("BAILIAN_UNAVAILABLE", "百炼试测暂不可用", 503)

        with SessionLocal() as db:
            job = db.query(RGBSegmentationJob).filter_by(id=job_id, lease=lease, state="running").first()
            if job is None:
                raise RGBSegmentationError("CANCELLED", "分析已取消", 409)
            grant = consent.verify_job(db, job, source)
        compare_fusion = grant["notice"] == consent.NOTICE

        def before_send(stage, canonical_sha):
            with SessionLocal() as db:
                job = db.query(RGBSegmentationJob).filter_by(id=job_id, lease=lease, state="running").first()
                if job is None or job.deadline_at <= datetime.utcnow():
                    raise RGBSegmentationError("CANCELLED", "分析已取消或超时", 409)
                owner = db.query(User).filter_by(id=job.user_id, is_active=True).first()
                if owner is None or owner.user_status == "banned" or health_data_consent_missing(db, job.user_id):
                    raise RGBSegmentationError("BAILIAN_CONSENT_REQUIRED", "本次照片分析授权已失效", 403)
                if consent.verify_job(db, job, source) != grant or (stage.startswith("smallspot_") and not compare_fusion):
                    raise RGBSegmentationError("BAILIAN_CONSENT_REQUIRED", "请重新确认本次百炼照片分析", 403)
                db.add(AuditLog(
                    user_id=job.user_id, action="diary_external_analysis_requested",
                    target_type="rgb_segmentation_job", scope="private", revokeable=False,
                    detail=json.dumps({"job_id": job.id, **grant,
                                       "canonical_sha256": canonical_sha, "stage": stage}),
                ))
                db.commit()

        return run(rgb, key, before_send, compare_fusion=compare_fusion)

    try:
        process_job(job_id, lease, assessment_inference=infer)
    except RGBSegmentationError as exc:
        fail(job_id, lease, exc.code)
    except Exception as exc:
        logger.error("Bailian preview failed for job %s (%s)", job_id, type(exc).__name__)
        fail(job_id, lease, "BAILIAN_UNAVAILABLE")


def fail(job_id, lease, code):
    with SessionLocal() as db:
        db.query(RGBSegmentationJob).filter_by(id=job_id, lease=lease, state="running").update(
            {"state": "failed", "stage": "failed", "error_code": code, "updated_at": datetime.utcnow()},
            synchronize_session=False,
        )
        db.commit()


def supervise():
    import fcntl
    import signal
    import subprocess
    import sys

    from web.backend.rgb_segmentation_worker import terminate_child

    artifacts.ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    stopping = False

    def stop(_signum, _frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    with (artifacts.ROOT / "bailian-preview.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with SessionLocal() as db:
            interrupted = db.query(RGBSegmentationJob).filter_by(state="running").filter(
                RGBSegmentationJob.context_json.contains('"external_analysis":')
            )
            interrupted.update(
                {"state": "failed", "stage": "failed", "error_code": "WORKER_RESTARTED"},
                synchronize_session=False,
            )
            db.commit()
        try:
            while not stopping:
                artifacts.atomic_write(HEARTBEAT, str(time()).encode())
                if not consent.provider_key():
                    sleep(1)
                    continue
                with SessionLocal() as db:
                    job = claim_job(db, queue=consent.QUEUE)
                if job is None:
                    sleep(0.5)
                    continue
                child = subprocess.Popen(
                    [sys.executable, "-m", "web.backend.bailian_assessment_worker", "--job", job.id, "--lease", job.lease],
                    start_new_session=True,
                )
                outcome = "BAILIAN_UNAVAILABLE"
                try:
                    while child.poll() is None and not stopping:
                        artifacts.atomic_write(HEARTBEAT, str(time()).encode())
                        with SessionLocal() as db:
                            current = db.query(RGBSegmentationJob).filter_by(id=job.id, lease=job.lease).first()
                            if current is None or current.state != "running":
                                break
                            if current.deadline_at <= datetime.utcnow():
                                outcome = "TIMEOUT"
                                break
                        sleep(0.5)
                finally:
                    terminate_child(child)
                    fail(job.id, job.lease, "WORKER_RESTARTED" if stopping else outcome)
        finally:
            HEARTBEAT.unlink(missing_ok=True)


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--job")
    cli.add_argument("--lease")
    args = cli.parse_args()
    if args.job and args.lease:
        run_job(args.job, args.lease)
    else:
        supervise()

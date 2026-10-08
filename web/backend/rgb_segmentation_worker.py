"""Durable bounded worker and disposable inference subprocesses.

Run with the existing backend environment, independently from uvicorn.
"""

import argparse
import json
import logging
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from datetime import datetime

logger = logging.getLogger("rgb_worker")


def inference(job_id: str, lease: str) -> int:
    from web.backend.services.rgb_segmentation.pipeline import process_job
    from web.backend.exceptions import RGBSegmentationError
    from web.backend.database.database import SessionLocal
    from web.backend.models.rgb_segmentation import RGBSegmentationJob

    try:
        import cv2

        cv2.setNumThreads(2)
        process_job(job_id, lease)
        return 0
    except RGBSegmentationError as exc:
        code = exc.code
    except Exception:
        logger.exception("RGB inference failed for task %s", job_id)
        code = "SERVICE_UNAVAILABLE"
    with SessionLocal() as db:
        db.query(RGBSegmentationJob).filter_by(
            id=job_id, lease=lease, state="running"
        ).update(
            {
                "state": "failed",
                "stage": "failed",
                "error_code": code,
                "updated_at": datetime.utcnow(),
            },
            synchronize_session=False,
        )
        db.commit()
    return 1


def terminate_child(child: subprocess.Popen) -> None:
    if child.poll() is not None:
        return
    try:
        os.killpg(child.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        child.wait(timeout=3)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            return
        child.wait(timeout=3)


def run_worker() -> None:
    import fcntl
    from web.backend.database.database import SessionLocal
    from web.backend.models.rgb_segmentation import RGBSegmentationJob
    from web.backend.services.rgb_segmentation import artifacts
    from web.backend.services.rgb_segmentation.jobs import claim_job

    artifacts.ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock = (artifacts.ROOT / "worker.lock").open("a")
    fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    stopping = False

    def stop(_signum, _frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    with SessionLocal() as db:
        # Previous process leases cannot finish after a worker restart.
        db.query(RGBSegmentationJob).filter_by(state="running").update(
            {"state": "failed", "stage": "failed", "error_code": "WORKER_RESTARTED"},
            synchronize_session=False,
        )
        db.commit()
    heartbeat = artifacts.ROOT / "worker-heartbeat.json"
    child = None
    last_cleanup = 0.0
    try:
        while not stopping:
            artifacts.atomic_write(
                heartbeat,
                json.dumps({"at": time.time(), "version": "rgb-worker-v1"}).encode(),
            )
            if time.monotonic() - last_cleanup > 3600:
                from web.backend.services.rgb_segmentation.cleanup import cleanup_jobs

                cleanup_jobs()
                last_cleanup = time.monotonic()
            with SessionLocal() as db:
                job = claim_job(db)
                if job is None:
                    time.sleep(0.5)
                    continue
                job_id, lease = job.id, job.lease
            child = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "web.backend.rgb_segmentation_worker",
                    "--infer",
                    job_id,
                    "--lease",
                    lease,
                ],
                cwd=str(artifacts.PROJECT_ROOT),
                start_new_session=True,
            )
            try:
                while child.poll() is None:
                    artifacts.atomic_write(
                        heartbeat,
                        json.dumps(
                            {"at": time.time(), "version": "rgb-worker-v1"}
                        ).encode(),
                    )
                    with SessionLocal() as db:
                        current = (
                            db.query(RGBSegmentationJob)
                            .filter_by(id=job_id, lease=lease)
                            .first()
                        )
                        cancelled = current is None or current.state != "running"
                        expired = (
                            current is not None
                            and current.deadline_at <= datetime.utcnow()
                        )
                        if expired and current.state == "running":
                            current.state, current.stage, current.error_code = (
                                "failed",
                                "failed",
                                "TIMEOUT",
                            )
                            db.commit()
                    if stopping or cancelled or expired:
                        terminate_child(child)
                        break
                    time.sleep(0.3)
                child.wait()
                with SessionLocal() as db:
                    db.query(RGBSegmentationJob).filter_by(
                        id=job_id, lease=lease, state="running"
                    ).update(
                        {
                            "state": "failed",
                            "stage": "failed",
                            "error_code": "SERVICE_UNAVAILABLE",
                        },
                        synchronize_session=False,
                    )
                    db.commit()
            finally:
                terminate_child(child)
                child = None
    finally:
        heartbeat.unlink(missing_ok=True)
        lock.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--infer")
    parser.add_argument("--lease")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    if args.infer:
        if not args.lease:
            parser.error("--lease required")
        return inference(args.infer, args.lease)
    run_worker()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

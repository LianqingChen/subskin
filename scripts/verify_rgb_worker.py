"""Exercise real worker processes against a disposable database and synthetic photo.

This script overrides database/artifact/registry paths before importing backend code.
It never uses live user records or exports training samples.
"""

import argparse
import io
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sam", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="subskin-rgb-worker-test-") as temporary:
        temp = Path(temporary)
        os.environ["DATABASE_URL"] = "sqlite:///" + str(temp / "test.sqlite")
        os.environ["SECRET_KEY"] = secrets.token_hex(32)
        os.environ["RGB_SEGMENTATION_DATA_ROOT"] = str(temp / "artifacts")
        os.environ["RGB_SEGMENTATION_REGISTRY"] = str(temp / "registry.json")
        os.environ["OMP_NUM_THREADS"] = "2"
        os.environ["MKL_NUM_THREADS"] = "2"
        (temp / "registry.json").write_text('{"enabled":false}')
        import numpy as np
        from PIL import Image
        from web.backend.api.rgb_segmentation import router
        from web.backend.database.database import Base, engine, SessionLocal
        from web.backend.database.models import User
        from web.backend.models.rgb_segmentation import RGBSegmentationJob
        from web.backend.models.vasi import VASIAssessment
        from web.backend.models.image_label import ImageLabel  # Register admin projection tables.
        from web.backend.services.rgb_segmentation.jobs import (
            create_job,
            cancel_job,
            serialize_job,
        )
        from web.backend.services.rgb_segmentation.refinement import enqueue_refinement
        from web.backend.services.rgb_segmentation import artifacts
        from web.backend.services.annotation_contract import encode_layer

        Base.metadata.create_all(engine)
        with SessionLocal() as db:
            db.add(User(id=1, username="synthetic-worker-owner", is_active=True))
            db.commit()
        rng = np.random.default_rng(2)
        rgb = np.clip(
            np.array([178, 137, 112]) + rng.integers(-15, 16, (600, 800, 3)), 0, 255
        ).astype(np.uint8)
        rgb[200:300, 300:500] = np.clip(
            np.array([224, 214, 195]) + rng.integers(-8, 9, (100, 200, 3)), 0, 255
        )
        stream = io.BytesIO()
        Image.fromarray(rgb).save(stream, format="PNG")
        source = stream.getvalue()
        with SessionLocal() as db:
            jid = create_job(db, 1, "synthetic-worker-main", source, "face", {}).id
        log = (temp / "worker.log").open("w")
        process = subprocess.Popen(
            [sys.executable, "-m", "web.backend.rgb_segmentation_worker"],
            cwd=str(root),
            env={
                key: value
                for key, value in os.environ.items()
                if key
                in {
                    "PATH",
                    "HOME",
                    "LANG",
                    "LC_ALL",
                    "LD_LIBRARY_PATH",
                    "PYTHONPATH",
                    "DATABASE_URL",
                    "RGB_SEGMENTATION_DATA_ROOT",
                    "RGB_SEGMENTATION_REGISTRY",
                    "OMP_NUM_THREADS",
                    "MKL_NUM_THREADS",
                }
            },
            stdout=log,
            stderr=log,
        )

        def poll(jid, predicate, seconds=45):
            deadline = time.monotonic() + seconds
            while time.monotonic() < deadline:
                with SessionLocal() as db:
                    data = serialize_job(
                        db.query(RGBSegmentationJob).filter_by(id=jid).one()
                    )
                if predicate(data):
                    return data
                if process.poll() is not None:
                    raise AssertionError("Worker exited unexpectedly")
                time.sleep(0.1)
            raise AssertionError("Timed out waiting for synthetic task")

        report = {}
        try:
            complete = poll(jid, lambda row: row["state"] in ("completed", "failed"))
            assert complete["state"] == "completed", complete
            report["assessment_job_completed"] = True
            report["untrained_candidate_requires_review"] = (
                complete["result"]["status"] == "review_required"
            )
            with SessionLocal() as db:
                cancelled = create_job(
                    db, 1, "synthetic-worker-cancel", source, "face", {}
                )
                cid = cancelled.id
                cancel_job(db, cid, 1)
            assert (
                poll(cid, lambda row: row["state"] == "cancelled")["assessment_id"]
                is None
            )
            report["cancelled_job_no_assessment"] = True
            skin_data = encode_layer(np.ones((600, 800), bool), (96, 165, 250))
            points = [{"x": 400.5 / 800, "y": 250.5 / 600, "label": 1}]
            if args.sam:
                with SessionLocal() as db:
                    rid = enqueue_refinement(
                        db,
                        jid,
                        1,
                        "synthetic-sam-refine",
                        complete["result"]["mask_revision"],
                        skin_data,
                        points,
                        [0.25, 0.22, 0.75, 0.61],
                    ).id
                refined = poll(
                    rid, lambda row: row["state"] in ("completed", "failed"), 80
                )
                report["sam_refinement_state"] = refined["state"]
                report["sam_refinement_error"] = refined["error_code"]
                assert refined["state"] == "completed", refined
                report["sam_measurement_still_requires_review"] = (
                    refined["result"]["measurement"] is None
                )
            # Force an actual running subprocess to hit its deadline.
            with SessionLocal() as db:
                tid = enqueue_refinement(
                    db,
                    jid,
                    1,
                    "synthetic-worker-timeout",
                    complete["result"]["mask_revision"],
                    skin_data,
                    points,
                    None,
                ).id
            poll(tid, lambda row: row["state"] == "running")
            with SessionLocal() as db:
                job = db.query(RGBSegmentationJob).filter_by(id=tid).one()
                job.deadline_at = datetime.utcnow() + timedelta(milliseconds=30)
                db.commit()
            timed = poll(tid, lambda row: row["state"] == "failed")
            assert timed["error_code"] == "TIMEOUT"
            # Wait for the parent to reap the disposable inference process.
            deadline = time.monotonic() + 6
            while time.monotonic() < deadline:
                children = subprocess.run(
                    ["pgrep", "-P", str(process.pid)], capture_output=True, text=True
                ).stdout.strip()
                if not children:
                    break
                time.sleep(0.1)
            assert not children
            report["running_process_timeout_reaped"] = True
            with SessionLocal() as db:
                assert db.query(VASIAssessment).count() == 1
            report["no_late_assessment_after_cancel_or_timeout"] = True
        finally:
            process.terminate()
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
            log.close()
            # The normalized public-view file was written only in this candidate root.
            image = root / "data/uploads/vasi" / ("rgb_" + jid + ".png")
            image.unlink(missing_ok=True)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2))
        args.output.chmod(0o600)
        print(json.dumps(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Delete expired/unowned private job artifacts; keep active observation revisions."""

import json
import logging
import shutil
from datetime import datetime, timedelta
from typing import Set

from sqlalchemy.exc import SQLAlchemyError
from web.backend.database.database import SessionLocal
from web.backend.database.models import User
from web.backend.exceptions import RGBSegmentationError
from web.backend.models.image_label import ImageLabel, ImageLabelLog
from web.backend.models.rgb_segmentation import RGBSegmentationJob
from web.backend.models.vasi import VASIAssessment
from web.backend.services.assessment_measurement import read_details
from web.backend.services.rgb_segmentation import artifacts

logger = logging.getLogger(__name__)


def _labeling_retained_revisions(db, job_id: str) -> Set[str]:
    """Revisions still referenced by admin image-labeling tasks for this job.

    Without this, ``cleanup_jobs`` deletes pixel-reviewed AI drafts about an hour
    after write (they are not in VASI assessment.details), and the labeling
    workspace then shows「标注版本暂不可用」.
    """
    kept: Set[str] = set()
    for label in (
        db.query(ImageLabel)
        .filter(ImageLabel.ai_details.contains(job_id))
        .all()
    ):
        sync = read_details(label.ai_details).get("rgb_sync") or {}
        if sync.get("job_id") != job_id:
            continue
        kept.update(
            {
                sync.get("ai_revision"),
                sync.get("previous_ai_revision"),
                (sync.get("gold") or {}).get("revision")
                if isinstance(sync.get("gold"), dict)
                else None,
            }
        )
        for row in (
            db.query(ImageLabelLog)
            .filter_by(image_label_id=label.id)
            .filter(ImageLabelLog.action.in_(("rgb-user-reference", "ai-draft-replaced")))
            .all()
        ):
            value = read_details(row.new_value)
            kept.update(
                {
                    value.get("revision"),
                    value.get("new_ai_revision"),
                    value.get("old_ai_revision"),
                    value.get("base_ai_revision"),
                }
            )
    return {r for r in kept if isinstance(r, str) and artifacts.REVISION_PATTERN.fullmatch(r)}


def cleanup_jobs() -> None:
    root = artifacts.ROOT / "jobs"
    if not root.exists():
        return
    cutoff = datetime.utcnow() - timedelta(days=7)
    with SessionLocal() as db:
        for folder in root.iterdir():
            if (
                folder.is_symlink()
                or not folder.is_dir()
                or not artifacts.JOB_PATTERN.fullmatch(folder.name)
            ):
                continue
            job = db.query(RGBSegmentationJob).filter_by(id=folder.name).first()
            age = datetime.utcfromtimestamp(folder.stat().st_mtime)
            if job is None:
                if age < datetime.utcnow() - timedelta(hours=1):
                    shutil.rmtree(folder)
                continue
            owner_exists = (
                db.query(User.id).filter_by(id=job.user_id).first() is not None
            )
            assessment = (
                db.query(VASIAssessment)
                .filter_by(id=job.assessment_id, user_id=job.user_id)
                .first()
                if job.assessment_id
                else None
            )
            if (
                job.state not in ("running", "queued")
                and assessment is not None
                and owner_exists
            ):
                try:
                    details = json.loads(assessment.details or "{}")
                    retained = {
                        json.loads(job.result_json or "{}").get("mask_revision"),
                        (details.get("raw_annotation") or {}).get("mask_revision"),
                    }
                    for review in details.get("annotation_reviews", []):
                        retained.update(
                            [review.get("revision"), review.get("previous_revision")]
                        )
                    retained.update(_labeling_retained_revisions(db, folder.name))
                    for revision in folder.iterdir():
                        if (
                            revision.is_dir()
                            and not revision.is_symlink()
                            and artifacts.REVISION_PATTERN.fullmatch(revision.name)
                            and revision.name not in retained
                            and datetime.utcfromtimestamp(revision.stat().st_mtime)
                            < datetime.utcnow() - timedelta(hours=1)
                        ):
                            shutil.rmtree(revision)
                except (ValueError, TypeError, AttributeError):
                    logger.warning(
                        "Deferred invalid RGB revision cleanup for task %s", job.id
                    )
            expired = job.updated_at < cutoff and (
                assessment is None or assessment.status == "abandoned"
            )
            if not owner_exists or expired:
                from web.backend.services.rgb_segmentation.label_review import purge_rgb_label_copies

                if job.assessment_id:
                    purge_rgb_label_copies(db, job.assessment_id, job.user_id, job.id)
                shutil.rmtree(folder)
                if (
                    assessment is None
                    or assessment.status == "abandoned"
                    or not owner_exists
                ):
                    image = (
                        artifacts.PROJECT_ROOT
                        / "data"
                        / "uploads"
                        / "vasi"
                        / ("rgb_" + job.id + ".png")
                    )
                    image.unlink(missing_ok=True)
                if not owner_exists and assessment is not None:
                    db.delete(assessment)
                db.delete(job)
        db.commit()
    try:
        from web.backend.services.rgb_segmentation.dataset_pipeline import prune_datasets

        with SessionLocal() as db:
            prune_datasets(db)  # expired copies and withdrawn subjects
    except (OSError, ValueError, RGBSegmentationError, SQLAlchemyError):
        logger.warning("Deferred training dataset pruning", exc_info=True)

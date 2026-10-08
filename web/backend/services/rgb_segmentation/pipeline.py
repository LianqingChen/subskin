"""Process one leased task; database completion is a compare-and-swap transaction."""

import json
from datetime import datetime
from typing import Any, Dict
from sqlalchemy.orm import Session
from web.backend.database.database import SessionLocal
from web.backend.database.models import User
from web.backend.models.rgb_segmentation import RGBSegmentationJob
from web.backend.models.vasi import VASIAssessment
from web.backend.exceptions import RGBSegmentationError
from web.backend.services.rgb_segmentation import artifacts
from web.backend.services.rgb_segmentation.images import (
    canonical_image,
    png_bytes,
    encode_mask,
)
from web.backend.services.rgb_segmentation.inference import infer_rgb
from web.backend.services.rgb_segmentation.policy import (
    annotation_metadata,
    measure_rgb,
    result_contract,
)
from web.backend.services.annotation_contract import encode_layer
from web.backend.services.vasi_quality import vasi_quality_checker
from web.backend.utils.assessment_body_sites import BODY_SITE_LABELS
from web.backend.services.rgb_segmentation.label_sync import sync_rgb_label


def stage(job_id: str, lease: str, value: str) -> None:
    with SessionLocal() as db:
        owner_exists = (
            db.query(User.id)
            .filter(User.id == RGBSegmentationJob.user_id, User.is_active.is_(True))
            .exists()
        )
        changed = (
            db.query(RGBSegmentationJob)
            .filter_by(id=job_id, lease=lease, state="running")
            .filter(owner_exists, RGBSegmentationJob.deadline_at > datetime.utcnow())
            .update(
                {"stage": value, "updated_at": datetime.utcnow()},
                synchronize_session=False,
            )
        )
        db.commit()
        if changed != 1:
            raise RGBSegmentationError("CANCELLED", "分析已取消或超时", 409)


def process_job(job_id: str, lease: str) -> None:
    stage(job_id, lease, "preprocessing")
    with SessionLocal() as db:
        context = json.loads(
            db.query(RGBSegmentationJob)
            .filter_by(id=job_id, lease=lease)
            .one()
            .context_json
        )
    if context.get("operation") == "refine":
        from web.backend.services.rgb_segmentation.refinement import process_refinement

        process_refinement(job_id, lease, context)
        return
    if context.get("operation") == "outline":
        from web.backend.services.rgb_segmentation.outline import process_outline

        process_outline(job_id, lease, context)
        return
    source = artifacts.read_input(job_id)
    rgb, metadata = canonical_image(source)
    image = png_bytes(rgb)
    stage(job_id, lease, "quality_check")
    quality = vasi_quality_checker.check_all(image)
    if quality.overall == "poor":
        raise RGBSegmentationError(
            "QUALITY_INFORMATION_LOST", "照片清晰度或曝光不足，请重拍"
        )
    stage(job_id, lease, "segmenting")
    masks, model = infer_rgb(rgb)
    stage(job_id, lease, "validating")
    decision = measure_rgb(
        rgb, masks, image, reviewed=False, calibration=context.get("calibration")
    )
    if decision["status"] == "retake_required":
        raise RGBSegmentationError(
            "QUALITY_INFORMATION_LOST", "照片局部过曝或过暗，请重拍"
        )
    manifest = artifacts.write_revision(
        job_id,
        image,
        {kind: encode_mask(mask) for kind, mask in masks.items()},
        {
            "image": metadata,
            "model": model,
            "quality": decision["quality"],
            "calibration": context.get("calibration"),
        },
    )
    revision = manifest["revision"]
    result = result_contract(
        job_id, metadata, revision, masks, decision, model, reviewed=False
    )
    annotation = annotation_metadata(job_id, revision, masks, metadata, model)
    # Public-facing original view is normalized to the same grid as the editor.
    filename = "rgb_" + job_id + ".png"
    artifacts.atomic_write(
        artifacts.PROJECT_ROOT / "data" / "uploads" / "vasi" / filename, image
    )
    with SessionLocal() as db:
        complete_job(
            db, job_id, lease, result, annotation, decision, masks, metadata, filename
        )


def complete_job(
    db: Session,
    job_id: str,
    lease: str,
    result: Dict[str, Any],
    annotation: Dict[str, Any],
    decision: Dict[str, Any],
    masks: dict,
    metadata: Dict[str, Any],
    filename: str,
) -> None:
    now = datetime.utcnow()
    # Hold the SQLite writer lock through the assessment insertion and job link.
    from sqlalchemy import text

    if db.bind.dialect.name == "sqlite":
        db.execute(text("BEGIN IMMEDIATE"))
    job = (
        db.query(RGBSegmentationJob)
        .filter_by(id=job_id, lease=lease, state="running")
        .first()
    )
    if job is None or job.deadline_at <= now:
        db.rollback()
        return
    if not db.query(User.id).filter_by(id=job.user_id, is_active=True).first():
        job.state, job.stage, job.error_code = "cancelled", "cancelled", "CANCELLED"
        db.commit()
        return
    context = json.loads(job.context_json)
    skin_layer = encode_layer(masks["skin"], (96, 165, 250))
    lesion_layer = encode_layer(masks["lesion"], (0, 170, 100))
    measurement = {**decision["measurement"], "mask_revision": result["mask_revision"]}
    details = {
        "annotation": annotation,
        "measurement": measurement,
        "rgb_result": result,
        "observation": context["observation"],
        "skin_layer_data_url": skin_layer,
        "lesion_layer_data_url": lesion_layer,
    }
    assessment = VASIAssessment(
        user_id=job.user_id,
        status="draft",
        image_url="/api/files/serve/vasi/" + filename,
        image_key="rgb_" + job_id,
        image_hash=metadata["source_sha256"],
        vasi_score=0.0,
        area_percentage=0.0,
        body_site=BODY_SITE_LABELS[context["body_site"]],
        classification="未确定",
        stage="未知",
        details=json.dumps(details, ensure_ascii=False),
        raw_api_response=json.dumps({"source": "rgb-tools-v1", "job_id": job_id}),
        assessment_source="rgb-tools-v1",
        confidence=None,
        auto_finalized=False,
        ai_skin_layer=skin_layer,
        ai_lesion_layer=lesion_layer,
        assessment_date=datetime.fromisoformat(context["observation"]["capture_date"]),
    )
    db.add(assessment)
    db.flush()
    sync_rgb_label(db, assessment)
    job.state, job.stage = "completed", "completed"
    job.result_json, job.assessment_id = (
        json.dumps(result, ensure_ascii=False),
        assessment.id,
    )
    job.revision, job.updated_at = 1, now
    db.commit()

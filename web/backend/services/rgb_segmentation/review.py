"""Revision-checked user reference masks, without automatic training export."""

import base64
import hashlib
import io
import json
from datetime import datetime, timezone
from typing import Any, Dict, Tuple
import numpy as np
from PIL import Image
from sqlalchemy import text
from sqlalchemy.orm import Session
from web.backend.exceptions import RGBSegmentationError
from web.backend.models.vasi import VASIAssessment
from web.backend.database.models import User
from web.backend.services.rgb_segmentation import artifacts
from web.backend.services.rgb_segmentation.images import encode_mask, decode_binary
from web.backend.services.rgb_segmentation.jobs import (
    owned_job,
    ensure_storage_capacity,
)
from web.backend.services.rgb_segmentation.policy import (
    annotation_metadata,
    measure_rgb,
    result_contract,
)
from web.backend.services.annotation_contract import encode_layer
from web.backend.services.assessment_measurement import read_details


def decode_editor_mask(value: str, shape: Tuple[int, int]) -> np.ndarray:
    try:
        if (
            not value.startswith("data:image/png;base64,")
            or len(value) > 8 * 1024 * 1024
        ):
            raise ValueError()
        raw = base64.b64decode(value.split(",", 1)[1], validate=True)
        photo = Image.open(io.BytesIO(raw))
        if photo.format != "PNG" or photo.size != (shape[1], shape[0]):
            raise ValueError()
        if photo.mode == "RGBA":
            return (
                np.asarray(photo.getchannel("A")) > 32
            )  # editor protocol's explicit alpha threshold
        if photo.mode == "L":
            return decode_binary(raw, shape)
        if photo.mode == "RGB":
            pixels = np.asarray(photo)
            foreground = (
                (pixels == 255).all(axis=2)
                | (pixels == (96, 165, 250)).all(axis=2)
                | (pixels == (0, 170, 100)).all(axis=2)
            )
            background = (pixels == 0).all(axis=2)
            if (foreground | background).all():
                return foreground
        raise ValueError()
    except (ValueError, OSError, Image.DecompressionBombError):
        raise RGBSegmentationError(
            "ARTIFACT_INVALID", "标注与当前照片不一致，请重新加载后调整"
        )


def review_job(
    db: Session,
    job_id: str,
    user_id: int,
    base_revision: str,
    skin_data: str,
    lesion_data: str,
    acknowledged: bool,
) -> Dict[str, Any]:
    if not acknowledged:
        raise RGBSegmentationError(
            "USER_REVIEW_REQUIRED", "请先核对皮肤、浅色范围和不确定部分"
        )
    job = owned_job(db, job_id, user_id)
    current = json.loads(job.result_json or "{}")
    if job.state != "completed" or current.get("mask_revision") != base_revision:
        raise RGBSegmentationError(
            "REVISION_CONFLICT", "标注版本已变化，请重新加载后调整", 409
        )
    initial_assessment = (
        db.query(VASIAssessment)
        .filter_by(id=job.assessment_id, user_id=user_id)
        .first()
    )
    if (
        initial_assessment is None
        or len(read_details(initial_assessment.details).get("annotation_reviews", []))
        >= 100
    ):
        raise RGBSegmentationError(
            "REVISION_LIMIT", "修订次数已达上限或记录不可用，请新建记录"
        )
    ensure_storage_capacity(db, user_id, revisions=1)
    manifest = artifacts.read_manifest(job_id, base_revision)
    metadata, model = manifest["metadata"]["image"], manifest["metadata"]["model"]
    image = artifacts.read_artifact(job_id, base_revision, "image")
    rgb = np.asarray(Image.open(io.BytesIO(image)).convert("RGB"))
    shape = rgb.shape[:2]
    skin = decode_editor_mask(skin_data, shape)
    lesion = decode_editor_mask(lesion_data, shape)
    original_excluded = decode_binary(
        artifacts.read_artifact(job_id, base_revision, "excluded"), shape
    )
    masks = {
        "skin": skin,
        "lesion": lesion,
        "uncertain": np.zeros(shape, bool),
        "excluded": original_excluded & ~skin,
    }
    decision = measure_rgb(
        rgb,
        masks,
        image,
        reviewed=True,
        calibration=manifest["metadata"].get("calibration"),
    )
    if decision["status"] != "measurable":
        raise RGBSegmentationError(
            decision["blocking_reasons"][0], decision["measurement"]["reasons"][0]
        )
    clipped_pixels = int((masks["lesion"] & ~masks["skin"]).sum())
    masks["lesion"] &= masks["skin"] & ~masks["excluded"]
    lesion = masks["lesion"]
    review = {
        "previous_revision": base_revision,
        "input_mask_sha256": hashlib.sha256(
            (skin_data + lesion_data).encode()
        ).hexdigest(),
        "clipped_edge_pixels": clipped_pixels,
        "actor_id": user_id,
        "at": datetime.now(timezone.utc).isoformat(),
    }
    new_manifest = artifacts.write_revision(
        job_id,
        image,
        {kind: encode_mask(mask) for kind, mask in masks.items()},
        {
            "image": metadata,
            "model": model,
            "quality": decision["quality"],
            "calibration": manifest["metadata"].get("calibration"),
            "review": review,
        },
    )
    revision = new_manifest["revision"]
    result = result_contract(
        job_id, metadata, revision, masks, decision, model, reviewed=True
    )
    annotation = annotation_metadata(
        job_id, revision, masks, metadata, model, reviewed=True
    )
    measurement = {**decision["measurement"], "mask_revision": revision}
    db.rollback()
    if db.bind.dialect.name == "sqlite":
        db.execute(text("BEGIN IMMEDIATE"))
    job = owned_job(db, job_id, user_id)
    if (
        job.state != "completed"
        or json.loads(job.result_json or "{}").get("mask_revision") != base_revision
    ):
        db.rollback()
        raise RGBSegmentationError(
            "REVISION_CONFLICT", "标注版本已变化，请重新加载后调整", 409
        )
    if not db.query(User.id).filter_by(id=user_id, is_active=True).first():
        db.rollback()
        raise RGBSegmentationError("NOT_FOUND", "记录不存在", 404)
    assessment = (
        db.query(VASIAssessment)
        .filter_by(id=job.assessment_id, user_id=user_id)
        .first()
    )
    if assessment is None or assessment.status == "abandoned":
        db.rollback()
        raise RGBSegmentationError("NOT_FOUND", "记录不存在", 404)
    details = read_details(assessment.details)
    reviews = details.setdefault("annotation_reviews", [])
    if len(reviews) >= 100:
        db.rollback()
        raise RGBSegmentationError("REVISION_LIMIT", "修订次数已达上限，请新建记录")
    details.setdefault("raw_annotation", details.get("annotation"))
    review["revision"] = revision
    review["previous_event_hash"] = reviews[-1]["event_hash"] if reviews else None
    review["event_hash"] = hashlib.sha256(
        json.dumps(review, sort_keys=True).encode()
    ).hexdigest()
    reviews.append(review)
    details.update(annotation=annotation, measurement=measurement, rgb_result=result)
    assessment.details = json.dumps(details, ensure_ascii=False)
    assessment.user_skin_layer = encode_layer(skin, (96, 165, 250))
    assessment.user_lesion_layer = encode_layer(lesion & skin, (0, 170, 100))
    assessment.user_mask_image = assessment.user_lesion_layer
    assessment.is_user_corrected = True
    assessment.final_area_percentage = measurement["area_percentage"]
    assessment.final_vasi_score = 0.0
    assessment.visual_features_json = None
    assessment.updated_at = datetime.utcnow()
    job.result_json, job.revision, job.updated_at = (
        json.dumps(result, ensure_ascii=False),
        job.revision + 1,
        datetime.utcnow(),
    )
    from web.backend.services.rgb_segmentation.label_sync import sync_rgb_label

    sync_rgb_label(db, assessment)
    db.commit()
    return {
        "status": "ok",
        "assessment_id": assessment.id,
        "measurement": {**measurement, "annotation": annotation},
        "skin_layer_data_url": assessment.user_skin_layer,
        "lesion_layer_data_url": assessment.user_lesion_layer,
        "final_area_percentage": measurement["area_percentage"],
        "final_vasi_score": 0.0,
        "diff_summary": {"modified": True},
        "result": result,
    }

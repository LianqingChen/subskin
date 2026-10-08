"""Bridge RGB references into the existing private admin labeling workspace."""

import json
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from web.backend.models.image_label import (
    ImageLabel,
    ImageLabelAnnotation,
    ImageLabelLog,
)
from web.backend.models.vasi import VASIAssessment
from web.backend.services.assessment_measurement import read_details
from web.backend.services.annotation_contract import encode_layer
from web.backend.services.rgb_segmentation import artifacts
from web.backend.services.rgb_segmentation.images import decode_binary


def is_rgb_label(label: ImageLabel) -> bool:
    return (
        bool(read_details(getattr(label, "ai_details", None)).get("rgb_sync"))
        or getattr(getattr(label, "assessment", None), "assessment_source", None)
        == "rgb-tools-v1"
    )


def sync_rgb_label(db: Session, assessment: VASIAssessment) -> Optional[ImageLabel]:
    """Idempotent projection; never commit or overwrite initial AI/admin versions."""
    if (
        assessment.assessment_source != "rgb-tools-v1"
        or assessment.status == "abandoned"
    ):
        return None
    details = read_details(assessment.details)
    annotation = details.get("annotation") or {}
    initial = details.get("raw_annotation") or annotation
    job_id, ai_revision = initial.get("job_id"), initial.get("mask_revision")
    if not job_id or not ai_revision:
        return None
    label = (
        db.query(ImageLabel)
        .filter_by(assessment_id=assessment.id, original_user_id=assessment.user_id)
        .first()
    )
    if label and label.is_user_deleted:
        return None
    if label is None or not read_details(label.ai_details).get("rgb_sync"):
        meta = artifacts.read_manifest(job_id, ai_revision)
        image = meta["metadata"]["image"]
        shape = (image["height"], image["width"])
        skin = decode_binary(
            artifacts.read_artifact(job_id, ai_revision, "skin"), shape
        )
        lesion = decode_binary(
            artifacts.read_artifact(job_id, ai_revision, "lesion"), shape
        )
        candidate = decode_binary(
            artifacts.read_artifact(job_id, ai_revision, "uncertain"), shape
        )
        proposal = (lesion | candidate) & skin
        provenance = {
            "job_id": job_id,
            "ai_revision": ai_revision,
            "source_sha256": image["source_sha256"],
            "canonical_sha256": image["sha256"],
            "model": meta["metadata"]["model"],
            "mask_convention": "normal_skin_and_lesion_exclusive",
            "training_state": "awaiting_authorized_dataset",
        }
        # Legacy image_hash is globally unique: do not merge distinct owners/observations.
        if label is None:
            label = ImageLabel(
                assessment_id=assessment.id,
                original_user_id=assessment.user_id,
                image_url=assessment.image_url,
                image_key=assessment.image_key,
                image_hash=None,
            )
            db.add(label)
            db.flush()
        label.ai_body_site = assessment.body_site
        label.ai_details = json.dumps(
            {"rgb_sync": provenance, "annotation": initial}, ensure_ascii=False
        )
        label.ai_is_vitiligo = None
        label.ai_area_percentage = None
        label.ai_vasi_score = None
        label.ai_vitiligo_type = None
        label.ai_vitiligo_stage = None
        label.last_model_version = provenance["model"].get("model_id") or provenance[
            "model"
        ].get("source")
        label.training_eligible = False
        label.is_phi_removed = True
        ai_row = (
            db.query(ImageLabelAnnotation)
            .filter_by(image_label_id=label.id, source="ai", region_index=0)
            .first()
        )
        if ai_row is None:
            ai_row = ImageLabelAnnotation(
                image_label_id=label.id, source="ai", region_index=0
            )
            db.add(ai_row)
        ai_row.body_site = assessment.body_site
        ai_row.skin_mask_data = encode_layer(skin & ~proposal, (147, 197, 253))
        ai_row.mask_data = encode_layer(proposal, (249, 168, 212))
        ai_row.is_vitiligo = None
        ai_row.area_percentage = None
        ai_row.notes = "RGB图像候选；原始模型掩码和不确定层保留在AI版本中，非确诊"
        db.add(
            ImageLabelLog(
                image_label_id=label.id,
                operator_id=assessment.user_id,
                action="rgb-ai-reference",
                new_value=json.dumps(provenance, ensure_ascii=False),
            )
        )
    if not assessment.user_skin_layer or not assessment.user_lesion_layer:
        return label
    revision = annotation.get("mask_revision")
    previous = (
        db.query(ImageLabelLog)
        .filter_by(image_label_id=label.id, action="rgb-user-reference")
        .order_by(ImageLabelLog.id.desc())
        .first()
    )
    if previous and read_details(previous.new_value).get("revision") == revision:
        return label
    meta = artifacts.read_manifest(job_id, revision)
    shape = (meta["metadata"]["image"]["height"], meta["metadata"]["image"]["width"])
    skin = decode_binary(artifacts.read_artifact(job_id, revision, "skin"), shape)
    lesion = decode_binary(artifacts.read_artifact(job_id, revision, "lesion"), shape)
    row = (
        db.query(ImageLabelAnnotation)
        .filter_by(image_label_id=label.id, source="user", region_index=0)
        .first()
    )
    if row is None:
        row = ImageLabelAnnotation(
            image_label_id=label.id, source="user", region_index=0
        )
        db.add(row)
    row.skin_mask_data = encode_layer(skin & ~lesion, (147, 197, 253))
    row.mask_data = encode_layer(lesion, (249, 168, 212))
    row.area_percentage = assessment.final_area_percentage
    row.body_site = assessment.body_site
    row.notes = "用户确认版本：" + revision
    row.updated_at = datetime.utcnow()
    label.user_area_percentage = assessment.final_area_percentage
    label.user_body_site = assessment.body_site
    label.training_eligible = False
    label.label_status = "pending"
    event = {
        "revision": revision,
        "previous_revision": (
            read_details(previous.new_value).get("revision") if previous else None
        ),
        "job_id": job_id,
        "actor": "user",
    }
    db.add(
        ImageLabelLog(
            image_label_id=label.id,
            operator_id=assessment.user_id,
            action="rgb-user-reference",
            new_value=json.dumps(event),
        )
    )
    return label

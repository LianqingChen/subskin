"""High-resolution vision outline as a bounded durable job.

The vision model only proposes geometry; pixel masks come from the existing
refine_annotation_layers pipeline (SAM / edge-aware) and never carry numbers.
Parent revisions are untouched, mirroring the refinement job contract.
"""
import io
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict

import numpy as np
from PIL import Image
from sqlalchemy.orm import Session

from web.backend.database.database import SessionLocal
from web.backend.exceptions import RGBSegmentationError
from web.backend.models.rgb_segmentation import RGBSegmentationJob
from web.backend.services import vision_outline
from web.backend.services.annotation_contract import AnnotationContractError, render_annotation
from web.backend.services.assessment_measurement import decode_mask
from web.backend.services.rgb_segmentation import artifacts
from web.backend.services.rgb_segmentation.images import encode_mask
from web.backend.services.rgb_segmentation.jobs import create_job, owned_job
from web.backend.services.rgb_segmentation.policy import measure_rgb, result_contract
from web.backend.utils.assessment_body_sites import BODY_SITE_LABELS
from web.backend.services.vasi_pixel_refine import refine_annotation_layers

logger = logging.getLogger(__name__)

OUTLINE_JOB_TIMEOUT_S = 260


def enqueue_outline(db: Session, parent_id: str, user_id: int, key: str,
                    revision: str) -> RGBSegmentationJob:
    parent = owned_job(db, parent_id, user_id)
    if (parent.state != "completed"
            or json.loads(parent.result_json or "{}").get("mask_revision") != revision):
        raise RGBSegmentationError("REVISION_CONFLICT", "标注已变化，请重新加载后调整", 409)
    try:
        original = artifacts.read_input(parent_id)
    except OSError as exc:
        raise RGBSegmentationError("NOT_FOUND", "原始照片已过期，无法自动粗定位，请手动调整", 410) from exc
    original_ctx = json.loads(parent.context_json)
    payload = {"operation": "outline", "parent_job_id": parent_id, "base_revision": revision}
    job = create_job(db, user_id, key, original, original_ctx.get("body_site") or "face",
                     payload, context_override={**original_ctx, **payload})
    job.deadline_at = datetime.utcnow() + timedelta(seconds=OUTLINE_JOB_TIMEOUT_S)
    db.commit()
    db.refresh(job)
    return job


def _mask_of(layers: Dict[str, Any], kind: str, shape) -> np.ndarray:
    url = layers.get(f"{kind}_layer_data_url")
    if url is None:
        url = (layers.get("annotation") or {}).get(f"{kind}_layer_data_url")
    mask = decode_mask(url, shape) if url else None
    return mask if mask is not None else np.zeros(shape, bool)


def process_outline(job_id: str, lease: str, context: Dict[str, Any]) -> None:
    from web.backend.services.rgb_segmentation.pipeline import stage

    parent_id, revision = context["parent_job_id"], context["base_revision"]
    with SessionLocal() as db:
        child = db.query(RGBSegmentationJob).filter_by(id=job_id, lease=lease).one()
        parent = owned_job(db, parent_id, child.user_id)
        owner = child.user_id
        if json.loads(parent.result_json or "{}").get("mask_revision") != revision:
            raise RGBSegmentationError("REVISION_CONFLICT", "标注已变化，请重新加载后调整", 409)
    manifest = artifacts.read_manifest(parent_id, revision)
    image = artifacts.read_artifact(parent_id, revision, "image")
    try:
        original = artifacts.read_input(parent_id)
    except OSError as exc:
        raise RGBSegmentationError("NOT_FOUND", "原始照片已过期，无法自动粗定位，请手动调整", 410) from exc
    site = context.get("body_site") or ""
    label = BODY_SITE_LABELS.get(site, site)

    stage(job_id, lease, "segmenting")
    try:
        geometry, outline_meta = vision_outline.propose_geometry_sync(original, label)
    except AnnotationContractError as exc:
        raise RGBSegmentationError("REGIONS_UNRESOLVED", str(exc), 422) from exc
    stage(job_id, lease, "validating")

    rgb = np.asarray(Image.open(io.BytesIO(image)).convert("RGB"))
    shape = rgb.shape[:2]
    settings = vision_outline.outline_settings()
    refined = refine_annotation_layers(
        image, geometry,
        time_budget_s=settings["refine_budget_s"],
        max_lesion_regions=settings["refine_regions"],
    )
    layers = refined if refined else render_annotation(geometry, shape[1], shape[0])
    skin = _mask_of(layers, "skin", shape)
    lesion = _mask_of(layers, "lesion", shape) & skin
    uncertain = _mask_of(layers, "uncertain", shape) & skin
    excluded = _mask_of(layers, "excluded", shape) & ~skin
    if not skin.any():
        raise RGBSegmentationError("SKIN_UNVERIFIED", "未得到可靠皮肤范围，请手动调整", 422)
    masks = {"skin": skin, "lesion": lesion, "uncertain": uncertain, "excluded": excluded}

    model = {"model_id": None, "refiner": "vision-outline", "source": "vision_outline_hires"}
    new = artifacts.write_revision(
        job_id, image, {key: encode_mask(mask) for key, mask in masks.items()},
        {"image": manifest["metadata"]["image"], "model": model,
         "parent_job_id": parent_id, "base_revision": revision, "outline": outline_meta},
    )
    decision = measure_rgb(rgb, masks, image, reviewed=False)
    result = result_contract(job_id, manifest["metadata"]["image"], new["revision"],
                             masks, decision, model, reviewed=False)
    with SessionLocal() as db:
        parent = owned_job(db, parent_id, owner)
        if json.loads(parent.result_json or "{}").get("mask_revision") != revision:
            raise RGBSegmentationError("REVISION_CONFLICT", "标注已变化，请重新加载后调整", 409)
        changed = (
            db.query(RGBSegmentationJob)
            .filter_by(id=job_id, lease=lease, state="running")
            .filter(RGBSegmentationJob.deadline_at > datetime.utcnow())
            .update({"state": "completed", "stage": "completed",
                     "result_json": json.dumps(result), "revision": 1,
                     "updated_at": datetime.utcnow()}, synchronize_session=False)
        )
        db.commit()
        if changed != 1:
            raise RGBSegmentationError("CANCELLED", "任务已取消", 409)

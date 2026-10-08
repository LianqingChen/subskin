"""SAM interaction as a bounded durable job, not a blocking API inference call."""

import base64
import io
import json
import math
from datetime import datetime
from typing import Any, Dict, List, Optional
import cv2
import numpy as np
from PIL import Image
from sqlalchemy.orm import Session
from web.backend.database.database import SessionLocal
from web.backend.exceptions import RGBSegmentationError
from web.backend.models.rgb_segmentation import RGBSegmentationJob
from web.backend.services import vasi_promptable
from web.backend.services.rgb_segmentation import artifacts
from web.backend.services.rgb_segmentation.images import decode_binary, encode_mask
from web.backend.services.rgb_segmentation.jobs import owned_job, create_job
from web.backend.services.rgb_segmentation.review import decode_editor_mask
from web.backend.services.rgb_segmentation.policy import measure_rgb, result_contract
from web.backend.services.vasi_pixel_evidence import (
    local_roi,
    colour_stats,
    colour_plausible,
    boundary_support,
)
from web.backend.services.assessment_measurement import decode_mask


def enqueue_refinement(
    db: Session,
    parent_id: str,
    user_id: int,
    key: str,
    revision: str,
    skin_data: str,
    points: List[Dict[str, Any]],
    box: Optional[List[float]],
) -> RGBSegmentationJob:
    parent = owned_job(db, parent_id, user_id)
    if (
        parent.state != "completed"
        or json.loads(parent.result_json or "{}").get("mask_revision") != revision
    ):
        raise RGBSegmentationError(
            "REVISION_CONFLICT", "照片标注已变化，请重新加载", 409
        )
    if not 1 <= len(points) <= 32 or not any(p.get("label", 1) == 1 for p in points):
        raise RGBSegmentationError("INVALID_INPUT", "请至少点选一处浅色区域")
    for p in points:
        if p.get("label", 1) not in (0, 1) or not all(
            isinstance(p.get(k), (float, int))
            and math.isfinite(p[k])
            and 0 <= p[k] <= 1
            for k in ["x", "y"]
        ):
            raise RGBSegmentationError("INVALID_INPUT", "点选位置无效")
    if box is not None and (
        len(box) != 4
        or not all(math.isfinite(v) and 0 <= v <= 1 for v in box)
        or box[0] >= box[2]
        or box[1] >= box[3]
    ):
        raise RGBSegmentationError("INVALID_INPUT", "局部范围无效")
    image = artifacts.read_artifact(parent_id, revision, "image")
    meta = artifacts.read_manifest(parent_id, revision)["metadata"]["image"]
    skin = decode_editor_mask(skin_data, (meta["height"], meta["width"]))
    original = json.loads(parent.context_json)
    payload = {
        "operation": "refine",
        "parent_job_id": parent_id,
        "base_revision": revision,
        "skin_binary": base64.b64encode(encode_mask(skin)).decode(),
        "points": points,
        "box": box,
    }
    return create_job(
        db,
        user_id,
        key,
        image,
        original["body_site"],
        payload,
        context_override={**original, **payload},
    )


def select_candidate(
    rgb: np.ndarray, skin: np.ndarray, roi: np.ndarray, points: list, candidates: list
) -> np.ndarray:
    h, w = skin.shape
    accepted = []
    for candidate in candidates:
        mask = decode_mask(candidate.get("mask_b64_png"))
        if mask is None or mask.shape != skin.shape or not mask.any():
            continue
        if int((mask & ~roi).sum()) > max(4, int(mask.sum() * 0.02)):
            continue
        mask &= roi
        if any(
            bool(
                mask[
                    min(h - 1, max(0, round(p[1] * h))),
                    min(w - 1, max(0, round(p[0] * w))),
                ]
            )
            != bool(p[2])
            for p in points
        ):
            continue
        stats = colour_stats(rgb, mask, skin & ~mask)
        boundary = boundary_support(rgb, mask, roi)
        if (
            not colour_plausible(stats)
            or not boundary.get("available")
            or boundary.get("support", 0) < 0.55
        ):
            continue
        # Image support first; SAM score is only a tie-breaker, never a clinical confidence.
        score = float(candidate.get("score") or 0)
        if not math.isfinite(score):
            continue
        accepted.append((boundary["support"], score, mask))
    if not accepted:
        raise RGBSegmentationError("REGIONS_UNRESOLVED", "边界仍不可靠，请用画笔调整")
    accepted.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return accepted[0][2]


def process_refinement(job_id: str, lease: str, context: Dict[str, Any]) -> None:
    from web.backend.services.rgb_segmentation.pipeline import stage

    parent_id, revision = context["parent_job_id"], context["base_revision"]
    with SessionLocal() as db:
        child = db.query(RGBSegmentationJob).filter_by(id=job_id, lease=lease).one()
        parent = owned_job(db, parent_id, child.user_id)
        owner = child.user_id
        if json.loads(parent.result_json or "{}").get("mask_revision") != revision:
            raise RGBSegmentationError(
                "REVISION_CONFLICT", "标注已变化，请重新点选", 409
            )
    manifest = artifacts.read_manifest(parent_id, revision)
    metadata = manifest["metadata"]["image"]
    image = artifacts.read_artifact(parent_id, revision, "image")
    rgb = np.asarray(Image.open(io.BytesIO(image)).convert("RGB"))
    h, w = rgb.shape[:2]
    skin = decode_binary(base64.b64decode(context["skin_binary"]), (h, w))
    points = [
        (
            min(w - 1, max(0, round(p["x"] * w - 0.5))) / w,
            min(h - 1, max(0, round(p["y"] * h - 0.5))) / h,
            p.get("label", 1),
        )
        for p in context["points"]
    ]
    x, y = next(
        (round(px * w), round(py * h)) for px, py, label in points if label == 1
    )
    if not skin[y, x]:
        raise RGBSegmentationError("SKIN_UNVERIFIED", "请先补充该位置的皮肤范围")
    proposal = decode_binary(
        artifacts.read_artifact(parent_id, revision, "uncertain"), (h, w)
    )
    proposal |= decode_binary(
        artifacts.read_artifact(parent_id, revision, "lesion"), (h, w)
    )
    _, labels = cv2.connectedComponents(proposal.astype(np.uint8), connectivity=8)
    if labels[y, x]:
        component = labels == labels[y, x]
    else:
        component = np.zeros((h, w), bool)
        radius = max(24, int(min(h, w) * 0.12))
        component[
            max(0, y - radius) : min(h, y + radius + 1),
            max(0, x - radius) : min(w, x + radius + 1),
        ] = True
    roi, box = local_roi(component, skin)
    if context.get("box"):
        box = context["box"]
        roi = np.zeros((h, w), bool)
        roi[
            int(box[1] * h) : int(math.ceil(box[3] * h)),
            int(box[0] * w) : int(math.ceil(box[2] * w)),
        ] = True
        roi &= skin
    stage(job_id, lease, "segmenting")
    cache_key = "rgb:user%d:%s:%s" % (owner, parent_id, metadata["sha256"])
    if vasi_promptable.prepare_image(cache_key, image) is None:
        raise RGBSegmentationError(
            "MODEL_UNAVAILABLE", "交互分割暂不可用，可使用画笔调整", 503
        )
    response = vasi_promptable.predict_by_points(
        cache_key, points, multimask=True, box=box, return_candidates=True
    )
    stage(job_id, lease, "validating")
    target = select_candidate(
        rgb, skin, roi, points, (response or {}).get("candidates", [])
    )
    empty = np.zeros((h, w), bool)
    masks = {
        "skin": skin,
        "lesion": target,
        "uncertain": empty.copy(),
        "excluded": empty.copy(),
    }
    model = {
        "model_id": None,
        "refiner": "sam-vit-b",
        "source": "interactive_sam_reference",
    }
    new = artifacts.write_revision(
        job_id,
        image,
        {key: encode_mask(mask) for key, mask in masks.items()},
        {
            "image": metadata,
            "model": model,
            "parent_job_id": parent_id,
            "base_revision": revision,
        },
    )
    decision = measure_rgb(rgb, masks, image, reviewed=False)
    result = result_contract(
        job_id, metadata, new["revision"], masks, decision, model, reviewed=False
    )
    with SessionLocal() as db:
        parent = owned_job(db, parent_id, owner)
        if json.loads(parent.result_json or "{}").get("mask_revision") != revision:
            raise RGBSegmentationError(
                "REVISION_CONFLICT", "标注已变化，请重新点选", 409
            )
        changed = (
            db.query(RGBSegmentationJob)
            .filter_by(id=job_id, lease=lease, state="running")
            .filter(RGBSegmentationJob.deadline_at > datetime.utcnow())
            .update(
                {
                    "state": "completed",
                    "stage": "completed",
                    "result_json": json.dumps(result),
                    "revision": 1,
                    "updated_at": datetime.utcnow(),
                },
                synchronize_session=False,
            )
        )
        db.commit()
        if changed != 1:
            raise RGBSegmentationError("CANCELLED", "任务已取消", 409)

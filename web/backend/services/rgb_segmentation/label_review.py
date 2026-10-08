"""Private immutable admin mask snapshots; separate from user observations."""

import hashlib
import json
import shutil
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import numpy as np
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session
from web.backend.exceptions import RGBSegmentationError
from web.backend.models.image_label import (
    ImageLabel,
    ImageLabelAnnotation,
    ImageLabelLog,
)
from web.backend.services.assessment_measurement import read_details
from web.backend.services.rgb_segmentation import artifacts
from web.backend.services.rgb_segmentation.images import encode_mask
from web.backend.services.rgb_segmentation.review import decode_editor_mask


def save_admin_reference(
    db: Session,
    label: ImageLabel,
    actor: int,
    annotations: Optional[List[Dict[str, Any]]],
    draft: bool,
) -> Optional[float]:
    """Snapshot masks before the legacy editor replaces its mutable current view."""
    if label.is_user_deleted or label.assessment is None:
        raise RGBSegmentationError("NOT_FOUND", "原记录已删除，不能继续标注", 404)
    if not annotations:
        return label.admin_area_percentage
    if (
        len(annotations) > 32
        or sum(
            len(a.get(key) or "")
            for a in annotations
            for key in ("skin_mask_data", "mask_data")
        )
        > 24 * 1024 * 1024
    ):
        raise RGBSegmentationError("ARTIFACT_INVALID", "标注过大，请减少区域后重试")
    lineage = read_details(label.ai_details)["rgb_sync"]
    meta = artifacts.read_manifest(lineage["job_id"], lineage["ai_revision"])
    image = meta["metadata"]["image"]
    shape = (image["height"], image["width"])
    normal = np.zeros(shape, bool)
    lesion = np.zeros(shape, bool)
    for row in annotations:
        if row.get("source") != "admin":
            continue
        if row.get("skin_mask_data"):
            normal |= decode_editor_mask(row["skin_mask_data"], shape)
        if row.get("mask_data"):
            lesion |= decode_editor_mask(row["mask_data"], shape)
    normal &= ~lesion
    total = int((normal | lesion).sum())
    if not total and not draft:
        raise RGBSegmentationError("SKIN_UNVERIFIED", "请先填涂皮肤或白斑范围")
    area = round(float(lesion.sum()) / total * 100, 2) if total else None
    previous = (
        db.query(ImageLabelLog)
        .filter_by(image_label_id=label.id, action="rgb-admin-reference")
        .order_by(ImageLabelLog.id.desc())
        .first()
    )
    current_user = (
        db.query(ImageLabelLog)
        .filter_by(image_label_id=label.id, action="rgb-user-reference")
        .order_by(ImageLabelLog.id.desc())
        .first()
    )
    metadata = {
        "actor_id": actor,
        "at": datetime.now(timezone.utc).isoformat(),
        "draft": draft,
        "ai_revision": lineage["ai_revision"],
        "user_revision": (
            read_details(current_user.new_value).get("revision")
            if current_user
            else None
        ),
        "previous_revision": (
            read_details(previous.new_value).get("revision") if previous else None
        ),
        "area_percentage": area,
        "training_state": "awaiting_authorized_dataset",
        "convention": "normal_skin_and_lesion_exclusive",
    }
    values = {
        "normal_skin.png": encode_mask(normal),
        "lesion.png": encode_mask(lesion),
        "total_skin.png": encode_mask(normal | lesion),
    }
    metadata["mask_sha256"] = {
        key: hashlib.sha256(value).hexdigest() for key, value in values.items()
    }
    serialized = json.dumps(metadata, sort_keys=True, ensure_ascii=False).encode()
    revision = hashlib.sha256(serialized).hexdigest()
    folder = artifacts.ROOT / "admin_labels" / str(label.id) / revision
    for name, value in values.items():
        artifacts.atomic_write(folder / name, value)
    artifacts.atomic_write(folder / "metadata.json", serialized)
    db.add(
        ImageLabelLog(
            image_label_id=label.id,
            operator_id=actor,
            action="rgb-admin-reference",
            new_value=json.dumps(
                {"revision": revision, **metadata}, ensure_ascii=False
            ),
        )
    )
    return area


def purge_rgb_label_copies(
    db: Session, assessment_id: int, user_id: int, job_id: str
) -> None:
    """Remove new private mask copies when their observation is erased/expired."""
    labels = (
        db.query(ImageLabel)
        .filter(
            or_(
                and_(
                    ImageLabel.assessment_id == assessment_id,
                    ImageLabel.original_user_id == user_id,
                ),
                ImageLabel.image_key == "rgb_" + job_id,
            )
        )
        .all()
    )
    for label in labels:
        if read_details(label.ai_details).get("rgb_sync", {}).get("job_id") != job_id:
            continue
        label.is_user_deleted = True
        label.training_eligible = False
        label.ai_details = json.dumps({"rgb_sync": {"deleted": True}})
        db.query(ImageLabelAnnotation).filter_by(image_label_id=label.id).delete(
            synchronize_session=False
        )
        shutil.rmtree(
            artifacts.ROOT / "admin_labels" / str(label.id), ignore_errors=True
        )
        output = artifacts.PROJECT_ROOT / "data" / "uploads" / "vasi" / "annotated"
        for p in output.glob("*" + str(label.id) + "*"):
            # Restrict removal to this label's generated names, never arbitrary paths.
            if p.is_file() and p.name.startswith(
                ("admin_" + str(label.id) + "_", "user_" + str(label.id) + "_")
            ):
                p.unlink()
        label.annotated_image_path = None
        label.annotated_image_url = None
        label.annotated_layers_path = None

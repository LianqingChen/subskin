"""Submit a five-class label version: immutable snapshot + ``LabelSubmission`` row."""

import hashlib
import io
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import numpy as np
from PIL import Image
from sqlalchemy.orm import Session

from web.backend.exceptions import RGBSegmentationError
from web.backend.models.image_label import ImageLabel, ImageLabelLog
from web.backend.models.label_submission import PREFILL_SOURCES, LabelSubmission
from web.backend.services.assessment_measurement import read_details
from web.backend.services.labeling import class_map, sources
from web.backend.services.labeling.attributes import GUIDELINE_VERSION, normalize_attributes
from web.backend.services.rgb_segmentation import artifacts
from web.backend.services.rgb_segmentation.images import decode_binary, encode_mask

MIN_LABELED_PIXELS = 64  # same floor as ml/rgb_segmentation's validator
OPEN_STATES = ("pending", "in_review", "returned", "gold")


def snapshot_dir(label_id: int, revision: str):
    if not artifacts.REVISION_PATTERN.fullmatch(revision or ""):
        raise RGBSegmentationError("NOT_FOUND", "标注版本不存在", 404)
    return artifacts.ROOT / "admin_labels" / str(label_id) / revision


def _png_shape(raw: bytes):
    with Image.open(io.BytesIO(raw)) as image:
        return image.height, image.width


def read_snapshot(label_id: int, revision: str) -> np.ndarray:
    """Class map of a snapshot; legacy two-layer snapshots are converted."""
    folder = snapshot_dir(label_id, revision)
    try:
        hashes = json.loads((folder / "metadata.json").read_text())["mask_sha256"]
        names = ["labels.png"] if "labels.png" in hashes else ["normal_skin.png", "lesion.png"]
        raws = {n: (folder / n).read_bytes() for n in names}
        if any(hashlib.sha256(v).hexdigest() != hashes[k] for k, v in raws.items()):
            raise ValueError()
        shape = _png_shape(raws[names[0]])
        if "labels.png" in raws:
            return class_map.from_png(raws["labels.png"], shape)
        return class_map.from_exclusive(
            decode_binary(raws["normal_skin.png"], shape), decode_binary(raws["lesion.png"], shape)
        )
    except (OSError, KeyError, ValueError):
        raise RGBSegmentationError("ARTIFACT_INVALID", "标注版本文件不可用")


def _latest_log(db: Session, label: ImageLabel, action: str) -> Optional[Dict[str, Any]]:
    row = (
        db.query(ImageLabelLog)
        .filter_by(image_label_id=label.id, action=action)
        .order_by(ImageLabelLog.id.desc())
        .first()
    )
    return read_details(row.new_value) if row else None


def submit(
    db: Session,
    label: ImageLabel,
    actor: int,
    labels_data_url: str,
    attributes: Dict[str, Any],
    prefill_source: str = "none",
    duration_ms: Optional[int] = None,
) -> LabelSubmission:
    if label.is_user_deleted or sources.kind(label) is None:
        raise RGBSegmentationError("NOT_FOUND", "原记录已删除或不可标注", 404)
    if label.label_status not in OPEN_STATES:
        raise RGBSegmentationError("INVALID_STATE", "该任务已标为跳过/不可用，请先恢复", 409)
    if prefill_source not in PREFILL_SOURCES:
        raise RGBSegmentationError("INVALID_REQUEST", "预填来源无效")
    if label.benchmark and prefill_source != "none":
        raise RGBSegmentationError("BLIND_REQUIRED", "基准集任务须盲标（不预填）", 409)
    _, shape = sources.canonical(label)
    labels = class_map.from_data_url(labels_data_url, shape)
    summary = class_map.stats(labels)
    if int((labels != class_map.UNKNOWN).sum()) < MIN_LABELED_PIXELS:
        raise RGBSegmentationError("SKIN_UNVERIFIED", "标注范围过小，请先标出皮肤与背景")
    if not summary["pixels"]["normal_skin"] and not summary["pixels"]["depigmented_skin"]:
        raise RGBSegmentationError("SKIN_UNVERIFIED", "没有标出任何皮肤；若图片不可用请标记为不可用")
    attrs = normalize_attributes(attributes)

    ai = sources.ai_draft(label)
    user = sources.user_version(db, label)
    summary["vs_ai"] = class_map.agreement(labels, ai) if ai is not None else None
    summary["vs_user"] = class_map.agreement(labels, user["labels"]) if user else None
    summary["user_revision"] = user["revision"] if user else None
    previous = _latest_log(db, label, "rgb-admin-reference")
    sync = sources.sync_of(label)
    metadata = {
        "actor_id": actor,
        "at": datetime.now(timezone.utc).isoformat(),
        "draft": False,
        "convention": "five_class_v1",
        "source_kind": sources.kind(label),
        "ai_revision": sync.get("ai_revision"),
        "source_id": sync.get("source_id"),
        "user_revision": user["revision"] if user else None,
        "previous_revision": previous.get("revision") if previous else None,
        "area_percentage": summary["lesion_ratio"],
        "guideline_version": GUIDELINE_VERSION,
        "prefill_source": prefill_source,
        "blind": prefill_source == "none",
        "training_state": "awaiting_authorized_dataset",
    }
    normal = labels == class_map.NORMAL
    lesion = labels == class_map.LESION
    values = {
        "labels.png": class_map.to_png(labels),
        "normal_skin.png": encode_mask(normal),
        "lesion.png": encode_mask(lesion),
        "total_skin.png": encode_mask(normal | lesion),
    }
    metadata["mask_sha256"] = {k: hashlib.sha256(v).hexdigest() for k, v in values.items()}
    serialized = json.dumps(metadata, sort_keys=True, ensure_ascii=False).encode()
    revision = hashlib.sha256(serialized).hexdigest()
    folder = snapshot_dir(label.id, revision)
    for name, value in values.items():
        artifacts.atomic_write(folder / name, value)
    artifacts.atomic_write(folder / "metadata.json", serialized)
    db.add(
        ImageLabelLog(
            image_label_id=label.id,
            operator_id=actor,
            action="rgb-admin-reference",
            new_value=json.dumps({"revision": revision, **metadata}, ensure_ascii=False),
        )
    )
    db.query(LabelSubmission).filter_by(image_label_id=label.id, status="submitted").update(
        {"status": "superseded"}, synchronize_session="fetch"
    )
    row = LabelSubmission(
        image_label_id=label.id,
        revision=revision,
        author_id=actor,
        status="submitted",
        prefill_source=prefill_source,
        blind=prefill_source == "none",
        duration_ms=duration_ms if duration_ms and 0 < duration_ms < 86_400_000 else None,
        guideline_version=GUIDELINE_VERSION,
        attributes=json.dumps(attrs, ensure_ascii=False),
        stats=json.dumps(summary, ensure_ascii=False),
    )
    db.add(row)
    label.label_status = "in_review"
    label.labeled_by = actor
    label.labeled_at = datetime.utcnow()
    label.admin_area_percentage = summary["lesion_ratio"]
    if attrs["body_site"]:
        label.admin_body_site = attrs["body_site"]
    label.admin_notes = attrs["notes"] or None
    label.labeling_duration_ms = row.duration_ms
    db.flush()
    return row

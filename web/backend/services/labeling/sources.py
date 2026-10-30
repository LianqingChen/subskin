"""Canonical photo + reference versions for one labeling task.

Two kinds of task source, both in the diary's canonical frame (EXIF applied,
sRGB, long side ≤ 1024):

- ``job``: a diary RGB job (``rgb_sync.job_id``/``ai_revision``), user-owned.
- ``upload``: an admin-supplied photo (batch upload or legacy import) stored
  under ``label_sources/{source_id}/`` with its own AI draft.
"""

import hashlib
import json
import shutil
import uuid
from typing import Any, Dict, Optional, Tuple

import numpy as np
from sqlalchemy.orm import Session

from web.backend.exceptions import RGBSegmentationError
from web.backend.models.image_label import ImageLabel, ImageLabelLog
from web.backend.services.assessment_measurement import read_details
from web.backend.services.labeling import class_map
from web.backend.services.rgb_segmentation import artifacts
from web.backend.services.rgb_segmentation.images import canonical_image, decode_binary, png_bytes


def sync_of(label: ImageLabel) -> Dict[str, Any]:
    return read_details(label.ai_details).get("rgb_sync") or {}


def kind(label: ImageLabel) -> Optional[str]:
    sync = sync_of(label)
    if sync.get("deleted"):
        return None
    if sync.get("job_id") and sync.get("ai_revision"):
        return "job"
    if sync.get("source_id"):
        return "upload"
    return None


def _source_dir(source_id: str):
    if not artifacts.JOB_PATTERN.fullmatch(source_id or ""):
        raise RGBSegmentationError("NOT_FOUND", "图片不存在", 404)
    return artifacts.ROOT / "label_sources" / source_id


def _source_meta(source_id: str) -> Dict[str, Any]:
    try:
        return json.loads((_source_dir(source_id) / "metadata.json").read_text())
    except (OSError, ValueError):
        raise RGBSegmentationError("NOT_FOUND", "图片已不可用", 404)


def _verified(path, expected: str) -> bytes:
    try:
        value = path.read_bytes()
    except OSError:
        raise RGBSegmentationError("NOT_FOUND", "图片已不可用", 404)
    if hashlib.sha256(value).hexdigest() != expected:
        raise RGBSegmentationError("ARTIFACT_INVALID", "图片校验失败")
    return value


def canonical(label: ImageLabel) -> Tuple[bytes, Tuple[int, int]]:
    """Canonical PNG bytes and (height, width)."""
    sync = sync_of(label)
    source = kind(label)
    if source == "job":
        meta = artifacts.read_manifest(sync["job_id"], sync["ai_revision"])["metadata"]["image"]
        image = artifacts.read_artifact(sync["job_id"], sync["ai_revision"], "image")
        return image, (meta["height"], meta["width"])
    if source == "upload":
        meta = _source_meta(sync["source_id"])
        image = _verified(_source_dir(sync["source_id"]) / "image.png", meta["image_sha256"])
        return image, (meta["height"], meta["width"])
    raise RGBSegmentationError("NOT_FOUND", "该记录没有可标注的规范化照片", 404)


def ai_draft(label: ImageLabel) -> Optional[np.ndarray]:
    sync = sync_of(label)
    source = kind(label)
    try:
        if source == "job":
            _, shape = canonical(label)
            read = lambda k: decode_binary(  # noqa: E731
                artifacts.read_artifact(sync["job_id"], sync["ai_revision"], k), shape
            )
            return class_map.from_masks(read("skin"), read("lesion"), read("uncertain"))
        if source == "upload":
            meta = _source_meta(sync["source_id"])
            raw = _verified(_source_dir(sync["source_id"]) / "ai.png", meta["ai_sha256"])
            return class_map.from_png(raw, (meta["height"], meta["width"]))
    except RGBSegmentationError:
        return None
    return None


def current_user_revision(db: Session, label: ImageLabel) -> Optional[str]:
    if kind(label) != "job":
        return None
    row = (
        db.query(ImageLabelLog)
        .filter_by(image_label_id=label.id, action="rgb-user-reference")
        .order_by(ImageLabelLog.id.desc())
        .first()
    )
    return read_details(row.new_value).get("revision") if row else None


def user_version(db: Session, label: ImageLabel) -> Optional[Dict[str, Any]]:
    """Latest diary-confirmed masks (job tasks only)."""
    sync = sync_of(label)
    revision = current_user_revision(db, label)
    if not revision:
        return None
    try:
        _, shape = canonical(label)
        skin = decode_binary(artifacts.read_artifact(sync["job_id"], revision, "skin"), shape)
        lesion = decode_binary(artifacts.read_artifact(sync["job_id"], revision, "lesion"), shape)
    except RGBSegmentationError:
        return None
    return {"revision": revision, "labels": class_map.from_masks(skin, lesion)}


def draft_from_rgb(rgb: np.ndarray) -> Tuple[np.ndarray, Dict[str, Any]]:
    from web.backend.services.rgb_segmentation.inference import infer_rgb

    masks, meta = infer_rgb(rgb)
    return class_map.from_masks(masks["skin"], masks["lesion"], masks["uncertain"]), meta


def draft_face_gb(rgb: np.ndarray) -> Optional[Tuple[np.ndarray, Dict[str, Any]]]:
    """Face-plaque HistGB draft (L-180-5). None when model/mediapipe unavailable → caller falls back."""
    import logging

    from ml.pixel_labeling import core, face_gb

    if not face_gb.MODEL_PATH.is_file():
        return None
    p = core.params_of({"params": {"skin": {"method": "mediapipe"}, "baseline_mode": "hybrid"}})
    extras: Dict[str, Any] = {}
    try:
        skin = core.skin_mask(rgb, p, extras)
    except Exception as exc:  # noqa: BLE001 — mediapipe/hands photos fall back to infer_rgb
        logging.getLogger(__name__).info("face_gb skin parse skipped: %s", type(exc).__name__)
        return None
    if int(skin.sum()) < 1000:
        return None
    try:
        lesion, gb_meta = face_gb.predict_lesion(rgb, skin, p, lips=extras.get("lips"))
    except Exception as exc:  # noqa: BLE001
        logging.getLogger(__name__).warning("face_gb predict failed: %s", type(exc).__name__, exc_info=True)
        return None
    labels = np.full(skin.shape, class_map.BACKGROUND, np.uint8)
    labels[skin] = class_map.NORMAL
    labels[lesion] = class_map.LESION
    lips = extras.get("lips")
    if lips is not None:
        labels[lips & skin] = class_map.NORMAL
        labels[lesion & ~lips] = class_map.LESION
    meta = {
        "model_id": gb_meta.get("model_id", "face-plaque-gb-v1"),
        "source": "face_plaque_gb",
        "skin_model": "mediapipe",
        "lesion_method": "hist_gb_lab_scores",
        "threshold": gb_meta.get("threshold_used"),
        "note": "面颈大斑 HistGB 初稿（180/s13 校准），仍需人工核对",
        "automatic_measurement": False,
    }
    return labels, meta


def draft_for_labeling_workspace(rgb: np.ndarray) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Admin「重新生成初稿」：优先 face-gb，失败再走通用 infer_rgb。"""
    drafted = draft_face_gb(rgb)
    if drafted is not None:
        return drafted
    return draft_from_rgb(rgb)


def create_upload_source(data: bytes, provenance: Dict[str, Any]) -> Dict[str, Any]:
    """Canonicalize an admin-supplied photo, draft it, and return ``rgb_sync``."""
    rgb, meta = canonical_image(data)
    image = png_bytes(rgb)
    labels, model = draft_from_rgb(rgb)
    ai = class_map.to_png(labels)
    source_id = uuid.uuid4().hex
    folder = _source_dir(source_id)
    record = {
        "image_sha256": hashlib.sha256(image).hexdigest(),
        "ai_sha256": hashlib.sha256(ai).hexdigest(),
        "width": meta["width"],
        "height": meta["height"],
        "source_sha256": meta["source_sha256"],
        "model": {k: model.get(k) for k in ("model_id", "source", "skin_model", "lesion_method")},
        "provenance": provenance,
    }
    artifacts.atomic_write(folder / "image.png", image)
    artifacts.atomic_write(folder / "ai.png", ai)
    artifacts.atomic_write(folder / "metadata.json", json.dumps(record, ensure_ascii=False).encode())
    return {
        "source_id": source_id,
        "source_sha256": meta["source_sha256"],
        "canonical_sha256": record["image_sha256"],
        "model": record["model"],
        "origin": provenance.get("origin", "admin_upload"),
        "training_state": "awaiting_authorized_dataset",
    }


def delete_upload_source(label: ImageLabel) -> None:
    source_id = sync_of(label).get("source_id")
    if source_id:
        shutil.rmtree(_source_dir(source_id), ignore_errors=True)

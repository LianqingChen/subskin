"""Five-class label maps — the exact format ``ml/rgb_segmentation`` trains on.

0 background, 1 normal_skin, 2 depigmented_skin, 3 occlusion, 4 unreadable,
255 unlabeled (ignored by the loss and by every metric here).
"""

import base64
import io
from typing import Dict, Optional, Tuple

import numpy as np
from PIL import Image

from web.backend.exceptions import RGBSegmentationError

BACKGROUND, NORMAL, LESION, OCCLUSION, UNREADABLE, UNKNOWN = 0, 1, 2, 3, 4, 255
VALUES = (BACKGROUND, NORMAL, LESION, OCCLUSION, UNREADABLE, UNKNOWN)
NAMES = {
    BACKGROUND: "background",
    NORMAL: "normal_skin",
    LESION: "depigmented_skin",
    OCCLUSION: "occlusion",
    UNREADABLE: "unreadable",
    UNKNOWN: "unknown",
}
_PREFIX = "data:image/png;base64,"
MAX_DATA_URL = 8 * 1024 * 1024


def from_masks(
    skin: np.ndarray,
    lesion: np.ndarray,
    uncertain: Optional[np.ndarray] = None,
) -> np.ndarray:
    """Prefill from diary-style layers (``skin`` = total skin incl. lesion).

    Non-skin becomes background; AI uncertainty stays unlabeled so the
    annotator must decide it instead of inheriting a guess.
    """
    labels = np.full(skin.shape, BACKGROUND, np.uint8)
    labels[skin] = NORMAL
    labels[lesion & skin] = LESION
    if uncertain is not None:
        labels[uncertain & skin] = UNKNOWN
    return labels


def from_exclusive(normal: np.ndarray, lesion: np.ndarray) -> np.ndarray:
    """Legacy admin snapshots (normal/lesion only, rest implicitly background)."""
    labels = np.zeros(normal.shape, np.uint8)
    labels[normal] = NORMAL
    labels[lesion] = LESION
    return labels


def to_png(labels: np.ndarray) -> bytes:
    out = io.BytesIO()
    Image.fromarray(labels.astype(np.uint8), mode="L").save(out, format="PNG", optimize=True)
    return out.getvalue()


def to_data_url(labels: np.ndarray) -> str:
    return _PREFIX + base64.b64encode(to_png(labels)).decode("ascii")


def _check(labels: np.ndarray) -> np.ndarray:
    if not np.isin(labels, VALUES).all():
        raise RGBSegmentationError("ARTIFACT_INVALID", "标注含无效类别，请刷新后重试")
    return labels


def from_png(raw: bytes, shape: Tuple[int, int]) -> np.ndarray:
    """Accept an ``L`` class PNG, or an editor canvas PNG whose red channel is the class."""
    try:
        photo = Image.open(io.BytesIO(raw))
        if photo.format != "PNG" or photo.size != (shape[1], shape[0]):
            raise ValueError()
        if photo.mode == "L":
            labels = np.asarray(photo)
        elif photo.mode in ("RGB", "RGBA"):
            pixels = np.asarray(photo)
            if photo.mode == "RGBA" and not (pixels[..., 3] == 255).all():
                raise ValueError()  # premultiplied alpha would corrupt class values
            labels = pixels[..., 0]
        else:
            raise ValueError()
    except (OSError, ValueError, Image.DecompressionBombError):
        raise RGBSegmentationError("ARTIFACT_INVALID", "标注与当前照片尺寸不一致，请刷新后重试")
    return _check(np.array(labels, dtype=np.uint8))


def from_data_url(value: str, shape: Tuple[int, int]) -> np.ndarray:
    if not isinstance(value, str) or not value.startswith(_PREFIX) or len(value) > MAX_DATA_URL:
        raise RGBSegmentationError("ARTIFACT_INVALID", "标注数据格式无效")
    try:
        raw = base64.b64decode(value[len(_PREFIX):], validate=True)
    except ValueError:
        raise RGBSegmentationError("ARTIFACT_INVALID", "标注数据格式无效")
    return from_png(raw, shape)


def stats(labels: np.ndarray) -> Dict[str, object]:
    counts = {NAMES[v]: int((labels == v).sum()) for v in VALUES}
    skin = counts["normal_skin"] + counts["depigmented_skin"]
    total = int(labels.size)
    return {
        "pixels": counts,
        "labeled_fraction": round(1 - counts["unknown"] / total, 4) if total else 0.0,
        # Same formula as the diary's 「照片内浅色占比」: lesion / visible skin.
        "lesion_ratio": round(counts["depigmented_skin"] / skin * 100, 2) if skin else None,
        "has_lesion": counts["depigmented_skin"] > 0,
    }


def dice(a: np.ndarray, b: np.ndarray, value: int) -> Optional[float]:
    """Per-class Dice over pixels both maps labeled; None when neither has the class."""
    valid = (a != UNKNOWN) & (b != UNKNOWN)
    x = (a == value) & valid
    y = (b == value) & valid
    denom = int(x.sum()) + int(y.sum())
    if denom == 0:
        return None
    return round(2 * int((x & y).sum()) / denom, 4)


def agreement(a: np.ndarray, b: np.ndarray) -> Dict[str, Optional[float]]:
    skin_a = np.where(np.isin(a, (NORMAL, LESION)), NORMAL, a)
    skin_b = np.where(np.isin(b, (NORMAL, LESION)), NORMAL, b)
    return {"lesion_dice": dice(a, b, LESION), "skin_dice": dice(skin_a, skin_b, NORMAL)}

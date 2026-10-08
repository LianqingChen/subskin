"""Pixel geometry shared by automatic and user-confirmed pair alignment."""
import io
import math
from typing import Any, Dict, Optional, Tuple

import cv2
import numpy as np
from PIL import Image, ImageOps

from web.backend.services.comparison_refinement import distributed


def decode_photo(data: bytes) -> np.ndarray:
    if not data or len(data) > 10 * 1024 * 1024:
        raise ValueError("照片为空或超过10MB，请重新选择")
    image = Image.open(io.BytesIO(data))
    if image.width * image.height > 32000000:
        raise ValueError("照片像素过大，请压缩后再试")
    image = ImageOps.exif_transpose(image).convert("RGB")
    image.thumbnail((1024, 1024))
    return np.asarray(image)


def manual_transform(a: np.ndarray, b: np.ndarray, settings: Dict[str, Any]) -> np.ndarray:
    values = {}
    limits = {"scale": (.25, 4), "rotation": (-180, 180), "x": (-1, 1), "y": (-1, 1)}
    for key, (low, high) in limits.items():
        raw = settings.get(key, 1 if key == "scale" else 0)
        if isinstance(raw, bool) or not isinstance(raw, (int, float)) or not math.isfinite(raw) or not low <= raw <= high:
            raise ValueError("对齐参数无效，请重新调整")
        values[key] = float(raw)
    ha, wa = a.shape[:2]
    hb, wb = b.shape[:2]
    scale = min(wa / wb, ha / hb) * values["scale"]
    angle = math.radians(values["rotation"])
    linear = scale * np.array([[math.cos(angle), -math.sin(angle)], [math.sin(angle), math.cos(angle)]])
    center = np.array([wa * (.5 + values["x"]), ha * (.5 + values["y"])])
    return np.column_stack((linear, center - linear @ np.array([wb / 2, hb / 2])))


def matched_points(a: np.ndarray, b: np.ndarray, mask_a: Optional[np.ndarray] = None, mask_b: Optional[np.ndarray] = None) -> Optional[Tuple[np.ndarray, np.ndarray]]:
    orb = cv2.ORB_create(nfeatures=4000)
    ka, da = orb.detectAndCompute(cv2.cvtColor(a, cv2.COLOR_RGB2GRAY), mask_a)
    kb, db = orb.detectAndCompute(cv2.cvtColor(b, cv2.COLOR_RGB2GRAY), mask_b)
    if da is None or db is None or len(da) < 2 or len(db) < 2:
        return None
    pairs = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(db, da, k=2)
    good = [p[0] for p in pairs if len(p) == 2 and p[0].distance < .7 * p[1].distance]
    if len(good) < 12:
        return None
    return np.float32([kb[m.queryIdx].pt for m in good]), np.float32([ka[m.trainIdx].pt for m in good])


def residual_error(a: np.ndarray, b: np.ndarray, transform: np.ndarray, mask_a: Optional[np.ndarray] = None, mask_b: Optional[np.ndarray] = None) -> Optional[float]:
    points = matched_points(a, b, mask_a, mask_b)
    if points is None:
        return None
    src, dst = points
    distances = np.linalg.norm(src @ transform[:, :2].T + transform[:, 2] - dst, axis=1)
    inliers = distances <= 3
    if int(inliers.sum()) < 10 or float(inliers.mean()) < .6:
        return None
    error = float(np.sqrt(np.mean(distances[inliers] ** 2)))
    return error if error <= 2.5 else None


def automatic_transform(a: np.ndarray, b: np.ndarray, mask_a: Optional[np.ndarray] = None,
                        mask_b: Optional[np.ndarray] = None) -> Optional[np.ndarray]:
    """Estimate a useful visual pose; numeric measurement validates separately."""
    points = matched_points(a, b, mask_a, mask_b)
    if points is None:
        return None
    src, dst = points
    tolerance = min(8., max(3., math.hypot(*a.shape[:2]) * .006))
    transform, inliers = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC, ransacReprojThreshold=tolerance)
    if transform is None or inliers is None or not np.isfinite(transform).all():
        return None
    keep = inliers.ravel().astype(bool)
    if int(keep.sum()) < 8 or float(keep.mean()) < .45 or not distributed(dst[keep], a.shape):
        return None
    scale = float(np.linalg.norm(transform[:, 0]))
    base_scale = min(a.shape[1] / b.shape[1], a.shape[0] / b.shape[0])
    if not .5 <= scale / base_scale <= 2 or np.linalg.det(transform[:, :2]) <= 0:
        return None
    return transform


def warp_pair(a: np.ndarray, b: np.ndarray, transform: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    h, w = a.shape[:2]
    valid = cv2.warpAffine(np.ones(b.shape[:2], np.uint8), transform, (w, h), flags=cv2.INTER_NEAREST).astype(bool)
    warped = cv2.warpAffine(b, transform, (w, h), borderValue=(255, 255, 255))
    reference = a.copy()
    reference[~valid] = 255
    return reference, warped, valid


def stable_skin_mask(prepared: Tuple[np.ndarray, np.ndarray, np.ndarray]) -> np.ndarray:
    _, skin, lesion = prepared
    expanded = cv2.dilate(lesion.astype(np.uint8), np.ones((11, 11), np.uint8)).astype(bool)
    return (skin & ~expanded).astype(np.uint8) * 255


def png_bytes(rgb: np.ndarray) -> bytes:
    output = io.BytesIO()
    Image.fromarray(rgb).save(output, format="PNG")
    return output.getvalue()

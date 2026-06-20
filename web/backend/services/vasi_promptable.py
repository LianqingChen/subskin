"""
SAM Promptable (point/box) segmentation service.

The user clicks on a vitiligo patch and SAM returns a precise mask.
Replaces the failed AutoMaskGenerator approach (which on CPU takes 15+s
and frequently misses small vitiligo patches).

Concurrency model:
  SamPredictor holds image state on the instance, so concurrent prepare/
  predict calls would race. We use a single global predictor + threading
  lock, and re-run set_image() on every predict call (~1s on CPU for
  cached numpy array). The cache stores the decoded numpy array, NOT the
  SAM features — features cannot be safely transplanted between calls.
"""

from __future__ import annotations

import io
import logging
import threading
import time
from collections import OrderedDict
from typing import Optional

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


SAM_MODEL_PATH = "/root/subskin/models/sam_vit_b_01ec64.pth"
EMBEDDING_CACHE_SIZE = 8

_predictor = None
_predictor_lock = threading.Lock()
_last_encoded_key: Optional[str] = None


def _get_predictor():
    global _predictor
    if _predictor is not None:
        return _predictor

    with _predictor_lock:
        if _predictor is not None:
            return _predictor
        try:
            import torch
            from segment_anything import sam_model_registry, SamPredictor

            device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info("Loading SAM ViT-B for promptable mode on %s...", device)
            sam = sam_model_registry["vit_b"](checkpoint=SAM_MODEL_PATH)
            sam.to(device=device).eval()
            _predictor = SamPredictor(sam)
            logger.info("SAM predictor ready")
            return _predictor
        except Exception as e:
            logger.error("Failed to load SAM predictor: %s", e, exc_info=True)
            return None


class _EmbeddingCache:
    def __init__(self, max_size: int = EMBEDDING_CACHE_SIZE):
        self.max_size = max_size
        self._store: "OrderedDict[str, dict]" = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[dict]:
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
                return self._store[key]
            return None

    def put(self, key: str, value: dict) -> None:
        with self._lock:
            self._store[key] = value
            self._store.move_to_end(key)
            while len(self._store) > self.max_size:
                self._store.popitem(last=False)

    def invalidate(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)


_embedding_cache = _EmbeddingCache()


def prepare_image(cache_key: str, image_bytes: bytes) -> Optional[dict]:
    """Decode image, cache numpy array. Image encoding (SAM set_image) happens
    lazily on first predict call to keep predict & encoding serialized under
    the global lock — preventing race conditions on shared SamPredictor state.
    """
    if _get_predictor() is None:
        return None

    cached = _embedding_cache.get(cache_key)
    if cached is not None:
        return {"width": cached["width"], "height": cached["height"], "cached": True}

    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img_np = np.array(img)
        h, w = img_np.shape[:2]

        _embedding_cache.put(cache_key, {
            "image_np": img_np,
            "width": w,
            "height": h,
        })
        return {"width": w, "height": h, "cached": False}
    except Exception as e:
        logger.error("prepare_image failed: %s", e, exc_info=True)
        return None


def predict_by_points(
    cache_key: str,
    points: list[tuple[float, float, int]],
    multimask: bool = True,
) -> Optional[dict]:
    """Run point-prompt prediction on the cached image.

    Args:
        cache_key: Same key used in prepare_image().
        points: list of (x_norm, y_norm, label). label=1 foreground, 0 background.
                Coordinates are in [0,1] normalized to the original image.
        multimask: Return 3 candidate masks if True, else best.

    Returns a dict with mask_polygon (normalized), mask_b64_png (PNG data URL),
    score, area_pixels, area_percent_in_image, width, height, predict_time_s.
    """
    predictor = _get_predictor()
    if predictor is None:
        return None

    cached = _embedding_cache.get(cache_key)
    if cached is None:
        logger.warning("No cached image for key=%s", cache_key)
        return None

    if not points:
        return None

    w, h = cached["width"], cached["height"]
    img_np = cached["image_np"]
    point_coords = np.array(
        [[float(p[0]) * w, float(p[1]) * h] for p in points],
        dtype=np.float32,
    )
    point_labels = np.array([int(p[2]) for p in points], dtype=np.int32)

    try:
        global _last_encoded_key
        with _predictor_lock:
            encode_elapsed = 0.0
            if _last_encoded_key != cache_key or not predictor.is_image_set:
                t0 = time.time()
                predictor.set_image(img_np)
                encode_elapsed = time.time() - t0
                _last_encoded_key = cache_key

            t0 = time.time()
            masks, scores, _ = predictor.predict(
                point_coords=point_coords,
                point_labels=point_labels,
                multimask_output=multimask,
            )
            predict_elapsed = time.time() - t0
            logger.info(
                "SAM encode=%.2fs predict=%.3fs for %d points (cache_hit=%s)",
                encode_elapsed, predict_elapsed, len(points), encode_elapsed == 0,
            )
            elapsed = encode_elapsed + predict_elapsed

        if hasattr(masks, "cpu"):
            masks = masks.cpu().numpy()
        if hasattr(scores, "cpu"):
            scores = scores.cpu().numpy()
        best_idx = int(np.argmax(scores))
        mask = np.asarray(masks[best_idx]).astype(bool)
        score = float(scores[best_idx])

        polygon = _mask_to_normalized_polygon(mask)
        mask_b64 = _mask_to_b64_png(mask)
        area_pixels = int(mask.sum())
        area_percent = round(100 * area_pixels / (w * h), 2)

        return {
            "mask_polygon": polygon,
            "mask_b64_png": mask_b64,
            "score": round(score, 3),
            "area_pixels": area_pixels,
            "area_percent_in_image": area_percent,
            "width": w,
            "height": h,
            "predict_time_s": round(elapsed, 3),
        }
    except Exception as e:
        logger.error("predict_by_points failed: %s", e, exc_info=True)
        return None


def _mask_to_normalized_polygon(mask: np.ndarray, max_points: int = 60) -> list[list[float]]:
    try:
        import cv2
        mask_u8 = (mask.astype(np.uint8)) * 255
        contours, _ = cv2.findContours(mask_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return []
        largest = max(contours, key=cv2.contourArea)
        epsilon = 0.005 * cv2.arcLength(largest, True)
        approx = cv2.approxPolyDP(largest, epsilon, True)
        h, w = mask.shape
        pts = [[round(float(p[0][0]) / w, 4), round(float(p[0][1]) / h, 4)] for p in approx]
        if len(pts) > max_points:
            step = len(pts) / max_points
            pts = [pts[int(i * step)] for i in range(max_points)]
        return pts
    except Exception as e:
        logger.warning("polygon extraction failed: %s", e)
        return []


def _mask_to_b64_png(mask: np.ndarray) -> str:
    import base64
    h, w = mask.shape
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[mask, 0] = 99
    arr[mask, 1] = 102
    arr[mask, 2] = 241
    arr[mask, 3] = 200
    img = Image.fromarray(arr, mode="RGBA")
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def predict_by_circle(
    cache_key: str,
    center: tuple[float, float],
    radius_x: float,
    radius_y: float,
) -> Optional[dict]:
    """Run circle-prompt prediction: user draws rough ellipse, SAM + color analysis refines boundary.

    Algorithm:
      1. Convert ellipse to SAM box prompt
      2. SAM generates initial mask
      3. Color-deviation analysis within mask detects vitiligo pixels
      4. Edge snapping refines boundary to image edges
      5. Returns polygon + confidence + area_percent
    """
    predictor = _get_predictor()
    if predictor is None:
        return None

    cached = _embedding_cache.get(cache_key)
    if cached is None:
        logger.warning("No cached image for key=%s", cache_key)
        return None

    w, h = cached["width"], cached["height"]
    img_np = cached["image_np"]

    cx_px, cy_px = center[0] * w, center[1] * h
    rx_px, ry_px = radius_x * w, radius_y * h
    box = np.array([cx_px - rx_px, cy_px - ry_px, cx_px + rx_px, cy_px + ry_px], dtype=np.float32)

    try:
        import cv2

        global _last_encoded_key
        with _predictor_lock:
            if _last_encoded_key != cache_key or not predictor.is_image_set:
                t0 = time.time()
                predictor.set_image(img_np)
                _last_encoded_key = cache_key
                logger.info("SAM encode=%.2fs for circle prompt", time.time() - t0)

            t0 = time.time()
            masks, scores, _ = predictor.predict(
                box=box,
                multimask_output=False,
            )
            predict_elapsed = time.time() - t0
            logger.info("SAM circle predict=%.3fs", predict_elapsed)

        if hasattr(masks, "cpu"):
            masks = masks.cpu().numpy()
        if hasattr(scores, "cpu"):
            scores = scores.cpu().numpy()
        best_idx = int(np.argmax(scores))
        sam_mask = np.asarray(masks[best_idx]).astype(bool)

        bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
        refined_mask = _refine_by_color(bgr, sam_mask)

        polygon = _mask_to_normalized_polygon(refined_mask)
        mask_b64 = _mask_to_b64_png(refined_mask)
        area_pixels = int(refined_mask.sum())
        area_percent = round(100 * area_pixels / (w * h), 2)
        confidence = _compute_color_confidence(bgr, refined_mask)

        return {
            "mask_polygon": polygon,
            "mask_b64_png": mask_b64,
            "score": round(float(scores[best_idx]), 3),
            "confidence": confidence,
            "area_pixels": area_pixels,
            "area_percent_in_image": area_percent,
            "width": w,
            "height": h,
            "predict_time_s": round(predict_elapsed, 3),
        }
    except Exception as e:
        logger.error("predict_by_circle failed: %s", e, exc_info=True)
        return None


def _refine_by_color(img_bgr: np.ndarray, sam_mask: np.ndarray) -> np.ndarray:
    """Within SAM mask, detect pixels that deviate significantly from skin color."""
    import cv2

    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    skin_pixels = hsv[sam_mask]
    if len(skin_pixels) < 100:
        return sam_mask

    skin_center = np.median(skin_pixels, axis=0).astype(np.float32)
    diff = hsv.astype(np.float32) - skin_center[np.newaxis, np.newaxis, :]
    distances = np.sqrt(np.sum(diff ** 2, axis=2))

    vitiligo_mask = np.zeros(sam_mask.shape, dtype=np.uint8)
    vitiligo_mask[sam_mask] = (distances[sam_mask] > 30).astype(np.uint8)

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    vitiligo_mask = cv2.morphologyEx(vitiligo_mask, cv2.MORPH_OPEN, kernel)
    vitiligo_mask = cv2.morphologyEx(vitiligo_mask, cv2.MORPH_CLOSE, kernel)

    return vitiligo_mask.astype(bool)


def _compute_color_confidence(img_bgr: np.ndarray, mask: np.ndarray) -> float:
    """Confidence = normalized color distance between lesion and skin."""
    import cv2

    if not mask.any():
        return 0.0

    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    lesion_pixels = hsv[mask]
    if len(lesion_pixels) < 10:
        return 0.0

    skin_hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    skin_pixels = skin_hsv[~mask & (hsv[:, :, 1] > 15)]
    if len(skin_pixels) < 10:
        return 0.0

    lesion_center = np.mean(lesion_pixels, axis=0)
    skin_center = np.mean(skin_pixels, axis=0)
    dist = float(np.sqrt(np.sum((lesion_center - skin_center) ** 2)))
    return round(min(dist / 100.0, 1.0), 3)


def invalidate_cache(cache_key: str) -> None:
    _embedding_cache.invalidate(cache_key)

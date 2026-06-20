"""
Skin-region detection and vitiligo white-patch identification.

Two-stage algorithm:
  Stage 1: Build a binary skin mask separating body skin from background.
           Combines YCrCb (Cr 133-180, Cb 77-130) and HSV (H 0-25 or 160-179,
           S 20-200, V 50-255) — the same dual-space approach used by the
           quality checker. Morphological cleanup removes salt-and-pepper noise.
  Stage 2: Within the skin mask, classify pixels as vitiligo if their lightness
           is at least 12 L* units above the skin's median L (relative test),
           AND their LAB chroma is low (low saturation; healthy skin has higher
           chroma from melanin). This catches *lighter-than-surrounding-skin*
           areas while rejecting white background, white clothing, paper, etc.

This module replaces the previous absolute-threshold approach (`L > 180`)
which incorrectly flagged white backgrounds and clothing as vitiligo.
"""

from __future__ import annotations

import logging
from typing import Optional, Tuple

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

try:
    import cv2
    _CV2_AVAILABLE = True
except ImportError:
    _CV2_AVAILABLE = False
    logger.warning("opencv-python not available; skin-mask detection disabled")


SKIN_HSV_RED_LOWER_1 = np.array([0, 20, 50], dtype=np.uint8)
SKIN_HSV_RED_UPPER_1 = np.array([25, 200, 255], dtype=np.uint8)
SKIN_HSV_RED_LOWER_2 = np.array([160, 20, 50], dtype=np.uint8)
SKIN_HSV_RED_UPPER_2 = np.array([179, 200, 255], dtype=np.uint8)
SKIN_YCRCB_LOWER = np.array([0, 133, 77], dtype=np.uint8)
SKIN_YCRCB_UPPER = np.array([255, 180, 130], dtype=np.uint8)

# Adaptive skin ranges for different Fitzpatrick types
SKIN_HSV_ADAPTIVE: dict[str, tuple] = {
    # (fitz_lower, fitz_upper): (hsv_lower_sat, hsv_upper_sat, ycrcb_lower_cr, ycrcb_upper_cr)
    "I_III": (18, 220, 130, 182),    # Light skin: wider saturation, narrower Cr
    "IV_VI": (12, 255, 120, 190),    # Dark skin: wider all around — lower sat for melanin-rich skin
}

# Estimated Fitzpatrick type from median LAB luminance
FITZ_L_THRESHOLDS = [
    (180, "I"),    # Very fair
    (155, "II"),   # Fair
    (130, "III"),  # Medium
    (105, "IV"),   # Olive/light brown
    (80, "V"),     # Brown
    (0, "VI"),     # Dark brown/black
]

VITILIGO_L_OFFSET = 12.0
VITILIGO_MAX_CHROMA = 35.0
MIN_SKIN_RATIO_FOR_DETECTION = 0.05
MORPH_KERNEL_SIZE = 7

FITZPATRICK_VITILIGO_THRESHOLDS: dict[str, tuple[float, float]] = {
    "I": (10.0, 30.0),
    "II": (11.0, 32.0),
    "III": (12.0, 35.0),
    "IV": (14.0, 38.0),
    "V": (16.0, 40.0),
    "VI": (18.0, 42.0),
}


def _estimate_fitzpatrick(img_rgb: np.ndarray) -> str:
    """Estimate Fitzpatrick skin type from median L channel in skin region."""
    if not _CV2_AVAILABLE:
        return "III"
    try:
        img_bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
        lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)
        L = lab[:, :, 0].astype(np.float32)

        # First pass: guess skin pixels using default thresholds
        hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
        ycrcb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2YCrCb)
        mask_hsv = cv2.bitwise_or(
            cv2.inRange(hsv, SKIN_HSV_RED_LOWER_1, SKIN_HSV_RED_UPPER_1),
            cv2.inRange(hsv, SKIN_HSV_RED_LOWER_2, SKIN_HSV_RED_UPPER_2),
        )
        mask_ycrcb = cv2.inRange(ycrcb, SKIN_YCRCB_LOWER, SKIN_YCRCB_UPPER)
        rough_skin = cv2.bitwise_or(mask_hsv, mask_ycrcb)

        if rough_skin.sum() < 500:
            return "III"

        median_l = float(np.median(L[rough_skin.astype(bool)]))
        for threshold, fitz in FITZ_L_THRESHOLDS:
            if median_l >= threshold:
                return fitz
        return "VI"
    except Exception:
        return "III"


def _get_adaptive_skin_thresholds(fitz_type: str) -> dict:
    """Return skin detection thresholds adapted to Fitzpatrick type."""
    if fitz_type in ("I", "II", "III"):
        sat_low, sat_high, cr_low, cr_high = SKIN_HSV_ADAPTIVE["I_III"]
    else:
        sat_low, sat_high, cr_low, cr_high = SKIN_HSV_ADAPTIVE["IV_VI"]

    return {
        "hsv_lower_1": np.array([0, sat_low, 50], dtype=np.uint8),
        "hsv_upper_1": np.array([25, sat_high, 255], dtype=np.uint8),
        "hsv_lower_2": np.array([160, sat_low, 50], dtype=np.uint8),
        "hsv_upper_2": np.array([179, sat_high, 255], dtype=np.uint8),
        "ycrcb_lower": np.array([0, cr_low, 75], dtype=np.uint8),
        "ycrcb_upper": np.array([255, cr_high, 132], dtype=np.uint8),
    }


def build_skin_mask(img_rgb: np.ndarray) -> Optional[np.ndarray]:
    """Return a boolean (H, W) mask where True = pixel is skin.

    Uses adaptive thresholds based on estimated Fitzpatrick skin type.
    The mask is the union of HSV and YCrCb skin-color matches, followed by
    morphological open + close to remove noise and fill small holes.
    """
    if not _CV2_AVAILABLE:
        return None

    try:
        img_bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
        hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
        ycrcb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2YCrCb)

        # Estimate Fitzpatrick and get adaptive thresholds
        fitz = _estimate_fitzpatrick(img_rgb)
        thresh = _get_adaptive_skin_thresholds(fitz)
        logger.debug("Skin detection: Fitzpatrick=%s, using adaptive thresholds", fitz)

        mask_hsv_1 = cv2.inRange(hsv, thresh["hsv_lower_1"], thresh["hsv_upper_1"])
        mask_hsv_2 = cv2.inRange(hsv, thresh["hsv_lower_2"], thresh["hsv_upper_2"])
        mask_ycrcb = cv2.inRange(ycrcb, thresh["ycrcb_lower"], thresh["ycrcb_upper"])

        skin_mask = cv2.bitwise_or(cv2.bitwise_or(mask_hsv_1, mask_hsv_2), mask_ycrcb)

        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (MORPH_KERNEL_SIZE, MORPH_KERNEL_SIZE))
        skin_mask = cv2.morphologyEx(skin_mask, cv2.MORPH_OPEN, kernel)
        skin_mask = cv2.morphologyEx(skin_mask, cv2.MORPH_CLOSE, kernel, iterations=2)

        # Optional: exclude known reference objects from skin mask if present
        # (reference cards, coins, rulers should not count as skin)
        # This is a best-effort exclusion based on color + shape heuristics:
        # - Pure white rectangle (reference card) → likely not skin
        # - Circular metallic object (coin) → likely not skin
        try:
            gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
            # Exclude near-pure-white regions (V>240) from skin mask
            _, white_mask = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY)
            white_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (20, 20))
            white_regions = cv2.morphologyEx(white_mask, cv2.MORPH_OPEN, white_kernel, iterations=2)
            skin_mask_bool = skin_mask.astype(bool)
            skin_mask_bool[white_regions.astype(bool)] = False
            return skin_mask_bool
        except Exception:
            pass

        return skin_mask.astype(bool)
    except Exception as e:
        logger.warning("Skin mask build failed: %s", e)
        return None


def expand_skin_mask_to_include_vitiligo(
    img_rgb: np.ndarray, skin_mask: np.ndarray
) -> np.ndarray:
    """Vitiligo lesions themselves are NOT detected by skin-color heuristics
    (they lack melanin chroma). To avoid excluding them from the analysis
    region, we expand the skin mask by morphologically dilating it and then
    keeping any pixel inside the convex hull of the skin region.

    Returns the expanded mask (boolean, same shape).
    """
    if not _CV2_AVAILABLE:
        return skin_mask

    try:
        mask_u8 = (skin_mask.astype(np.uint8)) * 255
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (21, 21))
        dilated = cv2.dilate(mask_u8, kernel, iterations=2)

        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return dilated.astype(bool)

        h, w = skin_mask.shape
        hull_mask = np.zeros((h, w), dtype=np.uint8)
        largest = max(contours, key=cv2.contourArea)
        hull = cv2.convexHull(largest)
        cv2.fillConvexPoly(hull_mask, hull, 255)

        combined = cv2.bitwise_or(dilated, hull_mask)
        return combined.astype(bool)
    except Exception as e:
        logger.warning("Skin mask expansion failed: %s", e)
        return skin_mask


def detect_vitiligo_within_skin(
    img_rgb: np.ndarray,
    analysis_region: np.ndarray,
    l_offset: Optional[float] = None,
    max_chroma: Optional[float] = None,
) -> Tuple[Optional[np.ndarray], dict]:
    """Detect vitiligo pixels within the analysis region using a *relative*
    lightness test against the surrounding skin's median.

    If l_offset/max_chroma are not provided, they are auto-adapted based on
    estimated Fitzpatrick skin type.

    Returns:
        (mask, stats) where mask is a boolean array (True = vitiligo) and
        stats contains the median skin L, threshold used, and pixel counts.
    """
    stats = {
        "skin_median_l": None,
        "l_threshold": None,
        "region_pixels": 0,
        "vitiligo_pixels": 0,
    }
    if not _CV2_AVAILABLE:
        return None, stats

    if l_offset is None or max_chroma is None:
        fitz = _estimate_fitzpatrick(img_rgb)
        adaptive_l, adaptive_chroma = FITZPATRICK_VITILIGO_THRESHOLDS.get(fitz, (12.0, 35.0))
        if l_offset is None:
            l_offset = adaptive_l
        if max_chroma is None:
            max_chroma = adaptive_chroma
        stats["fitzpatrick_type"] = fitz

    try:
        img_bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
        lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)
        L = lab[:, :, 0].astype(np.float32)
        A = lab[:, :, 1].astype(np.float32)
        B = lab[:, :, 2].astype(np.float32)

        chroma = np.sqrt((A - 128) ** 2 + (B - 128) ** 2)

        skin_l_values = L[analysis_region]
        if skin_l_values.size == 0:
            return None, stats

        skin_median_l = float(np.median(skin_l_values))
        skin_p25 = float(np.percentile(skin_l_values, 25))
        skin_p75 = float(np.percentile(skin_l_values, 75))

        l_threshold = max(skin_median_l + l_offset, skin_p75 + 5.0)

        vitiligo = (
            analysis_region
            & (L >= l_threshold)
            & (chroma <= max_chroma)
        )

        kernel_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        vit_u8 = (vitiligo.astype(np.uint8)) * 255
        vit_u8 = cv2.morphologyEx(vit_u8, cv2.MORPH_OPEN, kernel_open)
        vit_u8 = cv2.morphologyEx(vit_u8, cv2.MORPH_CLOSE, kernel_close)
        vitiligo = vit_u8.astype(bool)

        stats["skin_median_l"] = round(skin_median_l, 1)
        stats["skin_p25_l"] = round(skin_p25, 1)
        stats["skin_p75_l"] = round(skin_p75, 1)
        stats["l_threshold"] = round(l_threshold, 1)
        stats["region_pixels"] = int(analysis_region.sum())
        stats["vitiligo_pixels"] = int(vitiligo.sum())

        return vitiligo, stats
    except Exception as e:
        logger.warning("Vitiligo detection failed: %s", e)
        return None, stats


def mask_to_data_url(mask: np.ndarray, color: tuple = (99, 102, 241), alpha: int = 200) -> str:
    """Encode a boolean mask as a colored PNG data URL for frontend overlay."""
    import base64
    import io as _io
    h, w = mask.shape
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[mask, 0] = color[0]
    arr[mask, 1] = color[1]
    arr[mask, 2] = color[2]
    arr[mask, 3] = alpha
    img = Image.fromarray(arr, mode="RGBA")
    buf = _io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def mask_overlap_ratio(mask_a: np.ndarray, mask_b: np.ndarray) -> float:
    """Return |A ∩ B| / |A| — what fraction of mask_a is inside mask_b."""
    a_area = int(mask_a.sum())
    if a_area == 0:
        return 0.0
    intersection = int(np.logical_and(mask_a, mask_b).sum())
    return intersection / a_area


def split_into_connected_components(
    mask: np.ndarray, min_area: int = 50
) -> list:
    """Split a binary mask into separate connected components.

    Returns a list of boolean masks, one per component, filtered by min_area.
    """
    if not _CV2_AVAILABLE:
        return [mask] if mask.any() else []

    mask_u8 = (mask.astype(np.uint8)) * 255
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask_u8, connectivity=8)
    components = []
    for i in range(1, num_labels):
        if stats[i, cv2.CC_STAT_AREA] < min_area:
            continue
        components.append((labels == i))
    return components

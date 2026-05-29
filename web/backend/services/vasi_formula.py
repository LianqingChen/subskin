"""
Real VASI score computation following the modified VASI methodology
(Hamzavi et al. 2004) — hand units × residual depigmentation per body region.

Replaces the legacy `area_percentage × 2.5` fallback with a clinically
grounded formula that respects body-site surface-area weights.
"""

from __future__ import annotations

import base64
import io
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


# Approx. % of total body surface area per anatomical region (modified VASI / rule-of-9s).
# These values are intentionally aligned with web/app/src/constants/bodySites.ts
# (BSA_PERCENT) so the frontend and backend agree on weights.
BODY_SITE_BSA_PERCENT: dict[str, float] = {
    # English (VLM legacy / API canonical)
    "face": 4.5,
    "neck": 1.0,
    "chest": 9.0,
    "abdomen": 9.0,
    "upper_back": 9.0,
    "lower_back": 9.0,
    "back": 18.0,  # legacy alias kept for backward compatibility
    "left_arm": 4.5,
    "right_arm": 4.5,
    "arms": 9.0,  # legacy alias
    "left_hand": 1.0,
    "right_hand": 1.0,
    "hands": 2.0,  # legacy alias
    "left_leg": 9.0,
    "right_leg": 9.0,
    "legs": 18.0,  # legacy alias
    "left_foot": 1.75,
    "right_foot": 1.75,
    "feet": 3.5,  # legacy alias
    # 中文 (VLM returns Chinese body-site labels)
    "面部": 4.5,
    "颈部": 1.0,
    "手部": 2.0,
    "胸部": 9.0,
    "腹部": 9.0,
    "上背部": 9.0,
    "下背部": 9.0,
    "背部": 18.0,
    "上肢": 9.0,
    "下肢": 18.0,
    "足部": 3.5,
    "左臂": 4.5,
    "右臂": 4.5,
    "左手": 1.0,
    "右手": 1.0,
    "左腿": 9.0,
    "右腿": 9.0,
    "其他": 9.0,
}

DEFAULT_BSA_PERCENT = 9.0  # If body site unknown, assume one body region


def get_body_site_bsa(body_site: str) -> float:
    return BODY_SITE_BSA_PERCENT.get(body_site, DEFAULT_BSA_PERCENT)


def compute_vasi_v2(
    body_site: str,
    area_pct_in_region: float,
    depigmentation_level: float = 0.67,
) -> float:
    """Compute a VASI score for a single body-region assessment.

    Formula:
        hand_units = area_pct_in_region * BSA_PERCENT(body_site) / 100
        VASI = hand_units * depigmentation_level * 10   # scaled to ~0-100 range

    Args:
        body_site: One of the BODY_SITE_BSA_PERCENT keys.
        area_pct_in_region: % of the body region that is depigmented (0-100).
                            i.e., white pixels / region pixels × 100.
        depigmentation_level: 0.0-1.0 (0 = no depigmentation, 1.0 = complete).
                              From VLM: overall_depigmentation / 3.0.
                              Defaults to 0.67 (VLM level 2/3) when unavailable.

    Returns:
        VASI score, rounded to 1 decimal, clamped to [0, 100].
    """
    bsa = get_body_site_bsa(body_site)
    hand_units = (max(0.0, min(100.0, area_pct_in_region)) / 100.0) * bsa
    if depigmentation_level is None:
        depigmentation_level = 0.67  # VLM mid-range default (no VLM data)
    if depigmentation_level < 0:
        depigmentation_level = 0.0
    depig = max(0.0, min(1.0, depigmentation_level))
    score = hand_units * depig * 10
    return round(min(100.0, max(0.0, score)), 1)


def parse_mask_data_url(mask_data_url: str) -> Optional[Tuple[bytes, str]]:
    if not mask_data_url or not isinstance(mask_data_url, str):
        return None
    if not mask_data_url.startswith("data:"):
        return None
    try:
        header, encoded = mask_data_url.split(",", 1)
        content_type = header.split(";")[0].split(":")[1] if ":" in header else "image/png"
        return base64.b64decode(encoded), content_type
    except (ValueError, IndexError, Exception):
        return None


def compute_two_layer_area(
    skin_mask_bytes: bytes,
    lesion_mask_bytes: bytes,
) -> Optional[dict]:
    """Two-layer area computation: area% = lesion / (skin ∪ lesion).

    Both masks must be RGBA PNGs of the same size. The skin layer defines
    the evaluation region (denominator); the lesion layer is the numerator.
    Union ensures lesion pixels outside skin still count toward the region.
    """
    try:
        from PIL import Image
        import numpy as np
    except ImportError:
        return None

    try:
        skin_img = Image.open(io.BytesIO(skin_mask_bytes)).convert("RGBA")
        lesion_img = Image.open(io.BytesIO(lesion_mask_bytes)).convert("RGBA")
    except Exception as e:
        logger.warning("Failed to decode two-layer masks: %s", e)
        return None

    if skin_img.size != lesion_img.size:
        try:
            lesion_img = lesion_img.resize(skin_img.size, Image.NEAREST)
        except Exception:
            return None

    skin_alpha = np.array(skin_img.getchannel("A"))
    lesion_alpha = np.array(lesion_img.getchannel("A"))

    skin_mask = skin_alpha > 32
    lesion_mask = lesion_alpha > 32
    region_mask = skin_mask | lesion_mask

    region_px = int(region_mask.sum())
    lesion_px = int(lesion_mask.sum())
    total_px = skin_mask.size

    if region_px == 0:
        return None

    return {
        "area_percent_in_region": round((lesion_px / region_px) * 100, 2),
        "lesion_pixels": lesion_px,
        "region_pixels": region_px,
        "region_percent_of_image": round((region_px / total_px) * 100, 2),
    }


def compute_mask_area_percent(mask_bytes: bytes) -> Optional[float]:
    """Compute the % of opaque pixels in a mask PNG, against TOTAL pixels.
    Use compute_two_layer_area() instead for clinically meaningful %.
    """
    try:
        from PIL import Image
    except ImportError:
        logger.warning("Pillow not available; cannot compute mask area")
        return None

    try:
        img = Image.open(io.BytesIO(mask_bytes))
    except Exception as e:
        logger.warning("Failed to decode mask image: %s", e)
        return None

    if img.mode not in ("RGBA", "LA"):
        img = img.convert("RGBA")

    alpha = img.getchannel("A")
    total = alpha.width * alpha.height
    if total == 0:
        return None

    histogram = alpha.histogram()
    filled = sum(histogram[i] for i in range(33, 256))
    return round((filled / total) * 100, 2)


def compute_mask_area_percent_of_skin(
    mask_bytes: bytes,
    original_image_url: Optional[str],
    fetch_image_bytes,
) -> Optional[dict]:
    """Compute white-patch area as a % of the detected skin region.

    Returns a dict with both denominators for transparency:
        {
            "area_percent_in_skin": 12.3,    # vs skin pixels (primary)
            "area_percent_in_image": 4.5,    # vs total pixels (legacy)
            "skin_region_ratio": 36.6,       # skin / image
        }
    Returns None if mask or original image cannot be decoded, or if the skin
    region cannot be detected — caller should fall back to area_in_image.
    """
    try:
        from PIL import Image
        import numpy as np
    except ImportError:
        return None

    try:
        mask_img = Image.open(io.BytesIO(mask_bytes))
        if mask_img.mode not in ("RGBA", "LA"):
            mask_img = mask_img.convert("RGBA")
    except Exception:
        return None

    if original_image_url is None:
        return None

    try:
        orig_bytes = fetch_image_bytes(original_image_url)
        if not orig_bytes:
            return None
        orig_img = Image.open(io.BytesIO(orig_bytes)).convert("RGB")
    except Exception as e:
        logger.warning("Failed to load original image for skin denominator: %s", e)
        return None

    if mask_img.size != orig_img.size:
        try:
            mask_img = mask_img.resize(orig_img.size, Image.NEAREST)
        except Exception:
            return None

    try:
        from web.backend.services.vasi_skin_mask import (
            build_skin_mask,
            expand_skin_mask_to_include_vitiligo,
        )
    except ImportError:
        return None

    img_np = np.array(orig_img)
    skin_mask = build_skin_mask(img_np)
    if skin_mask is None or not skin_mask.any():
        return None
    analysis_region = expand_skin_mask_to_include_vitiligo(img_np, skin_mask)

    alpha = np.array(mask_img.getchannel("A"))
    mask_filled = alpha > 32

    mask_in_skin = np.logical_and(mask_filled, analysis_region)
    skin_pixels = max(int(analysis_region.sum()), 1)
    total_pixels = mask_filled.size
    mask_pixels_in_skin = int(mask_in_skin.sum())
    mask_pixels_total = int(mask_filled.sum())

    return {
        "area_percent_in_skin": round((mask_pixels_in_skin / skin_pixels) * 100, 2),
        "area_percent_in_image": round((mask_pixels_total / total_pixels) * 100, 2),
        "skin_region_ratio": round((analysis_region.sum() / total_pixels) * 100, 1),
    }

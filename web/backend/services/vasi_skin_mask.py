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

# 工作分辨率：4000×3000 原图上做 1.2% 长边的形态学核会带来秒级延迟，
# 肤色区域只需要区域级精度，处理后再按最近邻还原到原尺寸。
WORK_MAX_DIM = 1280
SKIN_OPEN_RATIO = 0.012      # 开运算核 / 长边：切断皮肤与背景之间的细桥
SKIN_WHITE_V_RATIO = 0.20    # 近纯白参考物（参考卡/纸张）判定窗口

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


def _skin_color_candidates(img_rgb: np.ndarray, fitz_type: str) -> np.ndarray:
    """严格肤色分类（uint8 0/255）。

    旧实现把 HSV 与 YCrCb 的匹配结果**取并集**，任何落在任一宽松色域内的
    像素都算皮肤 —— 实测墙面、窗帘、衣物、显示器支架全被纳入（手部照片
    skin=100%）。这里改为：
      - 亮肤色（I-III）：HSV ∩ YCrCb 严格交集，再并上 Kovac RGB 规则
        （补回被 HSV 饱和度下限漏掉的浅肤色）；
      - 深肤色（IV-VI）：HSV ∩ 放宽 Cr 下限的 YCrCb，避免交集过严丢皮肤。
    """
    img_bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    ycrcb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2YCrCb)
    thresh = _get_adaptive_skin_thresholds(fitz_type)

    mask_hsv = cv2.bitwise_or(
        cv2.inRange(hsv, thresh["hsv_lower_1"], thresh["hsv_upper_1"]),
        cv2.inRange(hsv, thresh["hsv_lower_2"], thresh["hsv_upper_2"]),
    )
    mask_ycrcb = cv2.inRange(ycrcb, thresh["ycrcb_lower"], thresh["ycrcb_upper"])
    strict = cv2.bitwise_and(mask_hsv, mask_ycrcb)

    if fitz_type in ("I", "II", "III"):
        r = img_rgb[:, :, 0].astype(np.int16)
        g = img_rgb[:, :, 1].astype(np.int16)
        b = img_rgb[:, :, 2].astype(np.int16)
        mx = np.maximum(np.maximum(r, g), b)
        mn = np.minimum(np.minimum(r, g), b)
        rgb_rule = (
            (r > 95) & (g > 40) & (b > 20)
            & ((mx - mn) > 15)
            & (np.abs(r - g) > 15)
            & (r > g) & (r > b)
        )
        strict = cv2.bitwise_or(strict, rgb_rule.astype(np.uint8) * 255)
    else:
        loose = cv2.inRange(
            ycrcb, np.array([0, 128, 72], np.uint8), np.array([255, 190, 135], np.uint8)
        )
        strict = cv2.bitwise_or(strict, cv2.bitwise_and(mask_hsv, loose))

    return strict


def build_skin_mask(img_rgb: np.ndarray) -> Optional[np.ndarray]:
    """Return a boolean (H, W) mask where True = pixel is skin.

    Uses adaptive thresholds based on estimated Fitzpatrick skin type, a strict
    HSV∩YCrCb (+RGB rule) colour model, scale-relative morphological opening
    (breaks the thin bridges that used to merge skin with background), and
    exclusion of near-pure-white reference objects.

    The returned mask always has the same H×W as the input (processing happens
    at a capped working resolution for speed, then is restored).
    """
    if not _CV2_AVAILABLE:
        return None

    try:
        h, w = img_rgb.shape[:2]
        scale = min(1.0, WORK_MAX_DIM / max(h, w))
        if scale < 1.0:
            work = cv2.resize(
                img_rgb,
                (max(1, int(w * scale)), max(1, int(h * scale))),
                interpolation=cv2.INTER_AREA,
            )
        else:
            work = img_rgb
        wh, ww = work.shape[:2]

        fitz = _estimate_fitzpatrick(work)
        logger.debug("Skin detection: Fitzpatrick=%s, using strict dual-space model", fitz)

        cand = _skin_color_candidates(work, fitz)
        k = max(3, int(SKIN_OPEN_RATIO * max(wh, ww)) | 1)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
        skin_mask = cv2.morphologyEx(cand, cv2.MORPH_OPEN, kernel)
        skin_mask = cv2.morphologyEx(skin_mask, cv2.MORPH_CLOSE, kernel, iterations=2)

        # 排除近纯白参考物（参考卡/硬币/纸张）——它们不应计入皮肤面积
        try:
            gray = cv2.cvtColor(cv2.cvtColor(work, cv2.COLOR_RGB2BGR), cv2.COLOR_BGR2GRAY)
            _, white_mask = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY)
            wk = max(5, int(SKIN_WHITE_V_RATIO * max(wh, ww)) | 1)
            white_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (wk, wk))
            white_regions = cv2.morphologyEx(white_mask, cv2.MORPH_OPEN, white_kernel, iterations=2)
            skin_bool = skin_mask.astype(bool)
            skin_bool[white_regions.astype(bool)] = False
            skin_mask = skin_bool.astype(np.uint8)
        except Exception:
            pass

        if scale < 1.0:
            skin_mask = cv2.resize(
                skin_mask, (w, h), interpolation=cv2.INTER_NEAREST
            )
        return skin_mask.astype(bool)
    except Exception as e:
        logger.warning("Skin mask build failed: %s", e)
        return None


def expand_skin_mask_to_include_vitiligo(
    img_rgb: np.ndarray, skin_mask: np.ndarray
) -> np.ndarray:
    """Vitiligo lesions themselves are NOT detected by skin-colour heuristics
    (they lack melanin chroma), so the analysis region must also cover them.

    历史实现对「膨胀后的最大轮廓」做**凸包**：当皮肤区域贴到画面边缘时，
    凸包等于整幅图像，分母（皮肤面积）严重失真 —— 实测白斑占比因此被
    系统性低估。现改为 `refine_skin_region()`：色彩候选 ∪ 邻近脱色素候选，
    主体连通域 + 填洞 + 有界膨胀，保持真实轮廓、绝不做凸包。
    """
    if not _CV2_AVAILABLE:
        return skin_mask
    try:
        from web.backend.services.vasi_edge_segmentation import refine_skin_region

        return refine_skin_region(img_rgb, skin_mask, None)
    except Exception as e:
        logger.warning("Skin mask expansion failed: %s", e)
        return skin_mask



def detect_vitiligo_within_skin(
    img_rgb: np.ndarray,
    analysis_region: np.ndarray,
    l_offset: Optional[float] = None,
    max_chroma: Optional[float] = None,
) -> Tuple[Optional[np.ndarray], dict]:
    """Detect vitiligo pixels within the analysis region.

    现在委派给 `vasi_edge_segmentation.segment_lesions_edge_aware`：
      逐像素 LAB 颜色 → 局部光照校正（剥离亮区求局部健康肤色中位）→
      邻域色差梯度 → 白斑似然 → 滞后双阈值 → 分水岭边缘吸附 → 连通域过滤。

    旧的「全图单一阈值」在全球光照不均时会把整片亮侧皮肤判成白斑
    （实测面部照片 12%~23% 误检），因此不再作为主路径。

    `l_offset` / `max_chroma` 仅为签名向后兼容保留，会写进 stats 便于排查。

    Returns:
        (mask, stats) — mask 为与输入同尺寸的 bool 数组。
    """
    stats: dict = {
        "skin_median_l": None,
        "l_threshold": None,
        "region_pixels": 0,
        "vitiligo_pixels": 0,
    }
    if not _CV2_AVAILABLE or analysis_region is None or not analysis_region.any():
        return None, stats

    try:
        from web.backend.services.vasi_edge_segmentation import segment_lesions_edge_aware

        region = analysis_region.astype(bool)
        stats["suggested_l_offset"] = l_offset
        stats["suggested_max_chroma"] = max_chroma

        # 记录全局中位/相对阈值（仅用于日志与历史字段兼容）
        img_bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
        lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)
        L = lab[:, :, 0].astype(np.float32)
        fitz = _estimate_fitzpatrick(img_rgb)
        adaptive_l, adaptive_chroma = FITZPATRICK_VITILIGO_THRESHOLDS.get(fitz, (12.0, 35.0))
        eff_l = l_offset if l_offset is not None else adaptive_l
        skin_l = L[region]
        stats["skin_median_l"] = round(float(np.median(skin_l)), 1)
        stats["l_threshold"] = round(float(np.median(skin_l) + eff_l), 1)
        stats["fitzpatrick_type"] = fitz
        stats["adaptive_chroma"] = max_chroma if max_chroma is not None else adaptive_chroma

        res = segment_lesions_edge_aware(img_rgb, region)
        mask = res["lesion_mask"]
        edge_stats = res.get("stats", {})
        stats["region_pixels"] = int(region.sum())
        stats["vitiligo_pixels"] = int(mask.sum())
        stats["method"] = "edge-aware-local-adaptive"
        stats["sigma_l"] = edge_stats.get("sigma_l")
        stats["sigma_c"] = edge_stats.get("sigma_c")
        stats["components"] = edge_stats.get("components")
        return mask, stats
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

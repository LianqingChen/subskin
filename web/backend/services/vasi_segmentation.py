"""
白斑像素级分割服务
基于 SAM (Segment Anything Model) 自动模式，nnUNet 作为额外回退

关键算法决策（修复 v2 — 用户反馈）:
  原算法用绝对阈值 L > 180 判断白斑，导致白色背景/衣服/纸张全部被识别成白斑。
  新算法分两阶段：
    1) 先用 HSV+YCrCb 双色彩空间识别皮肤前景（background 排除）
    2) 仅在皮肤区域内，用相对亮度阈值（skin_median_L + 12）检测白斑
  SAM 生成的 mask 必须与皮肤区域重叠 ≥50% 才被采纳，防止背景 mask 混入。
"""

import logging
import io
import math
import os
from typing import List, Dict, Any, Optional

import numpy as np
from PIL import Image

from web.backend.services.vasi_skin_mask import (
    build_skin_mask,
    expand_skin_mask_to_include_vitiligo,
    detect_vitiligo_within_skin,
    mask_overlap_ratio,
    mask_to_data_url,
    split_into_connected_components,
)

logger = logging.getLogger(__name__)

# ── SAM 延迟加载 (两级精度) ──

_sam_model = None          # 共享的 SAM ViT-B 模型权重 (只加载一次)
_sam_quick_generator = None   # 快速模式: points_per_side=8, crop_n_layers=0
_sam_precise_generator = None  # 精确模式: points_per_side=32, crop_n_layers=1
SAM_AVAILABLE = False


def _load_sam_model():
    """加载 SAM ViT-B 模型权重 (仅一次)"""
    global _sam_model, SAM_AVAILABLE

    if _sam_model is not None:
        return _sam_model

    try:
        import torch
        from segment_anything import sam_model_registry

        model_path = os.environ.get(
            "SAM_MODEL_PATH",
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "models", "sam_vit_b_01ec64.pth"),
        )
        model_path = os.path.abspath(model_path)
        device = "cuda" if torch.cuda.is_available() else "cpu"

        logger.info("Loading SAM ViT-B on %s...", device)
        _sam_model = sam_model_registry["vit_b"](checkpoint=model_path)
        _sam_model.to(device=device)
        SAM_AVAILABLE = True
        logger.info("SAM model loaded successfully")
        return _sam_model

    except Exception as e:
        logger.error("SAM model loading failed: %s", e)
        SAM_AVAILABLE = False
        return None


def _get_sam_generator(precision: str = "quick"):
    """获取指定精度的 SAM mask generator。

    Args:
        precision: "quick" (快速, ~10s CPU) 或 "precise" (精确, ~70s CPU)

    Returns:
        SamAutomaticMaskGenerator 实例, 或 None
    """
    global _sam_quick_generator, _sam_precise_generator

    if precision == "precise" and _sam_precise_generator is not None:
        return _sam_precise_generator
    if precision == "quick" and _sam_quick_generator is not None:
        return _sam_quick_generator

    sam = _load_sam_model()
    if sam is None:
        return None

    try:
        from segment_anything import SamAutomaticMaskGenerator

        if precision == "precise":
            _sam_precise_generator = SamAutomaticMaskGenerator(
                model=sam,
                points_per_side=32,          # 32×32=1024 网格点
                pred_iou_thresh=0.88,
                stability_score_thresh=0.92,
                min_mask_region_area=100,     # 较小阈值, 保留更多细节
                crop_n_layers=1,              # 额外裁剪层
                crop_n_points_downscale_factor=2,
            )
            logger.info("SAM precise generator created (points_per_side=32)")
            return _sam_precise_generator
        else:
            _sam_quick_generator = SamAutomaticMaskGenerator(
                model=sam,
                points_per_side=16,          # 16×16=256 grid points (was 64)
                pred_iou_thresh=0.80,        # 略低阈值, 确保捕获小斑块
                stability_score_thresh=0.85,
                min_mask_region_area=200,     # 降低阈值, 捕获小斑块
                crop_n_layers=0,             # 无额外裁剪
            )
            logger.info("SAM quick generator created (points_per_side=16)")
            return _sam_quick_generator

    except Exception as e:
        logger.error("SAM generator creation failed: %s", e)
        return None


def _merge_overlapping_masks(
    masks: List[np.ndarray], iou_threshold: float = 0.3
) -> List[np.ndarray]:
    """合并重叠的白斑 mask"""
    if len(masks) <= 1:
        return masks

    merged: List[np.ndarray] = []
    used = [False] * len(masks)

    for i in range(len(masks)):
        if used[i]:
            continue
        current = masks[i].copy()
        used[i] = True

        # 找所有与当前mask重叠的
        changed = True
        while changed:
            changed = False
            for j in range(i + 1, len(masks)):
                if used[j]:
                    continue
                # 简单重叠检测: 交集面积 / 较小mask面积
                intersection = np.logical_and(current, masks[j]).sum()
                min_area = min(current.sum(), masks[j].sum())
                if min_area > 0 and intersection / min_area > iou_threshold:
                    current = np.logical_or(current, masks[j])
                    used[j] = True
                    changed = True

        merged.append(current)

    return merged


# ── 轮廓提取 ──

def _mask_to_polygon(
    mask: np.ndarray,
    epsilon_factor: float = 0.005,
    max_points: int = 40,
) -> Optional[List[List[float]]]:
    """
    将二值 mask 转换为归一化的多边形坐标。

    Args:
        mask: 二值 numpy array (H, W)
        epsilon_factor: Douglas-Peucker 简化系数
        max_points: 最大顶点数

    Returns:
        polygon: [[x, y], ...] 归一化坐标 (0-1)
    """
    try:
        import cv2

        # ── Edge refinement: morphological closing to smooth SAM jaggies ──
        # SAM masks often have pixel-level roughness from grid sampling.
        # A small closing (dilation→erosion) smooths jagged edges
        # without significantly changing the lesion area.
        kernel_size = min(5, max(3, min(mask.shape) // 200))
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
        mask_smoothed = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_CLOSE, kernel)
        mask_uint8 = (mask_smoothed * 255).astype(np.uint8)
        contours, _ = cv2.findContours(
            mask_uint8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        if not contours:
            return None

        # 取最大轮廓
        largest = max(contours, key=cv2.contourArea)

        # 简化
        epsilon = epsilon_factor * cv2.arcLength(largest, True)
        approx = cv2.approxPolyDP(largest, epsilon, True)

        # 归一化
        h, w = mask.shape
        points: List[List[float]] = []
        for pt in approx:
            x, y = pt[0]
            points.append([round(float(x) / w, 3), round(float(y) / h, 3)])

        # 如果点太多，均匀采样
        if len(points) > max_points:
            step = len(points) / max_points
            points = [points[int(i * step)] for i in range(max_points)]

        return points

    except ImportError:
        # 纯 Python fallback: 边界跟踪
        return _mask_to_polygon_fallback(mask, max_points)


def _mask_to_polygon_fallback(
    mask: np.ndarray,
    max_points: int = 40,
) -> Optional[List[List[float]]]:
    """纯 Python 的 mask 轮廓提取（不依赖 opencv）"""
    h, w = mask.shape

    # 找边界像素
    try:
        from scipy import ndimage
        # 膨胀后与原mask求差 = 边界
        dilated = ndimage.binary_dilation(mask, iterations=1)
        boundary = np.logical_xor(dilated, mask)
    except ImportError:
        # 超级 fallback: 直接取mask像素的外接矩形采样
        rows, cols = np.where(mask)
        if len(rows) == 0:
            return None
        rmin, rmax = rows.min(), rows.max()
        cmin, cmax = cols.min(), cols.max()
        # 采样椭圆
        n_pts = min(max_points, 16)
        cx, cy = (cmin + cmax) / 2, (rmin + rmax) / 2
        rx, ry = (cmax - cmin) / 2, (rmax - rmin) / 2
        points: List[List[float]] = []
        for i in range(n_pts):
            angle = 2 * math.pi * i / n_pts
            x = cx + rx * math.cos(angle)
            y = cy + ry * math.sin(angle)
            points.append([
                round(max(0, min(1, x / w)), 3),
                round(max(0, min(1, y / h)), 3),
            ])
        return points

    # 从边界提取有序点
    boundary_points = np.argwhere(boundary)
    if len(boundary_points) == 0:
        return None

    # 简化采样
    step = max(1, len(boundary_points) // max_points)
    sampled = boundary_points[::step]

    points: List[List[float]] = []
    for pt in sampled:
        points.append([
            round(float(pt[1]) / w, 3),
            round(float(pt[0]) / h, 3),
        ])

    return points[:max_points]


# ── 主分割函数 ──

def segment_vitiligo(
    image_bytes: bytes,
    min_patch_area_ratio: float = 0.005,
    max_patches: int = 5,
    precision: str = "quick",
) -> Dict[str, Any]:
    """
    主入口: 对照片进行白斑分割。

    Args:
        image_bytes: JPEG/PNG 图片二进制数据
        min_patch_area_ratio: 最小白斑面积占比
        max_patches: 最大返回的白斑区域数
        precision: "quick" (~10s CPU) 或 "precise" (~70s CPU)

    Returns:
        {
            "success": bool,
            "contours": [{label, polygon, area_percent}, ...],
            "total_area_percent": float,
            "source": "sam" | "fallback",
            "precision": str,
            "error": Optional[str]
        }
    """
    result: Dict[str, Any] = {
        "success": False,
        "contours": [],
        "total_area_percent": 0.0,
        "source": "fallback",
        "precision": precision,
        "error": None,
    }

    # Step 1: 加载图片
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img_np = np.array(img)
    except Exception as e:
        result["error"] = f"Image load failed: {e}"
        return result

    h, w = img_np.shape[:2]
    total_pixels = h * w

    # Step 2: 尝试 SAM 分割
    mask_generator = _get_sam_generator(precision)

    if mask_generator is None:
        logger.warning("SAM unavailable, using CV fallback")
        return _fallback_segmentation(img_np, min_patch_area_ratio, max_patches)

    skin_mask = build_skin_mask(img_np)
    if skin_mask is None or skin_mask.sum() / total_pixels < 0.03:
        logger.warning(
            "Skin mask insufficient (ratio=%.3f). Using CV fallback.",
            (skin_mask.sum() / total_pixels) if skin_mask is not None else 0,
        )
        return _fallback_segmentation(img_np, min_patch_area_ratio, max_patches)

    analysis_region = expand_skin_mask_to_include_vitiligo(img_np, skin_mask)
    logger.info(
        "Skin foreground: %.1f%% of image; analysis region: %.1f%%",
        100 * skin_mask.sum() / total_pixels,
        100 * analysis_region.sum() / total_pixels,
    )

    try:
        logger.info(
            "Running SAM auto-segmentation (%s) on %dx%d image...",
            precision, w, h,
        )
        masks = mask_generator.generate(img_np)
        logger.info("SAM generated %d candidate masks", len(masks))

        white_patch_masks: List[np.ndarray] = []
        for m in masks:
            mask_array = m["segmentation"]

            if mask_overlap_ratio(mask_array, analysis_region) < 0.7:
                continue

            if _is_white_patch_mask_within_skin(img_np, mask_array, analysis_region):
                white_patch_masks.append(mask_array)

        logger.info("Filtered %d white patch masks within skin", len(white_patch_masks))

        vitiligo_mask, vit_stats = detect_vitiligo_within_skin(img_np, analysis_region)
        logger.info(
            "Relative-L vitiligo detection: skin_median_L=%s, threshold=%s, pixels=%s",
            vit_stats.get("skin_median_l"),
            vit_stats.get("l_threshold"),
            vit_stats.get("vitiligo_pixels"),
        )

        if vitiligo_mask is not None and vitiligo_mask.any():
            for component in split_into_connected_components(vitiligo_mask, min_area=100):
                if not any(np.array_equal(component, m) for m in white_patch_masks):
                    white_patch_masks.append(component)

        skin_pixels = max(int(analysis_region.sum()), 1)
        skin_region_ratio = round(100 * skin_mask.sum() / total_pixels, 1)

        if not white_patch_masks:
            result["source"] = "sam"
            result["error"] = "No vitiligo patches detected within skin region"
            result["skin_region_ratio"] = skin_region_ratio
            return result

        merged_masks = _merge_overlapping_masks(white_patch_masks)
        logger.info("Merged into %d patches", len(merged_masks))

        contours: List[Dict[str, Any]] = []
        total_area_in_skin = 0.0
        combined_lesion_mask = np.zeros_like(analysis_region, dtype=bool)

        for i, mask in enumerate(merged_masks[:max_patches]):
            patch_in_skin = np.logical_and(mask, analysis_region)
            area_pixels = int(patch_in_skin.sum())
            area_percent_in_skin = (area_pixels / skin_pixels) * 100
            area_percent_in_image = (area_pixels / total_pixels) * 100

            if area_percent_in_skin < min_patch_area_ratio * 100:
                continue

            polygon = _mask_to_polygon(patch_in_skin)
            if polygon is None:
                continue

            contours.append({
                "label": f"白斑{i + 1}",
                "polygon": polygon,
                "area_percent": round(area_percent_in_skin, 1),
                "area_percent_in_image": round(area_percent_in_image, 1),
            })
            total_area_in_skin += area_percent_in_skin
            combined_lesion_mask |= patch_in_skin

        if not contours:
            result["source"] = "sam"
            result["error"] = "White patches too small after filtering"
            result["skin_layer_data_url"] = mask_to_data_url(analysis_region, color=(96, 165, 250), alpha=110)
            result["lesion_layer_data_url"] = None
            return result

        result["success"] = True
        result["contours"] = contours
        result["total_area_percent"] = round(min(total_area_in_skin, 100.0), 1)
        result["source"] = "sam"
        result["skin_region_ratio"] = skin_region_ratio
        result["denominator"] = "skin_region"
        result["vitiligo_stats"] = vit_stats
        result["skin_layer_data_url"] = mask_to_data_url(analysis_region, color=(96, 165, 250), alpha=110)
        result["lesion_layer_data_url"] = mask_to_data_url(combined_lesion_mask, color=(244, 114, 182), alpha=180)
        return result

    except Exception as e:
        logger.error("SAM segmentation error: %s", e, exc_info=True)
        return _fallback_segmentation(img_np, min_patch_area_ratio, max_patches)


def _is_white_patch_mask_within_skin(
    image_np: np.ndarray,
    mask: np.ndarray,
    skin_region: np.ndarray,
    min_l_offset: float = 10.0,
    max_chroma: float = 35.0,
    max_skin_coverage: float = 0.7,
) -> bool:
    """Decide whether a SAM-generated mask represents a vitiligo patch.

    A real vitiligo patch must:
      1. Cover at most `max_skin_coverage` of the skin region (otherwise it's
         likely the whole skin, not a localized patch).
      2. Sit substantially inside the skin region (≥70% overlap, checked by caller).
      3. Be ≥ min_l_offset L* units lighter than the surrounding skin median.
      4. Have low chroma (median < max_chroma) — vitiligo lacks melanin pigment.

    Returns False if any condition fails. Conservative by design — false
    negatives are acceptable because the relative-L global detector
    (detect_vitiligo_within_skin) provides a second path.
    """
    if not mask.any():
        return False
    try:
        import cv2
    except ImportError:
        return False

    mask_area = int(mask.sum())
    skin_area = int(skin_region.sum())
    if skin_area == 0:
        return False
    if mask_area / skin_area > max_skin_coverage:
        return False

    img_bgr = cv2.cvtColor(image_np, cv2.COLOR_RGB2BGR)
    lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)
    L = lab[:, :, 0].astype(np.float32)
    A = lab[:, :, 1].astype(np.float32)
    B = lab[:, :, 2].astype(np.float32)
    chroma = np.sqrt((A - 128) ** 2 + (B - 128) ** 2)

    surrounding_skin = skin_region & (~mask)
    if surrounding_skin.sum() < 200:
        return False

    mask_l_median = float(np.median(L[mask]))
    skin_l_median = float(np.median(L[surrounding_skin]))
    mask_chroma_median = float(np.median(chroma[mask]))

    return (
        mask_l_median >= skin_l_median + min_l_offset
        and mask_chroma_median <= max_chroma
    )


def _fallback_segmentation(
    img_np: np.ndarray,
    min_patch_area_ratio: float,
    max_patches: int,
) -> Dict[str, Any]:
    """Skin-aware CV fallback when SAM is unavailable.

    Uses the same two-stage logic as the SAM path: skin foreground first,
    then relative-lightness vitiligo detection inside it.
    """
    h, w = img_np.shape[:2]
    total_pixels = h * w

    result: Dict[str, Any] = {
        "success": False,
        "contours": [],
        "total_area_percent": 0.0,
        "source": "fallback",
        "error": None,
    }

    skin_mask = build_skin_mask(img_np)
    if skin_mask is None or skin_mask.sum() / total_pixels < 0.03:
        result["error"] = "未检测到足够的皮肤区域，请让患处更靠近相机"
        return result

    analysis_region = expand_skin_mask_to_include_vitiligo(img_np, skin_mask)
    vitiligo_mask, stats = detect_vitiligo_within_skin(img_np, analysis_region)

    skin_pixels = max(int(analysis_region.sum()), 1)
    skin_region_ratio = round(100 * skin_mask.sum() / total_pixels, 1)

    if vitiligo_mask is None or not vitiligo_mask.any():
        result["error"] = "未在皮肤区域内检测到明显的白斑"
        result["skin_region_ratio"] = skin_region_ratio
        result["vitiligo_stats"] = stats
        return result

    patches_meta: List[Dict[str, Any]] = []
    for component in split_into_connected_components(vitiligo_mask, min_area=100):
        area_pixels = int(component.sum())
        area_percent_in_skin = (area_pixels / skin_pixels) * 100
        area_percent_in_image = (area_pixels / total_pixels) * 100
        if area_percent_in_skin < min_patch_area_ratio * 100:
            continue
        polygon = _mask_to_polygon(component)
        if polygon is None:
            continue
        patches_meta.append({
            "label": f"白斑{len(patches_meta) + 1}",
            "polygon": polygon,
            "area_percent": round(area_percent_in_skin, 1),
            "area_percent_in_image": round(area_percent_in_image, 1),
        })

    patches_meta.sort(key=lambda p: p["area_percent"], reverse=True)
    patches_meta = patches_meta[:max_patches]

    if patches_meta:
        result["success"] = True
        result["contours"] = patches_meta
        result["total_area_percent"] = round(
            sum(p["area_percent"] for p in patches_meta), 1
        )
    else:
        result["error"] = "检测到的白斑面积过小"

    result["skin_region_ratio"] = skin_region_ratio
    result["denominator"] = "skin_region"
    result["vitiligo_stats"] = stats
    result["skin_layer_data_url"] = mask_to_data_url(analysis_region, color=(96, 165, 250), alpha=110)
    if patches_meta and vitiligo_mask is not None:
        result["lesion_layer_data_url"] = mask_to_data_url(vitiligo_mask, color=(244, 114, 182), alpha=180)
    return result


# ── nnU-Net remote segmentation (additional fallback) ──────────────────────

try:
    import os as _os
    import httpx as _httpx

    _HTTPX_AVAILABLE = True
except ImportError:
    _HTTPX_AVAILABLE = False


class nnUNetSegmentationService:
    """nnU-Net segmentation service via Volcano Engine ML Platform.

    Issues async POST requests to the deployed nnU-Net online prediction
    endpoint. Returns structured segmentation results including VASI score,
    area percentage, contours, and confidence.
    """

    DEFAULT_TIMEOUT = 30  # seconds

    def __init__(self):
        self.endpoint = _os.getenv("VOLC_ML_ENDPOINT", "") if _HTTPX_AVAILABLE else ""
        self.token = _os.getenv("VOLC_ML_TOKEN", "") if _HTTPX_AVAILABLE else ""

    @property
    def available(self) -> bool:
        return bool(self.endpoint and self.token and _HTTPX_AVAILABLE)

    async def segment(self, image_bytes: bytes) -> Optional[Dict[str, Any]]:
        """Call nnU-Net segmentation API.

        Args:
            image_bytes: Preprocessed JPEG image bytes.

        Returns:
            Dict with vasi_score, area_percentage, contours, confidence,
            details, raw_response, source. None on failure.
        """
        if not self.available:
            return None

        try:
            async with _httpx.AsyncClient(timeout=self.DEFAULT_TIMEOUT) as client:
                response = await client.post(
                    self.endpoint,
                    headers={
                        "Authorization": f"Bearer {self.token}",
                        "Content-Type": "application/octet-stream",
                    },
                    content=image_bytes,
                )
                response.raise_for_status()
                raw_result = response.json()

                area_percentage = float(raw_result.get("area_percentage", 0))
                contours = raw_result.get("contours", [])
                confidence = float(raw_result.get("confidence", 0.5))

                validated_contours = _validate_contours(contours)

                details: Dict[str, Any] = {
                    "patch_count": len(validated_contours),
                    "source": "nnunet-segmentation",
                    "scale_factor": raw_result.get("scale_factor"),
                    "area_pixels": raw_result.get("area_pixels"),
                }

                return {
                    "vasi_score": round(area_percentage, 1),
                    "area_percentage": round(area_percentage, 1),
                    "contours": validated_contours,
                    "confidence": round(confidence, 2),
                    "details": details,
                    "raw_response": raw_result,
                    "source": "nnunet-segmentation",
                }

        except Exception as e:
            logger.warning("nnU-Net segmentation failed: %s", e)

        return None


def _validate_contours(contours: list) -> list:
    """Validate and normalize contour data from nnU-Net output."""
    if not isinstance(contours, list):
        return []

    valid: List[Dict[str, Any]] = []
    for c in contours:
        if not isinstance(c, dict):
            continue
        polygon = c.get("polygon", [])
        if not isinstance(polygon, list) or len(polygon) < 3:
            continue

        valid_points: List[List[float]] = []
        for pt in polygon:
            if (isinstance(pt, (list, tuple)) and len(pt) == 2
                    and isinstance(pt[0], (int, float))
                    and isinstance(pt[1], (int, float))):
                valid_points.append([
                    round(max(0.0, min(1.0, float(pt[0]))), 3),
                    round(max(0.0, min(1.0, float(pt[1]))), 3),
                ])

        if len(valid_points) >= 3:
            valid.append({
                "label": c.get("label", f"白斑{len(valid) + 1}"),
                "polygon": valid_points,
                "area_percent": float(c.get("area_percent", 0)),
            })

    return valid


# ── VLM-Guided Segmentation ──────────────────────────────────────────────────

def segment_vitiligo_guided(
    image_bytes: bytes,
    skin_bbox: Optional[List[float]] = None,
    lesion_centers: Optional[List[List[float]]] = None,
    precision: str = "quick",
    lesion_sizes: Optional[List[float]] = None,
    lesion_bboxes: Optional[List[List[float]]] = None,
    lesion_metas: Optional[List[Dict[str, Any]]] = None,
    is_ensemble: bool = False,
    lesion_edge_points: Optional[List[List[List[float]]]] = None,
) -> Dict[str, Any]:
    """VLM-guided SAM segmentation: use VLM's semantic understanding to
    guide SAM with box/point prompts instead of color heuristics.

    Args:
        image_bytes: JPEG/PNG image.
        skin_bbox: [x1, y1, x2, y2] normalized 0-1 from VLM.
        lesion_centers: [[cx, cy], ...] normalized 0-1 from VLM.
        precision: "quick" or "precise" (for log metadata only).
        lesion_sizes: [percent, ...] VLM's estimated_size_percent per lesion.
            Used to infer bbox for box-prompts (SAM's strongest guidance mode).
        lesion_bboxes: [[x1,y1,x2,y2], ...] VLM's direct per-lesion bbox (v4.0+).
            These are preferred over center+size inferred boxes.
        lesion_metas: [{"contrast":0.5,"confidence":0.8,"depigmentation":"2"}, ...]
            Per-lesion VLM metadata for adaptive SAM parameters.
        is_ensemble: True when lesions come from VLM consensus (two calls).
            Enables more aggressive low-contrast retry because consensus lesions
            are higher quality (fewer false positives).
        lesion_edge_points: [[[x,y], ...], ...] VLM's per-lesion boundary
            keypoints (normalized 0-1). Used as additional positive SAM prompts
            alongside the box, to refine irregular lesion edges.
    """
    result: Dict[str, Any] = {
        "success": False,
        "contours": [],
        "total_area_percent": 0.0,
        "source": "vlm-guided",
        "precision": precision,
        "error": None,
        "skin_region_ratio": None,
        "denominator": "skin_region",
    }

    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img_np = np.array(img)
    except Exception as e:
        result["error"] = f"Image load failed: {e}"
        return result

    h, w = img_np.shape[:2]
    total_pixels = h * w

    # ── Load SAM predictor ──
    try:
        import torch
        from segment_anything import sam_model_registry, SamPredictor

        sam = _load_sam_model()
        if sam is None:
            logger.warning("SAM not available for guided mode, falling back to auto")
            return segment_vitiligo(image_bytes, 0.005, 5, precision)

        predictor = SamPredictor(sam)
        predictor.set_image(img_np)
    except Exception as e:
        logger.error("SAM predictor setup failed: %s", e)
        return segment_vitiligo(image_bytes, 0.005, 5, precision)

    # ── Step 1: Skin mask via VLM box prompt or color fallback ──
    skin_pixels: Optional[int] = None
    skin_mask: Optional[np.ndarray] = None

    if skin_bbox and len(skin_bbox) == 4:
        x1 = max(0, int(skin_bbox[0] * w))
        y1 = max(0, int(skin_bbox[1] * h))
        x2 = min(w, int(skin_bbox[2] * w))
        y2 = min(h, int(skin_bbox[3] * h))

        if x2 > x1 and y2 > y1:
            try:
                masks, scores, _ = predictor.predict(
                    box=np.array([[x1, y1, x2, y2]]),
                    multimask_output=True,
                )
                best_idx = int(np.argmax(scores))
                skin_mask = np.asarray(masks[best_idx]).astype(bool)
                skin_pixels = int(skin_mask.sum())
                logger.info(
                    "VLM-guided skin mask: bbox=[%.2f,%.2f,%.2f,%.2f] → %d pixels (%.1f%%), score=%.3f",
                    skin_bbox[0], skin_bbox[1], skin_bbox[2], skin_bbox[3],
                    skin_pixels, 100 * skin_pixels / total_pixels, float(scores[best_idx]),
                )
            except Exception as e:
                logger.warning("VLM skin box prompt failed: %s", e)

    # Fallback to color-based skin detection if VLM guidance failed
    if skin_mask is None:
        skin_mask = build_skin_mask(img_np)
        if skin_mask is not None:
            skin_mask = expand_skin_mask_to_include_vitiligo(img_np, skin_mask)
            skin_pixels = int(skin_mask.sum())
            logger.info("Falling back to color-based skin mask: %d pixels", skin_pixels)
            result["source"] = "vlm-guided+color-skin"

    if skin_mask is None or skin_pixels is None or skin_pixels < total_pixels * 0.03:
        logger.warning("Insufficient skin region, falling back to auto")
        return segment_vitiligo(image_bytes, 0.005, 5, precision)

    skin_region_ratio = round(100 * skin_pixels / total_pixels, 1)
    result["skin_region_ratio"] = skin_region_ratio
    result["skin_layer_data_url"] = mask_to_data_url(skin_mask, color=(96, 165, 250), alpha=110)

    # ── Step 1.5: Crop SAM viewport to skin bbox ──
    # Without this, a single lesion point prompt often grabs the ENTIRE face/neck
    # because SAM sees the full image. By cropping to skin_bbox first, point
    # prompts only search within the skin region → much tighter initial masks.
    crop_x1 = crop_y1 = 0
    crop_w = w
    crop_h = h
    crop_img_np = img_np
    use_cropped = False

    if skin_bbox and len(skin_bbox) == 4:
        bx1 = max(0, int(skin_bbox[0] * w))
        by1 = max(0, int(skin_bbox[1] * h))
        bx2 = min(w, int(skin_bbox[2] * w))
        by2 = min(h, int(skin_bbox[3] * h))
        if bx2 > bx1 + 64 and by2 > by1 + 64:
            crop_x1, crop_y1 = bx1, by1
            crop_w, crop_h = bx2 - bx1, by2 - by1
            crop_img_np = img_np[crop_y1:by2, crop_x1:bx2]
            use_cropped = True
            logger.info(
                "Skin crop: [%d:%d, %d:%d] → %dx%d",
                crop_x1, by2, crop_y1, by2, crop_w, crop_h,
            )

    # ── Step 1.6: Decide SAM viewport for lesion detection ──
    # When we have VLM per-lesion bboxes, use FULL image for lesion prompts.
    # Box prompts naturally constrain SAM to the right region, so the skin crop
    # (designed to prevent point prompts from grabbing the whole face) is harmful:
    # lesions near the crop boundary get their bboxes clipped or zeroed.
    # Still use the skin crop for point-prompt-only fallback.
    use_full_for_lesions = bool(lesion_bboxes) if lesion_bboxes else False

    if use_full_for_lesions:
        # Keep predictor on full image for accurate bbox-to-pixel mapping
        logger.info(
            "Using FULL image for %d VLM-guided lesion bboxes (no skin crop)",
            len(lesion_bboxes),
        )
        # Reset crop params to full-image identity (bboxes map directly)
        crop_x1, crop_y1 = 0, 0
        crop_w, crop_h = w, h
        # predictor already set on full image from skin mask step — re-set to be safe
        try:
            predictor.set_image(img_np)
        except Exception as e:
            logger.warning("SAM full-image reset failed: %s", e)
    elif use_cropped:
        try:
            predictor.set_image(crop_img_np)
            logger.info("SAM predictor reset to cropped skin region (no lesion bboxes)")
        except Exception as e:
            logger.warning("SAM crop reset failed: %s, using full image", e)
            use_cropped = False
            predictor.set_image(img_np)
            crop_x1, crop_y1 = 0, 0
            crop_w, crop_h = w, h

    # ── Step 2: Lesion masks via VLM box/point prompts ──
    lesion_masks: List[np.ndarray] = []

    if lesion_centers:
        for i, center in enumerate(lesion_centers):
            if len(center) < 2:
                continue
            # Clamp center coordinates to [0, 1]
            cx = max(0.0, min(1.0, float(center[0])))
            cy = max(0.0, min(1.0, float(center[1])))

            # Convert VLM full-image normalized coords → crop-relative pixels
            px_full = int(cx * w)
            py_full = int(cy * h)
            px = px_full - crop_x1
            py = py_full - crop_y1

            # Skip if point falls outside crop region
            if px < 0 or px >= crop_w or py < 0 or py >= crop_h:
                logger.info(
                    "Lesion %d center [%.3f, %.3f] outside skin crop, skipping",
                    i + 1, cx, cy,
                )
                continue

            # Get VLM's size estimate for this lesion
            est_size_pct: Optional[float] = None
            if lesion_sizes and i < len(lesion_sizes):
                est_size_pct = lesion_sizes[i]

            try:
                # ── Strategy: box prompt (best) > point+neg ring (decent) ──
                # Prefer VLM's direct per-lesion bbox (v4.0+ prompt) over inferred box
                mask_crop: Optional[np.ndarray] = None
                score = 0.0
                prompt_type = "point+neg"

                # Check for VLM's direct bbox per lesion first
                vlm_bbox: Optional[List[float]] = None
                if lesion_bboxes and i < len(lesion_bboxes):
                    vlm_bbox = lesion_bboxes[i]

                if vlm_bbox and len(vlm_bbox) == 4:
                    # Get per-lesion VLM metadata for adaptive SAM
                    meta: Dict[str, Any] = {}
                    if lesion_metas and i < len(lesion_metas):
                        meta = lesion_metas[i] or {}
                    contrast = float(meta.get("contrast", 0.5))
                    confidence = float(meta.get("confidence", 0.5))

                    # Convert VLM full-image normalized bbox → crop-relative pixels
                    bx1 = int(vlm_bbox[0] * w) - crop_x1
                    by1 = int(vlm_bbox[1] * h) - crop_y1
                    bx2 = int(vlm_bbox[2] * w) - crop_x1
                    by2 = int(vlm_bbox[3] * h) - crop_y1
                    # Clamp to crop boundaries
                    bx1 = max(0, min(bx1, crop_w))
                    by1 = max(0, min(by1, crop_h))
                    bx2 = max(0, min(bx2, crop_w))
                    by2 = max(0, min(by2, crop_h))
                    if bx2 > bx1 + 5 and by2 > by1 + 5:
                        # Collect VLM edge_points that fall inside the box as
                        # extra positive prompts — they steer SAM toward the
                        # true (often irregular) lesion boundary instead of the
                        # rectangular box. Points outside the box/ crop are dropped.
                        edge_pos: List[List[int]] = []
                        if lesion_edge_points and i < len(lesion_edge_points):
                            for ep in lesion_edge_points[i] or []:
                                if not (isinstance(ep, (list, tuple)) and len(ep) == 2):
                                    continue
                                epx = max(0.0, min(1.0, float(ep[0]))) * w - crop_x1
                                epy = max(0.0, min(1.0, float(ep[1]))) * h - crop_y1
                                epx_i, epy_i = int(round(epx)), int(round(epy))
                                if 0 <= epx_i < crop_w and 0 <= epy_i < crop_h:
                                    edge_pos.append([epx_i, epy_i])

                        try:
                            if edge_pos:
                                # Combine box + positive edge points.
                                # SAM expects point_coords as [N,2] (x,y) and
                                # matching labels (1=positive). Dedup to avoid
                                # redundant prompts skewing the mask.
                                seen = set()
                                unique_pos: List[List[int]] = []
                                for p in edge_pos:
                                    key = (p[0], p[1])
                                    if key not in seen:
                                        seen.add(key)
                                        unique_pos.append(p)
                                point_coords = np.array(unique_pos, dtype=np.float32)
                                point_labels = np.ones(len(unique_pos), dtype=np.int32)
                                masks, scores, _ = predictor.predict(
                                    box=np.array([[bx1, by1, bx2, by2]]),
                                    point_coords=point_coords,
                                    point_labels=point_labels,
                                    multimask_output=True,
                                )
                                ep_note = f"+{len(unique_pos)}edge"
                            else:
                                masks, scores, _ = predictor.predict(
                                    box=np.array([[bx1, by1, bx2, by2]]),
                                    multimask_output=True,
                                )
                                ep_note = ""
                            best_idx = int(np.argmax(scores))
                            mask_crop = np.asarray(masks[best_idx]).astype(bool)
                            score = float(scores[best_idx])
                            prompt_type = f"vlm-bbox[{bx1},{by1},{bx2},{by2}]{ep_note}"
                            logger.debug(
                                "Lesion %d VLM direct bbox: [%.2f,%.2f,%.2f,%.2f] → crop %dx%d score=%.3f%s",
                                i + 1, vlm_bbox[0], vlm_bbox[1], vlm_bbox[2], vlm_bbox[3],
                                bx2 - bx1, by2 - by1, score, ep_note,
                            )
                        except Exception as e:
                            logger.warning("Lesion %d VLM bbox prompt failed: %s", i + 1, e)

                    # ── Low-contrast retry: expand bbox + negative boundary ring ──
                    # When contrast is low (< 0.5) and VLM confident (> 0.7),
                    # the tight bbox prompt may miss subtle edges.
                    # Expand bbox + negative boundary ring to capture more.
                    # Also retry tiny masks regardless of SAM score.
                    # Ensemble consensus lesions: more aggressive trigger (higher thresholds).
                    if mask_crop is not None:
                        bbox_area_pct = 100.0 * int(mask_crop.sum()) / max(crop_w * crop_h, 1)
                        if is_ensemble:
                            # Consensus lesions are higher quality; retry aggressively.
                            should_retry = (
                                contrast < 0.5
                                and confidence > 0.7
                                and (score < 0.92 or bbox_area_pct < 1.0)
                            )
                        else:
                            # Non-ensemble: relaxed thresholds to catch more low-contrast hits.
                            should_retry = (
                                contrast < 0.5
                                and confidence > 0.7
                                and (score < 0.88 or bbox_area_pct < 0.5)
                            )
                    else:
                        should_retry = False
                    if should_retry:
                        try:
                            logger.info(
                                "Lesion %d triggering low-contrast retry: contrast=%.2f, score=%.3f, area=%.2f%%",
                                i + 1, contrast, score, bbox_area_pct,
                            )
                            # Expand bbox ~33% each side
                            bw = bx2 - bx1
                            bh = by2 - by1
                            ebx1 = max(0, bx1 - bw // 3)
                            eby1 = max(0, by1 - bh // 3)
                            ebx2 = min(crop_w, bx2 + bw // 3)
                            eby2 = min(crop_h, by2 + bh // 3)

                            # Negative points: 8 points along expanded bbox boundary
                            neg_coords = []
                            for xp in [ebx1, (ebx1 + ebx2) // 2, ebx2]:
                                for yp in [eby1, (eby1 + eby2) // 2, eby2]:
                                    if (xp in (ebx1, ebx2) or yp in (eby1, eby2)):
                                        neg_coords.append([xp, yp])
                            # Keep only genuinely exterior points
                            neg_coords = [
                                c for c in neg_coords
                                if c[0] < bx1 or c[0] > bx2 or c[1] < by1 or c[1] > by2
                            ][:8]

                            point_coords = np.array(
                                [[(bx1 + bx2) // 2, (by1 + by2) // 2]] + neg_coords
                            )
                            point_labels = np.array([1] + [0] * len(neg_coords))

                            masks2, scores2, _ = predictor.predict(
                                point_coords=point_coords,
                                point_labels=point_labels,
                                multimask_output=True,
                            )
                            best_idx2 = int(np.argmax(scores2))
                            retry_mask = np.asarray(masks2[best_idx2]).astype(bool)
                            retry_score = float(scores2[best_idx2])

                            # Only accept retry if it produces a meaningfully better mask
                            # (larger area AND decent score increase)
                            orig_area = int(mask_crop.sum())
                            retry_area = int(retry_mask.sum())
                            if retry_score > score + 0.05 and retry_area > orig_area * 0.8:
                                logger.info(
                                    "Lesion %d low-contrast retry: contrast=%.2f, "
                                    "score %.3f→%.3f, area %d→%d px (expanded bbox + neg ring)",
                                    i + 1, contrast, score, retry_score,
                                    orig_area, retry_area,
                                )
                                mask_crop = retry_mask
                                score = retry_score
                                prompt_type = f"vlm-bbox[lo-contrast-retry]"
                            else:
                                logger.debug(
                                    "Lesion %d low-contrast retry rejected: "
                                    "score %.3f→%.3f, area %d→%d px",
                                    i + 1, score, retry_score, orig_area, retry_area,
                                )
                        except Exception as e:
                            logger.warning(
                                "Lesion %d low-contrast retry failed: %s", i + 1, e
                            )

                # Fallback: inferred box from size estimate (legacy path)
                if mask_crop is None and est_size_pct and est_size_pct > 0.1:
                    # Infer tight bbox from VLM's estimated_size_percent
                    # Use 2x the target area as box (generous but not full-skin)
                    crop_area = crop_w * crop_h
                    target_area = (est_size_pct / 100.0) * crop_area
                    # side = sqrt(area), but use half that for tighter box
                    half_side = int(math.sqrt(target_area) * 0.50)
                    # Clamp: minimum 30px, maximum 25% of crop dim
                    half_side = max(30, min(half_side, min(crop_w, crop_h) // 4))

                    bx1 = max(0, px - half_side)
                    by1 = max(0, py - half_side)
                    bx2 = min(crop_w, px + half_side)
                    by2 = min(crop_h, py + half_side)

                    if bx2 > bx1 + 5 and by2 > by1 + 5:
                        try:
                            masks, scores, _ = predictor.predict(
                                box=np.array([[bx1, by1, bx2, by2]]),
                                multimask_output=True,
                            )
                            best_idx = int(np.argmax(scores))
                            mask_crop = np.asarray(masks[best_idx]).astype(bool)
                            score = float(scores[best_idx])
                            prompt_type = f"box[{bx1},{by1},{bx2},{by2}]"
                            logger.debug(
                                "Lesion %d box prompt: est_size=%.1f%% → bbox %dx%d score=%.3f",
                                i + 1, est_size_pct, bx2 - bx1, by2 - by1, score,
                            )
                        except Exception as e:
                            logger.warning("Lesion %d box prompt failed: %s, falling back", i + 1, e)

                # Fallback: point prompt with auto negative ring
                if mask_crop is None:
                    neg_radius = int(min(crop_w, crop_h) * 0.08)
                    neg_offsets = [
                        [-neg_radius, 0], [neg_radius, 0],
                        [0, -neg_radius], [0, neg_radius],
                    ]
                    neg_coords = []
                    for dx, dy in neg_offsets:
                        nx, ny = px + dx, py + dy
                        if 0 <= nx < crop_w and 0 <= ny < crop_h:
                            neg_coords.append([nx, ny])

                    point_coords = np.array([[px, py]] + neg_coords)
                    point_labels = np.array([1] + [0] * len(neg_coords))

                    masks, scores, _ = predictor.predict(
                        point_coords=point_coords,
                        point_labels=point_labels,
                        multimask_output=True,
                    )
                    best_idx = int(np.argmax(scores))
                    mask_crop = np.asarray(masks[best_idx]).astype(bool)
                    score = float(scores[best_idx])

                # Map crop-relative mask back to full-image space
                mask_full = np.zeros((h, w), dtype=bool)
                mask_full[crop_y1:crop_y1 + crop_h, crop_x1:crop_x1 + crop_w] = mask_crop

                # Only keep if mask overlaps with skin and score is decent
                # When VLM identified this lesion with a bbox: use lower bar.
                # SAM scores reflect boundary crispness, not lesion presence.
                if vlm_bbox:
                    min_score = 0.3
                    min_overlap = 0.2
                else:
                    min_score = 0.4
                    min_overlap = 0.3

                overlap = mask_overlap_ratio(mask_full, skin_mask) if skin_mask is not None else 0
                # VLM-identified lesion with high score but zero overlap with color-based skin:
                # VLM's implicit skin detection is more reliable than the color heuristic.
                # Trust VLM — keep the mask but mark it as VLM-skin-trusted.
                if vlm_bbox and score >= 0.5 and overlap < min_overlap:
                    logger.info(
                        "Lesion %d VLM rescue: score=%.3f, overlap=%.2f (VLM skin > color skin)",
                        i + 1, score, overlap,
                    )
                    lesion_masks.append(mask_full)
                    area_pct = 100 * int(mask_crop.sum()) / max(crop_w * crop_h, 1)
                    logger.info(
                        "Lesion %d: center=[%.3f,%.3f] %s → %d px (%.1f%%), overlap=%.2f, score=%.3f (VLM-rescued)",
                        i + 1, cx, cy, prompt_type,
                        int(mask_crop.sum()), area_pct, overlap, score,
                    )
                elif overlap >= min_overlap and score >= min_score:
                    # Iterative refinement — only for point prompts, not box
                    # (box prompts already produce tight masks; refinement
                    #  on small masks causes catastrophic expansion)
                    if prompt_type == "point+neg":
                        refined_full = _refine_lesion_iterative(
                            predictor, px, py, mask_crop, max_iter=2
                        )
                        refined = np.zeros((h, w), dtype=bool)
                        refined[crop_y1:crop_y1 + crop_h, crop_x1:crop_x1 + crop_w] = refined_full
                    else:
                        # Box prompt: keep as-is (already tight)
                        refined_full = mask_crop
                        refined = mask_full
                    lesion_masks.append(refined)
                    area_pct = 100 * int(refined_full.sum()) / max(crop_w * crop_h, 1)
                    logger.info(
                        "Lesion %d: center=[%.3f,%.3f] %s → %d→%d px (%.1f%%), overlap=%.2f, score=%.3f",
                        i + 1, cx, cy, prompt_type,
                        int(mask_crop.sum()), int(refined_full.sum()), area_pct, overlap, score,
                    )
                else:
                    logger.info(
                        "Lesion %d rejected: overlap=%.2f, score=%.3f",
                        i + 1, overlap, score,
                    )
            except Exception as e:
                logger.warning("Lesion %d point prompt failed: %s", i + 1, e)

    # Fallback to relative-lightness detection if no lesion masks found
    if not lesion_masks:
        logger.info("No VLM-guided lesions found, trying relative-L detection")
        vitiligo_mask, vit_stats = detect_vitiligo_within_skin(img_np, skin_mask)
        if vitiligo_mask is not None and vitiligo_mask.any():
            for component in split_into_connected_components(vitiligo_mask, min_area=100):
                lesion_masks.append(component)
            result["source"] += "+color-lesion"
            result["vitiligo_stats"] = vit_stats

    if not lesion_masks:
        result["error"] = "No vitiligo patches detected"
        return result

    # ── Step 3: Merge overlapping, extract contours ──
    # VLM per-lesion bboxes: trust VLM's semantic separation — skip merge.
    # VLM is the expert that identified distinct patches; merging them would
    # undo that work. Use a flag because some VLM lesions may be rejected by SAM.
    _vlm_guided = lesion_bboxes is not None and len(lesion_bboxes) > 0
    if _vlm_guided:
        merged = lesion_masks  # Each VLM-identified lesion stays independent
        logger.info("VLM-guided: skipping merge (%d independent patches)", len(merged))
    else:
        merged = _merge_overlapping_masks(lesion_masks, iou_threshold=0.3)
        logger.info("Guided: merged into %d patches", len(merged))

    contours: List[Dict[str, Any]] = []
    total_area_in_skin = 0.0
    combined_lesion_mask = np.zeros_like(skin_mask, dtype=bool)
    skin_px = max(skin_pixels or 1, 1)

    for i, mask in enumerate(merged[:15]):
        # VLM-guided: trust VLM's skin region — use mask as-is for contour
        # but clip to skin mask for area calculation (prevents >100% bug).
        is_vlm_guided = _vlm_guided and i < len(lesion_masks)
        if is_vlm_guided:
            patch_in_skin = mask
            # Clip area calculation to skin region
            area_in_skin = np.logical_and(mask, skin_mask) if skin_mask is not None else mask
        else:
            patch_in_skin = np.logical_and(mask, skin_mask)
            area_in_skin = patch_in_skin

        area_pixels = int(area_in_skin.sum())
        area_percent_in_skin = (area_pixels / skin_px) * 100
        # Cap at 100% — a single lesion cannot cover more than the region
        area_percent_in_skin = min(area_percent_in_skin, 100.0)

        # VLM-guided: lower threshold (pinpoint depigmentation is clinically relevant)
        # Auto-detected: slightly higher to filter noise fragments
        if area_percent_in_skin < 0.05:
            logger.info("Patch %d too small (%.3f%%), skipping", i + 1, area_percent_in_skin)
            continue

        polygon = _mask_to_polygon(patch_in_skin)
        if polygon is None:
            continue

        contours.append({
            "label": f"白斑{i + 1}",
            "polygon": polygon,
            "area_percent": round(area_percent_in_skin, 1),
        })
        total_area_in_skin += area_percent_in_skin
        combined_lesion_mask |= patch_in_skin

    if not contours:
        result["error"] = "White patches too small after filtering"
        return result

    result["success"] = True
    result["contours"] = contours
    # Use combined mask area (OR of all patches) to handle overlaps correctly.
    # Summing individual areas overcounts when VLM bboxes overlap.
    combined_area_pct = (combined_lesion_mask.sum() / max(skin_pixels, 1)) * 100
    result["total_area_percent"] = round(min(combined_area_pct, 100.0), 1)
    result["total_area_sum_pct"] = round(min(total_area_in_skin, 100.0), 1)
    result["lesion_layer_data_url"] = mask_to_data_url(combined_lesion_mask, color=(244, 114, 182), alpha=180)
    return result


# --- Direction 3: Iterative SAM Refinement ---

def _sample_boundary_points(
    mask: np.ndarray, num_points: int = 6, margin: int = 3
) -> np.ndarray:
    """Sample evenly-spaced points along the mask boundary for negative prompts.

    Uses morphological gradient (dilation - erosion) to find boundary pixels,
    then samples N points evenly distributed along the boundary.

    Returns: Nx2 array of [x, y] pixel coordinates.
    """
    from scipy.ndimage import binary_dilation, binary_erosion

    h, w = mask.shape
    if mask.sum() < 10:
        # Too small — sample corners
        ys, xs = np.where(mask)
        idx = np.random.choice(len(ys), min(num_points, len(ys)), replace=False)
        return np.column_stack([xs[idx], ys[idx]])

    # Morphological boundary
    kernel = np.ones((3, 3), dtype=bool)
    dilated = binary_dilation(mask, structure=kernel, iterations=margin)
    eroded = binary_erosion(mask, structure=kernel, iterations=margin)
    boundary = dilated & ~eroded

    ys, xs = np.where(boundary)
    if len(ys) == 0:
        # Fallback: sample from mask edge
        ys, xs = np.where(mask)

    if len(ys) <= num_points:
        return np.column_stack([xs, ys])

    # Evenly spaced sampling along the boundary contour
    idx = np.linspace(0, len(ys) - 1, num_points, dtype=int)
    return np.column_stack([xs[idx], ys[idx]])


def _refine_lesion_iterative(
    predictor,
    center_px: int,
    center_py: int,
    initial_mask: np.ndarray,
    max_iter: int = 2,
) -> np.ndarray:
    """Refine a lesion mask via iterative SAM with boundary negative points.

    Strategy:
      1. Get initial mask from single point prompt
      2. Sample boundary points of the mask
      3. Re-run SAM with: positive(center) + negative(boundary_points)
      4. The negative points tell SAM "not here" -> tighter mask boundaries
      5. Repeat 1-2 times until convergence

    Returns refined boolean mask.
    """
    h, w = initial_mask.shape
    current_mask = initial_mask.copy()

    for it in range(max_iter):
        # Sample boundary points as negatives
        neg_pts = _sample_boundary_points(current_mask, num_points=6)

        # Build prompt: center as positive, boundary as negative
        point_coords = np.array([[center_px, center_py]] + neg_pts.tolist())
        point_labels = np.array([1] + [0] * len(neg_pts))

        try:
            masks, scores, _ = predictor.predict(
                point_coords=point_coords,
                point_labels=point_labels,
                multimask_output=True,
            )
            best_idx = int(np.argmax(scores))
            refined = np.asarray(masks[best_idx]).astype(bool)

            # Check if refinement changed much
            overlap = (current_mask & refined).sum()
            union = (current_mask | refined).sum()
            iou = overlap / union if union > 0 else 0

            if iou > 0.95:
                # Converged — no significant change
                break

            current_mask = refined
            logger.debug(
                "Iterative refine iter=%d: IoU=%.3f, area=%d px → %d px",
                it + 1, iou, int(initial_mask.sum()), int(current_mask.sum()),
            )

        except Exception as e:
            logger.warning("Iterative refine iter=%d failed: %s", it + 1, e)
            break

    return current_mask


def _segment_with_tiling(
    image_bytes: bytes,
    min_area_percent: float = 0.5,
    precision: str = "quick",
) -> Dict[str, Any]:
    """Multi-scale tiling: split large image into overlapping tiles to catch
    small lesions that SAM misses at full-image scale.

    Tile size: 512x512, overlap: 128px (25%).
    Each tile runs SAM independently, masks are merged with IoU dedup.
    """
    import torch
    from segment_anything import SamAutomaticMaskGenerator

    result: Dict[str, Any] = {
        "success": False,
        "contours": [],
        "total_area_percent": 0.0,
        "source": "sam-tiled",
        "precision": precision,
        "error": None,
    }

    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img_np = np.array(img)
    except Exception as e:
        result["error"] = f"Image load failed: {e}"
        return result

    h, w = img_np.shape[:2]
    total_pixels = h * w

    # Only tile if image is large enough
    if h <= 512 and w <= 512:
        logger.info("Image too small for tiling (%dx%d), skipping", h, w)
        return result

    try:
        sam = _load_sam_model()
        if sam is None:
            return result

        generator = _get_sam_generator(precision)
        if generator is None:
            return result
    except Exception as e:
        result["error"] = f"SAM setup failed: {e}"
        return result

    # Tile parameters
    tile_size = 512
    overlap = 128
    stride = tile_size - overlap

    # Collect all masks from all tiles
    all_masks: List[np.ndarray] = []
    tile_count = 0

    for y in range(0, h, stride):
        for x in range(0, w, stride):
            # Extract tile (clamp to image bounds)
            x1, y1 = x, y
            x2, y2 = min(x + tile_size, w), min(y + tile_size, h)

            # Skip tiny edge tiles
            if (x2 - x1) < 128 or (y2 - y1) < 128:
                continue

            tile = img_np[y1:y2, x1:x2]
            tile_count += 1

            try:
                raw_masks = generator.generate(tile)
                for m in raw_masks:
                    seg = m["segmentation"]
                    area = m["area"]
                    tile_area = (x2 - x1) * (y2 - y1)

                    # Skip tiny masks
                    if area < tile_area * 0.005:
                        continue

                    # Place tile mask into full-image coordinates
                    full_mask = np.zeros((h, w), dtype=bool)
                    full_mask[y1:y2, x1:x2] = seg
                    all_masks.append(full_mask)

            except Exception as e:
                logger.warning("Tile [%d:%d, %d:%d] failed: %s", y1, y2, x1, x2, e)
                continue

    if not all_masks:
        result["error"] = f"No masks found in {tile_count} tiles"
        return result

    logger.info(
        "Tiling: %d tiles → %d raw masks", tile_count, len(all_masks)
    )

    # Deduplicate overlapping masks
    merged = _merge_overlapping_masks(all_masks, iou_threshold=0.4)
    logger.info("Tiling: after dedup → %d masks", len(merged))

    # Filter by size relative to image
    result["contours"] = []
    total_area = 0.0
    for i, mask in enumerate(merged[:10]):
        area_px = int(mask.sum())
        area_pct = 100 * area_px / total_pixels
        if area_pct < min_area_percent:
            continue
        polygon = _mask_to_polygon(mask)
        if polygon is None:
            continue
        result["contours"].append({
            "label": f"白斑{i + 1}",
            "polygon": polygon,
            "area_percent": round(area_pct, 1),
        })
        total_area += area_pct

    if result["contours"]:
        result["success"] = True
        result["total_area_percent"] = round(min(total_area, 100.0), 1)

    return result


# ── Module-level singleton ───────────────────────────────────────────────────
nnunet_service = nnUNetSegmentationService()

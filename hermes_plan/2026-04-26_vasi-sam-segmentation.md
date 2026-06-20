# SubSkin 白斑边缘智能识别 — SAM 分割集成任务清单

> 目标: 用 SAM 像素级分割替换 VLM 假轮廓，实现真正的白斑边缘自动识别
> 效果: 拍照后自动圈出白斑真实边缘，不再依赖默认圆形
> 执行者: OpenCode CLI agent
> 工作目录: /root/subskin

---

## 问题诊断

```
当前流程:
  拍照 → VLM看图描述 → "估计"轮廓坐标 → 前端显示假轮廓
                                            ↑
                                    完全不贴合真实白斑边缘

目标流程:
  拍照 → 颜色预过滤(定位白斑) → SAM精细分割 → 轮廓提取 → 前端显示真实边缘
                                                              ↑
                                                      贴合物边缘的虚线
```

## 技术选型

| 方案 | 精度 | 速度 | 部署难度 | 需要训练 |
|------|------|------|---------|---------|
| VLM 描述(当前) | 假轮廓 | 1-3s | 0 | 否 |
| 传统CV | 中等 | 50ms | 轻 | 否 |
| **SAM 自动分割** ✅ | **高(像素级)** | **15-30s CPU** | **中** | **否** |

选择 SAM 的理由:
- 零训练数据需求（最大的优势）
- 真正像素级分割，边缘精确
- 开源，权重直接下载（ViT-B: 375MB）
- 已有 Python API
- 输出可直接转为现有 contour 格式

---

## 架构: 分离关注点

```
                    ┌─────────────────────────────┐
                    │     vasi.py: assess_vasi()   │
                    │                             │
  照片 ──────────► │ ┌─────────────────────────┐ │
                    │ │ vasi_segmentation.py    │ │  ← 新文件: SAM分割
                    │ │ (像素级白斑边缘识别)     │ │
                    │ │ → 返回真实contours       │ │
                    │ └─────────────────────────┘ │
                    │                             │
                    │ ┌─────────────────────────┐ │
                    │ │ _call_vision_model()    │ │  ← 保留: VLM只做判断
                    │ │ (分类/分期/描述)         │ │
                    │ │ → 返回vasi_score/       │ │
                    │ │   stage/classification   │ │
                    │ └─────────────────────────┘ │
                    └─────────────────────────────┘
```

VLM 不再负责轮廓，只做它擅长的事:
- "这是白斑还是正常皮肤?"
- "进展期还是稳定期?"
- "节段型还是非节段型?"

SAM 负责它擅长的事:
- 像素级精确提取白斑区域
- 输出贴合真实边缘的 polygon 轮廓

---

## 任务清单 (共 9 个任务)

### 🔵 Task 1: 安装 SAM 依赖

**命令** (在 SubSkin 服务器执行):

```bash
# 激活当前 Python 环境
cd /root/subskin

# 安装 segment-anything
pip install segment-anything

# 下载 SAM ViT-B 权重 (最小的模型，CPU也能跑)
mkdir -p /root/subskin/models
wget -O /root/subskin/models/sam_vit_b_01ec64.pth \
  https://dl.fbaipublicfiles.com/segment_anything/sam_vit_b_01ec64.pth

# 验证
python -c "from segment_anything import sam_model_registry; print('SAM OK')"
python -c "import torch; print(f'Torch {torch.__version__}')"
ls -lh /root/subskin/models/sam_vit_b_01ec64.pth
```

**预期**: 权重文件 ~375MB，torch > 1.7

---

### 🔵 Task 2: 创建白斑分割服务

**文件**: `/root/subskin/web/backend/services/vasi_segmentation.py` (新建)

```python
"""
白斑像素级分割服务
基于 SAM (Segment Anything Model) 自动模式
"""

import logging
import io
import json
import math
from typing import List, Dict, Any, Optional, Tuple

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# ── SAM 延迟加载 ──
_sam_predictor = None
SAM_AVAILABLE = False


def _get_sam_predictor():
    """懒加载 SAM 模型（避免启动时占用内存）"""
    global _sam_predictor, SAM_AVAILABLE
    if _sam_predictor is not None:
        return _sam_predictor
    
    try:
        import torch
        from segment_anything import sam_model_registry, SamAutomaticMaskGenerator
        
        model_path = "/root/subskin/models/sam_vit_b_01ec64.pth"
        device = "cuda" if torch.cuda.is_available() else "cpu"
        
        logger.info(f"Loading SAM ViT-B on {device}...")
        sam = sam_model_registry["vit_b"](checkpoint=model_path)
        sam.to(device=device)
        
        mask_generator = SamAutomaticMaskGenerator(
            model=sam,
            points_per_side=32,          # 网格密度 (越高越精细但越慢)
            pred_iou_thresh=0.88,         # 质量阈值
            stability_score_thresh=0.92,  # 稳定性阈值
            min_mask_region_area=100,     # 最小区域(像素)，过滤噪点
            crop_n_layers=1,
            crop_n_points_downscale_factor=2,
        )
        
        _sam_predictor = mask_generator
        SAM_AVAILABLE = True
        logger.info("SAM loaded successfully")
        return _sam_predictor
        
    except Exception as e:
        logger.error(f"SAM loading failed: {e}")
        SAM_AVAILABLE = False
        return None


# ── 颜色空间白斑过滤 ──

def _is_white_patch_mask(
    image_np: np.ndarray,
    mask: np.ndarray,
    brightness_threshold: float = 180,
    saturation_threshold: float = 60,
    min_white_ratio: float = 0.3,
) -> bool:
    """
    判断 SAM 生成的 mask 是否为白斑区域。
    
    策略: 在 LAB 颜色空间中检查 mask 内像素:
    - L 通道均值高 (白斑更亮)
    - 不是皮肤色 (低饱和度)
    - white_ratio > min_white_ratio
    """
    if not mask.any():
        return False
    
    # 提取 mask 内的像素
    masked_pixels = image_np[mask]
    if len(masked_pixels) == 0:
        return False
    
    # RGB → LAB
    try:
        import cv2
        lab = cv2.cvtColor(masked_pixels.reshape(-1, 1, 3).astype(np.uint8), cv2.COLOR_RGB2LAB)
        L = lab[:, :, 0].flatten()
        A = lab[:, :, 1].flatten()
        B = lab[:, :, 2].flatten()
    except ImportError:
        # fallback: 简易亮度检测
        brightness = masked_pixels.mean(axis=1)  # mean of R,G,B
        L = brightness
        A = np.zeros_like(brightness)
        B = np.zeros_like(brightness)
    
    # 白斑特征: 高亮度 + 低色度
    bright_pixels = (L > brightness_threshold).sum()
    total_pixels = len(L)
    white_ratio = bright_pixels / max(total_pixels, 1)
    
    # 色度检测 (白斑通常低饱和度)
    chroma = np.sqrt(A.astype(float)**2 + B.astype(float)**2)
    low_chroma_ratio = (chroma < saturation_threshold).sum() / max(total_pixels, 1)
    
    return white_ratio > min_white_ratio and low_chroma_ratio > 0.5


def _merge_overlapping_masks(masks: List[np.ndarray], iou_threshold: float = 0.3) -> List[np.ndarray]:
    """合并重叠的白斑 mask"""
    if len(masks) <= 1:
        return masks
    
    merged = []
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
    max_points: int = 30,
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
        
        mask_uint8 = (mask * 255).astype(np.uint8)
        contours, _ = cv2.findContours(mask_uint8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return None
        
        # 取最大轮廓
        largest = max(contours, key=cv2.contourArea)
        
        # 简化
        epsilon = epsilon_factor * cv2.arcLength(largest, True)
        approx = cv2.approxPolyDP(largest, epsilon, True)
        
        # 归一化
        h, w = mask.shape
        points = []
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
    max_points: int = 30,
) -> Optional[List[List[float]]]:
    """纯 Python 的 mask 轮廓提取（不依赖 opencv）"""
    h, w = mask.shape
    
    # 找边界像素
    from scipy import ndimage
    try:
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
        points = []
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
    
    points = []
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
) -> Dict[str, Any]:
    """
    主入口: 对照片进行白斑分割。
    
    Args:
        image_bytes: JPEG/PNG 图片二进制数据
        min_patch_area_ratio: 最小白斑面积占比
        max_patches: 最大返回的白斑区域数
    
    Returns:
        {
            "success": bool,
            "contours": [{label, polygon, area_percent}, ...],
            "total_area_percent": float,   # 白斑总面积占图片面积百分比
            "source": "sam" | "fallback",
            "error": str | null
        }
    """
    result = {
        "success": False,
        "contours": [],
        "total_area_percent": 0.0,
        "source": "fallback",
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
    mask_generator = _get_sam_predictor()
    
    if mask_generator is None:
        logger.warning("SAM unavailable, using CV fallback")
        return _fallback_segmentation(img_np, min_patch_area_ratio, max_patches)
    
    try:
        logger.info(f"Running SAM auto-segmentation on {w}x{h} image...")
        masks = mask_generator.generate(img_np)
        logger.info(f"SAM generated {len(masks)} candidate masks")
        
        # Step 3: 筛选白斑 mask
        white_patch_masks = []
        for m in masks:
            mask_array = m["segmentation"]
            if _is_white_patch_mask(img_np, mask_array):
                white_patch_masks.append(mask_array)
        
        logger.info(f"Filtered {len(white_patch_masks)} white patch masks")
        
        if not white_patch_masks:
            # SAM 跑完了但没找到白斑 → 可能是正常皮肤照片
            result["source"] = "sam"
            result["error"] = "No white patches detected by SAM"
            return result
        
        # Step 4: 合并重叠区域
        merged_masks = _merge_overlapping_masks(white_patch_masks)
        logger.info(f"Merged into {len(merged_masks)} patches")
        
        # Step 5: 提取轮廓
        contours = []
        total_area = 0
        
        for i, mask in enumerate(merged_masks[:max_patches]):
            area_pixels = mask.sum()
            area_percent = (area_pixels / total_pixels) * 100
            
            if area_percent < min_patch_area_ratio * 100:
                continue
            
            polygon = _mask_to_polygon(mask)
            if polygon is None:
                continue
            
            contours.append({
                "label": f"白斑{i + 1}",
                "polygon": polygon,
                "area_percent": round(area_percent, 1),
            })
            total_area += area_percent
        
        if not contours:
            result["source"] = "sam"
            result["error"] = "White patches too small after filtering"
            return result
        
        result["success"] = True
        result["contours"] = contours
        result["total_area_percent"] = round(min(total_area, 100), 1)
        result["source"] = "sam"
        return result
        
    except Exception as e:
        logger.error(f"SAM segmentation error: {e}", exc_info=True)
        return _fallback_segmentation(img_np, min_patch_area_ratio, max_patches)


def _fallback_segmentation(
    img_np: np.ndarray,
    min_patch_area_ratio: float,
    max_patches: int,
) -> Dict[str, Any]:
    """SAM 不可用时的 CV 回退方案"""
    h, w = img_np.shape[:2]
    total_pixels = h * w
    
    result = {
        "success": False,
        "contours": [],
        "total_area_percent": 0.0,
        "source": "fallback",
        "error": None,
    }
    
    try:
        import cv2
        
        # LAB 空间: L通道亮度阈值
        lab = cv2.cvtColor(img_np, cv2.COLOR_RGB2LAB)
        L = lab[:, :, 0]
        
        # 白斑: 高亮度区域
        _, thresh = cv2.threshold(L, 200, 255, cv2.THRESH_BINARY)
        
        # 形态学清理
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        cleaned = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, kernel)
        
        # 找轮廓
        contours_cv, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        patches = []
        for cnt in contours_cv:
            area = cv2.contourArea(cnt)
            area_percent = (area / total_pixels) * 100
            
            if area_percent < min_patch_area_ratio * 100:
                continue
            
            epsilon = 0.005 * cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, epsilon, True)
            
            points = []
            for pt in approx:
                x, y = pt[0]
                points.append([round(float(x) / w, 3), round(float(y) / h, 3)])
            
            patches.append({
                "label": f"白斑{len(patches) + 1}",
                "polygon": points[:30],
                "area_percent": round(area_percent, 1),
            })
        
        patches.sort(key=lambda p: p["area_percent"], reverse=True)
        patches = patches[:max_patches]
        
        if patches:
            result["success"] = True
            result["contours"] = patches
            result["total_area_percent"] = round(sum(p["area_percent"] for p in patches), 1)
        else:
            result["error"] = "No white patches found (CV fallback)"
        
        return result
        
    except Exception as e:
        result["error"] = f"Fallback segmentation failed: {e}"
        return result
```

**关键设计点**:
- SAM 懒加载: 只在第一次调用时加载模型，不阻塞服务启动
- 双重回退: SAM 不可用 → CV 亮度阈值 → 返回原始默认轮廓
- `_is_white_patch_mask()`: SAM 生成很多 mask，只保留"高亮度+低色度"的白斑区域
- `_merge_overlapping_masks()`: SAM 可能把一个大白斑切碎，合并回来
- `_mask_to_polygon()`: 从像素 mask 提取简化 polygon (Douglas-Peucker算法)
- Python 3.9 兼容: 全用 `List`/`Optional`/`Dict`

---

### 🔵 Task 3: 集成到 VASI 评估流程

**文件**: `/root/subskin/web/backend/services/vasi.py` (修改)

**修改点**: `_call_vasi_api()` 方法

```python
# 在 vasi.py 顶部新增 import
from web.backend.services.vasi_segmentation import segment_vitiligo

# 修改 _call_vasi_api() 方法
async def _call_vasi_api(self, image_file: bytes) -> Dict[str, Any]:
    """调用视觉大模型进行 VASI 评估
    
    新流程:
    1. SAM 分割 → 获取真实白斑轮廓
    2. VLM 分类 → 获取分期/分型/描述
    3. 合并结果
    """
    # Step 1: SAM 分割获取轮廓
    seg_result = await asyncio.to_thread(segment_vitiligo, image_file)
    
    if seg_result["success"]:
        contours = seg_result["contours"]
        area_from_seg = seg_result["total_area_percent"]
        seg_source = seg_result["source"]
        logger.info(f"SAM segmentation: {len(contours)} patches, {area_from_seg:.1f}% area ({seg_source})")
    else:
        logger.warning(f"Segmentation failed: {seg_result.get('error')}, falling back")
        contours = []
        area_from_seg = None
        seg_source = "none"
    
    # Step 2: VLM 评估 (分类+分期+描述，不再要求轮廓)
    vlm_result = await self._call_vision_model(image_file)
    
    if vlm_result is not None:
        # 优先使用 SAM 的面积和轮廓
        if area_from_seg is not None:
            vlm_result["area_percentage"] = area_from_seg
            vlm_result["contours"] = contours
            vlm_result["details"]["segmentation_source"] = seg_source
            vlm_result["source"] = f"sam-{seg_source}"
        else:
            # SAM 失败，使用 VLM 结果 (降级)
            vlm_result["source"] = "vlm-fallback"
        
        return vlm_result
    
    # Step 3: VLM 也失败了 → 用 SAM 结果构造完整的 mock 返回
    if contours:
        # 有 SAM 轮廓但没有 VLM → 估算 VASI
        estimated_vasi = min(area_from_seg * 2.5, 100)  # 粗估 VASI
        return {
            "vasi_score": round(estimated_vasi, 1),
            "area_percentage": round(area_from_seg, 1),
            "classification": "未确定",
            "stage": "稳定",
            "contours": contours,
            "details": {
                "description": f"AI识别到{len(contours)}处白斑区域，面积占比{area_from_seg:.1f}%。请手动调整轮廓以修正评估。",
                "confidence": 0.6,
                "detected_areas": len(contours),
                "segmentation_source": seg_source,
            },
            "raw_response": {"sam_result": seg_result},
            "source": f"sam-only-{seg_source}",
        }
    
    # 完全失败 → mock
    logger.warning("Both SAM and VLM unavailable, returning mock data")
    # ... 保留原有的 mock 逻辑
```

**关键变化**:
- VLM 不再负责轮廓 → VLM prompt 需同步简化 (Task 4)
- SAM 结果优先 → VLM 结果作为补充
- 面积计算来自 SAM 像素级统计，不再是 VLM "估计"
- 保留完整降级链: SAM+VLM → SAM only → VLM only → mock

---

### 🔵 Task 4: 简化 VLM Prompt（去除轮廓要求）

**文件**: `/root/subskin/web/backend/services/vasi.py` (修改 `_call_vision_model` 中的 prompt)

**修改**: 将 prompt 从要求 VLM 返回 contours 改为只做分类判断

```python
prompt = """你是一位专业的皮肤科AI助手，正在分析白癜风患者的皮肤照片。

请仔细观察照片，然后按以下JSON格式返回评估结果（只返回JSON，不要其他文字）：

{
  "vasi_score": 0-100,
  "area_percentage_estimate": 0-100,
  "classification": "节段型|非节段型|未确定",
  "stage": "进展期|稳定期|好转期",
  "body_site_confirmed": "面部|颈部|手部|躯干|上肢|下肢|足部|其他",
  "confidence": 0.0-1.0,
  "details": {
    "patch_count_estimate": 1,
    "color_type": "纯白|乳白|灰白|淡白",
    "border_clarity": "清晰|模糊|部分清晰",
    "description": "50字以内的白斑特征描述"
  }
}

注意:
1. 如果照片不是皮肤照片，返回 {"error": "无法识别皮肤图像"}
2. VASI评分要保守估计，宁低勿高
3. area_percentage_estimate 是粗略估计（精确面积将由计算机视觉算法计算）
4. 只返回JSON，不要其他文字
"""
```

**对应解析代码修改**:
```python
# 将 vlm 返回的 area_percentage_estimate 与 SAM 的精确面积合并
# 如果 SAM 成功，使用 SAM 的面积；否则使用 VLM 的估计
area_percentage = seg_area if seg_area is not None else float(parsed.get("area_percentage_estimate", 0))
```

---

### 🔵 Task 5: 增加图片尺寸限制

**文件**: `/root/subskin/web/backend/services/vasi_preprocess.py` (新建或扩展)

SAM 对大图很慢。增加预处理步骤:

```python
def resize_for_sam(image_bytes: bytes, max_size: int = 1024) -> bytes:
    """SAM处理前缩放到合适大小"""
    img = Image.open(io.BytesIO(image_bytes))
    
    # 等比缩放
    w, h = img.size
    if max(w, h) > max_size:
        ratio = max_size / max(w, h)
        new_size = (int(w * ratio), int(h * ratio))
        img = img.resize(new_size, Image.LANCZOS)
    
    # 同时确保最小尺寸
    if min(img.size) < 256:
        ratio = 256 / min(img.size)
        new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
        img = img.resize(new_size, Image.LANCZOS)
    
    output = io.BytesIO()
    img.save(output, format='JPEG', quality=90)
    return output.getvalue()
```

在 `vasi.py::assess_vasi()` 中，传递给 SAM 前先缩放。

---

### 🔵 Task 6: 更新轮廓坐标精度

**文件**: `/root/subskin/web/backend/services/vasi.py` (已有的 contour 验证逻辑)

当前 `_call_vision_model()` 末尾有 contour 验证代码 (line 547-587)。SAM 返回的是真实 polygon，验证逻辑需要调整:

```python
# SAM 返回的 contours 已经是精确的 → 降低验证严格度
# max_points 从 20 放宽到 40 (SAM 的边缘更复杂)
# 保留点清洗逻辑但不要过度简化
```

---

### 🔵 Task 7: 前端优化 — 轮廓加载状态

**文件**: `/root/subskin/web/app/src/views/TrackerPage.vue` (微调)

SAM 推理需要 15-30秒，前端需要更好的等待体验:

```vue
<!-- 在 isUploading 状态下显示进度提示 -->
<div v-if="isUploading" class="text-center py-4">
  <div class="animate-spin w-8 h-8 border-3 border-primary-500 border-t-transparent rounded-full mx-auto mb-3"></div>
  <p class="text-sm text-gray-500">
    {{ uploadStage === 'uploading' ? '📤 上传照片中...' : 
       uploadStage === 'segmenting' ? '🔍 AI正在识别白斑边缘...' : 
       uploadStage === 'analyzing' ? '🧠 AI正在分析白斑特征...' : 
       '⏳ 处理中...' }}
  </p>
  <p class="text-xs text-gray-400 mt-1">大照片可能需要15-30秒，请耐心等待</p>
</div>
```

**新增状态变量**:
```typescript
const uploadStage = ref<'uploading' | 'segmenting' | 'analyzing' | ''>('')
```

---

### 🔵 Task 8: 后端服务验证

```bash
# 1. 确认 SAM 可以加载
cd /root/subskin
python -c "
from web.backend.services.vasi_segmentation import _get_sam_predictor
p = _get_sam_predictor()
print('SAM loaded:', p is not None)
"

# 2. 重启服务
sudo systemctl restart subskin-backend

# 3. 检查日志 (SAM 懒加载，第一次评估时才会加载)
sudo journalctl -u subskin-backend --no-pager -n 20

# 4. 用测试照片调用
curl -X POST http://localhost:8000/api/vasi/assess \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "image=@test_vitiligo.jpg" \
  -F "body_site=face" | python -m json.tool

# 5. 检查返回的 contours 是否贴合照片中的白斑边缘
# (在浏览器中访问 SubSkin，上传测试照片查看效果)
```

---

### 🔵 Task 9: 前端构建与端到端验证

```bash
cd /root/subskin/web/app
npm run build
sudo cp -r dist/* /var/www/subskin/
sudo systemctl reload nginx
```

**验证清单**:
- [ ] 上传照片后，等待15-30秒
- [ ] 白斑边缘被虚线自动圈出，贴合真实白斑边界
- [ ] 可以拖拽控制点微调轮廓
- [ ] 面积显示与实际白斑占比匹配
- [ ] SAM 不可用时自动降级到 VLM / mock，不会崩溃
- [ ] 上传非皮肤照片不会报错

---

## 文件变更总览

| 操作 | 文件 | 说明 |
|------|------|------|
| 新建 | `web/backend/services/vasi_segmentation.py` | SAM 分割核心逻辑 |
| 新建 | `web/backend/services/vasi_preprocess.py` | 图片缩放预处理 |
| 修改 | `web/backend/services/vasi.py` | 集成 SAM + 简化 VLM prompt |
| 修改 | `web/app/src/views/TrackerPage.vue` | 加载状态提示 |
| 新建 | `models/sam_vit_b_01ec64.pth` | SAM 权重 (375MB) |

---

## 技术风险与缓解

| 风险 | 等级 | 缓解 |
|------|------|------|
| SAM CPU推理慢(15-30s) | 🟡 | 缩放图片到1024px + 异步处理 |
| SAM 权重 375MB | 🟢 | 服务器存储足够 |
| SAM 对白斑zero-shot精度不够 | 🟡 | 颜色预过滤 + 用户手动微调兜底 |
| 内存消耗 (SAM ~1.5GB) | 🟡 | 懒加载，只在评估时加载 |
| opencv 不可用 | 🟢 | 双重 fallback (scipy → 纯Python) |
| Python 3.9 + torch 兼容 | 🟢 | SAM 要求 torch>=1.7，3.9 没问题 |

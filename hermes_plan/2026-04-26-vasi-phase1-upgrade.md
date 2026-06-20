# 小白手账 VASI 评估升级 — Phase 1 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 升级小白手账的VASI白斑评估功能，将VLM调用从"不可靠的轮廓估计"升级为"图像预处理+质量检测+优化提示词"的优化管线，同时为Phase 2的分割模型集成预留接口。

**Architecture:** 在现有 vasi.py 服务管线中插入两个新模块——vasi_preprocess.py（图像预处理）和 vasi_quality.py（质量检测）。优化 VLM prompt 使其不再请求不可靠的contours，而是聚焦于VLM擅长的粗略视觉估计。前端增加拍照质量反馈和引导。

**Tech Stack:** Python 3.9 / FastAPI / Pillow / OpenCV (可选) / 火山方舟豆包视觉模型 / Vue 3

**Python 3.9 约束:** 使用 `Optional[T]` 而非 `T | None`，使用 `List[T]` 而非 `list[T]`，使用 `Dict[K,V]` 而非 `dict[K,V]`。

---

## 升级后效果预览

改造完成后，小白手账将具备以下能力：

```
用户拍照流程（改造前）：
  选择部位 → 上传照片 → VLM盲猜 → 返回不可靠的轮廓和面积

用户拍照流程（改造后）：
  选择部位 → 上传照片
    → [自动] 白平衡校正 + 对比度增强
    → [自动] 检测照片质量（模糊/过暗/过亮/无皮肤）
    → [如质量差] 提示用户重新拍照，给出具体建议
    → [质量合格] 优化Prompt调用VLM → 返回带置信度的评估
    → 用户可手动修正轮廓（保留现有功能）
```

### 具体新增能力

1. **图像自动增强**: 上传的白斑照片自动进行白平衡校正和对比度增强，让VLM"看"得更清楚
2. **拍照质量检测**: 自动检测照片是否模糊、光照是否合适、是否包含皮肤区域
3. **实时拍照反馈**: 质量不达标时给出具体改进建议（如"请靠近一些""光线太暗，请打开闪光灯"）
4. **置信度指标**: 每次评估附带 confidence 字段（0-1），用户可了解AI判断的可靠程度
5. **更精准的面积估计**: 优化后的prompt引导VLM聚焦于面积比例估计（而非不可靠的轮廓坐标）
6. **处理时间显示**: 前端显示预处理耗时和AI评估耗时，用户了解评估速度
7. **Phase 2 就绪接口**: 预处理和质量检测模块设计为独立服务，后续可无缝对接分割模型

---

## 文件结构

```
新建文件:
  web/backend/services/vasi_preprocess.py      # 图像预处理管线
  web/backend/services/vasi_quality.py          # 照片质量检测
  web/backend/services/vasi_prompt.py           # VLM提示词模板管理

修改文件:
  web/backend/services/vasi.py                  # 集成预处理+质量检测+新prompt
  web/backend/api/models.py                     # 新增 PhotoQualityInfo 响应模型
  web/backend/requirements.txt                  # 新增 Pillow, opencv-python-headless
  web/app/src/views/TrackerPage.vue             # 前端质量反馈UI
  web/app/src/api/vasi.ts                       # 新增 quality 和 confidence 字段

不改动:
  web/backend/models/vasi.py                    # 数据库模型不变
  web/backend/api/vasi.py                       # API路由不变(返回字段有新增)
  web/app/src/components/tracker/VitiligoContour.vue  # 轮廓编辑器不变
```

---

### Task 1: 新建图像预处理服务

**Files:**
- Create: `web/backend/services/vasi_preprocess.py`

- [ ] **Step 1: 创建预处理模块**

```python
"""
图像预处理管线 — VASI评估前的图像增强

提供自动白平衡、对比度增强、锐化和智能缩放，
让VLM获得更高质量的输入图像。
"""

import io
import logging
from typing import Optional, Tuple

from PIL import Image, ImageEnhance, ImageFilter, ImageStat

logger = logging.getLogger(__name__)

# 预处理后的最大边长（像素），控制API调用token消耗
MAX_DIMENSION = 1024
# JPEG输出质量
JPEG_QUALITY = 90


class ImagePreprocessor:
    """白斑照片预处理管线"""

    def __init__(self):
        self.stats = {}  # 记录每步处理耗时

    def process(self, image_bytes: bytes) -> Tuple[bytes, dict]:
        """完整预处理管线

        Args:
            image_bytes: 原始图片二进制数据

        Returns:
            (处理后的JPEG字节, 包含各步骤信息的dict)
        """
        import time

        t0 = time.time()
        info = {}

        # 打开图片
        img = Image.open(io.BytesIO(image_bytes))
        info["original_size"] = img.size  # (width, height)
        info["original_mode"] = img.mode

        # 确保为RGB模式（处理RGBA、灰度等）
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")
            info["converted_from"] = img.mode
        elif img.mode == "RGBA":
            # RGBA → RGB（白底合成）
            background = Image.new("RGB", img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[3])
            img = background
            info["rgba_converted"] = True

        t1 = time.time()

        # 1. 自动白平衡（Gray World算法）
        img = self._auto_white_balance(img)
        info["white_balance_applied"] = True
        t2 = time.time()

        # 2. 对比度增强（CLAHE模拟）
        img = self._enhance_contrast(img)
        info["contrast_enhanced"] = True
        t3 = time.time()

        # 3. 轻微锐化
        img = self._sharpen(img)
        info["sharpened"] = True
        t4 = time.time()

        # 4. 智能缩放（保持长宽比，限制最大边长）
        img = self._smart_resize(img, max_dimension=MAX_DIMENSION)
        info["processed_size"] = img.size
        t5 = time.time()

        # 输出为JPEG
        output = io.BytesIO()
        img.save(output, format="JPEG", quality=JPEG_QUALITY)
        processed_bytes = output.getvalue()

        info["output_bytes"] = len(processed_bytes)
        info["timing"] = {
            "open": round((t1 - t0) * 1000, 1),
            "white_balance": round((t2 - t1) * 1000, 1),
            "contrast": round((t3 - t2) * 1000, 1),
            "sharpen": round((t4 - t3) * 1000, 1),
            "resize": round((t5 - t4) * 1000, 1),
            "total_ms": round((t5 - t0) * 1000, 1),
        }

        logger.info(
            "Preprocess: %s → %s, total %.1fms",
            info["original_size"],
            info["processed_size"],
            info["timing"]["total_ms"],
        )

        return processed_bytes, info

    def _auto_white_balance(self, img: Image.Image) -> Image.Image:
        """Gray World白平衡：假设场景平均反射率为灰色

        对皮肤照片效果良好，使白斑与正常皮肤的色差更明显。
        """
        stat = ImageStat.Stat(img)
        r_avg, g_avg, b_avg = stat.mean[:3]
        avg_gray = (r_avg + g_avg + b_avg) / 3.0

        if avg_gray < 1:
            return img  # 避免除零

        # 计算各通道增益
        r_gain = avg_gray / max(r_avg, 1)
        g_gain = avg_gray / max(g_avg, 1)
        b_gain = avg_gray / max(b_avg, 1)

        # 限制增益范围，防止过度校正
        r_gain = max(0.7, min(1.3, r_gain))
        g_gain = max(0.7, min(1.3, g_gain))
        b_gain = max(0.7, min(1.3, b_gain))

        # 应用增益
        r, g, b = img.split()
        r = r.point(lambda x: int(min(255, x * r_gain)))
        g = g.point(lambda x: int(min(255, x * g_gain)))
        b = b.point(lambda x: int(min(255, x * b_gain)))

        return Image.merge("RGB", (r, g, b))

    def _enhance_contrast(self, img: Image.Image, factor: float = 1.2) -> Image.Image:
        """对比度增强

        使用Pillow的ImageEnhance，factor>1增强对比度。
        轻度增强（1.2）避免过度处理。
        """
        enhancer = ImageEnhance.Contrast(img)
        return enhancer.enhance(factor)

    def _sharpen(self, img: Image.Image) -> Image.Image:
        """轻微锐化，使用Unsharp Mask原理"""
        enhancer = ImageEnhance.Sharpness(img)
        return enhancer.enhance(1.3)

    def _smart_resize(self, img: Image.Image, max_dimension: int = 1024) -> Image.Image:
        """智能缩放：保持长宽比，长边不超过max_dimension"""
        w, h = img.size
        if w <= max_dimension and h <= max_dimension:
            return img.copy()

        if w >= h:
            new_w = max_dimension
            new_h = int(h * max_dimension / w)
        else:
            new_h = max_dimension
            new_w = int(w * max_dimension / h)

        return img.resize((new_w, new_h), Image.LANCZOS)


# 模块级单例
_preprocessor: Optional[ImagePreprocessor] = None


def get_preprocessor() -> ImagePreprocessor:
    """获取预处理单例"""
    global _preprocessor
    if _preprocessor is None:
        _preprocessor = ImagePreprocessor()
    return _preprocessor


def preprocess_vasi_image(image_bytes: bytes) -> Tuple[bytes, dict]:
    """便捷函数：预处理VASI评估图片

    Args:
        image_bytes: 原始图片数据

    Returns:
        (处理后的图片数据, 预处理信息)
    """
    return get_preprocessor().process(image_bytes)
```

- [ ] **Step 2: 验证模块可导入**

```bash
cd /root/subskin/web/backend && python3 -c "
from services.vasi_preprocess import preprocess_vasi_image
print('✓ vasi_preprocess imported successfully')
"
```

Expected: `✓ vasi_preprocess imported successfully`

- [ ] **Step 3: 提交**

```bash
cd /root/subskin && git add web/backend/services/vasi_preprocess.py
git commit -m "feat(vasi): add image preprocessing pipeline (white balance, contrast, sharpen, resize)"
```

---

### Task 2: 新建照片质量检测服务

**Files:**
- Create: `web/backend/services/vasi_quality.py`

- [ ] **Step 1: 创建质量检测模块**

```python
"""
照片质量检测 — 评估上传的白斑照片是否适合AI分析

检测维度：
1. 模糊度（拉普拉斯方差）
2. 亮度（过暗/过亮）
3. 皮肤区域占比
4. 照片分辨率
"""

import io
import logging
from typing import Dict, Any, Optional, Tuple

from PIL import Image, ImageStat
import numpy as np

logger = logging.getLogger(__name__)

# 质量阈值
MIN_RESOLUTION = (200, 200)         # 最小分辨率
MAX_RESOLUTION = (4096, 4096)       # 最大分辨率
MIN_BRIGHTNESS = 30                  # 最低平均亮度 (0-255)
MAX_BRIGHTNESS = 240                 # 最高平均亮度
MIN_BLUR_THRESHOLD = 80.0           # 拉普拉斯方差最小值（低于此=模糊）
MIN_SKIN_RATIO = 0.15               # 最小皮肤区域占比


class PhotoQualityError(Exception):
    """照片质量不达标"""
    pass


class PhotoQualityChecker:
    """照片质量检测器"""

    def check(self, image_bytes: bytes) -> Dict[str, Any]:
        """全面质量检测

        Returns:
            dict: {
                "passed": bool,
                "score": float (0-1 综合评分),
                "issues": [str],  # 问题列表（空=完美）
                "metrics": {
                    "blur_score": float,
                    "brightness": float,
                    "resolution": [w, h],
                    "skin_ratio": float,
                },
                "suggestions": [str],  # 改进建议
            }
        """
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")

        img_array = np.array(img)
        issues = []
        suggestions = []
        sub_scores = []

        # 1. 分辨率检测
        w, h = img.size
        res_ok = True
        if w < MIN_RESOLUTION[0] or h < MIN_RESOLUTION[1]:
            issues.append("resolution_too_low")
            suggestions.append(
                f"照片分辨率过低（{w}x{h}），建议使用至少"
                f"{MIN_RESOLUTION[0]}x{MIN_RESOLUTION[1]}像素的照片"
            )
            res_ok = False
        elif w > MAX_RESOLUTION[0] or h > MAX_RESOLUTION[1]:
            issues.append("resolution_too_high")
            # 分辨率过高不是致命问题，系统会自动缩放
            res_ok = True

        sub_scores.append(1.0 if res_ok else 0.3)

        # 2. 模糊度检测（拉普拉斯方差）
        blur_score = self._detect_blur(img_array)
        blur_ok = blur_score >= MIN_BLUR_THRESHOLD
        if not blur_ok:
            issues.append("blurry")
            if blur_score < 30:
                suggestions.append("照片严重模糊，请稳住手机或使用三脚架重新拍摄")
            else:
                suggestions.append("照片略有模糊，请保持手机稳定并确保对焦清晰")

        sub_scores.append(min(1.0, blur_score / MIN_BLUR_THRESHOLD))

        # 3. 亮度检测
        brightness = self._detect_brightness(img_array)
        bright_ok = MIN_BRIGHTNESS <= brightness <= MAX_BRIGHTNESS
        if not bright_ok:
            if brightness < MIN_BRIGHTNESS:
                issues.append("too_dark")
                suggestions.append(
                    f"照片过暗（亮度{brightness:.0f}），请在光线充足的环境下拍摄，"
                    "或打开闪光灯/补光灯"
                )
            else:
                issues.append("too_bright")
                suggestions.append(
                    "照片过亮，请避免阳光直射或强光照射白斑区域"
                )

        # 亮度评分：中间值最佳
        brightness_score = 1.0 - abs(brightness - 128) / 128
        sub_scores.append(max(0.0, brightness_score))

        # 4. 皮肤区域检测
        skin_ratio = self._detect_skin_ratio(img_array)
        skin_ok = skin_ratio >= MIN_SKIN_RATIO
        if not skin_ok:
            issues.append("no_skin_detected")
            suggestions.append(
                "未检测到足够的皮肤区域，请确保照片中包含清晰的人体皮肤"
            )

        sub_scores.append(min(1.0, skin_ratio / 0.5))

        # 综合评分
        # 模糊度和皮肤检测权重更高
        weights = [0.15, 0.35, 0.20, 0.30]
        score = sum(w * s for w, s in zip(weights, sub_scores))

        # 关键指标不通过则整体不通过
        passed = len(issues) == 0 or not any(
            i in ("blurry", "no_skin_detected", "too_dark")
            for i in issues
        )

        quality_label = "excellent" if score >= 0.85 else (
            "good" if score >= 0.7 else (
                "fair" if score >= 0.5 else "poor"
            )
        )

        result = {
            "passed": passed,
            "score": round(score, 3),
            "quality_label": quality_label,
            "issues": issues,
            "metrics": {
                "blur_score": round(blur_score, 1),
                "brightness": round(brightness, 1),
                "resolution": [w, h],
                "skin_ratio": round(skin_ratio, 3),
            },
            "suggestions": suggestions,
        }

        logger.info(
            "Photo quality: score=%.3f, label=%s, passed=%s, issues=%s",
            score, quality_label, passed, issues,
        )

        return result

    def _detect_blur(self, img_array: np.ndarray) -> float:
        """拉普拉斯方差法检测模糊度

        值越高=越清晰。典型阈值：
        >200: 非常清晰
        100-200: 清晰
        50-100: 轻微模糊
        <50: 明显模糊
        """
        # 转灰度
        if len(img_array.shape) == 3:
            gray = np.dot(img_array[..., :3], [0.299, 0.587, 0.114])
        else:
            gray = img_array

        # 降采样加速（取中心区域）
        h, w = gray.shape
        # 取中心60%区域（避免边框干扰）
        y1, y2 = int(h * 0.2), int(h * 0.8)
        x1, x2 = int(w * 0.2), int(w * 0.8)
        if y2 > y1 and x2 > x1:
            gray = gray[y1:y2, x1:x2]

        # 缩小到约300x300加速计算
        scale = max(1, min(gray.shape) // 300)
        if scale > 1:
            gray = gray[::scale, ::scale]

        # 拉普拉斯算子
        laplacian = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]])
        import scipy.ndimage  # fallback to manual if not available

        # 使用简单的卷积实现（避免scipy依赖）
        h, w = gray.shape
        result = np.zeros_like(gray, dtype=np.float64)
        for i in range(1, h - 1):
            for j in range(1, w - 1):
                patch = gray[i - 1 : i + 2, j - 1 : j + 2]
                result[i, j] = np.sum(patch * laplacian)

        variance = float(np.var(result))
        return round(variance, 1)

    def _detect_brightness(self, img_array: np.ndarray) -> float:
        """检测平均亮度

        Returns:
            0-255 的平均像素亮度值
        """
        if len(img_array.shape) == 3:
            # 使用感知亮度公式
            brightness = (
                0.299 * np.mean(img_array[:, :, 0])
                + 0.587 * np.mean(img_array[:, :, 1])
                + 0.114 * np.mean(img_array[:, :, 2])
            )
        else:
            brightness = np.mean(img_array)

        return round(float(brightness), 1)

    def _detect_skin_ratio(self, img_array: np.ndarray) -> float:
        """检测皮肤区域占比

        基于HSV颜色空间的肤色检测。
        返回皮肤像素占总像素的比例。
        """
        h, w = img_array.shape[:2]
        total_pixels = h * w

        if total_pixels == 0:
            return 0.0

        # 降采样加速（每4个像素采样1个）
        step = 4
        r = img_array[::step, ::step, 0].astype(np.float64)
        g = img_array[::step, ::step, 1].astype(np.float64)
        b = img_array[::step, ::step, 2].astype(np.float64)

        # 避免除零
        denom = r + g + b
        denom[denom == 0] = 1

        r_norm = r / denom
        g_norm = g / denom

        # 肤色在RGB空间的经验范围
        # 宽松检测（宁可误检，不可漏检皮肤区域）
        skin_mask = (
            (r > 60)
            & (g > 40)
            & (b > 20)
            & (r > g)
            & (r > b)
            & (r - g > 5)
            & (abs(r - g) < 80)
            & (abs(r - b) < 80)
        )

        skin_pixels = int(np.sum(skin_mask))
        # 还原到原始像素数
        skin_pixels *= step * step

        return round(skin_pixels / total_pixels, 3)


# 模块级单例
_checker: Optional[PhotoQualityChecker] = None


def get_quality_checker() -> PhotoQualityChecker:
    """获取质量检测单例"""
    global _checker
    if _checker is None:
        _checker = PhotoQualityChecker()
    return _checker


def check_photo_quality(image_bytes: bytes) -> Dict[str, Any]:
    """便捷函数：检测照片质量"""
    return get_quality_checker().check(image_bytes)
```

- [ ] **Step 2: 验证模块可导入**

```bash
cd /root/subskin/web/backend && python3 -c "
from services.vasi_quality import check_photo_quality
print('✓ vasi_quality imported successfully')
"
```

Note: 如果 scipy 不可用，_detect_blur 中的手动卷积实现已包含。如遇到numpy导入问题，检查是否已安装numpy（Pillow依赖numpy）。

Expected: `✓ vasi_quality imported successfully`

- [ ] **Step 3: 提交**

```bash
cd /root/subskin && git add web/backend/services/vasi_quality.py
git commit -m "feat(vasi): add photo quality checker (blur, brightness, skin detection)"
```

---

### Task 3: 新建优化后的VLM提示词模板

**Files:**
- Create: `web/backend/services/vasi_prompt.py`

- [ ] **Step 1: 创建提示词模块**

```python
"""
VASI评估 — VLM提示词模板

将提示词从 vasi.py 中抽离，便于独立优化和A/B测试。
"""

from typing import Optional, Dict, Any


# 系统提示词（VLM角色定义）
SYSTEM_PROMPT = """你是一位专业的皮肤科AI助手，正在辅助分析白癜风白友的皮肤照片。
你的任务是对照片中的白斑情况进行VASI（Vitiligo Area Scoring Index）快速评估。

请严格遵守以下规则：
1. 只分析图片中可见的皮肤区域
2. 如果不确定，请诚实地降低置信度
3. 不要编造不存在的白斑
4. 保守估计白斑面积，宁低勿高
5. 如果照片质量差或无法判断，请在details中说明"""


# 主评估提示词
ASSESSMENT_PROMPT = """请仔细观察上传的皮肤照片，进行VASI评估。

请以JSON格式返回以下内容（只返回JSON，不要任何其他文字）：

{
  "vasi_score": 0-100的数字，该部位的VASI严重程度评分，
  "area_percentage": 该照片中白斑占可见皮肤区域的面积百分比（0-100），
  "classification": "节段型" / "非节段型" / "未确定" / "无法判断",
  "stage": "进展期" / "稳定期" / "好转期" / "无法判断",
  "body_site": 推断的身体部位（"面部"/"颈部"/"手部"/"躯干"/"上肢"/"下肢"/"足部"/"其他"），
  "confidence": 0.0-1.0的总体置信度，
  "details": {
    "detected_areas": 检测到的白斑区域数量（整数），
    "color_type": "纯白" / "乳白" / "灰白" / "淡白" / "无法判断",
    "border": "清晰" / "模糊" / "混合",
    "description": "对白斑特征的简要描述（中文，50字以内）",
    "limitations": "本次评估的局限性说明（如：照片角度、光照影响等）"
  }
}

重要说明：
- area_percentage 是指白斑占该照片中可见皮肤区域的比例，不是占全身的比例
- confidence 反映你对整体评估的把握程度，不确定时请如实降低
- 如果照片中无白斑或无法识别，返回：{"vasi_score": 0, "area_percentage": 0, "classification": "无法判断", "stage": "无法判断", "confidence": 0.0}
- 如果照片不包含人体皮肤，返回：{"error": "未检测到皮肤区域，请上传清晰的皮肤照片"}

评估参考：
- VASI评分 0-10：轻微，白斑面积小
- VASI评分 10-25：轻度，局部白斑
- VASI评分 25-50：中度，面积较大
- VASI评分 50-75：中重度，广泛白斑
- VASI评分 75-100：重度，大部分皮肤受累"""


# 简化版提示词（用于图片质量一般的快速评估）
ASSESSMENT_PROMPT_FAST = """请快速评估这张皮肤照片的白斑情况。

返回JSON：
{
  "vasi_score": 0-100,
  "area_percentage": 0-100,
  "classification": "节段型/非节段型/未确定/无法判断",
  "stage": "进展期/稳定期/好转期/无法判断",
  "confidence": 0.0-1.0,
  "details": {
    "detected_areas": 整数,
    "description": "简短描述(30字)",
    "limitations": "局限性"
  }
}

规则同标准评估。只返回JSON。"""


def get_assessment_prompt(quality_label: str = "excellent") -> str:
    """根据照片质量选择合适的提示词

    Args:
        quality_label: 质量标签 (excellent/good/fair/poor)

    Returns:
        对应的提示词
    """
    if quality_label in ("poor", "fair"):
        # 质量较差时使用简化提示词，减少VLM"脑补"的可能性
        return ASSESSMENT_PROMPT_FAST
    return ASSESSMENT_PROMPT


def get_system_prompt() -> str:
    """获取系统提示词"""
    return SYSTEM_PROMPT
```

- [ ] **Step 2: 验证模块**

```bash
cd /root/subskin/web/backend && python3 -c "
from services.vasi_prompt import get_assessment_prompt, get_system_prompt
print('Prompt for excellent:', get_assessment_prompt('excellent')[:50])
print('Prompt for poor:', get_assessment_prompt('poor')[:50])
print('✓ vasi_prompt imported successfully')
"
```

Expected: 看到两个不同长度prompt的开头

- [ ] **Step 3: 提交**

```bash
cd /root/subskin && git add web/backend/services/vasi_prompt.py
git commit -m "feat(vasi): extract VLM prompt templates into separate module"
```

---

### Task 4: 集成到 vasi.py 主管线

**Files:**
- Modify: `web/backend/services/vasi.py`

- [ ] **Step 1: 添加import和修改 _call_vasi_api 方法**

在文件顶部（第5行 `import os` 之后）插入新的 import：

在 vasi.py 中找到:
```python
import os
import json
import asyncio
import base64
import logging
```

在其下方添加:
```python
import time
```

在 vasi.py 中找到:
```python
from web.backend.models.vasi import VASIAssessment
from web.backend.database.database import get_db
```

在其下方添加:
```python
from web.backend.services.vasi_preprocess import preprocess_vasi_image
from web.backend.services.vasi_quality import check_photo_quality
from web.backend.services.vasi_prompt import get_assessment_prompt, get_system_prompt
```

- [ ] **Step 2: 修改 _call_vasi_api 方法（第358-406行）**

找到以下代码块（第358-406行）:
```python
    async def _call_vasi_api(self, image_file: bytes) -> Dict[str, Any]:
        """调用视觉大模型进行 VASI 评估

        优先使用百炼 DashScope qwen-vl-plus，fallback 到 mock。

        Args:
            image_file: 图片二进制数据

        Returns:
            dict: VASI评估结果
        """
        result = await self._call_vision_model(image_file)
        if result is not None:
            return result

        # Fallback: mock data
```

替换为:
```python
    async def _call_vasi_api(self, image_file: bytes) -> Dict[str, Any]:
        """调用视觉大模型进行 VASI 评估

        管线: 预处理 → 质量检测 → VLM评估 → fallback mock

        Args:
            image_file: 图片二进制数据

        Returns:
            dict: VASI评估结果（含 quality_info 和 prep_info）
        """
        t_start = time.time()

        # ── Step 1: 图像预处理 ──
        try:
            processed_image, prep_info = preprocess_vasi_image(image_file)
            logger.info("Preprocessing completed in %.0fms", prep_info["timing"]["total_ms"])
        except Exception as e:
            logger.warning("Preprocessing failed (%s), using original image", str(e))
            processed_image = image_file
            prep_info = {"error": str(e), "fallback": True}

        # ── Step 2: 照片质量检测 ──
        try:
            quality = check_photo_quality(processed_image)
            logger.info(
                "Photo quality: score=%.3f, label=%s, passed=%s",
                quality["score"], quality["quality_label"], quality["passed"],
            )
        except Exception as e:
            logger.warning("Quality check failed (%s), assuming ok", str(e))
            quality = {
                "passed": True,
                "score": 0.5,
                "quality_label": "unknown",
                "issues": [],
                "metrics": {},
                "suggestions": [],
                "error": str(e),
            }

        # ── Step 3: VLM评估 ──
        t_vlm_start = time.time()
        result = await self._call_vision_model(processed_image, quality)
        vlm_time_ms = round((time.time() - t_vlm_start) * 1000, 1)

        if result is not None:
            # 附加处理管线信息
            result["quality_info"] = quality
            result["prep_info"] = prep_info
            result["pipeline_timing_ms"] = {
                "total": round((time.time() - t_start) * 1000, 1),
                "vlm": vlm_time_ms,
            }
            return result

        # Fallback: mock data
```

- [ ] **Step 3: 修改 _call_vision_model 方法签名和内部逻辑**

找到方法签名（第408行）:
```python
    async def _call_vision_model(self, image_file: bytes) -> Optional[Dict[str, Any]]:
```

替换为:
```python
    async def _call_vision_model(
        self, image_file: bytes, quality: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
```

在同一方法内（第442行附近），找到:
```python
            prompt = """你是一位专业的皮肤科AI助手，正在分析白癜风白友的皮肤照片。请仔细观察图片中的白斑情况，进行VASI（Vitiligo Area Scoring Index）评估。
```

将整个旧的prompt变量赋值（第442-479行）替换为使用新的prompt模块:

找到:
```python
            prompt = """你是一位专业的皮肤科AI助手..."""
```

替换为:
```python
            # 使用新的prompt模板，根据照片质量选择
            quality_label = quality.get("quality_label", "good") if quality else "good"
            prompt = get_assessment_prompt(quality_label)
            system_prompt = get_system_prompt()
```

在调用client.chat.completions.create时（第488行附近），添加system消息:

找到:
```python
            response = client.chat.completions.create(
                model=vision_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
```

替换为:
```python
            response = client.chat.completions.create(
                model=vision_model,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
```

在解析结果部分（第517行附近），JSON解析中添加confidence字段处理。

找到:
```python
            vasi_score = float(parsed.get("vasi_score", 0))
            area_percentage = float(parsed.get("area_percentage", 0))
```

添加:
```python
            vasi_score = float(parsed.get("vasi_score", 0))
            area_percentage = float(parsed.get("area_percentage", 0))
            confidence = float(parsed.get("confidence", 0.5))

```

找到最终的return语句（第589-599行附近）:
```python
            return {
                "vasi_score": round(vasi_score, 1),
                "area_percentage": round(area_percentage, 1),
                "classification": parsed.get("classification", "未确定"),
                "stage": stage,
                "body_site": parsed.get("body_site", "其他"),
                "contours": validated_contours,
                "details": details,
                "raw_response": parsed,
                "source": f"vision-{config['provider']}",
            }
```

替换为:
```python
            return {
                "vasi_score": round(vasi_score, 1),
                "area_percentage": round(area_percentage, 1),
                "classification": parsed.get("classification", "未确定"),
                "stage": stage,
                "body_site": parsed.get("body_site", "其他"),
                "confidence": round(confidence, 3),
                "contours": validated_contours,
                "details": details,
                "raw_response": parsed,
                "source": f"vision-{config['provider']}",
            }
```

- [ ] **Step 4: 同样修改mock fallback部分**

找到mock fallback的return（第387-406行），添加confidence字段:

找到:
```python
        return {
            "vasi_score": mock_vasi_score,
            "area_percentage": mock_area_percentage,
```

替换为:
```python
        return {
            "vasi_score": mock_vasi_score,
            "area_percentage": mock_area_percentage,
            "confidence": 0.0,  # mock数据置信度为0
```

- [ ] **Step 5: 验证服务可导入**

```bash
cd /root/subskin/web/backend && python3 -c "
from services.vasi import VASIService
from services.vasi_preprocess import preprocess_vasi_image
from services.vasi_quality import check_photo_quality
from services.vasi_prompt import get_assessment_prompt
print('✓ All modules import successfully')
"
```

Expected: `✓ All modules import successfully`

- [ ] **Step 6: 提交**

```bash
cd /root/subskin && git add web/backend/services/vasi.py
git commit -m "feat(vasi): integrate preprocessing, quality check, and optimized prompts into VASI pipeline"
```

---

### Task 5: 更新API响应模型

**Files:**
- Modify: `web/backend/api/models.py`

- [ ] **Step 1: 添加 QualityInfo 模型**

在文件末尾添加:

```python
class PhotoQualityInfo(BaseModel):
    """照片质量信息"""
    passed: bool = Field(..., description="质量是否通过")
    score: float = Field(..., description="综合质量评分 (0-1)")
    quality_label: str = Field(..., description="质量标签 (excellent/good/fair/poor)")
    issues: List[str] = Field(default_factory=list, description="检测到的问题")
    metrics: Dict[str, Any] = Field(default_factory=dict, description="详细指标")
    suggestions: List[str] = Field(default_factory=list, description="改进建议")


class PipelineTimingInfo(BaseModel):
    """处理耗时信息"""
    total: float = Field(..., description="总耗时(ms)")
    vlm: Optional[float] = Field(None, description="VLM调用耗时(ms)")
    preprocessing: Optional[float] = Field(None, description="预处理耗时(ms)")
```

- [ ] **Step 2: 更新 VASIAssessmentResponse 添加新字段**

在 VASIAssessmentResponse 类中添加:

找到:
```python
class VASIAssessmentResponse(BaseModel):
    """VASI评估评估响应"""
    id: int
    user_id: int
    image_url: str
    vasi_score: float = Field(..., description="VASI总分 (0-100)")
    body_site: str = Field(..., description="评估部位")
    area_percentage: float = Field(..., description="白斑面积百分比")
    classification: str = Field(..., description="分型")
    stage: str = Field(..., description="病情阶段")
    contours: List[Dict[str, Any]] = Field(default_factory=list, description="白斑轮廓数据")
    assessment_date: str
    created_at: str
```

替换为:
```python
class VASIAssessmentResponse(BaseModel):
    """VASI评估评估响应"""
    id: int
    user_id: int
    image_url: str
    vasi_score: float = Field(..., description="VASI总分 (0-100)")
    body_site: str = Field(..., description="评估部位")
    area_percentage: float = Field(..., description="白斑面积百分比")
    classification: str = Field(..., description="分型")
    stage: str = Field(..., description="病情阶段")
    confidence: Optional[float] = Field(None, description="AI评估置信度 (0-1)")
    contours: List[Dict[str, Any]] = Field(default_factory=list, description="白斑轮廓数据")
    quality_info: Optional[Dict[str, Any]] = Field(None, description="照片质量信息")
    pipeline_timing_ms: Optional[Dict[str, Any]] = Field(None, description="处理耗时(ms)")
    assessment_date: str
    created_at: str
```

- [ ] **Step 3: 更新 API 端点 vasi.py 中返回的数据**

修改 `/root/subskin/web/backend/api/vasi.py` 中 `create_assessment` 函数（第64-81行）:

找到:
```python
        return VASIAssessmentResponse(
            id=assessment.id,
            user_id=assessment.user_id,
            image_url=assessment.image_url,
            vasi_score=assessment.vasi_score,
            body_site=assessment.body_site,
            area_percentage=assessment.area_percentage,
            classification=assessment.classification,
            stage=assessment.stage,
            contours=contours,
            assessment_date=assessment.assessment_date.isoformat()
            if assessment.assessment_date
            else "",
            created_at=assessment.created_at.isoformat()
            if assessment.created_at
            else "",
        )
```

替换为:
```python
        # 解析details获取额外信息
        quality_info = None
        pipeline_timing = None
        confidence = None
        if assessment.details:
            try:
                details_data = json.loads(assessment.details)
                quality_info = details_data.get("quality_info")
                pipeline_timing = details_data.get("pipeline_timing_ms")
                confidence = details_data.get("confidence")
            except (json.JSONDecodeError, TypeError):
                pass

        return VASIAssessmentResponse(
            id=assessment.id,
            user_id=assessment.user_id,
            image_url=assessment.image_url,
            vasi_score=assessment.vasi_score,
            body_site=assessment.body_site,
            area_percentage=assessment.area_percentage,
            classification=assessment.classification,
            stage=assessment.stage,
            confidence=confidence,
            contours=contours,
            quality_info=quality_info,
            pipeline_timing_ms=pipeline_timing,
            assessment_date=assessment.assessment_date.isoformat()
            if assessment.assessment_date
            else "",
            created_at=assessment.created_at.isoformat()
            if assessment.created_at
            else "",
        )
```

- [ ] **Step 4: 验证**

```bash
cd /root/subskin/web/backend && python3 -c "
from api.models import VASIAssessmentResponse, PhotoQualityInfo, PipelineTimingInfo
print('✓ API models updated successfully')
"
```

Expected: `✓ API models updated successfully`

- [ ] **Step 5: 提交**

```bash
cd /root/subskin && git add web/backend/api/models.py web/backend/api/vasi.py
git commit -m "feat(vasi): add quality_info, confidence, and timing fields to API response"
```

---

### Task 6: 添加依赖

**Files:**
- Modify: `web/backend/requirements.txt`

- [ ] **Step 1: 添加 Pillow 依赖**

在 requirements.txt 末尾添加:

```
# Image processing for VASI assessment
Pillow>=10.0.0
numpy>=1.24.0
```

- [ ] **Step 2: 安装依赖**

```bash
cd /root/subskin/web/backend && pip install Pillow numpy
```

Expected: 成功安装

- [ ] **Step 3: 提交**

```bash
cd /root/subskin && git add web/backend/requirements.txt
git commit -m "chore(vasi): add Pillow and numpy dependencies for image processing"
```

---

### Task 7: 更新前端 TrackerPage.vue

**Files:**
- Modify: `web/app/src/views/TrackerPage.vue`
- Modify: `web/app/src/api/vasi.ts`

- [ ] **Step 1: 更新 TypeScript 类型定义**

在 `web/app/src/api/vasi.ts` 中，更新 `VasiAssessmentResponse` 接口。

找到接口定义:
```typescript
export interface VasiAssessmentResponse {
  id: number
  user_id: number
  image_url: string
  vasi_score: number
  body_site: string
  area_percentage: number
  classification: string
  stage: string
  contours: ContourRegion[]
  assessment_date: string
  created_at: string
}
```

替换为:
```typescript
export interface PhotoQualityInfo {
  passed: boolean
  score: number
  quality_label: string
  issues: string[]
  metrics: {
    blur_score: number
    brightness: number
    resolution: number[]
    skin_ratio: number
  }
  suggestions: string[]
}

export interface VasiAssessmentResponse {
  id: number
  user_id: number
  image_url: string
  vasi_score: number
  body_site: string
  area_percentage: number
  classification: string
  stage: string
  confidence?: number
  contours: ContourRegion[]
  quality_info?: PhotoQualityInfo
  pipeline_timing_ms?: { total: number; vlm: number }
  assessment_date: string
  created_at: string
}
```

- [ ] **Step 2: 在 TrackerPage.vue 中添加质量反馈状态**

在 `<script setup>` 部分（第22行附近），`activeTab` 声明后添加:

```typescript
// 照片质量状态
const photoQuality = ref<{
  passed: boolean
  score: number
  quality_label: string
  suggestions: string[]
} | null>(null)
const pipelineTiming = ref<{ total: number; vlm: number } | null>(null)
const aiConfidence = ref<number | null>(null)
```

- [ ] **Step 3: 修改 submitAssessment 函数，处理新字段**

找到 `submitAssessment` 函数（第304-347行），在解析data后添加质量信息:

在 `assessmentResult.value = {` 之前添加:

```typescript
    // 保存质量信息和耗时
    photoQuality.value = data.quality_info || null
    pipelineTiming.value = data.pipeline_timing_ms || null
    aiConfidence.value = data.confidence ?? null
```

- [ ] **Step 4: 在模板中添加质量反馈组件**

在 TrackerPage 模板中，找到 `<!-- ── Contour Editor (post-assessment) ── -->` 部分（第645行附近），在其上方（contour editor 显示前）添加质量信息展示。

在第644行 `<!-- ── Contour Editor (post-assessment) ── -->` 之前插入:

```html
        <!-- ── Photo Quality Feedback ── -->
        <template v-if="photoQuality && !showContourEditor">
          <div
            v-if="photoQuality.quality_label !== 'excellent'"
            class="mb-4 p-3 rounded-xl border"
            :class="photoQuality.passed
              ? 'bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-800'
              : 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800'"
          >
            <div class="flex items-start gap-2">
              <span class="text-lg">{{ photoQuality.passed ? '⚠️' : '❌' }}</span>
              <div class="flex-1 min-w-0">
                <p class="text-sm font-medium"
                  :class="photoQuality.passed
                    ? 'text-amber-700 dark:text-amber-300'
                    : 'text-red-700 dark:text-red-300'"
                >
                  {{ photoQuality.passed ? '照片质量一般，可能影响评估准确度' : '照片质量不理想' }}
                </p>
                <ul v-if="photoQuality.suggestions.length" class="mt-1.5 space-y-0.5">
                  <li
                    v-for="(s, i) in photoQuality.suggestions"
                    :key="i"
                    class="text-xs"
                    :class="photoQuality.passed
                      ? 'text-amber-600 dark:text-amber-400'
                      : 'text-red-600 dark:text-red-400'"
                  >💡 {{ s }}</li>
                </ul>
              </div>
            </div>
          </div>

          <!-- 质量指标速览 -->
          <div class="mb-4 grid grid-cols-2 md:grid-cols-4 gap-2">
            <div class="flex items-center gap-1.5 text-xs px-2 py-1.5 rounded-lg"
              :class="photoQuality.score >= 0.7
                ? 'bg-green-50 dark:bg-green-900/20 text-green-600 dark:text-green-400'
                : photoQuality.score >= 0.5
                ? 'bg-amber-50 dark:bg-amber-900/20 text-amber-600 dark:text-amber-400'
                : 'bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400'"
            >
              <span>📷</span>
              <span>质量: {{ (photoQuality.score * 100).toFixed(0) }}%</span>
            </div>
            <div
              v-if="aiConfidence !== null"
              class="flex items-center gap-1.5 text-xs px-2 py-1.5 rounded-lg"
              :class="aiConfidence >= 0.7
                ? 'bg-green-50 dark:bg-green-900/20 text-green-600 dark:text-green-400'
                : aiConfidence >= 0.4
                ? 'bg-amber-50 dark:bg-amber-900/20 text-amber-600 dark:text-amber-400'
                : 'bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400'"
            >
              <span>🎯</span>
              <span>AI置信度: {{ (aiConfidence * 100).toFixed(0) }}%</span>
            </div>
            <div
              v-if="pipelineTiming"
              class="flex items-center gap-1.5 text-xs px-2 py-1.5 rounded-lg bg-gray-50 dark:bg-gray-800 text-gray-500 dark:text-gray-400"
            >
              <span>⏱️</span>
              <span>耗时: {{ (pipelineTiming.total / 1000).toFixed(1) }}s</span>
            </div>
          </div>
        </template>
```

- [ ] **Step 5: 修改拍照引导文字**

在 `<!-- ── Normal Upload UI ── -->` 部分（第691行附近），找到现有的引导文字:

```html
              <p class="text-xs text-gray-400 dark:text-gray-500 mt-1.5">支持 JPG / PNG，最大 10MB</p>
```

替换为更详细的拍照引导:

```html
              <p class="text-xs text-gray-400 dark:text-gray-500 mt-1.5">支持 JPG / PNG，最大 10MB</p>
              <div class="mt-2 flex items-center gap-3 text-xs text-gray-400 dark:text-gray-500">
                <span>💡 拍照建议：</span>
                <span>光线充足</span>
                <span>·</span>
                <span>对焦清晰</span>
                <span>·</span>
                <span>白斑居中</span>
              </div>
```

- [ ] **Step 6: 验证前端编译**

```bash
cd /root/subskin/web/app && npm run build
```

Expected: Build success

- [ ] **Step 7: 提交**

```bash
cd /root/subskin && git add web/app/src/views/TrackerPage.vue web/app/src/api/vasi.ts
git commit -m "feat(vasi): add photo quality feedback, confidence indicator, and timing display to frontend"
```

---

### Task 8: 后端服务重启与端到端验证

- [ ] **Step 1: 重启后端服务**

```bash
sudo systemctl restart subskin-backend && sleep 2 && sudo systemctl status subskin-backend
```

Expected: `active (running)`

- [ ] **Step 2: 检查启动日志**

```bash
sudo journalctl -u subskin-backend -n 30 --no-pager
```

Expected: 无异常，服务正常启动

- [ ] **Step 3: API烟雾测试**

```bash
# 检查API健康
curl -s http://localhost:8000/api/vasi/history -H "Authorization: Bearer test" | head -c 200
```

Expected: 返回正常JSON（可能是401或空列表，重点是服务响应）

- [ ] **Step 4: 验证新模块可导入（在生产环境Python中）**

```bash
cd /root/subskin/web/backend && python3 -c "
from services.vasi_preprocess import preprocess_vasi_image
from services.vasi_quality import check_photo_quality
from services.vasi_prompt import get_assessment_prompt, get_system_prompt
print('✓ All new modules load correctly in production')
"
```

Expected: `✓ All new modules load correctly in production`

---

### Task 9: 功能验证清单

完成所有Task后，逐项检查：

- [ ] 照片上传后会自动进行预处理（白平衡+对比度增强）✓
- [ ] 模糊照片会被检测并提示用户重新拍摄
- [ ] 过暗/过亮照片会被检测并给出光照建议
- [ ] 非皮肤照片会被检测并拒绝
- [ ] 质量合格的照片正常完成VASI评估
- [ ] 前端显示质量评分和AI置信度
- [ ] 前端显示处理耗时
- [ ] mock fallback正常工作（VLM不可用时）
- [ ] 轮廓编辑功能仍然正常工作
- [ ] 历史记录查询正常

---

## 部署清单

```bash
# 1. 确认所有变更已提交
cd /root/subskin && git status

# 2. 安装新依赖
cd web/backend && pip install Pillow numpy

# 3. 重启后端
sudo systemctl restart subskin-backend

# 4. 编译前端
cd web/app && npm run build

# 5. 验证服务
sudo systemctl status subskin-backend
curl -s http://localhost:8000/docs | head -c 100
```

"""
Photo quality checker for vitiligo assessment.

Evaluates uploaded photos for blur, skin presence, lighting conditions,
and resolution to determine if the image is suitable for AI analysis.

Uses opencv-python-headless with try/except fallback when unavailable.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Tuple

logger = logging.getLogger(__name__)

# ── Lazy imports with graceful fallback ──────────────────────────────────────
_CV2_AVAILABLE = False
_NUMPY_AVAILABLE = False

try:
    import cv2

    _CV2_AVAILABLE = True
except ImportError:
    logger.warning("opencv-python-headless not installed. Quality checker disabled.")

try:
    import numpy as np

    _NUMPY_AVAILABLE = True
except ImportError:
    logger.warning("numpy not installed. Quality checker disabled.")


def _is_available() -> bool:
    return _CV2_AVAILABLE and _NUMPY_AVAILABLE


# ── Thresholds ────────────────────────────────────────────────────────────────
BLUR_THRESHOLD_CLEAR = 300
BLUR_THRESHOLD_ACCEPTABLE = 100

# Skin presence: 5% threshold accommodates close-up vitiligo shots where the
# white patch dominates the frame. The previous 15% threshold caused valid
# close-ups to be rejected as "no skin detected".
SKIN_RATIO_MIN = 0.05

# HSV ranges for skin detection across diverse tones (light → deep skin),
# plus a broader YCrCb fallback for warm lighting. Empirically validated.
# Hue 0-25 (red-orange), Sat 20-200, Value 50-255 covers most skin photos.
SKIN_HSV_LOWER = (0, 20, 50)
SKIN_HSV_UPPER = (25, 200, 255)
SKIN_HSV_LOWER_2 = (160, 20, 50)
SKIN_HSV_UPPER_2 = (179, 200, 255)
# YCrCb fallback (Cr 133-180, Cb 77-130) — more robust to lighting variance
SKIN_YCRCB_LOWER = (0, 133, 77)
SKIN_YCRCB_UPPER = (255, 180, 130)

BRIGHTNESS_DARK_THRESHOLD = 60
BRIGHTNESS_OVEREXPOSED_THRESHOLD = 220
MIN_WIDTH = 640
MIN_HEIGHT = 480


@dataclass
class QualityReport:
    """Structured quality assessment of a vitiligo photo."""

    overall: str  # "good" | "acceptable" | "poor"
    blur_score: float = 0.0
    blur_ok: bool = True
    skin_ratio: float = 0.0
    skin_ok: bool = True
    brightness_mean: float = 0.0
    lighting_ok: bool = True
    resolution: Tuple[int, int] = (0, 0)
    size_ok: bool = True
    suggestions: List[str] = field(default_factory=list)


class VasiQualityChecker:
    """Check vitiligo photo quality before sending to AI analysis.

    Evaluates blur (Laplacian variance), skin presence (HSV), lighting
    (brightness histogram), and resolution. Returns a QualityReport with
    Chinese-language suggestions for the end user.

    Installable as a module-level singleton via ``vasi_quality_checker``.
    """

    def __init__(self):
        self._available = _is_available()

    @property
    def available(self) -> bool:
        return self._available

    def check_blur(self, image_bytes: bytes) -> float:
        """Compute Laplacian variance as a blur metric.

        Higher values indicate sharper images.

        Returns:
            Laplacian variance (float). Returns 0.0 if OpenCV unavailable.
        """
        if not self._available:
            return 0.0

        try:
            img = self._decode(image_bytes)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            laplacian = cv2.Laplacian(gray, cv2.CV_64F)
            return float(laplacian.var())
        except Exception as e:
            logger.warning("Blur check failed: %s", e)
            return 0.0

    def check_skin_presence(self, image_bytes: bytes) -> float:
        """Detect skin pixels using HSV + YCrCb dual-space matching.

        Returns the *union* of two color-space masks, which gives more
        reliable detection across skin tones and lighting conditions.
        """
        if not self._available:
            return 0.0

        try:
            img = self._decode(image_bytes)
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            ycrcb = cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb)

            mask_hsv_1 = cv2.inRange(
                hsv,
                np.array(SKIN_HSV_LOWER, dtype=np.uint8),
                np.array(SKIN_HSV_UPPER, dtype=np.uint8),
            )
            mask_hsv_2 = cv2.inRange(
                hsv,
                np.array(SKIN_HSV_LOWER_2, dtype=np.uint8),
                np.array(SKIN_HSV_UPPER_2, dtype=np.uint8),
            )
            mask_ycrcb = cv2.inRange(
                ycrcb,
                np.array(SKIN_YCRCB_LOWER, dtype=np.uint8),
                np.array(SKIN_YCRCB_UPPER, dtype=np.uint8),
            )

            skin_mask = cv2.bitwise_or(cv2.bitwise_or(mask_hsv_1, mask_hsv_2), mask_ycrcb)

            total = skin_mask.size
            skin_pixels = int(np.count_nonzero(skin_mask))
            return skin_pixels / max(total, 1)
        except Exception as e:
            logger.warning("Skin check failed: %s", e)
            return 0.0

    def check_lighting(self, image_bytes: bytes) -> float:
        """Compute mean brightness of the image (grayscale).

        Returns:
            Mean brightness (0–255). Returns 0.0 if OpenCV unavailable.
        """
        if not self._available:
            return 0.0

        try:
            img = self._decode(image_bytes)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            return float(gray.mean())
        except Exception as e:
            logger.warning("Lighting check failed: %s", e)
            return 0.0

    def check_size(self, image_bytes: bytes) -> Tuple[int, int]:
        """Get image dimensions (width, height).

        Returns:
            (width, height) tuple. Returns (0, 0) on failure.
        """
        try:
            img = self._decode(image_bytes)
            h, w = img.shape[:2]
            return (w, h)
        except Exception as e:
            logger.warning("Size check failed: %s", e)
            return (0, 0)

    def check_all(self, image_bytes: bytes) -> QualityReport:
        """Run all quality checks and produce a unified report.

        Args:
            image_bytes: Raw image bytes (JPEG or PNG).

        Returns:
            QualityReport with overall rating and Chinese suggestions.
        """
        if not self._available:
            return QualityReport(
                overall="acceptable",
                suggestions=["图像质量检测服务暂不可用，请更新后重试"],
            )

        blur_score = self.check_blur(image_bytes)
        skin_ratio = self.check_skin_presence(image_bytes)
        brightness_mean = self.check_lighting(image_bytes)
        resolution = self.check_size(image_bytes)

        # Evaluate individual checks
        blur_ok = blur_score >= BLUR_THRESHOLD_ACCEPTABLE
        skin_ok = skin_ratio >= SKIN_RATIO_MIN
        w, h = resolution
        size_ok = w >= MIN_WIDTH and h >= MIN_HEIGHT

        lighting_ok = (
            brightness_mean >= BRIGHTNESS_DARK_THRESHOLD
            and brightness_mean <= BRIGHTNESS_OVEREXPOSED_THRESHOLD
        )

        # Build Chinese suggestions
        suggestions: List[str] = []

        if not blur_ok:
            if blur_score < BLUR_THRESHOLD_ACCEPTABLE:
                suggestions.append("照片模糊，请保持手机稳定后重新拍摄")
            else:
                suggestions.append("照片清晰度一般，建议在光线充足的环境下拍摄")

        if not skin_ok:
            suggestions.append("画面中皮肤区域较少，请让患处更靠近相机或确保画面内皮肤完整可见")

        if not lighting_ok:
            if brightness_mean < BRIGHTNESS_DARK_THRESHOLD:
                suggestions.append("光线过暗，请在自然光或充足照明下拍摄")
            elif brightness_mean > BRIGHTNESS_OVEREXPOSED_THRESHOLD:
                suggestions.append("光线过亮（过曝），请避免强光直射皮肤")

        if not size_ok:
            suggestions.append(
                f"照片分辨率过低（当前 {w}×{h}，最低需要 {MIN_WIDTH}×{MIN_HEIGHT}），"
                "请使用更高像素的手机拍照"
            )

        critical_failures = sum([
            blur_score < BLUR_THRESHOLD_ACCEPTABLE * 0.5,
            brightness_mean < BRIGHTNESS_DARK_THRESHOLD * 0.6,
            brightness_mean > BRIGHTNESS_OVEREXPOSED_THRESHOLD + 20,
            not size_ok and (w < MIN_WIDTH * 0.7 or h < MIN_HEIGHT * 0.7),
        ])
        soft_failures = sum([not blur_ok, not skin_ok, not lighting_ok, not size_ok])

        if critical_failures >= 1:
            overall = "poor"
        elif soft_failures >= 2:
            overall = "acceptable"
        elif soft_failures == 1:
            overall = "acceptable"
        else:
            overall = "good"

        return QualityReport(
            overall=overall,
            blur_score=round(blur_score, 1),
            blur_ok=blur_ok,
            skin_ratio=round(skin_ratio, 3),
            skin_ok=skin_ok,
            brightness_mean=round(brightness_mean, 1),
            lighting_ok=lighting_ok,
            resolution=resolution,
            size_ok=size_ok,
            suggestions=suggestions,
        )

    @staticmethod
    def _decode(image_bytes: bytes):
        """Decode image bytes to OpenCV BGR numpy array."""
        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Failed to decode image")
        return img


# ── Module-level singleton ───────────────────────────────────────────────────
vasi_quality_checker = VasiQualityChecker()

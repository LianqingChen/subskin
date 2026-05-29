"""
Image preprocessing service for vitiligo assessment.

Provides white balance correction, contrast enhancement, sharpening,
and full preprocessing pipeline to prepare images for nnU-Net segmentation.

Uses PIL/Pillow + numpy with try/except for graceful fallback on missing deps.
"""

import io
import logging

logger = logging.getLogger(__name__)

# ── Lazy imports with graceful fallback ──────────────────────────────────────
_PIL_AVAILABLE = False
_NUMPY_AVAILABLE = False
_CV2_AVAILABLE = False

try:
    from PIL import Image, ImageEnhance, ImageFilter

    _PIL_AVAILABLE = True
except ImportError:
    logger.warning("Pillow not installed. Image preprocessing will be disabled.")

try:
    import numpy as np

    _NUMPY_AVAILABLE = True
except ImportError:
    logger.warning("numpy not installed. Image preprocessing will be disabled.")

try:
    import cv2

    _CV2_AVAILABLE = True
except ImportError:
    logger.info("opencv-python not installed. CLAHE will fall back to PIL contrast.")


def _is_available() -> bool:
    """Check if minimum dependencies for preprocessing are satisfied."""
    return _PIL_AVAILABLE and _NUMPY_AVAILABLE


class VasiImagePreprocessor:
    """Preprocess vitiligo images for optimal segmentation.

    Applies a pipeline of: auto white balance → contrast enhancement →
    sharpen → resize to max 1024px → JPEG output.

    All methods accept and return PIL Image objects. Installable as a
    module-level singleton via ``vasi_preprocessor``.
    """

    MAX_DIM = 1024

    def __init__(self):
        self._available = _is_available()

    @property
    def available(self) -> bool:
        """Whether the preprocessor can operate on images."""
        return self._available

    # ── Algorithm Methods ────────────────────────────────────────────────────

    def auto_white_balance(self, img: "Image.Image") -> "Image.Image":
        """Correct white balance using the Gray World algorithm.

        Assumes the average color of the scene is gray. Computes per-channel
        scaling factors to make the mean of each channel equal the overall
        mean luminance.

        Args:
            img: RGB PIL Image.

        Returns:
            White-balanced PIL Image. Returns original if numpy unavailable.
        """
        if not self._available:
            return img

        img_arr = np.array(img, dtype=np.float32)

        # Per-channel means
        r_mean = img_arr[:, :, 0].mean()
        g_mean = img_arr[:, :, 1].mean()
        b_mean = img_arr[:, :, 2].mean()

        # Gray world target: overall mean
        gray_world_target = (r_mean + g_mean + b_mean) / 3.0

        # Avoid division by zero on dark images
        eps = 1e-6
        r_scale = gray_world_target / (r_mean + eps)
        g_scale = gray_world_target / (g_mean + eps)
        b_scale = gray_world_target / (b_mean + eps)

        # Apply scaling, clip to valid range
        img_arr[:, :, 0] = np.clip(img_arr[:, :, 0] * r_scale, 0, 255)
        img_arr[:, :, 1] = np.clip(img_arr[:, :, 1] * g_scale, 0, 255)
        img_arr[:, :, 2] = np.clip(img_arr[:, :, 2] * b_scale, 0, 255)

        return Image.fromarray(img_arr.astype(np.uint8))

    def enhance_contrast(self, img: "Image.Image") -> "Image.Image":
        """Enhance image contrast.

        Prefers CLAHE (Contrast Limited Adaptive Histogram Equalization) via
        OpenCV when available. Falls back to PIL ImageEnhance with factor 1.5.

        Args:
            img: RGB PIL Image.

        Returns:
            Contrast-enhanced PIL Image.
        """
        if not self._available:
            return img

        if _CV2_AVAILABLE:
            # Convert PIL → OpenCV (BGR), apply CLAHE on L channel, convert back
            img_arr = np.array(img)
            lab = cv2.cvtColor(img_arr, cv2.COLOR_RGB2LAB)
            l_channel, a_channel, b_channel = cv2.split(lab)

            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            l_clahe = clahe.apply(l_channel)

            lab_merged = cv2.merge((l_clahe, a_channel, b_channel))
            result_arr = cv2.cvtColor(lab_merged, cv2.COLOR_LAB2RGB)
            return Image.fromarray(result_arr)
        else:
            # PIL fallback: moderate contrast boost
            enhancer = ImageEnhance.Contrast(img)
            return enhancer.enhance(1.5)

    def sharpen(self, img: "Image.Image") -> "Image.Image":
        """Sharpen image using Unsharp Mask technique.

        Creates a blurred copy, subtracts from original, adds high-frequency
        detail back. Corresponds to: sharpened = original + (original - blurred).

        Args:
            img: RGB PIL Image.

        Returns:
            Sharpened PIL Image.
        """
        if not self._available:
            return img

        result = img.filter(ImageFilter.UnsharpMask(radius=2, percent=200, threshold=0))
        return result

    def resize_max_dim(self, img: "Image.Image", max_dim: int = 1024) -> "Image.Image":
        """Resize image so its largest dimension ≤ max_dim, keeping aspect ratio.

        Only downscales; never upscales images smaller than max_dim.

        Args:
            img: PIL Image.
            max_dim: Maximum allowed dimension in pixels.

        Returns:
            Resized PIL Image (or original if already small enough).
        """
        if not self._available:
            return img

        w, h = img.size
        largest = max(w, h)

        if largest <= max_dim:
            return img

        ratio = max_dim / largest
        new_w = int(w * ratio)
        new_h = int(h * ratio)

        return img.resize((new_w, new_h), Image.LANCZOS)

    # ── Pipeline Methods ─────────────────────────────────────────────────────

    def preprocess(self, image_bytes: bytes) -> bytes:
        """Run full preprocessing pipeline on raw image bytes.

        Pipeline: auto white balance → CLAHE contrast → sharpen →
        resize max 1024px → JPEG output.

        If any step fails, falls back to just resizing the original image.
        If preprocessing is entirely unavailable, returns the original bytes.

        Args:
            image_bytes: Raw image bytes (JPEG or PNG).

        Returns:
            Preprocessed image as JPEG bytes.
        """
        if not self._available:
            logger.info("Preprocessing unavailable, returning original image bytes")
            return image_bytes

        try:
            # Load
            img = Image.open(io.BytesIO(image_bytes)).convert("RGB")

            # Pipeline
            img = self.auto_white_balance(img)
            img = self.enhance_contrast(img)
            img = self.sharpen(img)
            img = self.resize_max_dim(img, self.MAX_DIM)

            # Encode to JPEG bytes
            output = io.BytesIO()
            img.save(output, format="JPEG", quality=92, optimize=True)
            return output.getvalue()

        except Exception as e:
            logger.warning("Preprocessing failed, returning original: %s", e)
            return image_bytes

    def resize_for_sam(self, image_bytes: bytes, max_size: int = 1024) -> bytes:
        """Resize image specifically for SAM processing.

        SAM inference time scales with image size. This ensures the longest
        side is at most max_size pixels (default 1024) while keeping a
        minimum of 256px on the shortest side.

        Args:
            image_bytes: Raw image bytes.
            max_size: Maximum dimension in pixels.

        Returns:
            Resized JPEG bytes, or original bytes on failure.
        """
        if not self._available:
            return image_bytes

        try:
            img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            w, h = img.size

            if max(w, h) > max_size:
                ratio = max_size / max(w, h)
                new_size = (int(w * ratio), int(h * ratio))
                img = img.resize(new_size, Image.LANCZOS)

            if min(img.size) < 256:
                ratio = 256 / min(img.size)
                new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
                img = img.resize(new_size, Image.LANCZOS)

            output = io.BytesIO()
            img.save(output, format="JPEG", quality=90)
            return output.getvalue()

        except Exception as e:
            logger.warning("SAM resize failed, returning original: %s", e)
            return image_bytes


# ── Module-level singleton ───────────────────────────────────────────────────
vasi_preprocessor = VasiImagePreprocessor()

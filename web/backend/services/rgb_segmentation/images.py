"""Canonical RGB frame and strict binary masks; display overlays are separate."""

import hashlib
import io
from typing import Any, Dict, List, Tuple
import cv2
import numpy as np
from PIL import Image, ImageCms, ImageOps, UnidentifiedImageError
from web.backend.exceptions import RGBSegmentationError

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000
MAX_SIDE = 1024  # matches the existing journal editor's working canvas


def png_bytes(image: np.ndarray) -> bytes:
    stream = io.BytesIO()
    Image.fromarray(image).save(stream, format="PNG")
    return stream.getvalue()


def canonical_image(data: bytes, max_side: int = MAX_SIDE) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Canonical RGB frame. ``max_side`` lets callers (high-resolution vision
    localization) request a larger working grid while measurement stays at 1024."""
    if not data or len(data) > MAX_UPLOAD_BYTES:
        raise RGBSegmentationError("INVALID_IMAGE", "请选择10MB以内的照片")
    try:
        photo = Image.open(io.BytesIO(data))
        if photo.format not in ("JPEG", "PNG", "WEBP"):
            raise RGBSegmentationError("INVALID_IMAGE", "请选择JPG、PNG或WebP照片")
        width, height = photo.size
        if width * height > MAX_IMAGE_PIXELS or getattr(photo, "n_frames", 1) != 1:
            raise RGBSegmentationError(
                "INVALID_IMAGE", "照片分辨率过大或包含多帧，请换一张静态照片"
            )
        orientation = int(photo.getexif().get(274, 1))
        profile = photo.info.get("icc_profile")
        normalized = ImageOps.exif_transpose(photo)
        if normalized.mode in ("RGBA", "LA") or "transparency" in normalized.info:
            rgba = normalized.convert("RGBA")
            if rgba.getchannel("A").getextrema()[0] < 255:
                raise RGBSegmentationError(
                    "INVALID_IMAGE", "请选择没有透明区域的原始照片"
                )
        color_status = "assumed_srgb"
        if profile:
            try:
                normalized = ImageCms.profileToProfile(
                    normalized,
                    ImageCms.ImageCmsProfile(io.BytesIO(profile)),
                    ImageCms.createProfile("sRGB"),
                    outputMode="RGB",
                )
                color_status = "icc_to_srgb"
            except (ValueError, OSError, ImageCms.PyCMSError):
                raise RGBSegmentationError(
                    "INVALID_IMAGE", "照片颜色信息无法读取，请换一张原图"
                )
        normalized = normalized.convert("RGB")
        original_width, original_height = normalized.size
        normalized.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        rgb = np.asarray(normalized).copy()
        h, w = rgb.shape[:2]
        encoded = png_bytes(rgb)
        metadata = {
            "source_sha256": hashlib.sha256(data).hexdigest(),
            "sha256": hashlib.sha256(encoded).hexdigest(),
            "width": w,
            "height": h,
            "original_width": original_width,
            "original_height": original_height,
            "exif_orientation_applied": orientation,
            "coordinate_frame": "normalized_original",
            "working_grid": [w, h],
            "to_original": [
                [original_width / w, 0, 0],
                [0, original_height / h, 0],
                [0, 0, 1],
            ],
            "transform_id": f"exif-srgb-fit{max_side}-v1",
            "color_status": color_status,
            "coordinates": "pixel_centers_(x+0.5)/width_(y+0.5)/height",
        }
        return rgb, metadata
    except RGBSegmentationError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise RGBSegmentationError("INVALID_IMAGE", "照片无法读取，请重新选择原图")


def encode_mask(mask: np.ndarray) -> bytes:
    if mask.ndim != 2 or mask.dtype != np.bool_:
        raise RGBSegmentationError("ARTIFACT_INVALID", "标注数据格式无效")
    return png_bytes(mask.astype(np.uint8) * 255)


def decode_binary(data: bytes, shape: Tuple[int, int]) -> np.ndarray:
    try:
        photo = Image.open(io.BytesIO(data))
        if (
            photo.format != "PNG"
            or photo.mode != "L"
            or photo.size != (shape[1], shape[0])
        ):
            raise ValueError()
        array = np.asarray(photo)
        if not np.isin(array, [0, 255]).all():
            raise ValueError()
        return array == 255
    except (OSError, ValueError, Image.DecompressionBombError):
        raise RGBSegmentationError("ARTIFACT_INVALID", "标注与照片不匹配，请重新加载")


# Hard retake only when the visible skin has lost recoverable detail.
HARD_CLIPPED = 0.35
HARD_DARK = 0.65
HARD_BLUR = 4.0
SOFT_BLUR = 20.0
GLARE_VALUE = 250
SHADOW_MAX = 40
SHADOW_MIN = 12
RETAKE_MESSAGE = "照片过曝、过暗或严重模糊，请重拍"


def _gray(rgb: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)


def _interior(skin: np.ndarray) -> np.ndarray:
    eroded = cv2.erode(skin.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
    return eroded if eroded.any() else skin


def frame_information_lost(rgb: np.ndarray) -> bool:
    """Whole-frame loss only. Localized glare, shadow, and mild blur are not retakes."""
    if rgb.ndim != 3 or rgb.shape[2] != 3 or min(rgb.shape[:2]) < 8:
        return True
    gray = _gray(rgb)
    clipped = float((rgb.min(axis=2) >= GLARE_VALUE).mean())
    dark = float((gray < 8).mean())
    blur = float(cv2.Laplacian(gray, cv2.CV_32F).var())
    return clipped > 0.85 or dark > 0.92 or blur < 1.5


def local_quality(rgb: np.ndarray, skin: np.ndarray) -> Dict[str, Any]:
    """Heuristic evidence on the declared visible-skin scope, not diagnosis."""
    if skin.shape != rgb.shape[:2] or int(skin.sum()) < 64:
        return {
            "status": "unknown",
            "reasons": ["SKIN_UNVERIFIED"],
            "soft_issues": [],
        }
    gray = _gray(rgb)
    interior = _interior(skin)
    luminance = gray[interior]
    clipped = float((rgb[interior].min(axis=1) >= GLARE_VALUE).mean())
    dark = float((luminance < 15).mean())
    shadow = float(((luminance < SHADOW_MAX) & (luminance >= SHADOW_MIN)).mean())
    blur = float(cv2.Laplacian(gray, cv2.CV_32F)[interior].var())
    lost = clipped > HARD_CLIPPED or dark > HARD_DARK or blur < HARD_BLUR
    soft: List[str] = []
    if not lost:
        if clipped > 0.005:
            soft.append("GLARE")
        if shadow > 0.02:
            soft.append("SHADOW")
        if blur < SOFT_BLUR:
            soft.append("MILD_EDGE_BLUR")
    return {
        "status": "retake_required" if lost else "review_required" if soft else "usable",
        "clipped_fraction": round(clipped, 4),
        "dark_fraction": round(dark, 4),
        "shadow_fraction": round(shadow, 4),
        "blur_score": round(blur, 2),
        "soft_issues": soft,
        "reasons": ["QUALITY_INFORMATION_LOST"] if lost else soft,
    }


def apply_soft_quality(
    rgb: np.ndarray, masks: Dict[str, np.ndarray]
) -> Tuple[Dict[str, np.ndarray], Dict[str, Any]]:
    """Route shadow, glare, and mild edge blur into review. Do not fail the job."""
    quality = local_quality(rgb, masks["skin"])
    updated = {kind: mask.copy() for kind, mask in masks.items()}
    if quality["status"] != "review_required":
        return updated, quality
    skin = updated["skin"]
    gray = _gray(rgb)
    uncertain = updated["uncertain"]
    excluded = updated["excluded"]
    issues = quality["soft_issues"]
    if "GLARE" in issues:
        glare = (rgb.min(axis=2) >= GLARE_VALUE) & skin
        ring = cv2.dilate(glare.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
        uncertain = uncertain | (ring & skin & ~glare)
        excluded = excluded | glare
        skin = skin & ~glare
    if "SHADOW" in issues:
        uncertain = uncertain | ((gray < SHADOW_MAX) & (gray >= SHADOW_MIN) & skin)
    if "MILD_EDGE_BLUR" in issues:
        eroded = cv2.erode(skin.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
        uncertain = uncertain | (skin & ~eroded if eroded.any() else skin)
    updated["skin"] = skin
    updated["excluded"] = excluded & ~skin
    updated["uncertain"] = uncertain & skin
    updated["lesion"] = updated["lesion"] & skin & ~updated["uncertain"]
    quality = dict(quality, routing="uncertain_or_excluded_review")
    return updated, quality

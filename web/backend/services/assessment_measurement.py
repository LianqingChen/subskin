"""Versioned photographic measurements; no clinical diagnosis or BSA inference."""
import base64
import hashlib
import io
import json
import math
from typing import Any, Dict, Optional

import numpy as np
from PIL import Image, ImageOps

MEASUREMENT_VERSION = "photo-mask-v1"
COMPARISON_VERSION = "common-roi-v1"


def read_details(value: Optional[str]) -> Dict[str, Any]:
    try:
        parsed = json.loads(value or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except (ValueError, TypeError):
        return {}


def decode_mask(layer: Optional[str], shape=None) -> Optional[np.ndarray]:
    """Read alpha for overlays; luminance only for genuine grayscale masks."""
    if not layer:
        return None
    try:
        payload = layer.split(",", 1)[-1]
        img = Image.open(io.BytesIO(base64.b64decode(payload)))
        mask = img.getchannel("A") if "A" in img.getbands() else img.convert("L")
        if shape is not None and mask.size != (shape[1], shape[0]):
            mask = mask.resize((shape[1], shape[0]), Image.Resampling.NEAREST)
        return np.asarray(mask) > (32 if "A" in img.getbands() else 127)
    except (ValueError, OSError, IndexError):
        return None


def normalize_capture(image_bytes: bytes) -> bytes:
    """Apply EXIF orientation once; keep original bytes for private archival."""
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(image_bytes))).convert("RGB")
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def measure_layers(skin_layer: Optional[str], lesion_layer: Optional[str],
                   image_bytes: Optional[bytes] = None, calibration: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    skin = decode_mask(skin_layer)
    lesion = decode_mask(lesion_layer, skin.shape if skin is not None else None)
    result: Dict[str, Any] = {
        "version": MEASUREMENT_VERSION, "status": "unavailable",
        "scope": "visible_skin", "area_percentage": None,
        "area_cm2": None, "clinical_vasi": None, "clinical_vasi_valid": False,
        "color": None, "border": None, "reasons": [],
    }
    if skin is None or lesion is None or not skin.any():
        result["reasons"] = ["未得到可靠的皮肤与白斑范围，暂不能量化"]
        return result
    # A lesion cannot be used to silently expand the measurement denominator.
    outside = int((lesion & ~skin).sum())
    if outside > max(4, int(lesion.sum()) * 0.02):
        result["reasons"] = ["白斑范围超出皮肤范围，请核对标注"]
        return result
    lesion = lesion & skin
    touches_edge = bool(lesion[0].any() or lesion[-1].any() or lesion[:, 0].any() or lesion[:, -1].any())
    result.update({
        "status": "partial" if touches_edge else "measured",
        "area_percentage": round(float(lesion.sum() / skin.sum() * 100), 2),
        "lesion_pixels": int(lesion.sum()), "skin_pixels": int(skin.sum()),
        "touches_frame": touches_edge,
        "mask_revision": hashlib.sha256(lesion.tobytes() + skin.tobytes()).hexdigest()[:20],
    })
    if touches_edge:
        result["reasons"].append("白斑接近画面边缘，可能未拍全；占比仅代表照片可见范围")
    if not lesion.any():
        result["reasons"].append("本图未分割出明确白斑，不能据此排除皮肤疾病")
    if calibration and calibration.get("same_plane") is True and not touches_edge:
        points = calibration.get("points") or []
        length = calibration.get("length_mm")
        if (len(points) == 2 and all(isinstance(p, list) and len(p) == 2 and
                all(isinstance(v, (int, float)) and math.isfinite(v) and 0 <= v <= 1 for v in p) for p in points)
                and isinstance(length, (int, float)) and math.isfinite(length) and 1 <= length <= 1000):
            h, w = skin.shape
            distance = math.hypot((points[1][0] - points[0][0]) * w, (points[1][1] - points[0][1]) * h)
            if distance >= 20:
                result["area_cm2"] = round(float(lesion.sum()) * (length / distance) ** 2 / 100, 2)
                result["scale"] = {"pixels_per_mm": round(distance / length, 4), "source": "user_reference", "scope": "planar_projection"}
                result["reasons"].append("平方厘米为按所选参照物估算的二维投影面积，不代表曲面真实皮肤面积")
    if image_bytes and lesion.any():
        import cv2
        rgb = np.asarray(Image.open(io.BytesIO(image_bytes)).convert("RGB").resize(
            (skin.shape[1], skin.shape[0]), Image.Resampling.LANCZOS))
        lab = cv2.cvtColor(rgb.astype(np.float32) / 255, cv2.COLOR_RGB2LAB)
        ring = cv2.dilate(lesion.astype(np.uint8), np.ones((21, 21), np.uint8)).astype(bool) & skin & ~lesion
        if int(ring.sum()) >= 50:
            delta = np.median(lab[lesion], axis=0) - np.median(lab[ring], axis=0)
            result["color"] = {"relative_lightness": round(float(delta[0]), 1),
                               "delta_e76": round(float(np.linalg.norm(delta)), 1),
                               "scope": "within_photo", "calibrated": False}
        contours, _ = cv2.findContours(lesion.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        perimeter = sum(cv2.arcLength(c, True) for c in contours)
        result["border"] = {"perimeter_pixels": round(perimeter, 1),
                            "status": "partial" if touches_edge else "outlined"}
        yy, xx = np.where(lesion)
        result["extent"] = {"width_pixels": int(xx.max()-xx.min()+1), "height_pixels": int(yy.max()-yy.min()+1),
                            "mask_width": int(skin.shape[1]), "mask_height": int(skin.shape[0])}
    return result


def measurement_for(assessment) -> Dict[str, Any]:
    details = read_details(assessment.details)
    result = details.get("measurement") or {
        "version": "legacy", "status": "legacy", "scope": "unknown",
        "area_percentage": None, "clinical_vasi": None, "clinical_vasi_valid": False,
        "reasons": ["历史记录的测量口径不同，请勿直接比较分数"],
    }

    if details.get("annotation"):
        from web.backend.services.annotation_measurement_policy import guard_annotation_measurement
        result = guard_annotation_measurement(result, details["annotation"])
        result = dict(result, annotation=details["annotation"])
    return result


def context_for(assessment) -> Dict[str, Any]:
    return read_details(assessment.details).get("observation") or {}


def comparison_fingerprint(a: Dict[str, Any], b: Dict[str, Any]) -> str:
    keys = ("ref", "image_key", "date", "canvas_json", "skin_layer", "user_lesion_layer",
            "ai_lesion_layer", "observation", "measurement", "image_digest")
    payload = [[info.get(k) for k in keys] for info in (a, b)]
    return hashlib.sha256(json.dumps([COMPARISON_VERSION, "same-site-alignment-v2", payload], sort_keys=True,
                                     default=str).encode()).hexdigest()

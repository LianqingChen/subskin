"""Pretrained person parsing for the skin denominator.

Colour thresholds confuse beige walls, clothes and floors with skin. The
MediaPipe multiclass selfie segmenter separates face/body skin from hair,
clothes and background; the face landmarker removes eyes and brows. Both
models are local files (the worker has no network) and are checksum-pinned.
"""

import hashlib
import threading
from pathlib import Path
from typing import Any, Dict, Optional
import cv2
import numpy as np
from web.backend.services.rgb_segmentation.artifacts import PROJECT_ROOT

MODEL_DIR = PROJECT_ROOT / "data" / "models" / "mediapipe"
SEGMENTER = ("selfie_multiclass_256x256.tflite", "c6748b1253a99067ef71f7e26ca71096cd449baefa8f101900ea23016507e0e0")  # pragma: allowlist secret (model checksum)
LANDMARKER = ("face_landmarker.task", "64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff")  # pragma: allowlist secret (model checksum)
# selfie_multiclass categories
BACKGROUND, HAIR, BODY_SKIN, FACE_SKIN, CLOTHES, OTHERS = range(6)
MIN_SKIN_FRACTION = 0.01  # below this the parser did not recognise a person

_lock = threading.Lock()
_models: Dict[str, Any] = {}


def _verified(name: str, sha256: str) -> Optional[Path]:
    path = MODEL_DIR / name
    try:
        if hashlib.sha256(path.read_bytes()).hexdigest() != sha256:
            return None
    except OSError:
        return None
    return path


def _load(kind: str):
    if kind in _models:
        return _models[kind]
    model = None
    try:
        from mediapipe.tasks.python import BaseOptions, vision

        if kind == "segmenter":
            path = _verified(*SEGMENTER)
            if path:
                model = vision.ImageSegmenter.create_from_options(
                    vision.ImageSegmenterOptions(
                        base_options=BaseOptions(model_asset_path=str(path)),
                        output_confidence_masks=True,
                        output_category_mask=False,
                    )
                )
        else:
            path = _verified(*LANDMARKER)
            if path:
                model = vision.FaceLandmarker.create_from_options(
                    vision.FaceLandmarkerOptions(
                        base_options=BaseOptions(model_asset_path=str(path)),
                        num_faces=2,
                    )
                )
    except Exception:  # mediapipe missing or model rejected: caller falls back
        model = None
    _models[kind] = model
    return model


def _face_features(rgb: np.ndarray, image) -> Dict[str, np.ndarray]:
    """Eyes+brows (never skin) and lips (skin, but never auto-marked)."""
    h, w = rgb.shape[:2]
    eyes = np.zeros((h, w), np.uint8)
    lips = np.zeros((h, w), np.uint8)
    landmarker = _load("landmarker")
    faces = 0
    if landmarker is not None:
        from mediapipe.tasks.python.vision import FaceLandmarksConnections as FM

        result = landmarker.detect(image)
        faces = len(result.face_landmarks)
        groups = [
            (eyes, FM.FACE_LANDMARKS_LEFT_EYE),
            (eyes, FM.FACE_LANDMARKS_RIGHT_EYE),
            (eyes, FM.FACE_LANDMARKS_LEFT_EYEBROW),
            (eyes, FM.FACE_LANDMARKS_RIGHT_EYEBROW),
            (lips, FM.FACE_LANDMARKS_LIPS),
        ]
        for face in result.face_landmarks:
            points = np.array([[p.x * w, p.y * h] for p in face])
            for target, connections in groups:
                index = sorted({c.start for c in connections} | {c.end for c in connections})
                cv2.fillConvexPoly(target, cv2.convexHull(points[index].astype(np.int32)), 1)
    pad = np.ones((max(3, h // 110),) * 2, np.uint8)
    return {
        "eyes": cv2.dilate(eyes, pad).astype(bool),
        "lips": cv2.dilate(lips, pad).astype(bool),
        "faces": faces,
    }


def parse_skin(rgb: np.ndarray) -> Optional[Dict[str, Any]]:
    """Return skin/occluder masks, or None when the parser is unavailable or
    does not see a person (callers keep the legacy colour fallback)."""
    with _lock:
        segmenter = _load("segmenter")
        if segmenter is None:
            return None
        import mediapipe as mp

        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
        result = segmenter.segment(image)
        confidence = np.stack([m.numpy_view() for m in result.confidence_masks], -1)
        if confidence.shape[:2] != rgb.shape[:2]:
            confidence = cv2.resize(confidence, (rgb.shape[1], rgb.shape[0]))
        skin_p = confidence[..., BODY_SKIN] + confidence[..., FACE_SKIN]
        skin = skin_p > 0.5
        if skin.mean() < MIN_SKIN_FRACTION:
            return None
        features = _face_features(rgb, image)
    occluder = (confidence[..., OTHERS] > 0.5) | features["eyes"]  # glasses, eyes, brows
    skin &= ~occluder
    count, labels, stats, _ = cv2.connectedComponentsWithStats(skin.astype(np.uint8), 8)
    keep = np.zeros_like(skin)
    floor = max(64, int(skin.sum() * 0.002))
    for i in range(1, count):
        if stats[i, cv2.CC_STAT_AREA] >= floor:
            keep |= labels == i
    return {
        "skin": keep,
        "skin_probability": skin_p.astype(np.float32),
        "no_draft": features["lips"] & keep,
        "faces": features["faces"],
    }

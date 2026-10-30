"""Per-pixel features shared by training and inference of the general pixel model.

No (x, y) coordinates: the model must recognise skin/lesion from colour, local contrast and
person parsing, never from where things usually sit in the calibration photos.
"""

from typing import Dict, List, Tuple

import cv2
import numpy as np

from ml.pixel_labeling import core, system_io as sio

VERSION = "f3"
MP_CLASSES = ("mp_bg", "mp_hair", "mp_body", "mp_face", "mp_clothes", "mp_other")
NAMES: List[str] = [
    "L", "A", "B", "chroma", "hue", "L_rel", "A_rel", "B_rel",
    *MP_CLASSES, "mp_ok", "eye_brow", "lips",
    "sl", "sl40", "sg", "L5", "L15_minus_L",
    "Lc7", "Lc15", "Lc31", "Bc15", "L_std5", "grad",
    "proposal",
    # relative to this person's own skin (L-189-3 / 263: white on dark skin ≠ normal light skin)
    "L_pct", "L_over_p25", "L_z", "B_under_p75", "A_under_p75", "sl80",
]


def _mediapipe(rgb: np.ndarray) -> Tuple[np.ndarray, Dict[str, np.ndarray], bool]:
    """Six selfie-multiclass confidences + face-landmark masks. All zeros when unavailable."""
    from web.backend.services.rgb_segmentation import skin_parsing as sp

    h, w = rgb.shape[:2]
    conf = np.zeros((h, w, 6), np.float32)
    marks = {"eyes": np.zeros((h, w), bool), "lips": np.zeros((h, w), bool)}
    with sp._lock:
        seg = sp._load("segmenter")
        if seg is None:
            return conf, marks, False
        import mediapipe as mp

        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
        c = np.stack([m.numpy_view() for m in seg.segment(image).confidence_masks], -1)
        if c.shape[:2] != (h, w):
            c = cv2.resize(c, (w, h))
        conf = c.astype(np.float32)
        face = sp._face_features(rgb, image)
    marks = {"eyes": face["eyes"], "lips": face["lips"]}
    return conf, marks, True


def proposal_skin(rgb: np.ndarray, conf: np.ndarray, mp_ok: bool) -> np.ndarray:
    """Generous skin superset used only as the reference area for whiteness scores."""
    _, _, B = core.lab_channels(rgb)
    warm = cv2.morphologyEx((B > 6).astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)).astype(bool)
    prop = warm | ((conf[..., 2] + conf[..., 3]) > 0.3) if mp_ok else warm
    if prop.mean() < 0.02:
        prop = np.ones(prop.shape, bool)
    return prop


def _person_skin(conf: np.ndarray, mp_ok: bool, prop: np.ndarray) -> np.ndarray:
    """Best guess of this person's skin for self-relative statistics."""
    if mp_ok:
        s = (conf[..., 2] + conf[..., 3]) > 0.5
        if s.mean() > 0.02:
            return s
    return prop


def _relative(L, A, B, rgb, skin):
    vals = np.sort(L[skin])
    pct = np.searchsorted(vals, L).astype(np.float32) / max(vals.size, 1)
    p10, p25, p50, p90 = np.percentile(L[skin], (10, 25, 50, 90))
    sl80 = core.depigmentation_score(rgb, skin, 80, mode="local")
    return [pct, L - p25, (L - p50) / max(p90 - p10, 1.0),
            np.percentile(B[skin], 75) - B, np.percentile(A[skin], 75) - A, sl80]


def _contrast(x: np.ndarray, region: np.ndarray, r: int) -> np.ndarray:
    """``x - open(x, r)`` inside ``region``: how much brighter than the local darker floor."""
    fill = float(np.median(x[region])) if region.any() else float(np.median(x))
    xs = np.where(region, x, fill).astype(np.float32)
    return x - cv2.morphologyEx(xs, cv2.MORPH_OPEN, core.disk(r))


def feature_maps(rgb: np.ndarray) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
    """``(H, W, len(NAMES))`` float32 + side masks (``lips``, ``eyes``, ``proposal``)."""
    L, A, B = core.lab_channels(rgb)
    conf, marks, mp_ok = _mediapipe(rgb)
    prop = proposal_skin(rgb, conf, mp_ok)
    p = core.params_of({})
    sl = core.depigmentation_score(rgb, prop, p["baseline_sigma"], mode="local")
    sl40 = core.depigmentation_score(rgb, prop, 40, mode="local")
    sg = core.depigmentation_score(rgb, prop, p["baseline_sigma"], mode="global")
    gx = cv2.Sobel(L, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(L, cv2.CV_32F, 0, 1, ksize=3)
    mean5 = cv2.blur(L, (5, 5))
    std5 = np.sqrt(np.maximum(cv2.blur(L * L, (5, 5)) - mean5 * mean5, 0))
    maps = [
        L, A, B, np.hypot(A, B), np.arctan2(B, A),
        L - np.median(L[prop]), A - np.median(A[prop]), B - np.median(B[prop]),
        *[conf[..., i] for i in range(6)],
        np.full(L.shape, float(mp_ok), np.float32), marks["eyes"].astype(np.float32), marks["lips"].astype(np.float32),
        sl, sl40, sg, cv2.GaussianBlur(L, (0, 0), 5), cv2.GaussianBlur(L, (0, 0), 15) - L,
        _contrast(L, prop, 7), _contrast(L, prop, 15), _contrast(L, prop, 31), -_contrast(-B, prop, 15),
        std5, cv2.GaussianBlur(np.hypot(gx, gy), (0, 0), 2),
        prop.astype(np.float32),
        *_relative(L, A, B, rgb, _person_skin(conf, mp_ok, prop)),
    ]
    feats = np.stack([np.asarray(m, np.float32) for m in maps], -1)
    return feats, {"lips": marks["lips"], "eyes": marks["eyes"], "proposal": prop, "hair": conf[..., 1] > 0.5}


def cached(task_id: int, rgb: np.ndarray) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
    """Feature maps cached per task in the (gitignored) work dir."""
    f = sio.work_dir(task_id) / f"features_{VERSION}.npz"
    if f.exists():
        z = np.load(f)
        return z["feats"], {k: z[k] for k in ("lips", "eyes", "proposal", "hair")}
    feats, side = feature_maps(rgb)
    np.savez_compressed(f, feats=feats, **side)
    return feats, side

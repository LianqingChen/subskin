"""Face-plaque HistGradientBoosting prior calibrated on gold revisions (180/s13 → L-180-5).

Predicts depigmented skin from Lab + local/global depigmentation scores. Not a pixel copy of
any mask: the model learns a decision surface in feature space. Cross-half dice ~0.73–0.86 on
the calibration image without using (x,y).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import cv2
import joblib
import numpy as np

from ml.pixel_labeling import core

MODEL_PATH = Path(__file__).resolve().parent / "models" / "face_plaque_gb_v1.joblib"


def _feat_maps(rgb: np.ndarray, skin: np.ndarray, p: Dict[str, Any]):
    L, A, B = core.lab_channels(rgb)
    sl, sg = core.score_pair(rgb, skin, {**p, "baseline_mode": "hybrid"})
    if sg is None:
        sg = core.depigmentation_score(
            rgb, skin, p["baseline_sigma"], mode="global",
            global_exclude_percentile=p.get("global_exclude_percentile", 70),
        )
    sl40 = core.depigmentation_score(rgb, skin, 40, mode="local")
    L5 = cv2.GaussianBlur(L, (0, 0), 5)
    L15 = cv2.GaussianBlur(L, (0, 0), 15)
    return L, A, B, sl, sl40, sg, L5, L15


def build_features(rgb: np.ndarray, skin: np.ndarray, p: Optional[Dict[str, Any]] = None):
    p = core.params_of({"params": p or {}})
    L, A, B, sl, sl40, sg, L5, L15 = _feat_maps(rgb, skin, p)
    ys, xs = np.where(skin)
    X = np.stack([
        L[ys, xs], A[ys, xs], B[ys, xs],
        sl[ys, xs], sl40[ys, xs], sg[ys, xs],
        L5[ys, xs], L15[ys, xs] - L[ys, xs],
        L[ys, xs] - float(np.median(L[skin])),
        B[ys, xs] - float(np.median(B[skin])),
    ], 1).astype(np.float32)
    return ys, xs, X, {"L": L, "sl": sl, "sg": sg}


def predict_lesion(rgb: np.ndarray, skin: np.ndarray, p: Optional[Dict[str, Any]] = None,
                   threshold: Optional[float] = None, lips: Optional[np.ndarray] = None
                   ) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Return boolean lesion mask + meta. Requires ``face_plaque_gb_v1.joblib``."""
    bundle = joblib.load(MODEL_PATH)
    clf, thr = bundle["clf"], float(bundle["threshold"] if threshold is None else threshold)
    ys, xs, X, maps = build_features(rgb, skin, p)
    prob = np.zeros(skin.shape, np.float32)
    prob[ys, xs] = clf.predict_proba(X)[:, 1]
    les = prob >= thr
    if lips is not None:
        les &= ~lips
    les = cv2.morphologyEx(les.astype(np.uint8), cv2.MORPH_CLOSE, core.disk(2)).astype(bool)
    # brow fringe: bright near-skin in upper face connected to lesion (L-180-2/5)
    L = maps["L"]
    h, w = skin.shape
    ys_s, xs_s = np.where(skin)
    y0, y1 = int(ys_s.min()), int(ys_s.max())
    band = cv2.dilate(skin.astype(np.uint8), core.disk(12)).astype(bool) & ~skin
    ref = float(np.median(L[skin & (L <= np.percentile(L[skin], 50))]))
    brow = band & (L > ref + 2) & (L < ref + 28) & (np.arange(h)[:, None] < y0 + 0.3 * (y1 - y0))
    brow &= cv2.dilate(les.astype(np.uint8), core.disk(15)).astype(bool)
    les |= brow
    meta = {**bundle.get("meta", {}), "threshold_used": thr, "lesion_px": int(les.sum())}
    return les, meta

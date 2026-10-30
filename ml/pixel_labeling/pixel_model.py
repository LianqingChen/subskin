"""General pixel model (v2): background / normal skin / lesion / occlusion from ``features.NAMES``.

Trained on every approved gold. Honest accuracy comes from leave-one-group-out (LOGO): each
gold is scored by a model that never saw that photo nor other photos of the same person.
Fold models are kept so ``bench`` can score golds without leakage.
"""

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2
import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier

from ml.pixel_labeling import core, features, gold, metrics

MODEL_DIR = Path(__file__).resolve().parent / "models"
MODEL_ID = "pixel-gb-v2"
FINAL = MODEL_DIR / "pixel_gb_v2.joblib"
FOLDS = MODEL_DIR / "pixel_gb_v2_folds"
CARD = MODEL_DIR / "pixel_gb_v2.json"
CLASSES = (0, 1, 2, 3)  # background, normal skin, lesion, occlusion (gold 255 is ignored)
PER_CLASS = 20000
DEFAULT_THR = 0.5


def _sample(entry: Dict[str, Any], rng: np.random.Generator):
    rgb, hu = gold.load(entry)
    feats, side = features.cached(entry["task_id"], rgb)
    # golds disagree on hair (174/180-182 background, 191 occlusion): train on neither until settled
    contested = (side["hair"] & np.isin(hu, (0, 3))).ravel()
    xs, ys = [], []
    for c in CLASSES:
        idx = np.flatnonzero((hu.ravel() == c) & ~contested)
        if idx.size == 0:
            continue
        pick = rng.choice(idx, min(PER_CLASS, idx.size), replace=False)
        xs.append(feats.reshape(-1, feats.shape[-1])[pick])
        ys.append(np.full(pick.size, c, np.int8))
    x, y = np.concatenate(xs), np.concatenate(ys)
    # every photo weighs the same; inside a photo every class weighs the same
    w = np.ones(y.size, np.float32)
    for c in CLASSES:
        m = y == c
        if m.any():
            w[m] = 1.0 / (m.sum() * len(xs))
    return x, y, w * 1e5


def fit(entries: List[Dict[str, Any]], seed: int = 0) -> Dict[str, Any]:
    rng = np.random.default_rng(seed)
    parts = [_sample(e, rng) for e in entries]
    x, y, w = (np.concatenate([p[i] for p in parts]) for i in range(3))
    clf = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.1, max_leaf_nodes=63,
                                         l2_regularization=1.0, random_state=seed)
    clf.fit(x, y, sample_weight=w)
    return {"clf": clf, "features": features.NAMES, "feature_version": features.VERSION,
            "trained_on": [f"{e['task_id']}/s{e['submission_id']}" for e in entries],
            "lesion_threshold": DEFAULT_THR}


def proba(bundle: Dict[str, Any], feats: np.ndarray, stride: int = 1) -> np.ndarray:
    """Class probabilities ``(H, W, 4)``. ``stride>1`` predicts a sub-grid and interpolates (tuning only)."""
    h, w, k = feats.shape
    sub = feats[::stride, ::stride]
    sh, sw = sub.shape[:2]
    p = bundle["clf"].predict_proba(sub.reshape(-1, k))
    out = np.zeros((sh * sw, 4), np.float32)
    for j, c in enumerate(bundle["clf"].classes_):
        out[:, int(c)] = p[:, j]
    out = out.reshape(sh, sw, 4)
    return out if stride == 1 else cv2.resize(out, (w, h), interpolation=cv2.INTER_LINEAR)


def labels_from(prob: np.ndarray, side: Dict[str, np.ndarray], thr: float) -> np.ndarray:
    """Skin vs background vs occlusion by argmax; inside skin, lesion by share of skin probability."""
    skin_p = prob[..., 1] + prob[..., 2]
    top = np.argmax(np.stack([prob[..., 0], skin_p, prob[..., 3]], -1), -1)
    skin = top == 1
    skin = _drop_small(skin, max(64, int(skin.sum() * 0.002)))
    lesion = skin & (prob[..., 2] / np.maximum(skin_p, 1e-6) >= thr)
    lesion = cv2.morphologyEx(lesion.astype(np.uint8), cv2.MORPH_OPEN, core.disk(1)).astype(bool)
    lesion = cv2.morphologyEx(lesion.astype(np.uint8), cv2.MORPH_CLOSE, core.disk(2)).astype(bool) & skin
    lesion = _drop_small(lesion, 12)
    occl = (top == 2) & ~skin & ~side.get("hair", np.zeros(skin.shape, bool))  # hair → background (majority gold)
    occl = _drop_small(occl, 40)
    labels = np.zeros(skin.shape, np.uint8)
    labels[skin] = 1
    labels[lesion] = 2
    labels[occl] = 3
    return labels


def _drop_small(m: np.ndarray, floor: int) -> np.ndarray:
    n, lbl, st, _ = cv2.connectedComponentsWithStats(m.astype(np.uint8), 8)
    keep = np.zeros(n, bool)
    keep[1:] = st[1:, cv2.CC_STAT_AREA] >= floor
    return keep[lbl]


def _pick_threshold(held: List[Any]) -> float:
    """One global lesion threshold chosen on the held-out fold probabilities (validation).

    In-sample tuning picked ~0.75 and under-called every new photo (LOGO 0.34 vs 0.45 at 0.2).
    """
    best = (-1.0, DEFAULT_THR)
    for thr in np.arange(0.1, 0.81, 0.05):
        d = np.mean([metrics.summary(labels_from(p, s, thr), hu)["lesion_dice_tol2"] or 0 for p, s, hu in held])
        best = max(best, (float(d), round(float(thr), 2)))
    return best[1]


def predict(rgb: np.ndarray, bundle: Optional[Dict[str, Any]] = None, task_id: Optional[int] = None) -> np.ndarray:
    bundle = bundle or load()
    feats, side = features.cached(task_id, rgb) if task_id is not None else features.feature_maps(rgb)
    return labels_from(proba(bundle, feats), side, bundle["lesion_threshold"])


def load(path: Path = FINAL) -> Dict[str, Any]:
    return joblib.load(path)


def fold_path(group: str) -> Path:
    return FOLDS / f"{group}.joblib"


def train_all(log=print) -> Dict[str, Any]:
    """LOGO fold models + final model + model card with per-gold held-out metrics."""
    entries = gold.registry()
    FOLDS.mkdir(parents=True, exist_ok=True)
    groups = sorted({e["group"] for e in entries})
    folds, probs = {}, []
    for g in groups:
        t0 = time.time()
        folds[g] = fit([e for e in entries if e["group"] != g])
        folds[g]["held_out_group"] = g
        for e in entries:
            if e["group"] == g:
                rgb, hu = gold.load(e)
                feats, side = features.cached(e["task_id"], rgb)
                probs.append((e, proba(folds[g], feats), side, hu))
        log(f"[{g}] fold trained ({time.time() - t0:.0f}s)")
    thr = _pick_threshold([(p, s, hu) for _, p, s, hu in probs])
    held: List[Dict[str, Any]] = []
    for e, p, s, hu in probs:
        held.append({"task_id": e["task_id"], "submission_id": e["submission_id"], "group": e["group"],
                     **metrics.summary(labels_from(p, s, thr), hu)})
        log(f"{held[-1]}")
    for g, b in folds.items():
        b["lesion_threshold"] = thr
        joblib.dump(b, fold_path(g))
    final = fit(entries)
    final["lesion_threshold"] = thr
    joblib.dump(final, FINAL)
    card = {"model_id": MODEL_ID, "feature_version": features.VERSION, "features": features.NAMES,
            "trained_on": final["trained_on"], "lesion_threshold": final["lesion_threshold"],
            "threshold_note": "single global threshold picked on held-out fold probabilities (lesion_dice_tol2)",
            "logo": held, "logo_mean": metrics.mean(held),
            "created": time.strftime("%Y-%m-%d %H:%M:%S")}
    CARD.write_text(json.dumps(card, ensure_ascii=False, indent=1))
    return card

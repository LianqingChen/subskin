"""Per-photo depigmentation draft inside a parsed skin mask.

Untrained and photo-adaptive: fit a smooth illumination surface on the
currently-normal skin, correct L*/b*, score pigment with the individual
typology angle (ITA, larger = less melanin), split with Otsu, iterate, then
let GrabCut align the boundary with colour edges. The draft is pre-filled for
the user to confirm; it is never a clinical measurement.
"""

from typing import Any, Dict
import cv2
import numpy as np

ITERATIONS = 3
MIN_ITA_GAP = 8.0  # degrees between class medians; below = no visible contrast
MIN_SHARE, MAX_SHARE = 0.003, 0.95
SAMPLE = 30000


def _design(xs: np.ndarray, ys: np.ndarray, w: int, h: int) -> np.ndarray:
    x, y = xs / w - 0.5, ys / h - 0.5
    return np.stack([np.ones_like(x), x, y, x * x, x * y, y * y], 1)


def _surface(values: np.ndarray, support: np.ndarray, rng) -> np.ndarray:
    h, w = values.shape
    ys, xs = np.nonzero(support)
    pick = rng.choice(len(xs), min(SAMPLE, len(xs)), replace=False)
    coef, *_ = np.linalg.lstsq(
        _design(xs[pick].astype(float), ys[pick].astype(float), w, h),
        values[ys[pick], xs[pick]],
        rcond=None,
    )
    yy, xx = np.mgrid[0:h, 0:w]
    return (_design(xx.ravel().astype(float), yy.ravel().astype(float), w, h) @ coef).reshape(h, w)


def _otsu(values: np.ndarray) -> float:
    lo, hi = np.percentile(values, [0.5, 99.5])
    scaled = np.clip((values - lo) / max(hi - lo, 1e-6) * 255, 0, 255).astype(np.uint8)
    t, _ = cv2.threshold(scaled.reshape(-1, 1), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return float(lo + t / 255 * (hi - lo))


def pigment_map(rgb: np.ndarray, skin: np.ndarray, exclude: np.ndarray) -> Dict[str, Any]:
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    lum = lab[..., 0] * 100 / 255
    yellow = lab[..., 2] - 128
    core = cv2.erode(skin.astype(np.uint8), np.ones((7, 7), np.uint8)).astype(bool) & ~exclude
    if core.sum() < 500:
        return {"ok": False, "reason": "skin_too_small"}
    rng = np.random.default_rng(0)
    normal = core.copy()
    ita = np.zeros_like(lum)
    threshold = 0.0
    for _ in range(ITERATIONS):
        lum_c = lum - _surface(lum, normal, rng) + np.median(lum[normal])
        yellow_c = yellow - _surface(yellow, normal, rng) + np.median(yellow[normal])
        ita = np.degrees(np.arctan2(lum_c - 50, np.maximum(yellow_c, 1e-3)))
        threshold = _otsu(ita[core])
        light = core & (ita > threshold)
        if (core & ~light).sum() < 0.05 * core.sum():
            break
        normal = core & ~light
    light = core & (ita > threshold)
    spread = float(ita[core].std()) + 1e-6
    gap = float(np.median(ita[light]) - np.median(ita[core & ~light])) if light.any() and (core & ~light).any() else 0.0
    return {"ok": True, "ita": ita, "threshold": threshold, "spread": spread, "gap": gap, "core": core}


def _grabcut(rgb: np.ndarray, skin: np.ndarray, prob: np.ndarray) -> np.ndarray:
    seed = np.full(skin.shape, cv2.GC_BGD, np.uint8)
    seed[skin] = cv2.GC_PR_BGD
    seed[skin & (prob > 0.5)] = cv2.GC_PR_FGD
    seed[skin & (prob > 0.95)] = cv2.GC_FGD
    seed[skin & (prob < 0.05)] = cv2.GC_BGD  # confident normal skin anchors the colour model
    if not (seed == cv2.GC_FGD).any() or not (seed[skin] == cv2.GC_BGD).any():
        return skin & (prob > 0.5)
    bg, fg = np.zeros((1, 65)), np.zeros((1, 65))
    try:
        cv2.grabCut(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), seed, None, bg, fg, 3, cv2.GC_INIT_WITH_MASK)
    except cv2.error:
        return skin & (prob > 0.5)
    return np.isin(seed, [cv2.GC_FGD, cv2.GC_PR_FGD]) & skin


def _clean(mask: np.ndarray, skin: np.ndarray) -> np.ndarray:
    m = mask.astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))
    count, labels, stats, _ = cv2.connectedComponentsWithStats(m, 8)
    floor = max(24, int(skin.sum() * 0.0005))
    keep = np.zeros(mask.shape, bool)
    for i in range(1, count):
        if stats[i, cv2.CC_STAT_AREA] >= floor:
            keep |= labels == i
    return keep & skin


def draft_lesion(rgb: np.ndarray, skin: np.ndarray, no_draft: np.ndarray) -> Dict[str, Any]:
    """Return ``lesion`` (pre-filled draft), ``uncertain`` (thin review band or,
    when contrast is too low, the whole candidate) and a ``check`` report."""
    empty = np.zeros(skin.shape, bool)
    stats = pigment_map(rgb, skin, no_draft)
    if not stats["ok"]:
        return {"lesion": empty, "uncertain": empty.copy(), "check": {"status": stats["reason"]}}
    ita, threshold, spread = stats["ita"], stats["threshold"], stats["spread"]
    prob = 1 / (1 + np.exp(-(ita - threshold) / (0.15 * spread)))
    prob[~skin | no_draft] = 0
    lesion = _clean(_grabcut(rgb, skin & ~no_draft, prob), skin)
    share = float(lesion.sum() / max(1, skin.sum()))
    check = {
        "status": "draft",
        "ita_gap": round(stats["gap"], 2),
        "ita_threshold": round(threshold, 2),
        "share": round(share, 4),
    }
    if stats["gap"] < MIN_ITA_GAP or not MIN_SHARE <= share <= MAX_SHARE:
        # No reliable contrast: show as candidate only, user decides.
        check["status"] = "low_contrast" if stats["gap"] < MIN_ITA_GAP else "implausible_share"
        return {"lesion": empty, "uncertain": lesion, "check": check}
    near = np.abs(ita - threshold) < 0.5 * spread
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 13))
    ring = cv2.dilate(lesion.astype(np.uint8), k).astype(bool) & ~lesion
    band = ring & near & skin & ~no_draft
    return {"lesion": lesion, "uncertain": band, "check": check}

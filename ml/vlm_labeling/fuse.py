"""Region verdicts -> five-class pixel map.

The model's region verdicts are *weak labels for this one image*.  A small per-image classifier
learns this person's lesion-vs-normal colour under this lighting from the confidently judged
regions, then decides every skin pixel; verdict and classifier are blended so a single wrong
verdict is outvoted by colour evidence and a colour-ambiguous region (lit normal skin) follows
the verdict.  Regions where the two strongly disagree are returned for a second look.

Simulated on 182 (≈600 skin regions, ±2px Dice): perfect verdicts 0.979 · 10% flipped 0.949 · 20% flipped 0.904.
"""

from typing import Dict, List, Tuple

import cv2
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier

# verdict codes used by the protocol (rubric.md defines them for the model)
CODES = {"B": 0, "N": 1, "L": 2, "O": 3, "X": 4}
SKIN_CODES = ("N", "L", "M", "U")

# appearance features only: no (x, y) — position must never decide a lesion
FEATURES = ["L", "A", "B", "chroma", "hue", "L_rel", "A_rel", "B_rel", "sl", "sl40", "sg", "L5",
            "L15_minus_L", "Lc7", "Lc15", "Lc31", "Bc15", "L_std5", "grad",
            "L_pct", "L_over_p25", "L_z", "B_under_p75", "A_under_p75", "sl80"]


# skin-vs-background additionally uses the person parser (mediapipe) confidences
SKIN_FEATURES = FEATURES + ["mp_bg", "mp_hair", "mp_body", "mp_face", "mp_clothes", "mp_other"]


def _blur_stack(feats: np.ndarray, names: List[str], use: List[str] = FEATURES) -> np.ndarray:
    ix = [names.index(n) for n in use]
    f = feats[..., ix]
    extra = [cv2.GaussianBlur(np.ascontiguousarray(f[..., i]), (0, 0), s) for s in (3, 9) for i in range(3)]
    return np.concatenate([f, np.stack(extra, -1)], -1)


def crossfit_proba(feats: np.ndarray, names: List[str], seg: np.ndarray, pos: np.ndarray, neg: np.ndarray,
                   skin: np.ndarray, folds: int = 3, seed: int = 0, per_class: int = 30000,
                   use: List[str] = FEATURES, clean: float = 0.0) -> np.ndarray:
    """P(lesion) per skin pixel.  Regions are split into ``folds`` groups; a judged region is scored
    only by models that never saw its own verdict (out-of-fold), so a wrong verdict cannot be
    memorised and shows up as a disagreement.  Unjudged skin (M/U) gets the fold average."""
    H, W = seg.shape
    Xf = _blur_stack(feats, names, use).reshape(-1, len(use) + 6)
    rng = np.random.default_rng(seed)
    rids = np.unique(seg[seg >= 0])
    fold_of = np.full(seg.max() + 2, -1, np.int32)
    fold_of[rids + 1] = rng.permutation(np.arange(rids.size) % folds)
    F = fold_of[seg + 1].ravel()
    posf, negf, skf = pos.ravel(), neg.ravel(), skin.ravel()
    judged = posf | negf
    p = np.zeros(H * W, np.float32)
    acc = np.zeros(H * W, np.float32)
    for k in range(folds):
        tr_p = np.flatnonzero(posf & (F != k))
        tr_n = np.flatnonzero(negf & (F != k))
        if tr_p.size < 50 or tr_n.size < 50:
            continue
        tr_p = rng.choice(tr_p, min(per_class, tr_p.size), replace=False)
        tr_n = rng.choice(tr_n, min(per_class, tr_n.size), replace=False)
        idx = np.concatenate([tr_p, tr_n])
        y = np.concatenate([np.ones(tr_p.size), np.zeros(tr_n.size)])
        clf = HistGradientBoostingClassifier(max_iter=120, learning_rate=0.1, l2_regularization=1.0,
                                             min_samples_leaf=300, random_state=seed + k)
        clf.fit(Xf[idx], y)
        if clean > 0:
            # self-cleaning: a region judged L that is only partly depigmented puts normal pixels
            # into the positive set; drop samples the first fit finds implausible and refit
            pr = clf.predict_proba(Xf[idx])[:, 1]
            keep = ((y == 1) & (pr >= clean)) | ((y == 0) & (pr <= 1 - clean))
            if keep[y == 1].sum() >= 50 and keep[y == 0].sum() >= 50:
                clf = HistGradientBoostingClassifier(max_iter=120, learning_rate=0.1, l2_regularization=1.0,
                                                     min_samples_leaf=300, random_state=seed + k)
                clf.fit(Xf[idx][keep], y[keep])
        held = np.flatnonzero(skf & judged & (F == k))       # out-of-fold for judged pixels
        if held.size:
            p[held] = clf.predict_proba(Xf[held])[:, 1]
        free = np.flatnonzero(skf & ~judged)                  # unjudged: average over folds
        if free.size:
            acc[free] += clf.predict_proba(Xf[free])[:, 1]
    free = skf & ~judged
    p[free] = acc[free] / folds
    return p.reshape(H, W)


def fuse(feats: np.ndarray, names: List[str], seg: np.ndarray, verdicts: Dict[int, str],
         gate: float = 0.35, pixel_override: float = 0.1, unsure_band: Tuple[float, float] = (0.4, 0.6),
         folds: int = 3, seed: int = 0, refine_skin: bool = True, clean: float = 0.0) -> Tuple[np.ndarray, Dict]:
    """Gate fusion (chosen by simulation on 182, see SKILL.md §measured):
    verdict decides a judged region unless its out-of-fold colour probability contradicts it by
    ``gate`` (then colour decides every pixel of it); inside agreeing regions single pixels flip
    only when colour is near-certain (``pixel_override``); unjudged skin (M/U) follows colour."""
    H, W = seg.shape
    labels = np.zeros((H, W), np.uint8)              # outside proposal = background
    vmap = np.full(seg.max() + 2, "B", dtype="<U1")  # index rid+1 so -1 -> "B"
    for rid, v in verdicts.items():
        vmap[int(rid) + 1] = v
    V = vmap[seg + 1]
    for code, cls in CODES.items():
        if code in ("N", "L"):
            continue
        labels[V == code] = cls
    skin = np.isin(V, SKIN_CODES)
    pos, neg = V == "L", V == "N"
    info = {"n_L": int(pos.sum()), "n_N": int(neg.sum()), "classifier": None, "disagree": []}
    if not skin.any():
        return labels, info
    if pos.sum() < 200 or neg.sum() < 200:
        # one-sided image (all lesion / no lesion): verdicts are the whole answer
        labels[skin] = 1
        labels[pos] = 2
        labels[V == "U"] = 255
        info["classifier"] = "skipped (one class)"
        return labels, info

    p = crossfit_proba(feats, names, seg, pos, neg, skin, folds=folds, seed=seed, clean=clean)
    p = cv2.GaussianBlur(p, (0, 0), 1.2)
    rid = np.where(seg >= 0, seg, seg.max() + 1)
    cnt = np.bincount(rid.ravel())
    rmean = np.bincount(rid.ravel(), p.ravel()) / np.maximum(cnt, 1)
    RP = rmean[rid]
    dis = (pos & (RP < gate)) | (neg & (RP > 1 - gate))
    q = np.where(pos, 1.0, np.where(neg, 0.0, p))
    q = np.where(dis, p, q)
    q = np.where(pos & (p < pixel_override), p, q)
    q = np.where(neg & (p > 1 - pixel_override), p, q)
    labels[skin] = 1
    labels[skin & (q >= 0.5)] = 2
    lo, hi = unsure_band
    labels[(V == "U") & (q > lo) & (q < hi)] = 255
    info["classifier"] = "hgb-crossfit-gate"

    # skin vs non-skin with the same out-of-fold gate: region borders that straddle skin and a
    # skin-coloured table/wall (186 -> background) or skin and lip vermilion (185 -> occlusion).
    # Each class needs enough verdict pixels to learn from.
    judged_skin = pos | neg
    for code, cls, minpx in (("B", 0, 2000), ("O", 3, 1500)):
        other = V == code
        if not refine_skin or other.sum() < minpx:
            continue
        cur_skin = np.isin(labels, (1, 2, 255)) & skin
        ps = crossfit_proba(feats, names, seg, judged_skin, other, cur_skin | other, folds=folds,
                            seed=seed + 11 + cls, use=SKIN_FEATURES + (["lips"] if code == "O" else []))
        ps = cv2.GaussianBlur(ps, (0, 0), 1.2)
        smean = np.bincount(rid.ravel(), ps.ravel()) / np.maximum(cnt, 1)
        SP = smean[rid]
        move = cur_skin & ((judged_skin & (SP < gate) & (ps < 0.5))       # region contradicted
                           | (judged_skin & (ps < pixel_override))        # near-certain pixel
                           | (~judged_skin & (ps < 0.5)))                 # M/U follow colour
        labels[move] = cls
        info[f"skin_to_{code}_px"] = int(move.sum())

    # regions where colour evidence contradicts the verdict -> second look by the model
    for r_ in np.unique(seg[(pos | neg)]):
        v = verdicts.get(int(r_))
        mp = float(rmean[r_])
        if (v == "L" and mp < gate) or (v == "N" and mp > 1 - gate):
            info["disagree"].append({"id": int(r_), "verdict": v, "p_lesion": round(mp, 3)})
    info["p_lesion"] = p
    return labels, info

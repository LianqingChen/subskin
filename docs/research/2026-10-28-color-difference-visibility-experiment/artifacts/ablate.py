"""Leave-one-person-out lesion-vs-normal pixel classifier inside the gold skin region.

Isolates "识别白斑" from "识别皮肤": the skin region is the gold one (oracle). Compares feature
families to answer: absolute colour vs person-relative colour vs local contrast.
Read-only; uses cached features from data/labeling_work.
"""
import json
import sys
import time
import cv2
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline

sys.path.insert(0, "/root/subskin")
from ml.pixel_labeling import features, gold  # noqa: E402

N = features.NAMES
FAM = {
    "abs": ["L", "A", "B", "chroma", "hue"],
    "rel": ["L_rel", "A_rel", "B_rel", "L_pct", "L_over_p25", "L_z", "B_under_p75", "A_under_p75"],
    "local": ["sl", "sl40", "sg", "sl80", "L5", "L15_minus_L", "Lc7", "Lc15", "Lc31", "Bc15", "L_std5", "grad"],
    "parse": [*features.MP_CLASSES, "mp_ok", "eye_brow", "lips", "proposal"],
}
SETS = {
    "abs(色值)": FAM["abs"],
    "rel(本人相对色)": FAM["rel"],
    "local(周围色差)": FAM["local"],
    "abs+rel": FAM["abs"] + FAM["rel"],
    "abs+rel+local": FAM["abs"] + FAM["rel"] + FAM["local"],
    "all": FAM["abs"] + FAM["rel"] + FAM["local"] + FAM["parse"],
}
PER_CLASS = 15000
rng = np.random.default_rng(0)


def disk(r):
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))


def clean(m):
    m = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_OPEN, disk(1))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, disk(2))
    n, lbl, st, _ = cv2.connectedComponentsWithStats(m, 8)
    keep = np.zeros(n, bool)
    keep[1:] = st[1:, cv2.CC_STAT_AREA] >= 12
    return keep[lbl]


def dice(a, b):
    s = int(a.sum() + b.sum())
    return 2 * int((a & b).sum()) / s if s else None


data = []
for e in gold.registry():
    rgb, hu = gold.load(e)
    f, _ = features.cached(e["task_id"], rgb)
    region = np.isin(hu, (1, 2))
    data.append({"task": e["task_id"], "group": e["group"], "f": f, "region": region, "y": hu == 2})
    print("loaded", e["task_id"], e["group"], "lesion share", round(float((hu == 2).sum() / region.sum()), 3), flush=True)
groups = sorted({d["group"] for d in data})


def sample(d, cols):
    x = d["f"][..., cols]
    pos = np.flatnonzero((d["region"] & d["y"]).ravel())
    neg = np.flatnonzero((d["region"] & ~d["y"]).ravel())
    xs, ys, ws = [], [], []
    for idx, c in ((pos, 1), (neg, 0)):
        if idx.size == 0:
            continue
        pick = rng.choice(idx, min(PER_CLASS, idx.size), replace=False)
        xs.append(x.reshape(-1, x.shape[-1])[pick])
        ys.append(np.full(pick.size, c))
        ws.append(np.full(pick.size, 1.0 / pick.size))
    return np.concatenate(xs), np.concatenate(ys), np.concatenate(ws) * 1e4


def make(kind):
    if kind == "hgb":
        return HistGradientBoostingClassifier(max_iter=100, learning_rate=0.1, max_leaf_nodes=31, l2_regularization=1.0, random_state=0)
    return make_pipeline(StandardScaler(), LogisticRegression(max_iter=300, C=1.0))


def run(kind, name, names):
    cols = [N.index(n) for n in names]
    probs = {}
    t0 = time.time()
    for g in groups:
        tr = [sample(d, cols) for d in data if d["group"] != g]
        x, y, w = (np.concatenate([p[i] for p in tr]) for i in range(3))
        clf = make(kind)
        if kind == "hgb":
            clf.fit(x, y, sample_weight=w)
        else:
            clf.fit(x, y, logisticregression__sample_weight=w)
        for d in data:
            if d["group"] == g:
                p = np.zeros(d["region"].shape, np.float32)
                idx = np.flatnonzero(d["region"].ravel())
                p.ravel()[idx] = clf.predict_proba(d["f"][..., cols].reshape(-1, len(cols))[idx])[:, 1]
                probs[d["task"]] = p
    # threshold per image chosen on the OTHER groups' held-out probabilities
    def score(thr, ds):
        out = []
        for d in ds:
            pred = clean((probs[d["task"]] >= thr) & d["region"]) & d["region"]
            v = dice(pred, d["y"])
            if v is not None:
                out.append(v)
        return float(np.mean(out)) if out else 0.0
    grid = np.arange(0.1, 0.91, 0.05)
    rows = []
    for d in data:
        others = [o for o in data if o["group"] != d["group"]]
        thr = max(grid, key=lambda t: score(t, others))
        pred = clean((probs[d["task"]] >= thr) & d["region"]) & d["region"]
        p5 = clean((probs[d["task"]] >= 0.5) & d["region"]) & d["region"]
        rows.append({"task": d["task"], "thr": round(float(thr), 2), "dice": dice(pred, d["y"]), "dice@0.5": dice(p5, d["y"]),
                     "pred_ratio": round(100 * pred.sum() / d["region"].sum(), 2),
                     "gold_ratio": round(100 * d["y"].sum() / d["region"].sum(), 2)})
    mean = float(np.mean([r["dice"] for r in rows if r["dice"] is not None]))
    mean5 = float(np.mean([r["dice@0.5"] for r in rows if r["dice@0.5"] is not None]))
    err = float(np.mean([abs(r["pred_ratio"] - r["gold_ratio"]) for r in rows]))
    print(f"{kind:3s} {name:18s} mean Dice {mean:.3f} (@0.5 {mean5:.3f}) ratio MAE {err:.1f}pp  [{time.time() - t0:.0f}s]", flush=True)
    return {"kind": kind, "set": name, "mean_dice": mean, "mean_dice_0.5": mean5, "ratio_mae_pp": err, "rows": rows}


results = []
for name, names in SETS.items():
    results.append(run("hgb", name, names))
    json.dump(results, open("/root/subskin/tmp/pixel_clf/ablate.json", "w"), indent=1)
for name in ("abs+rel+local",):
    results.append(run("lr", name, SETS[name]))
    json.dump(results, open("/root/subskin/tmp/pixel_clf/ablate.json", "w"), indent=1)
print("DONE")

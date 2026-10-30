"""Colour-difference rule: reference = this person's normal-skin colour; lesion = pixels whose colour differs by > t (and lighter).
Oracle reference (from gold normal pixels) gives the upper bound of the idea; practical references need no labels."""
import json, sys
import cv2, numpy as np
from skimage.color import rgb2lab, deltaE_ciede2000
from sklearn.metrics import roc_auc_score
sys.path.insert(0, "/root/subskin")
from ml.pixel_labeling import gold  # noqa: E402

def disk(r): return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2*r+1, 2*r+1))
def clean(m):
    m = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_OPEN, disk(1)); m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, disk(2))
    n, lbl, st, _ = cv2.connectedComponentsWithStats(m, 8); keep = np.zeros(n, bool); keep[1:] = st[1:, cv2.CC_STAT_AREA] >= 12
    return keep[lbl]
def dice(a, b):
    s = int(a.sum()+b.sum()); return 2*int((a&b).sum())/s if s else None

def local_ref(lab, normal, sigma=60):
    """Normalised-convolution local mean of normal-skin colour (handles lighting gradients)."""
    w = normal.astype(np.float32); den = cv2.GaussianBlur(w, (0, 0), sigma) + 1e-6
    return np.stack([cv2.GaussianBlur(lab[..., c]*w, (0, 0), sigma)/den for c in range(3)], -1)

data = []
for e in gold.registry():
    rgb, hu = gold.load(e); lab = rgb2lab(rgb.astype(np.float32)/255).astype(np.float32)
    region = np.isin(hu, (1, 2)); y = hu == 2; normal = hu == 1
    refs = {}
    refs["oracle-global"] = np.broadcast_to(np.median(lab[normal], 0), lab.shape) if normal.sum() > 50 else None
    refs["oracle-local"] = local_ref(lab, normal) if normal.sum() > 50 else None
    refs["auto-median"] = np.broadcast_to(np.median(lab[region], 0), lab.shape)               # all skin, no labels
    dark = region & (lab[..., 0] <= np.percentile(lab[..., 0][region], 50))
    refs["auto-darker-half"] = np.broadcast_to(np.median(lab[dark], 0), lab.shape)             # no labels
    sc = {}
    for k, r in refs.items():
        if r is None: continue
        dE = deltaE_ciede2000(lab, np.ascontiguousarray(r)).astype(np.float32)
        sc[k] = np.where(lab[..., 0] > r[..., 0], dE, -dE)                                      # signed: lighter than reference = positive
    data.append({"task": e["task_id"], "group": e["group"], "region": region, "y": y, "normal": normal, "sc": sc, "lab": lab})
    print("prep", e["task_id"], flush=True)

KEYS = ["oracle-local", "oracle-global", "auto-darker-half", "auto-median"]
grid = np.arange(1, 41, 1.0)
rng = np.random.default_rng(0)
out = {}
for k in KEYS:
    ds = [d for d in data if k in d["sc"]]
    def D(d, t): return dice(clean((d["sc"][k] > t) & d["region"]) & d["region"], d["y"])
    # per-image AUC of the colour-difference score (lesion vs normal pixels): ceiling of ANY threshold rule on this score
    aucs = {}
    for d in ds:
        pos = np.flatnonzero((d["region"] & d["y"]).ravel()); neg = np.flatnonzero((d["region"] & ~d["y"]).ravel())
        if pos.size < 20 or neg.size < 20: continue
        pp = rng.choice(pos, min(30000, pos.size), replace=False); nn = rng.choice(neg, min(30000, neg.size), replace=False)
        s = d["sc"][k].ravel(); aucs[d["task"]] = round(float(roc_auc_score(np.r_[np.ones(pp.size), np.zeros(nn.size)], np.r_[s[pp], s[nn]])), 3)
    best = {d["task"]: max(((D(d, t) or 0), t) for t in grid) for d in ds}                       # per-image best t (oracle upper bound)
    cache = {(d["task"], t): D(d, t) or 0 for d in ds for t in grid}
    loo, rows = {}, []
    for d in ds:                                                                                 # one global t, chosen on the OTHER people
        others = [o for o in ds if o["group"] != d["group"]]
        t = max(grid, key=lambda t: np.mean([cache[(o["task"], t)] for o in others]))
        pr = clean((d["sc"][k] > t) & d["region"]) & d["region"]
        rows.append({"task": d["task"], "t": float(t), "dice": dice(pr, d["y"]) or 0.0,
                     "pred": round(100*pr.sum()/d["region"].sum(), 2), "gold": round(100*d["y"].sum()/d["region"].sum(), 2)})
    fixed = {t: float(np.mean([cache[(d["task"], t)] for d in ds])) for t in (3, 5, 8, 10, 15, 20)}
    res = {"global_t_LOGO_mean_dice": round(float(np.mean([r["dice"] for r in rows])), 3),
           "ratio_MAE_pp": round(float(np.mean([abs(r["pred"]-r["gold"]) for r in rows])), 1),
           "per_image_best_t_mean_dice": round(float(np.mean([v[0] for v in best.values()])), 3),
           "best_t_range": [min(v[1] for v in best.values()), max(v[1] for v in best.values())],
           "fixed_t_mean_dice": {str(t): round(v, 3) for t, v in fixed.items()},
           "auc_mean": round(float(np.mean(list(aucs.values()))), 3), "auc_min": min(aucs.values()), "auc": aucs,
           "per_image": {r["task"]: [round(r["dice"], 2), r["t"]] for r in rows}}
    out[k] = res
    print(f"\n[{k}] n={len(ds)}  global t (LOGO) Dice {res['global_t_LOGO_mean_dice']}  ratio MAE {res['ratio_MAE_pp']}pp | per-image-best-t Dice {res['per_image_best_t_mean_dice']} (best t range {res['best_t_range']})")
    print("   fixed t -> Dice:", res["fixed_t_mean_dice"], "| AUC mean", res["auc_mean"], "min", res["auc_min"])
    print("   per-image Dice@LOGO-t:", res["per_image"], flush=True)
    print("   per-image AUC:", aucs, flush=True)
json.dump(out, open("/root/subskin/tmp/pixel_clf/thr.json", "w"), indent=1); print("DONE")

"""Learning curve: real held-out accuracy vs number of synthetic composites (from OTHER persons' photos only).
Total synthetic weight is held fixed (lambda x number of real training images) so only synthetic DIVERSITY grows with N."""
import glob, json, re, sys, time
import cv2, numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
sys.path.insert(0, "/root/subskin")
from ml.pixel_labeling import features, gold  # noqa: E402

CHUNK, PER_CLASS = 50, 15000
def disk(r): return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2*r+1, 2*r+1))
def clean(m):
    m = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_OPEN, disk(1)); m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, disk(2))
    n, lbl, st, _ = cv2.connectedComponentsWithStats(m, 8); keep = np.zeros(n, bool); keep[1:] = st[1:, cv2.CC_STAT_AREA] >= 12
    return keep[lbl]
def dice(a, b):
    s = int(a.sum() + b.sum()); return 2 * int((a & b).sum()) / s if s else None

data = []
for e in gold.registry():
    rgb, hu = gold.load(e); f, _ = features.cached(e["task_id"], rgb)
    data.append({"task": e["task_id"], "group": e["group"], "f": f, "region": np.isin(hu, (1, 2)), "y": hu == 2})
groups = sorted({d["group"] for d in data})
files = []
for p in sorted(glob.glob("/root/subskin/tmp/pixel_clf/comp2/*_*.npz")):
    if p.endswith(".tmp.npz"): continue
    z = np.load(p); files.append({"chunk": int(re.search(r"_(\d+)\.npz", p).group(1)), "group": str(z["group"]), "x": z["x"], "y": z["y"], "cid": z["cid"]})
print(f"real images {len(data)} | composite chunk files {len(files)} (= {len(files) * CHUNK} composites, {sum(len(f['y']) for f in files):,} rows)", flush=True)

def real_sample(d, rng):
    out = []
    for idx, c in ((np.flatnonzero((d["region"] & d["y"]).ravel()), 1), (np.flatnonzero((d["region"] & ~d["y"]).ravel()), 0)):
        if idx.size == 0: continue
        pick = rng.choice(idx, min(PER_CLASS, idx.size), replace=False)
        out.append((d["f"].reshape(-1, d["f"].shape[-1])[pick], np.full(pick.size, c), np.full(pick.size, 1.0 / pick.size)))
    return [np.concatenate([o[i] for o in out]) for i in range(3)]

def syn_sample(fs, scale):
    """class-balanced per composite; every composite's two classes sum to `scale` each."""
    xs, ys, ws = [], [], []
    for f in fs:
        key = f["cid"].astype(np.int64) * 2 + f["y"]; cnt = np.bincount(key)
        xs.append(f["x"]); ys.append(f["y"]); ws.append(scale / cnt[key])
    return np.concatenate(xs), np.concatenate(ys), np.concatenate(ws)

def run(seed, per_base, lam):
    rng = np.random.default_rng(seed); probs = {}
    use = [f for f in files if f["chunk"] < per_base // CHUNK]
    for g in groups:
        tr = [real_sample(d, rng) for d in data if d["group"] != g]
        x, y, w = (np.concatenate([p[i] for p in tr]) for i in range(3))
        if use and lam > 0:
            fs = [f for f in use if f["group"] != g]
            if fs:
                n_comp = len(fs) * CHUNK
                sx, sy, sw = syn_sample(fs, lam * len(tr) / n_comp)
                x, y, w = np.concatenate([x, sx]), np.concatenate([y, sy]), np.concatenate([w, sw])
        clf = HistGradientBoostingClassifier(max_iter=100, learning_rate=0.1, max_leaf_nodes=31, l2_regularization=1.0, random_state=seed).fit(x, y, sample_weight=w * 1e4)
        for d in data:
            if d["group"] == g:
                p = np.zeros(d["region"].shape, np.float32); idx = np.flatnonzero(d["region"].ravel())
                p.ravel()[idx] = clf.predict_proba(d["f"].reshape(-1, d["f"].shape[-1])[idx])[:, 1]; probs[d["task"]] = p
        del x, y, w
    def score(thr, ds):
        v = [dice(clean((probs[d["task"]] >= thr) & d["region"]) & d["region"], d["y"]) for d in ds]; return float(np.mean([a for a in v if a is not None]))
    grid = np.arange(0.1, 0.91, 0.05); rows = {}
    for d in data:
        thr = max(grid, key=lambda t: score(t, [o for o in data if o["group"] != d["group"]]))
        pr = clean((probs[d["task"]] >= thr) & d["region"]) & d["region"]
        rows[d["task"]] = {"dice": dice(pr, d["y"]) or 0.0, "pred": 100 * pr.sum() / d["region"].sum(), "gold": 100 * d["y"].sum() / d["region"].sum()}
    return rows

max_per_base = max(f["chunk"] for f in files) * CHUNK + CHUNK if files else 0
POINTS = [(0, 0.0, (0, 1))] + [(c, 0.5, (0, 1)) for c in (50, 150, 300) if c <= max_per_base] + \
         [(c, 2.0, (0, 1)) for c in (150, 300) if c <= max_per_base] + [(max_per_base, 0.5, (0,)), (max_per_base, 2.0, (0,))]
res = []
for per_base, lam, seeds in POINTS:
    for seed in seeds:
        t0 = time.time(); rows = run(seed, per_base, lam)
        rec = {"per_base": per_base, "n_composites": per_base * len(groups) if per_base else 0, "lambda": lam, "seed": seed, "rows": rows,
               "mean_dice": float(np.mean([r["dice"] for r in rows.values()])), "ratio_mae": float(np.mean([abs(r["pred"] - r["gold"]) for r in rows.values()]))}
        res.append(rec); json.dump(res, open("/root/subskin/tmp/pixel_clf/comp_eval2.json", "w"))
        print(f"composites/base={per_base:4d} lambda={lam} seed={seed}  mean Dice {rec['mean_dice']:.3f}  ratio MAE {rec['ratio_mae']:.1f}pp  [{time.time() - t0:.0f}s]", flush=True)
print("DONE")

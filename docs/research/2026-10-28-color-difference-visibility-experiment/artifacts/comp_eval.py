"""Leave-one-person-out: does adding synthetic composites (made only from OTHER persons' photos) help on held-out REAL photos?"""
import glob, json, sys, time
import cv2, numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
sys.path.insert(0, "/root/subskin")
from ml.pixel_labeling import features, gold  # noqa: E402

PER_CLASS = 15000
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
comps = []
for p in sorted(glob.glob("/root/subskin/tmp/pixel_clf/comp/c_*.npz")):
    z = np.load(p); comps.append({"x": z["x"], "y": z["y"], "group": str(z["group"])})
print("real images", len(data), "| composites", len(comps), flush=True)

def real_sample(d, rng):
    out = []
    for idx, c in ((np.flatnonzero((d["region"] & d["y"]).ravel()), 1), (np.flatnonzero((d["region"] & ~d["y"]).ravel()), 0)):
        if idx.size == 0: continue
        pick = rng.choice(idx, min(PER_CLASS, idx.size), replace=False)
        out.append((d["f"].reshape(-1, d["f"].shape[-1])[pick], np.full(pick.size, c), np.full(pick.size, 1.0 / pick.size)))
    return [np.concatenate([o[i] for o in out]) for i in range(3)]

def comp_sample(c, w):
    out = []
    for cls in (1, 0):
        m = c["y"] == cls
        if m.any(): out.append((c["x"][m], np.full(int(m.sum()), cls), np.full(int(m.sum()), w / m.sum())))
    return [np.concatenate([o[i] for o in out]) for i in range(3)]

def run(seed, wsyn):
    rng = np.random.default_rng(seed); probs = {}
    for g in groups:
        tr = [real_sample(d, rng) for d in data if d["group"] != g]
        if wsyn > 0: tr += [comp_sample(c, wsyn) for c in comps if c["group"] != g]
        x, y, w = (np.concatenate([p[i] for p in tr]) for i in range(3))
        clf = HistGradientBoostingClassifier(max_iter=100, learning_rate=0.1, max_leaf_nodes=31, l2_regularization=1.0, random_state=seed).fit(x, y, sample_weight=w * 1e4)
        for d in data:
            if d["group"] == g:
                p = np.zeros(d["region"].shape, np.float32); idx = np.flatnonzero(d["region"].ravel())
                p.ravel()[idx] = clf.predict_proba(d["f"].reshape(-1, d["f"].shape[-1])[idx])[:, 1]; probs[d["task"]] = p
    def score(thr, ds):
        v = [dice(clean((probs[d["task"]] >= thr) & d["region"]) & d["region"], d["y"]) for d in ds]; v = [x for x in v if x is not None]; return float(np.mean(v))
    grid = np.arange(0.1, 0.91, 0.05); rows = {}
    for d in data:
        thr = max(grid, key=lambda t: score(t, [o for o in data if o["group"] != d["group"]]))
        pr = clean((probs[d["task"]] >= thr) & d["region"]) & d["region"]
        rows[d["task"]] = {"dice": dice(pr, d["y"]) or 0.0, "pred": 100 * pr.sum() / d["region"].sum(), "gold": 100 * d["y"].sum() / d["region"].sum()}
    return rows

SETTINGS = {"real only": 0.0, "+synthetic w=1.0": 1.0, "+synthetic w=0.3": 0.3}
res = {k: [] for k in SETTINGS}
for seed in (0, 1, 2):
    for name, w in SETTINGS.items():
        t0 = time.time(); rows = run(seed, w); res[name].append(rows)
        print(f"seed {seed} {name:18s} mean Dice {np.mean([r['dice'] for r in rows.values()]):.3f}  ratio MAE {np.mean([abs(r['pred'] - r['gold']) for r in rows.values()]):.1f}pp  [{time.time() - t0:.0f}s]", flush=True)
json.dump(res, open("/root/subskin/tmp/pixel_clf/comp_eval.json", "w"), indent=1)
tasks = [d["task"] for d in data]
print("\n=== summary over 3 seeds (mean ± sd of the per-seed means) ===")
base = {t: np.mean([r[t]["dice"] for r in res["real only"]]) for t in tasks}
for name in SETTINGS:
    per_seed = [np.mean([r[t]["dice"] for t in tasks]) for r in res[name]]; mae = [np.mean([abs(r[t]["pred"] - r[t]["gold"]) for t in tasks]) for r in res[name]]
    mean_t = {t: np.mean([r[t]["dice"] for r in res[name]]) for t in tasks}; d = np.array([mean_t[t] - base[t] for t in tasks])
    print(f"{name:18s} Dice {np.mean(per_seed):.3f} ± {np.std(per_seed):.3f} | ratio MAE {np.mean(mae):.1f}pp | vs real-only: mean {d.mean():+.3f}, improved {int((d > 0.005).sum())}, worse {int((d < -0.005).sum())} of {len(tasks)}")
print("\nper-image Dice  (real only -> +syn w=1.0 -> +syn w=0.3):")
for t in tasks:
    print(f"  {t}: {base[t]:.2f} -> {np.mean([r[t]['dice'] for r in res['+synthetic w=1.0']]):.2f} -> {np.mean([r[t]['dice'] for r in res['+synthetic w=0.3']]):.2f}   gold ratio {res['real only'][0][t]['gold']:.1f}%")

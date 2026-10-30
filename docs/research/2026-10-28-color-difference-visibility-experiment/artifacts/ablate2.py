"""Foundation-model features (SAM ViT-B encoder, PCA-32, label-free) vs handcrafted, same LOGO protocol as ablate.py."""
import json, sys, time
import cv2, numpy as np
from sklearn.decomposition import PCA
from sklearn.ensemble import HistGradientBoostingClassifier
sys.path.insert(0, "/root/subskin")
from ml.pixel_labeling import features, gold  # noqa: E402

N = features.NAMES
HAND = [n for n in N]  # 'all' set of ablate.py == every feature
PER_CLASS, K = 15000, 32
rng = np.random.default_rng(0)

def disk(r): return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2*r+1, 2*r+1))
def clean(m):
    m = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_OPEN, disk(1)); m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, disk(2))
    n, lbl, st, _ = cv2.connectedComponentsWithStats(m, 8); keep = np.zeros(n, bool); keep[1:] = st[1:, cv2.CC_STAT_AREA] >= 12
    return keep[lbl]
def dice(a, b):
    s = int(a.sum()+b.sum()); return 2*int((a&b).sum())/s if s else None

entries = gold.registry(); data = []
for e in entries:
    rgb, hu = gold.load(e); f, _ = features.cached(e["task_id"], rgb)
    emb = np.load(f"/root/subskin/tmp/pixel_clf/emb/sam_{e['task_id']}.npy")
    data.append({"task": e["task_id"], "group": e["group"], "f": f, "emb": emb, "region": np.isin(hu, (1, 2)), "y": hu == 2, "hw": hu.shape})
# label-free PCA over valid SAM grid cells of all photos
cells = []
for d in data:
    h, w = d["hw"]; s = 1024/max(h, w); gh, gw = max(1, int(h*s/16)), max(1, int(w*s/16))
    cells.append(d["emb"][:, :gh, :gw].reshape(256, -1).T)
pca = PCA(K, random_state=0).fit(np.concatenate(cells))
print("PCA explained variance", round(float(pca.explained_variance_ratio_.sum()), 3), flush=True)
for d in data:
    h, w = d["hw"]; s = 1024/max(h, w)
    grid = pca.transform(d["emb"].reshape(256, -1).T).reshape(64, 64, K).astype(np.float32)
    up = cv2.resize(grid, (1024, 1024), interpolation=cv2.INTER_LINEAR)[:int(round(h*s)), :int(round(w*s))]
    d["sam"] = cv2.resize(up, (w, h), interpolation=cv2.INTER_LINEAR)
    d["all"] = np.concatenate([d["f"], d["sam"]], -1); del d["emb"]
groups = sorted({d["group"] for d in data})
SETS = {"hand(全部手工特征)": slice(0, len(N)), "sam32(仅SAM特征)": slice(len(N), len(N)+K), "hand+sam32": slice(0, len(N)+K)}

def sample(d, cols):
    x = d["all"][..., cols]; out = []
    for idx, c in ((np.flatnonzero((d["region"] & d["y"]).ravel()), 1), (np.flatnonzero((d["region"] & ~d["y"]).ravel()), 0)):
        if idx.size == 0: continue
        pick = rng.choice(idx, min(PER_CLASS, idx.size), replace=False)
        out.append((x.reshape(-1, x.shape[-1])[pick], np.full(pick.size, c), np.full(pick.size, 1.0/pick.size)))
    return [np.concatenate([o[i] for o in out]) for i in range(3)]

def run(name, cols):
    t0 = time.time(); probs = {}
    for g in groups:
        tr = [sample(d, cols) for d in data if d["group"] != g]
        x, y, w = (np.concatenate([p[i] for p in tr]) for i in range(3))
        clf = HistGradientBoostingClassifier(max_iter=100, learning_rate=0.1, max_leaf_nodes=31, l2_regularization=1.0, random_state=0).fit(x, y, sample_weight=w*1e4)
        for d in data:
            if d["group"] == g:
                p = np.zeros(d["region"].shape, np.float32); idx = np.flatnonzero(d["region"].ravel())
                nf = d["all"][..., cols].shape[-1]
                p.ravel()[idx] = clf.predict_proba(d["all"][..., cols].reshape(-1, nf)[idx])[:, 1]; probs[d["task"]] = p
    def score(thr, ds):
        v = [dice(clean((probs[d["task"]] >= thr) & d["region"]) & d["region"], d["y"]) for d in ds]
        v = [x for x in v if x is not None]; return float(np.mean(v)) if v else 0.0
    grid = np.arange(0.1, 0.91, 0.05); rows = []
    for d in data:
        thr = max(grid, key=lambda t: score(t, [o for o in data if o["group"] != d["group"]]))
        pr = clean((probs[d["task"]] >= thr) & d["region"]) & d["region"]
        rows.append({"task": d["task"], "dice": dice(pr, d["y"]), "pred_ratio": round(100*pr.sum()/d["region"].sum(), 2), "gold_ratio": round(100*d["y"].sum()/d["region"].sum(), 2)})
    m = float(np.mean([r["dice"] for r in rows if r["dice"] is not None])); e = float(np.mean([abs(r["pred_ratio"]-r["gold_ratio"]) for r in rows]))
    print(f"{name:20s} mean Dice {m:.3f} ratio MAE {e:.1f}pp [{time.time()-t0:.0f}s]", flush=True)
    print("   per-image:", {r["task"]: round(r["dice"], 2) for r in rows}, flush=True)
    return {"set": name, "mean_dice": m, "ratio_mae_pp": e, "rows": rows}

res = [run(n, c) for n, c in SETS.items()]
json.dump(res, open("/root/subskin/tmp/pixel_clf/ablate2.json", "w"), indent=1); print("DONE")

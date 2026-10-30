"""Can the normal-skin reference be estimated WITHOUT labels? Iterative self-estimation of a local reference."""
import json, sys
import cv2, numpy as np
from skimage.color import rgb2lab, deltaE_ciede2000
sys.path.insert(0, "/root/subskin")
from ml.pixel_labeling import gold  # noqa: E402
exec(open("/root/subskin/tmp/pixel_clf/thr.py").read().split("data = []")[0].split("from ml.pixel_labeling import gold  # noqa: E402")[1])  # reuse disk/clean/dice/local_ref

data = []
for e in gold.registry():
    rgb, hu = gold.load(e); lab = rgb2lab(rgb.astype(np.float32)/255).astype(np.float32)
    data.append({"task": e["task_id"], "group": e["group"], "lab": lab, "region": np.isin(hu, (1, 2)), "y": hu == 2, "normal": hu == 1})

def score(lab, ref):
    dE = deltaE_ciede2000(lab, np.ascontiguousarray(ref)).astype(np.float32)
    return np.where(lab[..., 0] > ref[..., 0], dE, -dE)

def run(d, t, sigma, iters, init="dark", margin=5):
    lab, region = d["lab"], d["region"]
    L = lab[..., 0]
    normal = region & (L <= np.percentile(L[region], 50)) if init == "dark" else region.copy()
    for _ in range(iters):
        ref = local_ref(lab, normal, sigma)
        les = clean((score(lab, ref) > t) & region) & region
        grown = cv2.dilate(les.astype(np.uint8), disk(margin)).astype(bool)
        new_normal = region & ~grown
        if new_normal.sum() < 0.03 * region.sum(): break
        normal = new_normal
    ref = local_ref(lab, normal, sigma)
    return clean((score(lab, ref) > t) & region) & region

grid_t = (6, 8, 10)
results = {}
for sigma in (40, 80):
    for iters in (1, 3, 6):
        cache = {}
        for t in grid_t:
            cache[t] = {d["task"]: dice(run(d, t, sigma, iters), d["y"]) or 0.0 for d in data}
        for t in grid_t:
            m = float(np.mean(list(cache[t].values())))
            results[f"sigma{sigma}-iters{iters}-t{t}"] = {"mean_dice": round(m, 3), "per_image": {k: round(v, 2) for k, v in cache[t].items()}}
            print(f"sigma={sigma:3d} iters={iters} t={t:2d}  mean Dice {m:.3f}", flush=True)
best = max(results, key=lambda k: results[k]["mean_dice"])
print("\nbest (selected on these same 16 images -> optimistic):", best, results[best]["mean_dice"]); print(results[best]["per_image"])
# honest number: choose config by leaving each person out
keys = list(results); groups = sorted({d["group"] for d in data}); vals = []
for g in groups:
    ids = [d["task"] for d in data if d["group"] == g]
    others = [d["task"] for d in data if d["group"] != g]
    k = max(keys, key=lambda k: np.mean([results[k]["per_image"][o] for o in others]))
    vals += [results[k]["per_image"][i] for i in ids]
print("leave-one-person-out config selection: mean Dice", round(float(np.mean(vals)), 3))
json.dump(results, open("/root/subskin/tmp/pixel_clf/thr2.json", "w"), indent=1)

"""Paste synthetic lesions onto REAL normal-skin pixels of the gold photos (exact masks), keep only sampled training pixels.
Min colour difference comes from the visibility test (dE2000 >= 2.5 was seen 100% of the time)."""
import sys, time, json
import cv2, numpy as np
from skimage.color import rgb2lab, lab2rgb, deltaE_ciede2000
sys.path.insert(0, "/root/subskin")
from ml.pixel_labeling import features, gold  # noqa: E402

N_COMP, PER_CLASS = 2, 15000
rng = np.random.default_rng(0)

def lesion_color(base, s):
    k = 1 - min(0.6, 0.025 * s); return np.array([base[0] + 0.85 * s, base[1] * k, base[2] * k])

def offset_for(base, target):
    f = lambda s: float(deltaE_ciede2000(base[None, None].astype(float), lesion_color(base, s)[None, None])[0, 0])
    lo, hi = 0.0, 90.0
    for _ in range(30):
        m = (lo + hi) / 2
        if f(m) < target: lo = m
        else: hi = m
    c = lesion_color(base, (lo + hi) / 2); return c - base

def blob_alpha(shape, cx, cy, R, edge):
    h, w = shape; ph = rng.uniform(0, 6.28, 3)
    yy, xx = np.mgrid[0:h, 0:w]; dx, dy = xx - cx, yy - cy; th = np.arctan2(dy, dx)
    r = R * (1 + 0.18 * np.sin(2 * th + ph[0]) + 0.12 * np.sin(3 * th + ph[1]) + 0.08 * np.sin(5 * th + ph[2]))
    t = np.clip(0.5 + (r - np.hypot(dx, dy)) / edge, 0, 1); return (t * t * (3 - 2 * t)).astype(np.float32)

out_meta = []
for e in gold.registry():
    rgb, hu = gold.load(e); lab = rgb2lab(rgb.astype(np.float32) / 255).astype(np.float32)
    normal = hu == 1
    if normal.sum() < 20000: print("skip (little normal skin)", e["task_id"]); continue
    dist = cv2.distanceTransform(normal.astype(np.uint8), cv2.DIST_L2, 5)
    for k in range(N_COMP):
        t0 = time.time(); rgb2, hu2 = rgb.copy(), hu.copy(); info = []
        for _ in range(int(rng.integers(1, 4))):
            for _try in range(30):
                R = float(rng.uniform(18, 70)); cand = np.flatnonzero((dist > 1.4 * R).ravel())
                if cand.size: break
                R *= 0.7
            if not cand.size: continue
            cy, cx = divmod(int(rng.choice(cand)), hu.shape[1])
            target = float(np.exp(rng.uniform(np.log(2.5), np.log(15)))); edge = float(rng.choice([2.0, 4.0, 6.0]))
            a = blob_alpha(hu.shape, cx, cy, R, edge)
            disk = (np.hypot(*np.mgrid[0:hu.shape[0], 0:hu.shape[1]] - np.array([cy, cx])[:, None, None]) < 1.2 * R) & normal
            base = np.median(lab[disk], 0); off = offset_for(base, target)
            box = np.where(a > 0.01); y0, y1, x0, x1 = box[0].min(), box[0].max() + 1, box[1].min(), box[1].max() + 1
            lab_box = lab[y0:y1, x0:x1] + a[y0:y1, x0:x1, None] * off[None, None]
            conv = (np.clip(lab2rgb(lab_box), 0, 1) * 255).round().astype(np.uint8)
            m = a[y0:y1, x0:x1] > 0.01; rgb2[y0:y1, x0:x1][m] = conv[m]
            hu2[(a > 0.5) & normal] = 2; info.append({"R": round(R), "dE": round(target, 1), "edge": edge})
        feats, _ = features.feature_maps(rgb2)
        region = np.isin(hu2, (1, 2)); y = hu2 == 2; xs, ys = [], []
        for idx, c in ((np.flatnonzero((region & y).ravel()), 1), (np.flatnonzero((region & ~y).ravel()), 0)):
            if idx.size == 0: continue
            pick = rng.choice(idx, min(PER_CLASS, idx.size), replace=False)
            xs.append(feats.reshape(-1, feats.shape[-1])[pick]); ys.append(np.full(pick.size, c))
        np.savez_compressed(f"/root/subskin/tmp/pixel_clf/comp/c_{e['task_id']}_{k}.npz", x=np.concatenate(xs), y=np.concatenate(ys), group=e["group"], task=e["task_id"])
        out_meta.append({"task": e["task_id"], "k": k, "blobs": info, "sec": round(time.time() - t0, 1)})
        print("composite", e["task_id"], k, info, f"{time.time() - t0:.0f}s", flush=True)
json.dump(out_meta, open("/root/subskin/tmp/pixel_clf/comp/meta.json", "w"), indent=1); print("DONE")

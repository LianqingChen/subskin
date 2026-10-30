"""Scale-up: ~10,000 synthetic composites (lesions pasted on REAL normal skin, exact masks). min dE2000 2.5 (visibility test).
Resumable, parallel, low priority. Output: comp2/{task}_{chunk}.npz with sampled training pixels only."""
import os, sys, time, json, multiprocessing as mp
import numpy as np

PER_CLASS, CHUNK, TOTAL = 400, 50, 10000
OUT = "/root/subskin/tmp/pixel_clf/comp2"

def lesion_color(base, s):
    k = 1 - min(0.6, 0.025 * s); return np.array([base[0] + 0.85 * s, base[1] * k, base[2] * k])

def work(args):
    entry, chunk = args
    path = f"{OUT}/{entry['task_id']}_{chunk}.npz"
    if os.path.exists(path): return entry["task_id"], chunk, 0, 0.0
    os.nice(19)
    sys.path.insert(0, "/root/subskin")
    import cv2; cv2.setNumThreads(1)
    from skimage.color import rgb2lab, lab2rgb, deltaE_ciede2000
    from ml.pixel_labeling import features, gold
    rng = np.random.default_rng(entry["task_id"] * 1000 + chunk)
    rgb, hu = gold.load(entry); lab = rgb2lab(rgb.astype(np.float32) / 255).astype(np.float32)
    normal = hu == 1; dist = cv2.distanceTransform(normal.astype(np.uint8), cv2.DIST_L2, 5)
    H, W = hu.shape; yy, xx = np.mgrid[0:H, 0:W]
    def offset_for(base, target):
        f = lambda s: float(deltaE_ciede2000(base[None, None].astype(float), lesion_color(base, s)[None, None])[0, 0])
        lo, hi = 0.0, 90.0
        for _ in range(26):
            m = (lo + hi) / 2
            if f(m) < target: lo = m
            else: hi = m
        return lesion_color(base, (lo + hi) / 2) - base
    xs, ys, cids = [], [], []; t0 = time.time()
    for k in range(CHUNK):
        rgb2, hu2 = rgb.copy(), hu.copy()
        for _ in range(int(rng.integers(1, 4))):
            cand = np.array([])
            for _try in range(30):
                R = float(rng.uniform(18, 70)); cand = np.flatnonzero((dist > 1.4 * R).ravel())
                if cand.size: break
            if not cand.size: continue
            cy, cx = divmod(int(rng.choice(cand)), W)
            target = float(np.exp(rng.uniform(np.log(2.5), np.log(15)))); edge = float(rng.choice([2.0, 4.0, 6.0]))
            ph = rng.uniform(0, 6.28, 3); dx, dy = xx - cx, yy - cy; th = np.arctan2(dy, dx); dd = np.hypot(dx, dy)
            r = R * (1 + 0.18 * np.sin(2 * th + ph[0]) + 0.12 * np.sin(3 * th + ph[1]) + 0.08 * np.sin(5 * th + ph[2]))
            t = np.clip(0.5 + (r - dd) / edge, 0, 1); a = (t * t * (3 - 2 * t)).astype(np.float32)
            base = np.median(lab[(dd < 1.2 * R) & normal], 0); off = offset_for(base, target)
            box = np.where(a > 0.01); y0, y1, x0, x1 = box[0].min(), box[0].max() + 1, box[1].min(), box[1].max() + 1
            conv = (np.clip(lab2rgb(lab[y0:y1, x0:x1] + a[y0:y1, x0:x1, None] * off[None, None]), 0, 1) * 255).round().astype(np.uint8)
            m = a[y0:y1, x0:x1] > 0.01; rgb2[y0:y1, x0:x1][m] = conv[m]; hu2[(a > 0.5) & normal] = 2
        feats, _ = features.feature_maps(rgb2)
        region = np.isin(hu2, (1, 2)); y = hu2 == 2
        for idx, c in ((np.flatnonzero((region & y).ravel()), 1), (np.flatnonzero((region & ~y).ravel()), 0)):
            if idx.size == 0: continue
            pick = rng.choice(idx, min(PER_CLASS, idx.size), replace=False)
            xs.append(feats.reshape(-1, feats.shape[-1])[pick]); ys.append(np.full(pick.size, c, np.int8)); cids.append(np.full(pick.size, k, np.int16))
    np.savez_compressed(path + ".tmp.npz", x=np.concatenate(xs), y=np.concatenate(ys), cid=np.concatenate(cids), group=entry["group"], task=entry["task_id"])
    os.replace(path + ".tmp.npz", path)
    return entry["task_id"], chunk, CHUNK, time.time() - t0

if __name__ == "__main__":
    sys.path.insert(0, "/root/subskin")
    from ml.pixel_labeling import gold
    os.makedirs(OUT, exist_ok=True)
    entries = gold.registry()
    import numpy as _np
    ok = []
    for e in entries:                                   # only photos with enough real normal skin to paste onto
        _, hu = gold.load(e)
        if int((hu == 1).sum()) >= 20000: ok.append(e)
    per_base = -(-TOTAL // len(ok)); chunks = -(-per_base // CHUNK)
    print(f"bases {len(ok)}/{len(entries)} | composites per base {chunks * CHUNK} | total {len(ok) * chunks * CHUNK}", flush=True)
    tasks = [(e, c) for c in range(chunks) for e in ok]  # chunk-major so partial runs cover all bases evenly
    done = 0; t0 = time.time()
    with mp.get_context("spawn").Pool(4) as pool:
        for tid, ch, n, sec in pool.imap_unordered(work, tasks):
            done += 1
            if done % 8 == 0 or done == len(tasks): print(f"{done}/{len(tasks)} chunks | {time.time() - t0:.0f}s elapsed", flush=True)
    json.dump({"bases": [e["task_id"] for e in ok], "chunks": chunks, "chunk": CHUNK}, open(f"{OUT}/meta.json", "w"))
    print("DONE", flush=True)

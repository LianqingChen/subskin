"""Pixel-level vitiligo labeling toolkit. Workflow + rules: .agents/skills/vitiligo-pixel-labeling/SKILL.md

    python -m ml.pixel_labeling draft 199                # general model first draft (+ decisions skeleton)
    python -m ml.pixel_labeling prep 189                 # skin mask, score heatmap, numbered candidates + galleries
    python -m ml.pixel_labeling gallery 189 10 16 21     # centred 5x crops of chosen candidates
    python -m ml.pixel_labeling grid 189 520 210 600 260 # 10px coordinate grid (nails, polygons)
    python -m ml.pixel_labeling compose 189              # decisions/189.json -> labels + overview
    python -m ml.pixel_labeling view 189 500 170 1010 600
    python -m ml.pixel_labeling apply 189 --actor 9      # write as AI draft (pending upload/job tasks only)
    python -m ml.pixel_labeling review 189               # AI draft vs latest human revision
    python -m ml.pixel_labeling train                    # retrain general model on every gold (LOGO card)
    python -m ml.pixel_labeling bench --tag note         # score auto drafts + decision replays vs every gold
"""

import argparse
import json

import numpy as np

from ml.pixel_labeling import core, ops, render, review, system_io as sio
from web.backend.services.labeling import class_map

BASES = ("candidates", "face-gb-v1", "pixel-gb-v2")


def _prep(tid: int):
    rgb = sio.load_image(tid)
    p = core.params_of(sio.load_decisions(tid))
    extras = {}
    skin = core.skin_mask(rgb, p, extras)
    score, gscore = core.score_pair(rgb, skin, p)
    extras["_global_score"] = gscore
    lbl, comps = core.candidates(score, skin, p)
    return rgb, p, skin, score, lbl, comps, extras


def cmd_prep(a):
    rgb, p, skin, score, lbl, comps, extras = _prep(a.task)
    wd = sio.work_dir(a.task)
    json.dump(comps, open(wd / "candidates.json", "w"))
    render.heat(rgb, score, skin, wd / "heat.jpg")
    h, w = skin.shape
    sk = rgb.copy(); sk[~skin] = (sk[~skin] * 0.25).astype(np.uint8)
    over = render.draw_candidates(sk, lbl, comps)
    scale = min(2.0, 1400 / max(h, w))
    render.pair(rgb, over, (0, 0, w, h), scale, [(c["cx"], c["cy"], str(c["id"])) for c in comps]).save(
        wd / "candidates.jpg", quality=88)
    interior = [c for c in comps if c["rim"] < 0.2 and c["area"] >= 30]
    files = _gallery(a.task, rgb, lbl, comps, [c["id"] for c in interior], "g")
    risk = {}
    if p.get("baseline_mode", "local") in ("local", "hybrid"):
        risk = core.large_plaque_risk(skin, comps, rgb)
    out = {"skin_px": int(skin.sum()), "baseline_mode": p.get("baseline_mode", "local"),
           "candidates": len(comps), "interior_ge30": [c["id"] for c in interior],
           "edge_or_small": [c["id"] for c in comps if c not in interior],
           "large_plaque_risk": risk,
           "files": [str(wd / "heat.jpg"), str(wd / "candidates.jpg"), *files]}
    if extras.get("lips") is not None:
        np.save(wd / "lips.npy", extras["lips"])
    print(json.dumps(out, ensure_ascii=False))


def _gallery(tid, rgb, lbl, comps, ids, prefix):
    by = {c["id"]: c for c in comps}
    wd = sio.work_dir(tid)
    tiles = []
    for i in ids:
        c = by[i]
        over = render.draw_candidates(rgb, lbl, [c])
        tiles.append(render.centred_tile(rgb, [over], c["cx"], c["cy"],
                                         f"#{i} ({c['cx']},{c['cy']}) area={c['area']} score={c['score']} rim={c['rim']}"))
    files = []
    for k in range(0, len(tiles), 8):
        f = wd / f"{prefix}_{k // 8 + 1}.jpg"
        render.sheet(tiles[k:k + 8], f)
        files.append(str(f))
    return files


def cmd_gallery(a):
    rgb, _, _, _, lbl, comps, _ = _prep(a.task)
    print(_gallery(a.task, rgb, lbl, comps, a.ids, a.name))


def cmd_grid(a):
    rgb = sio.load_image(a.task)
    f = sio.work_dir(a.task) / f"grid_{a.x0}_{a.y0}.jpg"
    render.grid_crop(rgb, (a.x0, a.y0, a.x1, a.y1), a.scale, f)
    print(f)


def must_decide(comps, p):
    """Interior blobs >=30px, plus edge blobs that are clearly whiter (lesson L-188-1/L-188-4)."""
    return [c["id"] for c in comps if (c["rim"] < 0.2 and c["area"] >= 30) or c["score"] >= p["t_hi"]]


def _compose_candidates(tid, d):
    rgb, p, skin, score, lbl, comps, extras = _prep(tid)
    decided = set(d.get("lesion", []) + d.get("unknown", []) + d.get("reject", [])
                  + [i for k in ("lesion_roi", "unknown_roi") for i, _ in d.get(k, [])])
    missing = [i for i in must_decide(comps, p) if i not in decided]
    if missing and not d.get("legacy_implicit_reject"):
        raise SystemExit(f"undecided candidates {missing}: put each in lesion / unknown / reject "
                         f"(gallery: python -m ml.pixel_labeling gallery {tid} {' '.join(map(str, missing))})")
    if p["skin"].get("method") == "mediapipe" and "lips_polygons" not in d and extras.get("lips") is not None:
        d = {**d, "_lips_mask": extras["lips"]}
    if extras.get("_global_score") is not None:
        d = {**d, "_global_score": extras["_global_score"]}
    return rgb, core.compose(skin, score, lbl, comps, d, p), extras


def _shift_lab(rgb, skin, shift):
    """Move skin colour by a fixed Lab offset (OpenCV units) — cross-photo colour cast, L-181-1."""
    import cv2
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    for c, k in enumerate(("dL", "dA", "dB")):
        lab[..., c][skin] = np.clip(lab[..., c][skin] + float(shift.get(k, 0)), 0, 255)
    return cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_LAB2RGB)


def _compose_face_gb(tid, d):
    from ml.pixel_labeling import face_gb
    rgb = sio.load_image(tid)
    p = core.params_of(d)
    p["skin"] = {**p["skin"], "method": "mediapipe"}
    extras = {}
    skin = core.skin_mask(rgb, p, extras)
    bp = d.get("base_params", {})
    src = _shift_lab(rgb, skin, bp["lab_shift"]) if bp.get("lab_shift") else rgb
    les, _ = face_gb.predict_lesion(src, skin, p, threshold=bp.get("threshold"), lips=extras.get("lips"))
    labels = np.zeros(skin.shape, np.uint8)
    labels[skin | les] = 1
    labels[les] = 2
    return rgb, labels, extras


def _compose_pixel_gb(tid, d):
    from ml.pixel_labeling import features, pixel_model
    rgb = sio.load_image(tid)
    bundle = pixel_model.load()
    feats, side = features.cached(tid, rgb)
    thr = d.get("base_params", {}).get("threshold", bundle["lesion_threshold"])
    return rgb, pixel_model.labels_from(pixel_model.proba(bundle, feats), side, thr), {"lips": side["lips"]}


def _overrides(labels, d):
    """Explicit polygons win over any base/op. Occlusion last."""
    h, w = labels.shape
    out = labels.copy()
    for key, value in (("background_polygons", 0), ("normal_polygons", 1), ("lesion_polygons", 2),
                       ("unknown_polygons", 255), ("unreadable_polygons", 4), ("occlusion_polygons", 3)):
        m = core._polys(h, w, d.get(key))
        out[m] = value
    return out


def _compose(tid):
    d = sio.load_decisions(tid)
    if not d:
        raise SystemExit(f"write ml/pixel_labeling/decisions/{tid}.json first (or run: draft {tid})")
    base = d.get("base", "candidates")
    if base not in BASES:
        raise SystemExit(f"unknown base {base!r}; use one of {BASES}")
    if base == "candidates":
        rgb, labels, extras = _compose_candidates(tid, d)  # polygons handled inside core.compose
        return rgb, ops.apply(labels, rgb, extras, d.get("ops"))
    rgb, labels, extras = (_compose_face_gb if base == "face-gb-v1" else _compose_pixel_gb)(tid, d)
    labels = ops.apply(labels, rgb, extras, d.get("ops"))
    return rgb, _overrides(labels, d)


def cmd_compose(a):
    rgb, labels = _compose(a.task)
    wd = sio.work_dir(a.task)
    np.save(wd / "labels.npy", labels)
    h, w = labels.shape
    render.pair(rgb, render.draw_labels(rgb, labels), (0, 0, w, h), min(1.0, 1400 / max(h, w))).save(
        wd / "result.jpg", quality=88)
    print(json.dumps({"stats": class_map.stats(labels), "file": str(wd / "result.jpg")}, ensure_ascii=False))


def cmd_draft(a):
    """First draft for a new task from the general model; writes a decisions skeleton if none."""
    from ml.pixel_labeling import pixel_model
    f = sio.DECISIONS / f"{a.task}.json"
    if not f.exists():
        f.write_text(json.dumps({
            "task_id": a.task, "base": "pixel-gb-v2", "model_id": pixel_model.MODEL_ID,
            "image": "一句话：部位+斑型+特殊坑", "ops": [],
            "lesion_polygons": [], "normal_polygons": [], "unknown_polygons": [],
            "occlusion_polygons": [], "background_polygons": [],
            "notes": {"_method": "pixel-gb-v2 初稿；修订只加 ops/多边形，并写明 lesson"},
        }, ensure_ascii=False, indent=2))
    cmd_compose(a)


def cmd_train(a):
    from ml.pixel_labeling import pixel_model
    card = pixel_model.train_all()
    print(json.dumps({"logo_mean": card["logo_mean"], "lesion_threshold": card["lesion_threshold"],
                      "card": str(pixel_model.CARD)}, ensure_ascii=False))


def cmd_bench(a):
    from ml.pixel_labeling import bench
    print(bench.run(a.tag))


def cmd_view(a):
    rgb = sio.load_image(a.task)
    labels = np.load(sio.work_dir(a.task) / "labels.npy")
    f = sio.work_dir(a.task) / f"view_{a.x0}_{a.y0}_{a.x1}_{a.y1}.jpg"
    render.pair(rgb, render.draw_labels(rgb, labels), (a.x0, a.y0, a.x1, a.y1), a.scale).save(f, quality=90)
    print(f)


def cmd_apply(a):
    _, labels = _compose(a.task)
    d = sio.load_decisions(a.task)
    sio.apply_draft(a.task, labels, d.get("model_id", "pixel-reviewed-v1"),
                    d.get("model_source", "逐像素：颜色分割皮肤 + 局部基线白度候选 + 逐块放大人工核对（不确定处=255）"), a.actor)
    print(json.dumps({"applied": a.task, "stats": class_map.stats(labels)}, ensure_ascii=False))


def cmd_review(a):
    rgb = sio.load_image(a.task)
    d = sio.load_decisions(a.task)
    ai = sio.ai_draft(a.task)
    info, human = sio.latest_submission(a.task, a.submission)
    result = {"task_id": a.task, "submission": info, "ai_model": d.get("model_id"),
              **review.compare(rgb, ai, human, d, core.params_of(d))}
    sio.REVIEWS.mkdir(exist_ok=True)
    out = sio.REVIEWS / f"{a.task}-s{info['submission_id']}.json"
    review.dump(result, out)
    files = review.render_review(rgb, ai, human, result, sio.work_dir(a.task))
    subst = [{k: r[k] for k in ("no", "category", "area", "cx", "cy", "median_score", "candidates")}
             for r in result["regions"] if r["kind"] == "substantive"]
    print(json.dumps({"summary": result["summary"], "substantive_regions": subst, "json": str(out), "files": files},
                     ensure_ascii=False, indent=1))


def cmd_face_gb(a):
    """Face-plaque HistGB prior (L-180-5). Writes labels.npy + result.jpg; optional --apply."""
    from ml.pixel_labeling import face_gb
    rgb = sio.load_image(a.task)
    p = core.params_of(sio.load_decisions(a.task) or {"params": {"skin": {"method": "mediapipe"}}})
    if p["skin"].get("method") != "mediapipe":
        p["skin"] = {**p["skin"], "method": "mediapipe"}
    extras = {}
    skin = core.skin_mask(rgb, p, extras)
    les, meta = face_gb.predict_lesion(rgb, skin, p, threshold=a.threshold, lips=extras.get("lips"))
    labels = np.zeros(skin.shape, np.uint8)
    labels[skin | les] = 1
    labels[les] = 2
    if extras.get("lips") is not None:
        labels[extras["lips"]] = 1
        labels[les & ~extras["lips"]] = 2
    wd = sio.work_dir(a.task)
    np.save(wd / "labels.npy", labels)
    h, w = labels.shape
    render.pair(rgb, render.draw_labels(rgb, labels), (0, 0, w, h), min(1.0, 1400 / max(h, w))).save(
        wd / "result.jpg", quality=88)
    out = {"stats": class_map.stats(labels), "meta": meta, "file": str(wd / "result.jpg")}
    if a.apply:
        sio.apply_draft(a.task, labels, meta.get("model_id", "face-plaque-gb-v1"),
                        "面颈大斑 HistGB 先验（Lab+白度分，L-180-5 校准）", a.actor)
        out["applied"] = a.task
    print(json.dumps(out, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser(prog="python -m ml.pixel_labeling")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("prep", "compose", "draft"):
        sub.add_parser(name).add_argument("task", type=int)
    sub.add_parser("train")
    sub.add_parser("bench").add_argument("--tag", default="")
    g = sub.add_parser("gallery"); g.add_argument("task", type=int); g.add_argument("ids", type=int, nargs="+")
    g.add_argument("--name", default="pick")
    for name in ("grid", "view"):
        s = sub.add_parser(name); s.add_argument("task", type=int)
        for k in ("x0", "y0", "x1", "y1"):
            s.add_argument(k, type=int)
        s.add_argument("--scale", type=int, default=8 if name == "grid" else 2)
    s = sub.add_parser("apply"); s.add_argument("task", type=int); s.add_argument("--actor", type=int, required=True)
    s = sub.add_parser("review"); s.add_argument("task", type=int); s.add_argument("--submission", type=int)
    s = sub.add_parser("face-gb"); s.add_argument("task", type=int)
    s.add_argument("--threshold", type=float, default=None)
    s.add_argument("--apply", action="store_true")
    s.add_argument("--actor", type=int, default=9)
    a = ap.parse_args()
    cmd = a.cmd.replace("-", "_")
    globals()[f"cmd_{cmd}"](a)


if __name__ == "__main__":
    main()

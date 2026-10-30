"""Compare the AI draft with the human revision: metrics + numbered disagreement regions.

The agent then judges each substantive region (is the human right?) and writes the lesson to
``.agents/skills/vitiligo-pixel-labeling/LESSONS.md``. This module only measures; it never decides.
"""

import json
from typing import Any, Dict, List, Optional

import cv2
import numpy as np

from ml.pixel_labeling import core, render

NAMES = {0: "background", 1: "normal", 2: "lesion", 3: "occlusion", 4: "unreadable", 255: "unknown"}
# (ai class, human class) -> error category, from the AI's point of view
CATEGORY = {
    (1, 2): "missed_lesion", (255, 2): "unknown_was_lesion", (0, 2): "missed_lesion",
    (2, 1): "overcalled_lesion", (255, 1): "unknown_was_normal",
    (0, 1): "missed_skin", (1, 0): "overcalled_skin", (2, 0): "overcalled_skin", (255, 0): "overcalled_skin",
    (2, 255): "lesion_too_confident", (1, 255): "normal_too_confident",
}
COLORS = {
    "missed_lesion": (255, 0, 0), "unknown_was_lesion": (255, 120, 120), "overcalled_lesion": (0, 120, 255),
    "unknown_was_normal": (120, 200, 255), "missed_skin": (0, 220, 0), "overcalled_skin": (160, 0, 255),
    "occlusion": (255, 160, 0), "lesion_too_confident": (255, 255, 0), "normal_too_confident": (200, 200, 0),
    "other": (128, 128, 128),
}
MIN_REGION = 20
BAND = 3  # px from an AI class edge: brush-stroke jitter, not a judgement error


def _category(a: int, h: int) -> str:
    if a == 3 or h == 3:
        return "occlusion"
    return CATEGORY.get((a, h), "other")


def _dice(a: np.ndarray, b: np.ndarray) -> Optional[float]:
    s = int(a.sum() + b.sum())
    return round(2 * int((a & b).sum()) / s, 4) if s else None


def compare(rgb: np.ndarray, ai: np.ndarray, human: np.ndarray, decisions: Dict[str, Any],
            p: Dict[str, Any]) -> Dict[str, Any]:
    skin = core.skin_mask(rgb, p)
    score = core.depigmentation_score(rgb, skin, p["baseline_sigma"])
    lbl, comps = core.candidates(score, skin, p)
    lab_to_id = {c["lab"]: c["id"] for c in comps}
    decided = {i: k for k in ("lesion", "unknown", "reject") for i in decisions.get(k, [])}
    for k in ("lesion", "unknown"):
        for i, _ in decisions.get(f"{k}_roi", []):
            decided.setdefault(i, f"{k}(partial roi)")

    edges = np.zeros(ai.shape, bool)
    for v in np.unique(ai):
        m = (ai == v).astype(np.uint8)
        edges |= cv2.morphologyEx(m, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)).astype(bool)
    band = cv2.dilate(edges.astype(np.uint8), core.disk(BAND)).astype(bool)

    classes = sorted(NAMES)
    confusion = {NAMES[a]: {NAMES[h]: int(((ai == a) & (human == h)).sum()) for h in classes} for a in classes}
    known = human != 255
    summary = {
        "lesion_dice": _dice(ai == 2, human == 2),
        "skin_dice": _dice(np.isin(ai, (1, 2, 255)), np.isin(human, (1, 2, 255))),
        "pixel_agreement_on_human_known": round(float((ai[known] == human[known]).mean()), 4) if known.any() else None,
        "ai_lesion_ratio": core_ratio(ai), "human_lesion_ratio": core_ratio(human),
        "changed_pixels": int((ai != human).sum()),
    }

    regions: List[Dict[str, Any]] = []
    cat_map = np.full(ai.shape, "", object)
    diff = ai != human
    for a, h in {(int(x), int(y)) for x, y in zip(ai[diff], human[diff])}:
        m = (ai == a) & (human == h)
        cat = _category(a, h)
        cat_map[m] = cat
        n, cl, st, cen = cv2.connectedComponentsWithStats(m.astype(np.uint8), 8)
        for i in range(1, n):
            area = int(st[i, cv2.CC_STAT_AREA])
            if area < MIN_REGION:
                continue
            r = cl == i
            in_band = float((r & band).sum()) / area
            hit = np.unique(lbl[r]); hit = [lab_to_id[x] for x in hit if x in lab_to_id]
            near = cv2.dilate(r.astype(np.uint8), core.disk(6)).astype(bool)
            hit_near = sorted({lab_to_id[x] for x in np.unique(lbl[near]) if x in lab_to_id} - set(hit))
            regions.append({
                "ai": NAMES[a], "human": NAMES[h], "category": cat, "area": area,
                "cx": int(cen[i][0]), "cy": int(cen[i][1]),
                "bbox": [int(st[i, 0]), int(st[i, 1]), int(st[i, 0] + st[i, 2]), int(st[i, 1] + st[i, 3])],
                "kind": "boundary" if in_band > 0.8 else "substantive",
                "median_score": round(float(np.median(score[r])), 1),
                "candidates": [{"id": c, "ai_decision": decided.get(c, "normal (not selected)")} for c in hit],
                "adjacent_candidates": hit_near,
                "below_candidate_threshold": not hit and float(np.percentile(score[r], 90)) < p["t_hi"],
            })
    regions.sort(key=lambda r: (r["kind"] != "substantive", -r["area"]))
    for k, r in enumerate(regions, 1):
        r["no"] = k
    by_cat: Dict[str, Dict[str, int]] = {}
    for r in regions:
        d = by_cat.setdefault(r["category"], {"substantive": 0, "boundary": 0})
        d[r["kind"]] += r["area"]
    summary["pixels_by_category"] = by_cat
    return {"summary": summary, "confusion_ai_rows_human_cols": confusion, "regions": regions}


def core_ratio(labels: np.ndarray) -> float:
    n, l = int((labels == 1).sum()), int((labels == 2).sum())
    return round(100 * l / max(1, n + l), 2)


def render_review(rgb: np.ndarray, ai: np.ndarray, human: np.ndarray, result: Dict[str, Any], wd) -> List[str]:
    over = (rgb * 0.45).astype(np.uint8)
    for r in result["regions"]:
        x0, y0, x1, y1 = r["bbox"]
        sub = (ai[y0:y1, x0:x1] == {v: k for k, v in NAMES.items()}[r["ai"]]) & \
              (human[y0:y1, x0:x1] == {v: k for k, v in NAMES.items()}[r["human"]])
        over[y0:y1, x0:x1][sub] = COLORS[r["category"]]
    texts = [(r["cx"], r["cy"], str(r["no"])) for r in result["regions"] if r["kind"] == "substantive"]
    h, w = rgb.shape[:2]
    scale = min(1.0, 1400 / max(h, w))
    render.pair(rgb, over, (0, 0, w, h), scale, texts).save(wd / "review_overview.jpg", quality=88)
    ai_v, hu_v = render.draw_labels(rgb, ai), render.draw_labels(rgb, human)
    tiles = [render.centred_tile(rgb, [ai_v, hu_v], r["cx"], r["cy"],
                                 f"#{r['no']} {r['category']} {r['ai']}→{r['human']} area={r['area']} score={r['median_score']}",
                                 radius=max(32, min(80, (r["bbox"][2] - r["bbox"][0]) // 2 + 12)), scale=4)
             for r in result["regions"] if r["kind"] == "substantive"][:24]
    files = [str(wd / "review_overview.jpg")]
    for k in range(0, len(tiles), 6):
        f = wd / f"review_regions_{k // 6 + 1}.jpg"
        render.sheet(tiles[k:k + 6], f, cols=1)
        files.append(str(f))
    return files


def dump(result: Dict[str, Any], path) -> None:
    path.write_text(json.dumps(result, ensure_ascii=False, indent=1))

"""Collect RGB disagreement leads for human review.

The colour score uses regions where both masks agree to estimate a within-photo
colour axis. An optional vision model compares a blinded pair of outlines in a
randomized order. Agreement between these RGB cues prioritizes reviewer attention.
The report records coverage and leaves acceptance to the reviewer.
"""

import json
import random
from pathlib import Path
from typing import Dict, List, Optional

import cv2
import numpy as np
from PIL import Image, ImageDraw

from ml.pixel_labeling import core
from ml.vlm_labeling.client import VLM, image_part
from ml.vlm_labeling.regions import _font


def _lab(rgb: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)


def colour_centres(rgb: np.ndarray, ai: np.ndarray, gold: np.ndarray) -> Optional[Dict[str, np.ndarray]]:
    lab = _lab(rgb)
    agree_les = (ai == 2) & (gold == 2)
    agree_nor = (ai == 1) & (gold == 1)
    # erode so the centres come from cores, not from the borders under dispute
    k = np.ones((7, 7), np.uint8)
    agree_les = cv2.erode(agree_les.astype(np.uint8), k).astype(bool) | (agree_les & (agree_les.sum() < 2000))
    agree_nor = cv2.erode(agree_nor.astype(np.uint8), k).astype(bool) | (agree_nor & (agree_nor.sum() < 2000))
    if not agree_les.any() or not agree_nor.any():
        return None
    return {"L": np.median(lab[agree_les], 0), "N": np.median(lab[agree_nor], 0)}


def boundary_contrast(rgb: np.ndarray, labels: np.ndarray, band: int = 3) -> Optional[float]:
    """Mean ΔE between the ring just inside and just outside the lesion boundary (skin only)."""
    lab = _lab(rgb)
    les = (labels == 2).astype(np.uint8)
    skin = np.isin(labels, (1, 2))
    k = core.disk(band)
    inner = les.astype(bool) & ~cv2.erode(les, k).astype(bool)
    outer = cv2.dilate(les, k).astype(bool) & ~les.astype(bool) & skin
    if inner.sum() < 50 or outer.sum() < 50:
        return None
    return round(float(np.linalg.norm(np.median(lab[inner], 0) - np.median(lab[outer], 0))), 2)


def disputes(ai: np.ndarray, gold: np.ndarray, min_area: int = 150) -> List[Dict]:
    out = []
    for ai_says, predicted, approved in (("L", 2, 1), ("N", 1, 2)):
        diff = (ai == predicted) & (gold == approved)
        n, cc, stats, _ = cv2.connectedComponentsWithStats(diff.astype(np.uint8), connectivity=8)
        for i in range(1, n):
            x, y, width, height, area = map(int, stats[i])
            if area < min_area:
                continue
            out.append({"id": len(out), "area": area, "bbox": [x, y, x + width, y + height],
                        "ai_says": ai_says, "_mask": cc == i})
    out.sort(key=lambda d: -d["area"])
    return out


def colour_verdict(rgb: np.ndarray, d: Dict, centres: Dict[str, np.ndarray]) -> Dict:
    """Position of disputed pixels on this person's *depigmentation axis*: normal-core -> lesion-core
    direction in (L*, b*) only.  Redness (a*) is ignored: on 195 the agreed lesion core was inflamed
    pink while depigmented fingers were not, and nearest-centre in full Lab sided with the wrong label."""
    lab = _lab(rgb)[d["_mask"]][:, [0, 2]]
    n, l = centres["N"][[0, 2]], centres["L"][[0, 2]]
    axis = l - n
    squared_length = float(axis @ axis)
    if squared_length < 1e-6:
        return {"colour_winner": "?"}
    t = ((lab - n) @ axis) / squared_length  # 0 = normal core, 1 = lesion core
    frac_lesion_like = float((t > 0.5).mean())
    ai_l = d["ai_says"] == "L"
    support_ai = frac_lesion_like if ai_l else 1 - frac_lesion_like
    winner = "ai" if support_ai > 0.6 else "gold" if support_ai < 0.4 else "tie"
    return {"lesion_like": round(frac_lesion_like, 3), "axis_t_median": round(float(np.median(t)), 3),
            "colour_winner": winner}


def _outline(crop: np.ndarray, mask: np.ndarray, colour=(0, 255, 255)) -> Image.Image:
    im = crop.copy()
    cnts, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    cv2.drawContours(im, cnts, -1, colour, 1)
    return Image.fromarray(im)


def referee_sheet(rgb: np.ndarray, ai: np.ndarray, gold: np.ndarray, d: Dict, a_is_ai: bool,
                  cell: int = 420) -> Image.Image:
    H, W = rgb.shape[:2]
    x0, y0, x1, y1 = d["bbox"]
    side = int(max(x1 - x0, y1 - y0) * 2.2) + 40
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    bx0, by0 = max(0, cx - side // 2), max(0, cy - side // 2)
    bx1, by1 = min(W, bx0 + side), min(H, by0 + side)
    crop = rgb[by0:by1, bx0:bx1]
    ma, mb = (ai, gold) if a_is_ai else (gold, ai)
    panels = [Image.fromarray(crop), _outline(crop, ma[by0:by1, bx0:bx1] == 2), _outline(crop, mb[by0:by1, bx0:bx1] == 2)]
    s = cell / max(crop.shape[:2])
    size = (int(crop.shape[1] * s), int(crop.shape[0] * s))
    sheet = Image.new("RGB", (size[0] * 3 + 20, size[1] + 34), (30, 30, 30))
    dr = ImageDraw.Draw(sheet)
    f = _font(22)
    for j, (p, t) in enumerate(zip(panels, ("原图", "A", "B"))):
        sheet.paste(p.resize(size, Image.LANCZOS), (j * (size[0] + 10), 34))
        dr.text((j * (size[0] + 10) + 8, 4), t, fill=(0, 255, 255), font=f)
    return sheet


def referee(vlm: VLM, sheet: Image.Image, idx: int) -> str:
    text = ("独立比较普通 RGB 中可见的边界。三张图是同一处皮肤：第 1 张原图；第 2、3 张分别画了"
            "候选轮廓 A 和 B（青色细线圈出「白斑 = 色素脱失的皮肤」）。只比较两条轮廓在这处的差异："
            "哪一条更准确地沿着真实的脱色边界（把脱色皮肤圈进来、把正常肤色留在外面）？"
            "核对受光、高光、唇红及眉区可见皮肤。原图证据不足时选择 same。"
            '输出 JSON：{"better": "A" 或 "B" 或 "same", "why": "一句话"}')
    r = vlm.ask(f"referee:{idx}", "只比较图像可见外观，输出待人工核对的建议。", [
        image_part(sheet), {"type": "text", "text": text},
    ])
    b = str((r["data"] or {}).get("better", "")).strip().upper()
    return b if b in ("A", "B", "SAME") else "?"


def run(task_id: int, rgb: np.ndarray, ai: np.ndarray, gold: np.ndarray, out_dir: Path,
        referee_model: Optional[str] = "qwen3.7-plus", max_components: int = 40, seed: int = 0) -> Dict:
    if ai.ndim != 2 or ai.shape != gold.shape or rgb.shape != (*ai.shape, 3):
        raise ValueError("Original RGB and both coatings must share the same image grid")
    out_dir.mkdir(parents=True, mode=0o700, exist_ok=True)
    rng = random.Random(seed)
    ds = disputes(ai, gold)[:max_components]
    cen = colour_centres(rgb, ai, gold) if ds else None
    vlm = VLM(referee_model, out_dir / "referee.jsonl") if referee_model else None
    rows = []
    for d in ds:
        row = {k: v for k, v in d.items() if not k.startswith("_")}
        if cen is None:
            row["colour_winner"] = "?"
        else:
            row.update(colour_verdict(rgb, d, cen))
        a_is_ai = rng.random() < 0.5
        sheet = referee_sheet(rgb, ai, gold, d, a_is_ai)
        sheet_name = f"dispute_{d['id']:02d}.jpg"
        sheet.save(out_dir / sheet_name, quality=85)
        row["review_image"] = sheet_name
        row["panel_sources"] = {"A": "ai" if a_is_ai else "gold", "B": "gold" if a_is_ai else "ai"}
        if vlm is not None:
            try:
                b = referee(vlm, sheet, d["id"])
            except RuntimeError:
                b = "?"
            row["referee_raw"] = b
            row["referee_winner"] = ("ai" if (b == "A") == a_is_ai else "gold") if b in ("A", "B") else \
                ("tie" if b == "SAME" else "?")
        rows.append(row)

    def tally(key):
        t: Dict[str, int] = {}
        for r in rows:
            t[r.get(key, "?")] = t.get(r.get(key, "?"), 0) + r["area"]
        return t

    both = [r for r in rows if r.get("colour_winner") == r.get("referee_winner") and r.get("colour_winner") in ("ai", "gold")]
    known_diff = (ai != gold) & (gold != 255)
    white_normal_diff = known_diff & np.isin(ai, (1, 2)) & np.isin(gold, (1, 2))
    dispute_pixels = sum(r["area"] for r in rows)
    report = {
        "task_id": task_id, "referee": referee_model, "n_disputes": len(rows),
        "dispute_px": dispute_pixels,
        "boundary_contrast": {"ai": boundary_contrast(rgb, ai), "gold": boundary_contrast(rgb, gold)},
        "evidence_status": "human_review_required",
        "accepted_reference_correction_pixels": 0,
        "coverage": {
            "known_difference_pixels": int(known_diff.sum()),
            "white_normal_difference_pixels": int(white_normal_diff.sum()),
            "lead_pixels": dispute_pixels,
            "uncovered_known_difference_pixels": int(known_diff.sum()) - dispute_pixels,
        },
        "colour_px": tally("colour_winner"), "referee_px": tally("referee_winner"),
        "agreed_px": {"ai": int(sum(r["area"] for r in both if r["colour_winner"] == "ai")),
                      "gold": int(sum(r["area"] for r in both if r["colour_winner"] == "gold"))},
        "components": rows,
    }
    with (out_dir / "adjudication.json").open("w") as file:
        json.dump(report, file, ensure_ascii=False, indent=1, allow_nan=False)
    return report

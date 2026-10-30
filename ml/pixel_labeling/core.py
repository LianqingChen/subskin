"""Pixel algorithms: skin mask, local-baseline depigmentation score, candidates, label composition.

Everything here is deterministic given the image and ``decisions/<id>.json`` params, so a
decision file replays to the exact same label map on any machine.
"""

from typing import Any, Dict, List, Optional

import cv2
import numpy as np

DEFAULT_PARAMS: Dict[str, Any] = {
    "skin": {"method": "color_b", "b_min": 6, "min_area": 5000, "hole_max": 2000},
    # local = hand/small spots. global = large plaques BUT fails under left/right lighting
    # asymmetry (L-180-4). hybrid = local candidates + fill absorbed cores only (L-180-2+4).
    "baseline_mode": "local",
    "baseline_sigma": 25,
    "global_exclude_percentile": 70,
    # hybrid grow: fill plaque cores where global is high AND local is negative (absorbed),
    # never fill flat lit normal skin (global high, local ≈ 0) — L-180-4.
    "hybrid_global_fill": 12.0,
    "hybrid_core_max": -1.0,
    "t_hi": 7.0,
    "t_lo": 4.0,
    "min_candidate_area": 15,
    "grow_score": 3.0,
    "grow_iters": 2,
}
# Face/body diary photos: use ``"skin": {"method": "mediapipe"}``. Colour-b fails on beige walls.


def disk(r: int) -> np.ndarray:
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))


def params_of(decisions: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    p = {**DEFAULT_PARAMS, **((decisions or {}).get("params") or {})}
    p["skin"] = {**DEFAULT_PARAMS["skin"], **p["skin"]}
    return p


def lab_channels(rgb: np.ndarray):
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    return lab[..., 0] * 100 / 255, lab[..., 1] - 128, lab[..., 2] - 128


def _polys(h: int, w: int, polys: List[List[List[int]]]) -> np.ndarray:
    m = np.zeros((h, w), np.uint8)
    for poly in polys or []:
        cv2.fillPoly(m, [np.asarray(poly, np.int32)], 1)
    return m.astype(bool)


def skin_mask(rgb: np.ndarray, p: Dict[str, Any], extras: Optional[Dict[str, Any]] = None) -> np.ndarray:
    """Skin mask. ``color_b`` for blue/white drape; ``mediapipe`` for face/body diary photos.

    ``hole_max=None`` fills every enclosed hole; a number fills only holes smaller than it,
    which keeps background trapped between fingers/hands out of the skin.

    If ``extras`` is a dict, mediapipe fills ``extras['eyes']`` / ``extras['lips']`` (lips =
    no_draft: keep as skin, never auto-lesion).
    """
    s = p["skin"]
    h, w = rgb.shape[:2]
    if s["method"] == "mediapipe":
        from web.backend.services.rgb_segmentation.skin_parsing import parse_skin
        parsed = parse_skin(rgb)
        if parsed is None:
            raise RuntimeError("mediapipe skin parsing unavailable")
        skin = parsed["skin"].copy()
        if extras is not None:
            # lips stay skin but must never be auto-grown into lesion
            extras["lips"] = parsed["no_draft"]
        skin |= _polys(h, w, s.get("add_polygons"))
        skin &= ~_polys(h, w, s.get("remove_polygons"))
        return skin
    if s["method"] == "wood_aware":
        return _skin_wood_aware(rgb, s)
    if s["method"] != "color_b":
        raise ValueError(f"unsupported skin method {s['method']}")
    _, _, B = lab_channels(rgb)
    raw = cv2.morphologyEx((B > s["b_min"]).astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, lbl, st, _ = cv2.connectedComponentsWithStats(raw, 8)
    keep = np.zeros((h, w), bool)
    for i in range(1, n):
        if st[i, cv2.CC_STAT_AREA] > s["min_area"]:
            keep |= lbl == i
    if s["hole_max"] is None:
        ff = keep.astype(np.uint8).copy()
        cv2.floodFill(ff, np.zeros((h + 2, w + 2), np.uint8), (0, 0), 2)
        skin = keep | (ff == 0)
    else:
        n2, hl, hs, _ = cv2.connectedComponentsWithStats((~keep).astype(np.uint8), 4)
        skin = keep.copy()
        for i in range(1, n2):
            if hs[i, cv2.CC_STAT_AREA] < s["hole_max"]:
                skin |= hl == i
    skin |= _polys(h, w, s.get("add_polygons"))
    skin &= ~_polys(h, w, s.get("remove_polygons"))
    return skin


def _skin_wood_aware(rgb: np.ndarray, s: Dict[str, Any]) -> np.ndarray:
    """Hands on a wooden/warm table (L-186-1): pigmented skin ∪ cool bright plaques − yellow wood.

    ``color_b`` keeps everything yellow, so it swallows the table and drops the (low-b*) plaques.
    """
    h, w = rgb.shape[:2]
    L, A, B = lab_channels(rgb)
    pig = (L < s.get("pig_Lmax", 55)) & (B > s.get("pig_bmin", 2)) & (B < 30) & (np.abs(A) < 25)
    dep = (L > s.get("dep_Lmin", 52)) & (B < s.get("dep_bmax", 4)) & (B > -20) & (np.abs(A) < 20)
    wood = (L > s.get("wood_Lmin", 58)) & (B > s.get("wood_bmin", 7))
    raw = cv2.morphologyEx(((pig | dep) & ~wood).astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, lbl, st, _ = cv2.connectedComponentsWithStats(raw, 8)
    skin = np.zeros((h, w), bool)
    for a, i in sorted(((st[i, cv2.CC_STAT_AREA], i) for i in range(1, n)), reverse=True)[: s.get("max_parts", 4)]:
        if a >= s.get("min_area", 3000):
            skin |= lbl == i
    n2, hl, hs, _ = cv2.connectedComponentsWithStats((~skin).astype(np.uint8), 4)
    for i in range(1, n2):
        if hs[i, cv2.CC_STAT_AREA] < (s.get("hole_max") or 2000):
            skin |= hl == i
    skin |= _polys(h, w, s.get("add_polygons"))
    skin &= ~_polys(h, w, s.get("remove_polygons"))
    return skin


def _local_mean(x: np.ndarray, mask: np.ndarray, sigma: float) -> np.ndarray:
    num = cv2.GaussianBlur(np.where(mask, x, 0).astype(np.float32), (0, 0), sigma)
    den = cv2.GaussianBlur(mask.astype(np.float32), (0, 0), sigma)
    return num / np.maximum(den, 1e-3)


def depigmentation_score(rgb: np.ndarray, skin: np.ndarray, sigma: float,
                         mode: str = "local", global_exclude_percentile: float = 70) -> np.ndarray:
    """``dL - 0.8*db``: lighter AND less yellow than the reference skin. Positive = whiter.

    - ``local``: Gaussian neighbourhood (two-pass). Hands/small spots. Absorbs large plaque cores (L-180-2).
    - ``global``: median of darker skin percentile. Recovers plaque cores but paints lit normal
      cheek as lesion when the other half of the face is darker (L-180-4). Prefer ``hybrid``.
    - ``hybrid``: same array as ``local`` (candidates must be local). Core fill uses a separate
      global map inside ``compose`` (L-180-2 + L-180-4).
    """
    L, _, B = lab_channels(rgb)
    Ls, Bs = cv2.GaussianBlur(L, (0, 0), 1.2), cv2.GaussianBlur(B, (0, 0), 1.2)
    if mode == "global":
        thr = float(np.percentile(Ls[skin], global_exclude_percentile))
        ref = skin & (Ls <= thr)
        if ref.sum() < 64:
            ref = skin
        dL = Ls - float(np.median(Ls[ref]))
        dB = Bs - float(np.median(Bs[ref]))
        return dL - 0.8 * dB
    # local (+ hybrid candidate score)
    core = cv2.erode(skin.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
    light = Ls - _local_mean(Ls, core, sigma) > 6
    dL = Ls - _local_mean(Ls, core & ~light, sigma)
    dB = Bs - _local_mean(Bs, core & ~light, sigma)
    return dL - 0.8 * dB


def score_pair(rgb: np.ndarray, skin: np.ndarray, p: Dict[str, Any]):
    """Return ``(candidate_score, global_score_or_None)`` for the active baseline_mode."""
    mode = p.get("baseline_mode", "local")
    sigma = p["baseline_sigma"]
    pct = p.get("global_exclude_percentile", 70)
    if mode == "global":
        g = depigmentation_score(rgb, skin, sigma, mode="global", global_exclude_percentile=pct)
        return g, g
    local = depigmentation_score(rgb, skin, sigma, mode="local")
    if mode == "hybrid":
        g = depigmentation_score(rgb, skin, sigma, mode="global", global_exclude_percentile=pct)
        return local, g
    return local, None


def large_plaque_risk(skin: np.ndarray, comps: List[Dict[str, Any]], rgb: np.ndarray) -> Dict[str, Any]:
    """After a *local*-baseline prep: detect large-plaque failure mode (L-180-2).

    Signal: many candidates but they cover little skin, while a large share of skin is
    brighter than the skin-median L* (extensive depigmentation visible on the photo).
    """
    skin_n = max(1, int(skin.sum()))
    cand_px = sum(c["area"] for c in comps)
    L, _, _ = lab_channels(rgb)
    bright = skin & (L > float(np.median(L[skin])) + 3)
    frac_cand = cand_px / skin_n
    frac_bright = float(bright.sum()) / skin_n
    # Also flag left/right L asymmetry on skin (L-180-4 lighting trap for pure global).
    ys, xs = np.where(skin)
    mid = int(np.median(xs)) if len(xs) else skin.shape[1] // 2
    left = skin & (np.arange(skin.shape[1])[None, :] < mid)
    right = skin & ~left
    asym = 0.0
    if left.any() and right.any():
        asym = abs(float(np.median(L[left]) - np.median(L[right])))
    warn = (
        frac_bright > 0.18
        and (frac_cand < 0.08 or frac_cand < 0.55 * frac_bright)
        and len(comps) >= 5
    )
    return {
        "candidate_skin_fraction": round(frac_cand, 4),
        "bright_skin_fraction": round(frac_bright, 4),
        "n_candidates": len(comps),
        "L_half_asymmetry": round(asym, 2),
        "warn_large_plaque": warn,
        "hint": (
            "switch params.baseline_mode=hybrid (local candidates + core fill). "
            "Do NOT use pure global on lit face photos (L-180-4). Do NOT copy user version (L-180-3)."
        ),
    }


def candidates(score: np.ndarray, skin: np.ndarray, p: Dict[str, Any]):
    """Hysteresis blobs (seed > t_hi, grow through > t_lo). ``rim`` = share on the skin edge (9px)."""
    rim = skin & ~cv2.erode(skin.astype(np.uint8), disk(4)).astype(bool)
    lo = (score > p["t_lo"]) & skin
    _, lbl = cv2.connectedComponents(lo.astype(np.uint8), connectivity=8)
    hi = np.unique(lbl[(score > p["t_hi"]) & skin])
    cand = np.isin(lbl, hi[hi > 0])
    cand = cv2.morphologyEx(cand.astype(np.uint8), cv2.MORPH_OPEN, disk(1)).astype(bool)
    n, lbl, st, cen = cv2.connectedComponentsWithStats(cand.astype(np.uint8), 8)
    comps = []
    for i in range(1, n):
        area = int(st[i, cv2.CC_STAT_AREA])
        if area < p["min_candidate_area"]:
            continue
        m = lbl == i
        comps.append({"id": len(comps) + 1, "lab": i, "area": area, "cx": int(cen[i][0]), "cy": int(cen[i][1]),
                      "rim": round(float((m & rim).sum()) / area, 2), "score": round(float(np.median(score[m])), 1)})
    return lbl, comps


def compose(skin: np.ndarray, score: np.ndarray, lbl: np.ndarray, comps: List[Dict[str, Any]],
            decisions: Dict[str, Any], p: Dict[str, Any]) -> np.ndarray:
    """Five-class map from per-candidate decisions. Priority: occlusion > unknown-free lesion > unknown > skin."""
    h, w = skin.shape
    by_id = {c["id"]: c["lab"] for c in comps}
    yy, xx = np.mgrid[0:h, 0:w]

    def comp(ids):
        return np.isin(lbl, [by_id[i] for i in ids]) if ids else np.zeros((h, w), bool)

    def roi_parts(items):
        m = np.zeros((h, w), bool)
        for cid, (x0, y0, x1, y1) in items or []:
            box = np.zeros((h, w), bool); box[y0:y1, x0:x1] = True
            m |= comp([cid]) & box
        return m

    occl = np.zeros((h, w), np.uint8)
    for cx, cy, rx, ry in decisions.get("nails_ellipse", []):
        cv2.ellipse(occl, (cx, cy), (rx, ry), 0, 0, 360, 1, -1)
    occl = occl.astype(bool) | _polys(h, w, decisions.get("occlusion_polygons"))
    for cx, cy in decisions.get("nails_hull", []):
        # lighter pixels connected to the nail centre inside a 21px disk, convex hull
        near = (xx - cx) ** 2 + (yy - cy) ** 2
        region = (near <= 21 ** 2) & skin & (score > 2.5)
        _, l = cv2.connectedComponents(region.astype(np.uint8), connectivity=8)
        inner = region & (near <= 8 ** 2)
        pick = l[cy, cx] if region[cy, cx] else (np.bincount(l[inner].ravel()).argmax() if inner.any() else 0)
        if pick == 0:
            continue
        cs, _ = cv2.findContours((l == pick).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        hull = np.zeros((h, w), np.uint8)
        cv2.fillPoly(hull, [cv2.convexHull(np.vstack(cs))], 1)
        occl |= hull.astype(bool)
    occl &= skin

    lesion_poly = _polys(h, w, decisions.get("lesion_polygons"))
    unknown_poly = _polys(h, w, decisions.get("unknown_polygons"))
    lesion = comp(decisions.get("lesion")) | roi_parts(decisions.get("lesion_roi")) | lesion_poly
    unknown = comp(decisions.get("unknown")) | roi_parts(decisions.get("unknown_roi")) | unknown_poly
    # Force-normal carve-outs (pigment islands / specular) — after grow (L-180-2)
    normal_force = _polys(h, w, decisions.get("normal_polygons"))
    lips = _polys(h, w, decisions.get("lips_polygons"))
    if decisions.get("_lips_mask") is not None:
        lips = lips | np.asarray(decisions["_lips_mask"], bool)
    # Grow stays inside mediapipe skin; explicit polygons may fill brow/eye holes (L-180-2).
    # hybrid: also fill absorbed plaque cores (global high AND local negative) — not flat lit
    # normal skin where global is high but local ≈ 0 (L-180-4).
    skin_grow = skin | lesion_poly | unknown_poly
    gscore = decisions.get("_global_score")
    hybrid = p.get("baseline_mode") == "hybrid" and gscore is not None
    g_fill = float(p.get("hybrid_global_fill", 12.0))
    core_max = float(p.get("hybrid_core_max", -1.0))
    for _ in range(p["grow_iters"] + (8 if hybrid else 0)):
        near = cv2.dilate(lesion.astype(np.uint8), disk(3 if not hybrid else 2)).astype(bool)
        through = score > p["grow_score"]
        if hybrid:
            through = through | ((gscore > g_fill) & (score < core_max))
        lesion |= near & skin_grow & through & ~lips & ~normal_force
    lesion = (
        cv2.morphologyEx(lesion.astype(np.uint8), cv2.MORPH_CLOSE, disk(1)).astype(bool)
        & skin_grow & ~occl & ~lips & ~normal_force
    )
    unknown &= skin_grow & ~lesion & ~occl & ~normal_force

    skin_u = skin | lesion | unknown | occl
    labels = np.zeros((h, w), np.uint8)
    labels[skin_u] = 1
    labels[lesion] = 2
    labels[unknown] = 255
    labels[occl] = 3
    return labels

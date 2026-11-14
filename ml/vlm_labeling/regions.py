"""Region proposals (superpixels) + numbered tiles for Set-of-Mark prompting.

A VLM cannot output pixel-accurate coordinates (measured on 182: hairline-box errors of 30-130px),
but it can reliably say "region 37 is depigmented skin".  So the protocol is: local code proposes
small colour-coherent regions, the model judges each numbered region, local code turns the
judgements into pixels (``fuse.py``).
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from skimage.segmentation import find_boundaries, slic

from ml.pixel_labeling import core

# Oracle ceiling on 182 (perfect verdicts, majority label per region, ±2px Dice):
#   150 regions 0.906 · 300 0.949 · 600 0.978 · 1200 0.984 — 500-700 skin regions is the sweet spot.
DEFAULT_SKIN_REGIONS = 600
TILE_MAX_REGIONS = 80


@dataclass
class Regions:
    seg: np.ndarray                      # int32 region id per pixel, -1 = outside proposal (auto background)
    table: List[Dict]                    # per-region stats (id, area, centroid, bbox, lab, priors)
    tiles: List[Dict] = field(default_factory=list)   # {"id", "box": [x0,y0,x1,y1], "regions": [...]}
    params: Dict = field(default_factory=dict)


def proposal_mask(side: Dict[str, np.ndarray], conf_bg: np.ndarray) -> np.ndarray:
    """Everything that is not confidently background (wall/sky) — the model must see all of it."""
    m = (conf_bg < 0.9) | side["proposal"]
    m = cv2.dilate(m.astype(np.uint8), core.disk(6)).astype(bool)
    return m


def build(rgb: np.ndarray, feats: np.ndarray, side: Dict[str, np.ndarray], names: List[str],
          n_skin: int = DEFAULT_SKIN_REGIONS, compactness: float = 10.0) -> Regions:
    ix = {n: i for i, n in enumerate(names)}
    conf_bg = feats[..., ix["mp_bg"]] if feats[..., ix["mp_ok"]].max() > 0 else np.zeros(rgb.shape[:2], np.float32)
    mask = proposal_mask(side, conf_bg)
    skin_p = (feats[..., ix["mp_face"]] + feats[..., ix["mp_body"]]) > 0.3
    skin_p = cv2.dilate(skin_p.astype(np.uint8), core.disk(8)).astype(bool) & mask
    rest = mask & ~skin_p
    # skin gets fine regions (lesion borders live there); hair/clothes/eyes area gets coarse ones
    n = int(n_skin)
    seg = np.full(mask.shape, -1, np.int32)
    if skin_p.any():
        seg = np.where(skin_p, slic(rgb, n_segments=n, compactness=compactness, start_label=0,
                                    mask=skin_p, convert2lab=True), -1).astype(np.int32)
    if rest.sum() > 500:
        n_rest = int(np.clip(n * rest.sum() / max(skin_p.sum(), 1) / 4, 20, 300))
        s2 = slic(rgb, n_segments=n_rest, compactness=compactness, start_label=0, mask=rest, convert2lab=True)
        seg = np.where(rest, np.where(s2 >= 0, s2 + seg.max() + 1, -1), seg).astype(np.int32)
    else:
        n_rest = 0
    seg[~mask] = -1
    # relabel contiguous 0..K-1
    ids = np.unique(seg[seg >= 0])
    lut = np.full(int(ids.max()) + 2, -1, np.int32)
    lut[ids] = np.arange(ids.size)
    seg = np.where(seg >= 0, lut[np.clip(seg, 0, None)], -1)

    L, A, B = core.lab_channels(rgb)
    table = []
    flat = seg.ravel()
    order = np.argsort(flat, kind="stable")
    bounds = np.searchsorted(flat[order], np.arange(ids.size + 1))
    H, W = seg.shape
    for k in range(ids.size):
        pix = order[bounds[k]:bounds[k + 1]]
        ys, xs = np.divmod(pix, W)
        def m(name):  # noqa: E306
            return round(float(feats[..., ix[name]].ravel()[pix].mean()), 3)
        table.append({
            "id": k, "area": int(pix.size),
            "cx": int(xs.mean()), "cy": int(ys.mean()),
            "bbox": [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1],
            "L": round(float(L.ravel()[pix].mean()), 1), "A": round(float(A.ravel()[pix].mean()), 1),
            "B": round(float(B.ravel()[pix].mean()), 1),
            "p_bg": m("mp_bg"), "p_hair": m("mp_hair"), "p_body": m("mp_body"), "p_face": m("mp_face"),
            "p_clothes": m("mp_clothes"), "p_other": m("mp_other"),
            "eyes": round(float(side["eyes"].ravel()[pix].mean()), 3),
            "lips": round(float(side["lips"].ravel()[pix].mean()), 3),
        })
    r = Regions(seg=seg, table=table, params={"n_skin": n_skin, "n_rest": n_rest, "compactness": compactness})
    # fine routes (scattered spots) would need 40+ tiles at 80 ids each; cap tile count instead
    r.tiles = make_tiles(r, max_regions=max(TILE_MAX_REGIONS, len(table) // 20))
    return r


def make_tiles(r: Regions, max_regions: int = TILE_MAX_REGIONS) -> List[Dict]:
    """Recursive split of the proposal bbox until each tile holds <= max_regions centroids."""
    pts = np.array([[t["cx"], t["cy"]] for t in r.table])
    ys, xs = np.nonzero(r.seg >= 0)
    root = [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]
    out: List[Dict] = []

    def rec(box):
        x0, y0, x1, y1 = box
        sel = np.flatnonzero((pts[:, 0] >= x0) & (pts[:, 0] < x1) & (pts[:, 1] >= y0) & (pts[:, 1] < y1))
        if sel.size == 0:
            return
        if sel.size <= max_regions:
            out.append({"id": len(out), "box": list(box), "regions": [int(i) for i in sel]})
            return
        if (x1 - x0) >= (y1 - y0):
            xm = (x0 + x1) // 2
            rec([x0, y0, xm, y1]); rec([xm, y0, x1, y1])  # noqa: E702
        else:
            ym = (y0 + y1) // 2
            rec([x0, y0, x1, ym]); rec([x0, ym, x1, y1])  # noqa: E702

    rec(root)
    return out


def _font(size: int):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


def crop_box(box: List[int], shape: Tuple[int, int], margin: int = 24) -> List[int]:
    H, W = shape
    x0, y0, x1, y1 = box
    return [max(0, x0 - margin), max(0, y0 - margin), min(W, x1 + margin), min(H, y1 + margin)]


def render_tile(rgb: np.ndarray, r: Regions, tile: Dict, labels: np.ndarray = None,
                target: int = 1024) -> Tuple[Image.Image, Image.Image, List[int]]:
    """(clean crop, marked crop, crop box).  Marked = thin region borders + region numbers;
    with ``labels`` the current draft is shown as a translucent fill (review pass)."""
    cb = crop_box(tile["box"], rgb.shape[:2])
    x0, y0, x1, y1 = cb
    s = target / max(x1 - x0, y1 - y0)
    size = (max(1, int((x1 - x0) * s)), max(1, int((y1 - y0) * s)))
    crop = rgb[y0:y1, x0:x1]
    clean = Image.fromarray(crop).resize(size, Image.LANCZOS)
    mk = np.array(clean).astype(np.float32)
    if labels is not None:
        lab = cv2.resize(labels[y0:y1, x0:x1], size, interpolation=cv2.INTER_NEAREST)
        for k, c in {2: (255, 0, 0), 3: (0, 90, 255), 4: (160, 0, 200), 255: (255, 230, 0)}.items():
            m = lab == k
            mk[m] = 0.6 * mk[m] + 0.4 * np.array(c)
    segc = cv2.resize(r.seg[y0:y1, x0:x1], size, interpolation=cv2.INTER_NEAREST)
    bd = find_boundaries(segc, mode="inner")
    mk[bd] = (0.3 * mk[bd] + 0.7 * np.array((255, 255, 0))) if labels is None else (0.4 * mk[bd] + 0.6 * np.array((255, 255, 255)))
    marked = Image.fromarray(mk.clip(0, 255).astype(np.uint8))
    d = ImageDraw.Draw(marked)
    f = _font(max(11, int(13 * min(1.6, s))))
    for rid in tile["regions"]:
        t = r.table[rid]
        # put the number on a pixel that belongs to the region (centroid may fall outside for C-shapes)
        cx, cy = t["cx"], t["cy"]
        if r.seg[cy, cx] != rid:
            ys, xs = np.nonzero(r.seg[t["bbox"][1]:t["bbox"][3], t["bbox"][0]:t["bbox"][2]] == rid)
            j = len(ys) // 2
            cx, cy = t["bbox"][0] + int(xs[j]), t["bbox"][1] + int(ys[j])
        px, py = (cx - x0) * s, (cy - y0) * s
        txt = str(rid)
        d.text((px, py), txt, fill=(255, 255, 255), font=f, anchor="mm", stroke_width=2, stroke_fill=(0, 0, 0))
    return clean, marked, cb


def overview(rgb: np.ndarray, r: Regions, labels: np.ndarray = None, target: int = 1024) -> Image.Image:
    """Whole image with tile boxes numbered (so the model knows where each tile sits)."""
    H, W = rgb.shape[:2]
    s = target / max(H, W)
    im = rgb.astype(np.float32).copy()
    if labels is not None:
        for k, c in {2: (255, 0, 0), 3: (0, 90, 255), 4: (160, 0, 200), 255: (255, 230, 0)}.items():
            m = labels == k
            im[m] = 0.6 * im[m] + 0.4 * np.array(c)
    out = Image.fromarray(im.clip(0, 255).astype(np.uint8)).resize((int(W * s), int(H * s)), Image.LANCZOS)
    d = ImageDraw.Draw(out)
    f = _font(22)
    for t in r.tiles:
        x0, y0, x1, y1 = [int(v * s) for v in t["box"]]
        d.rectangle([x0, y0, x1, y1], outline=(0, 255, 255), width=2)
        d.text((x0 + 6, y0 + 4), f"T{t['id']}", fill=(0, 255, 255), font=f, stroke_width=2, stroke_fill=(0, 0, 0))
    return out


def tile_regions_summary(r: Regions, tile: Dict) -> Dict[int, Dict]:
    return {rid: r.table[rid] for rid in tile["regions"]}


def region_ids_at(r: Regions) -> np.ndarray:
    return r.seg

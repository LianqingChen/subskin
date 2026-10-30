"""Named, parameterised post-ops for ``decisions[*].ops`` — the code form of past lessons.

Each op takes the label map plus a shared context and returns a new label map. Ops are applied
in list order after the base draft, before the explicit polygon overrides. Add an op here
(with its lesson id) instead of writing a one-off script; a decision file that names an op not
in ``OPS`` fails loudly so it can never silently stop replaying.
"""

from typing import Any, Callable, Dict, List

import cv2
import numpy as np

from ml.pixel_labeling import core


class Ctx:
    """Lazily computed image measurements shared by ops."""

    def __init__(self, rgb: np.ndarray, extras: Dict[str, Any]):
        self.rgb = rgb
        self.extras = extras
        self.L, self.A, self.B = core.lab_channels(rgb)
        self._scores = None

    def scores(self, skin: np.ndarray):
        if self._scores is None:
            p = core.params_of({"params": {"baseline_mode": "hybrid"}})
            self._scores = core.score_pair(self.rgb, skin, p)
        return self._scores


def _skin(labels: np.ndarray) -> np.ndarray:
    return np.isin(labels, (1, 2, 255))


def _roi(shape, roi) -> np.ndarray:
    m = np.zeros(shape, bool)
    if roi is None:
        m[:] = True
    else:
        x0, y0, x1, y1 = roi
        m[y0:y1, x0:x1] = True
    return m


def _pigment_ref(ctx: Ctx, labels: np.ndarray, sg: np.ndarray) -> float:
    """Median L of normal-looking skin (low whiteness, not hair-dark)."""
    pig = (labels == 1) & (sg < 5) & (ctx.L > 25)
    return float(np.median(ctx.L[pig])) if pig.sum() > 300 else float(np.percentile(ctx.L[_skin(labels)], 40))


def _grow_islands(seed: np.ndarray, allowed: np.ndarray, min_area: int, steps: int) -> np.ndarray:
    """Keep components of ``allowed`` touching ``seed`` or larger than ``min_area``; geodesic grow."""
    n, cc, st, _ = cv2.connectedComponentsWithStats(allowed.astype(np.uint8), 8)
    keep = np.zeros(n, bool)
    touch = np.unique(cc[seed & allowed])
    keep[touch] = True
    keep[1:] |= st[1:, cv2.CC_STAT_AREA] >= min_area
    keep[0] = False
    out = seed | keep[cc]
    for _ in range(steps):
        out |= cv2.dilate(out.astype(np.uint8), core.disk(2)).astype(bool) & allowed
    return out


def chalk_fill(labels, ctx: Ctx, roi=None, dL=12.0, sg=7.0, min_area=20, steps=16):
    """L-199-1: bright chalky plaque the model under-calls (absorbed local score)."""
    skin = _skin(labels)
    _, g = ctx.scores(skin)
    area = skin & _roi(skin.shape, roi)
    allowed = area & (ctx.L >= _pigment_ref(ctx, labels, g) + dL) & (g > sg)
    les = _grow_islands((labels == 2) & area, allowed, min_area, steps)
    out = labels.copy()
    out[les & area & (labels != 3)] = 2
    return out


def local_contrast_fill(labels, ctx: Ctx, roi=None, open_r=15, dL=5.0, sg=1.0, min_area=20, steps=10):
    """L-199-1: fainter patches — brighter than the local darker floor ``open(L, r)``."""
    skin = _skin(labels)
    _, g = ctx.scores(skin)
    fill = float(np.median(ctx.L[skin])) if skin.any() else 50.0
    floor = cv2.morphologyEx(np.where(skin, ctx.L, fill).astype(np.float32), cv2.MORPH_OPEN, core.disk(open_r))
    area = skin & _roi(skin.shape, roi)
    allowed = area & (ctx.L - floor > dL) & (g > sg)
    les = _grow_islands((labels == 2) & area, allowed, min_area, steps)
    les = cv2.morphologyEx(les.astype(np.uint8), cv2.MORPH_CLOSE, core.disk(3)).astype(bool) & area
    out = labels.copy()
    out[les & (labels != 3)] = 2
    return out


def litflat_trim(labels, ctx: Ctx, band=3, sl_abs=1.0, sg_max=8.0):
    """L-180-4: lesion fringe that is only globally bright (lit normal skin) goes back to normal."""
    skin = _skin(labels)
    sl, g = ctx.scores(skin)
    les = labels == 2
    fringe = les & cv2.dilate((~les).astype(np.uint8), core.disk(band)).astype(bool)
    out = labels.copy()
    out[fringe & (np.abs(sl) < sl_abs) & (g < sg_max)] = 1
    return out


def ellipse_fill(labels, ctx: Ctx, L_margin=0.0, sl=2.5, R=3, max_scale=3.2, ring=25):
    """L-207-1/2: round trunk plaques — grow each lesion blob as an ellipse until its rim is no
    brighter than the surrounding normal skin; keep only whiteness-gated pixels."""
    skin = _skin(labels)
    sl_map, _ = ctx.scores(skin)
    seed = labels == 2
    n, cc = cv2.connectedComponents(seed.astype(np.uint8), 8)
    h, w = seed.shape
    cur = seed.copy()
    for i in range(1, n):
        m = cc == i
        ys, xs = np.where(m)
        if xs.size < 5:
            continue
        (cx, cy), (ma, mi), ang = cv2.fitEllipse(np.column_stack([xs, ys]).astype(np.float32))
        near = cv2.dilate(m.astype(np.uint8), np.ones((ring, ring), np.uint8)).astype(bool) & ~m & skin
        ref = float(np.median(ctx.L[near])) if near.any() else float(np.median(ctx.L[m])) - 10
        chosen = 1.0
        for sc in np.arange(1.0, max_scale + 0.05, 0.05):
            e = np.zeros((h, w), np.uint8)
            cv2.ellipse(e, (int(round(cx)), int(round(cy))), (max(1, int(ma * sc / 2)), max(1, int(mi * sc / 2))),
                        float(ang), 0, 360, 1, -1)
            e = e.astype(bool)
            rim = e & ~cv2.erode(e.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool) & skin
            if rim.any() and float(np.median(ctx.L[rim])) <= ref + L_margin:
                break
            chosen = float(sc)
        e = np.zeros((h, w), np.uint8)
        cv2.ellipse(e, (int(round(cx)), int(round(cy))), (max(1, int(ma * chosen / 2)), max(1, int(mi * chosen / 2))),
                    float(ang), 0, 360, 1, -1)
        cur |= e.astype(bool) & skin & (sl_map > sl)
    dist = cv2.distanceTransform((~cur).astype(np.uint8), cv2.DIST_L2, 5)
    cur |= skin & (dist > 0) & (dist <= R) & (sl_map > sl)
    out = labels.copy()
    out[cur & (labels != 3)] = 2
    return out


def global_score_fill(labels, ctx: Ctx, sg=17.0, close_r=5, pigment_L_off=3.0, min_area=100):
    """L-186-1: large hand plaques — lesion = globally white skin, closed, pigment islands back to normal."""
    skin = _skin(labels) & (labels != 3)
    _, g = ctx.scores(skin)
    les = skin & (g > sg)
    les = cv2.morphologyEx(les.astype(np.uint8), cv2.MORPH_CLOSE, core.disk(close_r)).astype(bool) & skin
    ref = skin & (g < 0) & (ctx.L < 50)
    med = float(np.median(ctx.L[ref])) if ref.sum() > 1000 else 40.0
    les &= ~((ctx.L < med + pigment_L_off) & (g < sg))
    n, cc, st, _ = cv2.connectedComponentsWithStats(les.astype(np.uint8), 8)
    keep = np.zeros(n, bool)
    keep[1:] = st[1:, cv2.CC_STAT_AREA] >= min_area
    out = labels.copy()
    out[(labels == 2) & skin] = 1
    out[keep[cc]] = 2
    return out


def lesion_close_gated(labels, ctx: Ctx, r=2, sg=2.0, sl=1.0):
    """L-207-1: smooth lesion borders, but only accept closed pixels that are themselves whitish."""
    skin = _skin(labels)
    sl_map, g = ctx.scores(skin)
    les = labels == 2
    closed = cv2.morphologyEx(les.astype(np.uint8), cv2.MORPH_CLOSE, core.disk(r)).astype(bool)
    out = labels.copy()
    out[closed & ~les & skin & (g > sg) & (sl_map > sl) & (labels != 3)] = 2
    return out


def fringe_trim(labels, ctx: Ctx, sl_max=1.5, band=2):
    """L-207-1: drop the outer lesion ring whose local whiteness is ~0 (normal skin glued on)."""
    skin = _skin(labels)
    sl_map, _ = ctx.scores(skin)
    les = labels == 2
    fringe = les & cv2.dilate((~les).astype(np.uint8), core.disk(band)).astype(bool)
    out = labels.copy()
    out[fringe & (sl_map < sl_max)] = 1
    return out


def fill_lesion_holes(labels, ctx: Ctx, max_area=400):
    """L-201-1: absorbed core leaves a hollow ring — fill small enclosed holes inside lesions."""
    les = labels == 2
    n, cc, st, _ = cv2.connectedComponentsWithStats((~les).astype(np.uint8), 4)
    out = labels.copy()
    for i in range(1, n):
        x, y, w_, h_, a = st[i]
        touches = x == 0 or y == 0 or x + w_ >= les.shape[1] or y + h_ >= les.shape[0]
        if a <= max_area and not touches:
            m = (cc == i) & np.isin(labels, (1, 255))
            out[m] = 2
    return out


def lips_occlusion(labels, ctx: Ctx):
    """L-185-1: lips are not skin — mark them occlusion (mediapipe landmarks)."""
    lips = ctx.extras.get("lips")
    out = labels.copy()
    if lips is not None:
        out[np.asarray(lips, bool)] = 3
    return out


def dark_marks_occlusion(labels, ctx: Ctx, gray_max=35, min_area=30, max_area=5000, elong=2.0, pad=2):
    """L-185-1/L-186: black arrows / annotation marks drawn on the photo are occlusion."""
    rgb = ctx.rgb
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    dark = (gray < gray_max) & (rgb.max(-1) < gray_max + 10)
    dark = cv2.morphologyEx(dark.astype(np.uint8), cv2.MORPH_CLOSE, core.disk(1))
    n, cc, st, _ = cv2.connectedComponentsWithStats(dark, 8)
    mark = np.zeros(labels.shape, bool)
    for i in range(1, n):
        a, w_, h_ = st[i, cv2.CC_STAT_AREA], st[i, cv2.CC_STAT_WIDTH], st[i, cv2.CC_STAT_HEIGHT]
        if min_area < a < max_area and max(w_, h_) / max(min(w_, h_), 1) >= elong:
            mark |= cc == i
    mark = cv2.dilate(mark.astype(np.uint8), core.disk(pad)).astype(bool)
    out = labels.copy()
    out[mark] = 3
    return out


def relabel_lesion_as_normal(labels, ctx: Ctx):
    """Reviewed call that the draft's lesion is not depigmentation (e.g. a naturally pink palm)."""
    out = labels.copy()
    out[labels == 2] = 1
    return out


def nail_ellipses(labels, ctx: Ctx, items):
    """L-186-2 / L-189-2: explicit nail ellipses (cx, cy, rx, ry), reviewed on a grid, become occlusion."""
    h, w = labels.shape
    m = np.zeros((h, w), np.uint8)
    for cx, cy, rx, ry in items:
        cv2.ellipse(m, (int(cx), int(cy)), (int(rx), int(ry)), 0, 0, 360, 1, -1)
    out = labels.copy()
    out[m.astype(bool)] = 3
    return out


def occlusion_to_background(labels, ctx: Ctx):
    """L-201-2: the model calls clothing edges (beanie, collar) occlusion — when the photo has no real
    occluder, send all predicted occlusion to background; real ones go back via occlusion_polygons."""
    out = labels.copy()
    out[labels == 3] = 0
    return out


def fingertip_nails(labels, ctx: Ctx, rx=16, ry=22, yoff=-2, max_tip_y=None, min_gap=25):
    """L-186-2: nails sit at finger tips (tops of the skin profile) — ellipse there as occlusion."""
    skin = _skin(labels)
    h, w = skin.shape
    top = np.where(skin.any(0), skin.argmax(0), h).astype(np.float32)
    top = cv2.blur(top.reshape(1, -1), (21, 1)).ravel()
    limit = max_tip_y if max_tip_y is not None else h // 2
    occl = np.zeros((h, w), np.uint8)
    last = -min_gap
    for x in range(8, w - 8):
        y = top[x]
        if y >= limit or y > top[x - 8:x].min() or y > top[x + 1:x + 9].min() or x - last < min_gap:
            continue
        last = x
        cv2.ellipse(occl, (x, int(y) + ry + yoff), (rx, ry), 0, 0, 360, 1, -1)
    out = labels.copy()
    out[occl.astype(bool) & skin] = 3
    return out


OPS: Dict[str, Callable[..., np.ndarray]] = {
    f.__name__: f for f in (chalk_fill, local_contrast_fill, litflat_trim, ellipse_fill, global_score_fill,
                            lesion_close_gated, fringe_trim, fill_lesion_holes,
                            lips_occlusion, dark_marks_occlusion, occlusion_to_background,
                            fingertip_nails, nail_ellipses, relabel_lesion_as_normal)
}


def apply(labels: np.ndarray, rgb: np.ndarray, extras: Dict[str, Any], steps: List[Dict[str, Any]]) -> np.ndarray:
    ctx = Ctx(rgb, extras)
    for step in steps or []:
        step = dict(step)
        name = step.pop("op")
        if name not in OPS:
            raise SystemExit(f"unknown op {name!r}; available: {sorted(OPS)}")
        labels = OPS[name](labels, ctx, **step)
    return labels

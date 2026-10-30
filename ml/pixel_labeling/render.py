"""Review images. Rule: never judge from a downscaled overview — judge from centred, magnified crops."""

from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONT_PATH = "/usr/share/fonts/google-noto-cjk/NotoSerifCJK-Bold.ttc"
# label contour colours: lesion magenta, occlusion orange, unknown yellow, skin outline green
CLASS_COLORS = {2: (255, 0, 200), 3: (255, 160, 0), 255: (255, 255, 0)}


def font(size: int):
    return ImageFont.truetype(FONT_PATH, size)


def heat(rgb: np.ndarray, score: np.ndarray, skin: np.ndarray, out: Path) -> None:
    vis = np.clip((score + 2) / 22 * 255, 0, 255).astype(np.uint8)
    hm = cv2.applyColorMap(vis, cv2.COLORMAP_JET)[..., ::-1].copy()
    hm[~skin] = 0
    Image.fromarray(np.hstack([rgb, hm])).save(out, quality=88)


def draw_labels(rgb: np.ndarray, labels: np.ndarray) -> np.ndarray:
    o = rgb.copy()
    for v, col in CLASS_COLORS.items():
        cs, _ = cv2.findContours((labels == v).astype(np.uint8), cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
        cv2.drawContours(o, cs, -1, col, 1)
    cs, _ = cv2.findContours(np.isin(labels, (1, 2, 3, 255)).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    cv2.drawContours(o, cs, -1, (0, 255, 120), 1)
    return o


def draw_candidates(rgb: np.ndarray, lbl: np.ndarray, comps: List[Dict]) -> np.ndarray:
    o = rgb.copy()
    for c in comps:
        cs, _ = cv2.findContours((lbl == c["lab"]).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        cv2.drawContours(o, cs, -1, (255, 0, 200) if c["rim"] < 0.2 else (255, 200, 0), 1)
    return o


def pair(rgb: np.ndarray, over: np.ndarray, box: Tuple[int, int, int, int], scale: float,
         texts: Sequence[Tuple[int, int, str]] = ()) -> Image.Image:
    """Original on top, annotated below, same crop and scale."""
    x0, y0, x1, y1 = box
    W, H = int((x1 - x0) * scale), int((y1 - y0) * scale)
    a = Image.fromarray(rgb[y0:y1, x0:x1]).resize((W, H), Image.LANCZOS)
    b = Image.fromarray(over[y0:y1, x0:x1]).resize((W, H), Image.NEAREST)
    d = ImageDraw.Draw(b)
    for cx, cy, t in texts:
        if x0 <= cx < x1 and y0 <= cy < y1:
            d.text(((cx - x0) * scale + 6, (cy - y0) * scale - 8), t, fill=(255, 255, 0), font=font(16),
                   stroke_width=2, stroke_fill=(0, 0, 0))
    out = Image.new("RGB", (W, 2 * H + 6), "white")
    out.paste(a, (0, 0)); out.paste(b, (0, H + 6))
    return out


def sheet(tiles: List[Image.Image], out: Path, cols: int = 2) -> None:
    W, H = max(t.width for t in tiles), max(t.height for t in tiles)
    s = Image.new("RGB", (cols * W + 10 * (cols - 1), ((len(tiles) + cols - 1) // cols) * (H + 10)), "white")
    for k, t in enumerate(tiles):
        s.paste(t, ((k % cols) * (W + 10), (k // cols) * (H + 10)))
    s.save(out, quality=88)


def centred_tile(rgb: np.ndarray, layers: List[np.ndarray], cx: int, cy: int, title: str,
                 radius: int = 32, scale: int = 5) -> Image.Image:
    """Side-by-side magnified crops centred on (cx, cy): original | each annotated layer."""
    h, w = rgb.shape[:2]
    x0, y0 = min(max(0, cx - radius), max(0, w - 2 * radius)), min(max(0, cy - radius), max(0, h - 2 * radius))
    x1, y1 = min(w, x0 + 2 * radius), min(h, y0 + 2 * radius)
    S = ((x1 - x0) * scale, (y1 - y0) * scale)
    panels = [Image.fromarray(rgb[y0:y1, x0:x1]).resize(S, Image.LANCZOS)]
    panels += [Image.fromarray(l[y0:y1, x0:x1]).resize(S, Image.NEAREST) for l in layers]
    t = Image.new("RGB", (len(panels) * (S[0] + 8), S[1] + 30), "white")
    for k, p in enumerate(panels):
        t.paste(p, (k * (S[0] + 8), 30))
    ImageDraw.Draw(t).text((4, 2), title, fill="black", font=font(20))
    return t


def grid_crop(rgb: np.ndarray, box: Tuple[int, int, int, int], scale: int, out: Path) -> None:
    """Magnified crop with labelled 10px grid lines, for reading exact image coordinates (nails, polygons)."""
    x0, y0, x1, y1 = box
    crop = Image.fromarray(rgb[y0:y1, x0:x1]).resize(((x1 - x0) * scale, (y1 - y0) * scale), Image.LANCZOS)
    d = ImageDraw.Draw(crop)
    f = font(14)
    for gx in range(x0 - x0 % 10 + 10, x1, 10):
        X = (gx - x0) * scale
        d.line([(X, 0), (X, crop.height)], fill=(255, 255, 0), width=1)
        d.text((X + 2, 2), str(gx), fill=(255, 255, 0), font=f)
    for gy in range(y0 - y0 % 10 + 10, y1, 10):
        Y = (gy - y0) * scale
        d.line([(0, Y), (crop.width, Y)], fill=(0, 255, 255), width=1)
        d.text((2, Y + 2), str(gy), fill=(0, 255, 255), font=f)
    crop.save(out, quality=88)

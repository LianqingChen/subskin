#!/usr/bin/env python3
"""生成 qwen-vl-max vs qwen3-vl-plus bbox 叠加对比图"""
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path("/root/subskin")
d = json.loads((ROOT / "tmp/vlm_compare/raw_results.json").read_text())

IMAGES = [
    ("small_2.4MB", "data/uploads/vasi/1778982711_746295e9.jpg"),
    ("mid_2.7MB",   "data/uploads/vasi/1778935155_f19b02c6.jpg"),
    ("large_3.0MB", "data/uploads/vasi/1780474134_e630b5b2.jpg"),
]

# 尝试找一个能渲染中文的字体
def get_font(size):
    for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
              "/root/subskin/web/app/public/fonts/NotoSansSC-Bold.ttf"]:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()

COLORS = {"qwen-vl-max": "#ff3030", "qwen3-vl-plus": "#30a0ff"}

def draw_on(img: Image.Image, lesions, color, label):
    img = img.copy().convert("RGB")
    W, H = img.size
    dr = ImageDraw.Draw(img, "RGBA")
    f = get_font(max(14, W // 60))
    for i, L in enumerate(lesions):
        bbox = L.get("bbox") or []
        if len(bbox) != 4: continue
        x1, y1, x2, y2 = bbox
        if max(x1,y1,x2,y2) <= 1.5:  # normalized
            x1, x2 = x1*W, x2*W
            y1, y2 = y1*H, y2*H
        x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
        dr.rectangle([x1, y1, x2, y2], outline=color, width=4)
        tag = f"L{i+1} d{L.get('depigmentation_level','?')}"
        # text bg
        try:
            tb = dr.textbbox((x1+2, y1+2), tag, font=f)
            dr.rectangle(tb, fill=color)
            dr.text((x1+2, y1+2), tag, fill="white", font=f)
        except Exception:
            dr.text((x1+2, y1+2), tag, fill=color, font=f)
    # title bar
    bar_h = max(40, W // 25)
    bar = Image.new("RGB", (W, bar_h), color)
    bdr = ImageDraw.Draw(bar)
    title_f = get_font(max(18, W // 40))
    bdr.text((10, 5), label, fill="white", font=title_f)
    out = Image.new("RGB", (W, H + bar_h), "white")
    out.paste(bar, (0, 0))
    out.paste(img, (0, bar_h))
    return out

outdir = ROOT / "tmp/vlm_compare"
saved = []
for img_label, img_path in IMAGES:
    img = Image.open(img_path)
    # Resize large
    W, H = img.size
    if max(W, H) > 1200:
        scale = 1200 / max(W, H)
        img = img.resize((int(W*scale), int(H*scale)))
    panels = []
    for model in ["qwen-vl-max", "qwen3-vl-plus"]:
        r = d[img_label][model]
        p = r.get("parsed") or {}
        lesions = p.get("suspected_lesions") or []
        n = len(lesions)
        depig = p.get("overall_depigmentation", "?")
        area = p.get("area_percentage_estimate", "?")
        label = f"{model}  [{n} lesions, depig={depig}, area={area}%, {r['latency_s']}s]"
        panels.append(draw_on(img, lesions, COLORS[model], label))
    # stack horizontal
    h = max(p.height for p in panels)
    w = sum(p.width for p in panels) + 10
    canvas = Image.new("RGB", (w, h), "white")
    x = 0
    for p in panels:
        canvas.paste(p, (x, 0))
        x += p.width + 10
    out = outdir / f"compare_{img_label}.jpg"
    canvas.save(out, quality=85)
    saved.append(out)
    print(f"saved {out} ({canvas.size})")

print("\nDone")

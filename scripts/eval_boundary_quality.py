#!/usr/bin/env python3
"""白斑候选质量离线评测：以用户确认掩膜为金标准，量化候选的边界与面积质量。

用法：
  python3 scripts/eval_boundary_quality.py --source cv --user 9
  python3 scripts/eval_boundary_quality.py --source stability --user 9
  python3 scripts/eval_boundary_quality.py --source vlm --user 9 --limit 3 --variant hires_zoom

指标：IoU、面积相对误差、边界 F1@容差（以 1024 网格为基准换算到各图原生像素）。
输出：控制台表格 + tmp/eval_boundary/<ts>.json。视觉变体才产生 API 调用与成本。
"""
import argparse
import base64
import io
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path("/root/subskin")
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

ENV = {}
for line in (ROOT / "web" / "backend" / ".env").read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    ENV[k.strip()] = v.strip().strip('"').strip("'")
os.environ.setdefault("LLM_ENCRYPTION_KEY", ENV.get("LLM_ENCRYPTION_KEY", ""))
os.environ.setdefault("DATABASE_URL", ENV.get("DATABASE_URL", ""))

import numpy as np
from PIL import Image

TOLERANCES = (0, 4, 8, 16, 32)


def load_records(user_id: int, limit: int, body_site=None):
    from web.backend.database.database import SessionLocal
    from web.backend.models.vasi import VASIAssessment

    db = SessionLocal()
    try:
        query = db.query(VASIAssessment).filter(
            VASIAssessment.user_id == user_id,
            VASIAssessment.user_skin_layer.isnot(None),
            VASIAssessment.user_lesion_layer.isnot(None),
        )
        if body_site:
            query = query.filter(VASIAssessment.body_site == body_site)
        rows = query.order_by(VASIAssessment.id.desc()).limit(limit).all()
        return [
            {
                "id": r.id,
                "body_site": r.body_site,
                "image_url": r.image_url,
                "details": r.details or "{}",
                "user_skin_layer": r.user_skin_layer,
                "user_lesion_layer": r.user_lesion_layer,
            }
            for r in rows
        ]
    finally:
        db.close()


def decode(url):
    from web.backend.services.assessment_measurement import decode_mask

    return decode_mask(url)


def boundary_scores(pred: np.ndarray, gold: np.ndarray, scale: float):
    import cv2

    result = {"by_tol": {}}
    gold_area = int(gold.sum())
    pred_area = int(pred.sum())
    union = int((pred | gold).sum())
    result["iou"] = round(float((pred & gold).sum()) / union, 3) if union else 1.0
    result["area_rel"] = round((pred_area - gold_area) / gold_area, 3) if gold_area else None
    result["pred_px"] = pred_area
    result["gold_px"] = gold_area
    for tolerance in TOLERANCES:
        tol = int(round(tolerance * scale))
        if tol > 0:
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * tol + 1, 2 * tol + 1))
            pred_hit = int((pred & cv2.dilate(gold.astype(np.uint8), kernel).astype(bool)).sum())
            gold_hit = int((gold & cv2.dilate(pred.astype(np.uint8), kernel).astype(bool)).sum())
        else:
            pred_hit = int((pred & gold).sum())
            gold_hit = pred_hit
        precision = pred_hit / pred_area if pred_area else 0.0
        recall = gold_hit / gold_area if gold_area else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        result["by_tol"][tolerance] = (round(precision, 3), round(recall, 3), round(f1, 3))
    return result


def cv_candidate(record) -> np.ndarray:
    details = json.loads(record["details"] or "{}")
    raw = details.get("raw_annotation") or {}
    url = raw.get("uncertain_layer_data_url")
    if not url:
        return None
    return decode(url)


def original_bytes(record) -> bytes:
    details = json.loads(record["details"] or "{}")
    job_id = (details.get("annotation") or {}).get("job_id") or (details.get("raw_annotation") or {}).get("job_id")
    if job_id:
        try:
            from web.backend.services.rgb_segmentation import artifacts

            return artifacts.read_input(job_id)
        except OSError:
            pass
    url = record.get("image_url") or ""
    if "/api/files/serve/" in url:
        path = ROOT / "data" / "uploads" / url.split("/api/files/serve/", 1)[1]
        if path.exists():
            return path.read_bytes()
    return None


def vlm_candidate(record, variant: str):
    from web.backend.services import vision_outline
    from web.backend.services.annotation_contract import render_annotation
    from web.backend.services.rgb_segmentation.images import canonical_image, png_bytes
    from web.backend.services.vasi_pixel_refine import refine_annotation_layers
    from web.backend.utils.assessment_body_sites import BODY_SITE_LABELS

    original = original_bytes(record)
    if not original:
        return None, {"error": "original-missing"}
    kwargs = {"zoom": variant in ("hires_zoom", "hires_zoom_consensus"),
              "consensus": variant == "hires_zoom_consensus",
              "thinking": "off"}
    geometry, meta = vision_outline.propose_geometry_sync(
        original, BODY_SITE_LABELS.get("face", "面部"), **kwargs)
    rgb, _ = canonical_image(original)
    image_bytes = png_bytes(rgb)
    settings = vision_outline.outline_settings()
    provenance = None
    layers = refine_annotation_layers(
        image_bytes, geometry,
        time_budget_s=settings["refine_budget_s"],
        max_lesion_regions=settings["refine_regions"],
    )
    if layers:
        provenance = layers.get("provenance")
    else:
        layers = render_annotation(geometry, rgb.shape[1], rgb.shape[0])
    mask = decode(layers.get("lesion_layer_data_url"))
    return mask, meta, provenance


def stability_scores(record):
    from web.backend.services.rgb_segmentation.images import canonical_image
    from web.backend.services.vasi_edge_segmentation import segment_lesions_edge_aware
    from web.backend.services.vasi_skin_mask import build_skin_mask

    original = original_bytes(record)
    if not original:
        return None
    rgb, _ = canonical_image(original)
    h, w = rgb.shape[:2]
    variants = [("original", rgb)]
    for factor in (1.25, 1.6):
        ch, cw = int(h / factor), int(w / factor)
        y0, x0 = (h - ch) // 2, (w - cw) // 2
        view = rgb[y0:y0 + ch, x0:x0 + cw]
        variants.append((f"zoom_in_{factor}",
                         np.asarray(Image.fromarray(view).resize((w, h), Image.Resampling.LANCZOS))))
    small = Image.fromarray(rgb).resize((int(w * 0.7), int(h * 0.7)), Image.Resampling.LANCZOS)
    variants.append(("downscale_0.7",
                     np.asarray(small.resize((w, h), Image.Resampling.BILINEAR))))
    rows = []
    for label, view in variants:
        skin = build_skin_mask(view)
        if skin is None or not skin.any():
            rows.append({"variant": label, "area_pct": None})
            continue
        lesion = (segment_lesions_edge_aware(view, region=skin.astype(bool)) or {}).get("lesion_mask")
        lesion = lesion.astype(bool) if lesion is not None else np.zeros(skin.shape, bool)
        rows.append({"variant": label, "area_pct": round(float(lesion.sum()) / float(skin.sum()) * 100, 2)})
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=("cv", "vlm", "stability"), default="cv")
    parser.add_argument("--user", type=int, default=9)
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--body-site", default=None)
    parser.add_argument("--variant", default="hires_zoom",
                        choices=("hires", "hires_zoom", "hires_zoom_consensus"))
    args = parser.parse_args()

    records = load_records(args.user, args.limit, args.body_site)
    if not records:
        print("no records with user-confirmed masks"); return 1
    print(f"records: {[r['id'] for r in records]}  source={args.source}")
    summary = []
    for record in records:
        gold = decode(record["user_lesion_layer"])
        skin = decode(record["user_skin_layer"])
        if gold is None or skin is None or not skin.any():
            print(f"id={record['id']}: skip (mask decode failed)")
            continue
        gold = gold & skin
        if not gold.any():
            print(f"id={record['id']}: skip (user-confirmed gold lesion is empty)")
            continue
        scale = gold.shape[1] / 1024.0
        if args.source == "cv":
            pred = cv_candidate(record)
            if pred is None:
                print(f"id={record['id']}: no stored candidate")
                continue
            pred = pred & skin
            scores = boundary_scores(pred, gold, scale)
            print(f"id={record['id']} cv: IoU={scores['iou']} area_rel={scores['area_rel']} "
                  f"f1@8={scores['by_tol'][8][2]} f1@32={scores['by_tol'][32][2]}")
            summary.append({"id": record["id"], "source": "cv", **scores})
        elif args.source == "stability":
            rows = stability_scores(record)
            if rows is None:
                print(f"id={record['id']}: original missing"); continue
            values = [r["area_pct"] for r in rows if r["area_pct"] is not None]
            spread = round(max(values) - min(values), 2) if len(values) > 1 else None
            print(f"id={record['id']} stability: {rows} spread={spread}pp")
            summary.append({"id": record["id"], "source": "stability", "rows": rows, "spread_pp": spread})
        else:
            started = time.time()
            pred, meta, provenance = vlm_candidate(record, args.variant)
            if pred is None:
                print(f"id={record['id']} vlm: {meta}"); continue
            pred = pred & skin
            scores = boundary_scores(pred, gold, scale)
            scores["meta"] = meta
            reasons = {}
            if provenance:
                for region in provenance.get("regions") or []:
                    for reason in region.get("reasons") or []:
                        reasons[reason] = reasons.get(reason, 0) + 1
                for reason in provenance.get("fallback_reasons") or []:
                    reasons[reason] = reasons.get(reason, 0) + 1
            scores["refine_status"] = (provenance or {}).get("status")
            scores["refine_engines"] = (provenance or {}).get("engine")
            scores["refine_reasons"] = reasons
            print(f"id={record['id']} vlm[{args.variant}]: IoU={scores['iou']} area_rel={scores['area_rel']} "
                  f"f1@8={scores['by_tol'][8][2]} f1@32={scores['by_tol'][32][2]} "
                  f"({round(time.time() - started, 1)}s, passes={len(meta.get('passes', []))})")
            print(f"   refine_status={scores['refine_status']} engines={(provenance or {}).get('engine')}")
            print(f"   reject reasons: {reasons}")
            summary.append({"id": record["id"], "source": f"vlm:{args.variant}", **scores})

    if summary and args.source in ("cv", "vlm"):
        f1s = [s["by_tol"][8][2] for s in summary if "by_tol" in s]
        f32 = [s["by_tol"][32][2] for s in summary if "by_tol" in s]
        ious = [s["iou"] for s in summary]
        print("-" * 60)
        print(f"mean IoU={round(sum(ious)/len(ious), 3)}  mean f1@8={round(sum(f1s)/len(f1s), 3)}  "
              f"mean f1@32={round(sum(f32)/len(f32), 3)}  n={len(summary)}")

    out_dir = ROOT / "tmp" / "eval_boundary"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{args.source}_{args.variant if args.source == 'vlm' else ''}_{int(time.time())}.json"
    out.write_text(json.dumps({"args": vars(args), "summary": summary}, ensure_ascii=False, indent=1))
    print(f"written: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""
VASI Pipeline Diagnostic: run full pipeline on real uploaded images,
save intermediate + final visualization for manual inspection.

Output per image → data/vasi_diagnostic/
  1. *_original.jpg      — original
  2. *_vlm_bboxes.jpg    — VLM bboxes overlaid (from raw_api_response)
  3. *_sam_contours.jpg  — SAM contours overlaid (from details.contours)
  4. *_final.jpg         — combined overlay
  5. *_result.json       — numeric data
"""

import sys, os, json, io, asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.chdir(Path(__file__).resolve().parents[1])

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from web.backend.database.database import SessionLocal
from web.backend.database.models import User
from web.backend.services.vasi import VASIService


COLORS = [
    (0, 200, 80),   (220, 50, 50),   (50, 110, 255),
    (250, 190, 0),  (220, 60, 220),  (0, 200, 230),
    (255, 130, 0),  (140, 70, 230),  (0, 150, 0),   (180, 40, 40),
]


def draw_bboxes(rgb_img, bboxes, labels=None, lw=3):
    h, w = rgb_img.shape[:2]
    canvas = Image.fromarray(rgb_img).copy()
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
    except Exception:
        font = ImageFont.load_default()
    for i, bbox in enumerate(bboxes):
        x1=int(float(bbox[0])*w); y1=int(float(bbox[1])*h)
        x2=int(float(bbox[2])*w); y2=int(float(bbox[3])*h)
        color = COLORS[i%len(COLORS)]
        for o in range(lw):
            draw.rectangle([x1-o,y1-o,x2+o,y2+o], outline=color)
        text = labels[i] if labels and i<len(labels) else f"L{i+1}"
        tb = draw.textbbox((x1+4, max(y1-24,0)), text, font=font)
        draw.rectangle([tb[0]-3,tb[1]-2,tb[2]+3,tb[3]+2], fill=color)
        draw.text((x1+4, max(y1-24,0)), text, fill=(255,255,255), font=font)
    return np.array(canvas)


def draw_contours(rgb_img, contours_data, lw=2):
    canvas = Image.fromarray(rgb_img).convert("RGBA")
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
    except Exception:
        font = ImageFont.load_default()
    for i, cd in enumerate(contours_data):
        pts = cd.get("points") or cd.get("contour") or cd.get("polygon") or []
        if not pts or len(pts) < 3:
            continue
        color = COLORS[i%len(COLORS)]
        label = cd.get("label", f"C{i+1}")
        area = cd.get("area_percent", 0)
        pts_t = [(int(float(p[0])), int(float(p[1]))) for p in pts]

        overlay = Image.new("RGBA", canvas.size, (0,0,0,0))
        ImageDraw.Draw(overlay).polygon(pts_t, fill=(*color, 80))
        canvas = Image.alpha_composite(canvas, overlay)

        draw = ImageDraw.Draw(canvas)
        for o in range(lw):
            draw.line(pts_t+[pts_t[0]], fill=color, width=1)

        cx, cy = pts_t[0][0]+5, max(pts_t[0][1]-6, 0)
        text = f"{label}({area:.1f}%)"
        tb = draw.textbbox((cx,cy), text, font=font)
        draw.rectangle([tb[0]-2,tb[1]-2,tb[2]+2,tb[3]+2], fill=color)
        draw.text((cx,cy), text, fill=(255,255,255), font=font)
    return np.array(canvas.convert("RGB"))


async def process_image(image_path: str, output_dir: str):
    os.makedirs(output_dir, exist_ok=True)
    basename = Path(image_path).stem

    pil_img = Image.open(image_path).convert("RGB")
    w, h = pil_img.size
    img_rgb = np.array(pil_img)
    pil_img.save(os.path.join(output_dir, f"{basename}_original.jpg"))

    print(f"\n{'='*70}")
    print(f"📷 {basename}  {w}x{h}")
    print(f"{'='*70}")

    # ── Get a real user from DB ──
    db = SessionLocal()
    try:
        user = db.query(User).order_by(User.id.asc()).first()
        if not user:
            print("❌ No user in DB!")
            return
        user_id = user.id
        print(f"  Using user_id={user_id}")

        # ── Read image bytes ──
        with open(image_path, "rb") as f:
            img_bytes = f.read()

        # ── Step 1: VLM only ──
        print("\n[1] VLM call...")
        vlm_result = None
        vlm_bboxes, vlm_labels = [], []
        try:
            service = VASIService(db)
            vlm_result = await service._call_vision_model(img_bytes)
            if vlm_result:
                lesions = vlm_result.get("suspected_lesions", [])
                print(f"    VLM detected {len(lesions)} suspected lesions")
                for i, l in enumerate(lesions):
                    bbox = l.get("bbox")
                    conf = float(l.get("confidence", 0))
                    depig = l.get("depigmentation_level", "?")
                    size = l.get("estimated_size_percent", "?")
                    print(f"      L{i+1}: conf={conf:.0%} depig={depig} size={size}% bbox={bbox}")
                    if bbox and len(bbox) == 4:
                        vlm_bboxes.append([float(v) for v in bbox])
                        vlm_labels.append(f"L{i+1} conf={conf:.0%}")
            else:
                print("    VLM returned null!")
        except Exception as e:
            print(f"    VLM failed: {e}")
            import traceback; traceback.print_exc()

        if vlm_bboxes:
            vlm_img = draw_bboxes(img_rgb, vlm_bboxes, vlm_labels)
            Image.fromarray(vlm_img).save(os.path.join(output_dir, f"{basename}_vlm_bboxes.jpg"))
            print(f"    → vlm_bboxes.jpg ({len(vlm_bboxes)} bboxes)")

        # ── Step 2: Full VASI assessment ──
        print("\n[2] Full VASI assessment (VLM → SAM → formula)...")
        try:
            assessment = await service.assess_vasi(
                user_id=user_id,
                image_file=img_bytes,
                body_site="面部",
                image_type="image/jpeg",
                image_filename=f"{basename}.jpg",
                precision="quick",
            )
        except Exception as e:
            print(f"    assess_vasi failed: {e}")
            import traceback; traceback.print_exc()
            db.rollback()
            return

        # ── Extract contours from assessment.details ──
        contours = []
        details = {}
        raw_response = {}
        try:
            details = json.loads(assessment.details) if isinstance(assessment.details, str) else assessment.details or {}
            raw_response = json.loads(assessment.raw_api_response) if isinstance(assessment.raw_api_response, str) else assessment.raw_api_response or {}
            contours = details.get("contours", [])
        except Exception:
            pass

        print(f"    VASI={assessment.vasi_score}, Area={assessment.area_percentage}%")
        print(f"    Source={assessment.assessment_source}, contours={len(contours)}")

        # Print per-lesion details from contours
        if contours:
            print(f"\n  Per-lesion SAM contours:")
            for c in contours:
                area = c.get("area_percent", "N/A")
                depig = c.get("depigmentation_level", c.get("depigmentation_norm", "N/A"))
                conf = c.get("confidence", "N/A")
                contrast = c.get("contrast_to_skin", c.get("contrast_factor", "N/A"))
                n_pts = len(c.get("points", c.get("contour", c.get("polygon", []))))
                print(f"    {c.get('label')}: area={area}% depig={depig} conf={conf} n_pts={n_pts}")

            # Draw SAM contours
            contours_img = draw_contours(img_rgb, contours)
            Image.fromarray(contours_img).save(os.path.join(output_dir, f"{basename}_sam_contours.jpg"))
            print(f"\n    → sam_contours.jpg ({len(contours)} contours)")

            # Draw combined overlay
            overlay = draw_contours(img_rgb.copy(), contours)
            if vlm_bboxes:
                overlay = draw_bboxes(overlay, vlm_bboxes, vlm_labels)
            Image.fromarray(overlay).save(os.path.join(output_dir, f"{basename}_final.jpg"))
            print(f"    → final.jpg")
        else:
            print(f"    ⚠️  No contours!")

        # ── Save JSON data ──
        lesion_details = []
        for c in contours:
            lesion_details.append({
                "label": c.get("label"),
                "area_percent": c.get("area_percent"),
                "depigmentation_level": c.get("depigmentation_level"),
                "depigmentation_norm": c.get("depigmentation_norm"),
                "contrast_to_skin": c.get("contrast_to_skin"),
                "confidence": c.get("confidence"),
                "n_points": len(c.get("points", c.get("contour", c.get("polygon", [])))),
            })

        result_data = {
            "image": basename,
            "size": [w, h],
            "vasi_score": assessment.vasi_score,
            "area_percentage": assessment.area_percentage,
            "source": assessment.assessment_source,
            "classification": assessment.classification,
            "stage": assessment.stage,
            "confidence": assessment.confidence,
            "num_contours": len(contours),
            "lesion_details": lesion_details,
        }
        with open(os.path.join(output_dir, f"{basename}_result.json"), "w") as f:
            json.dump(result_data, f, indent=2, ensure_ascii=False, default=str)

    finally:
        db.close()


async def main():
    upload_dir = "/root/subskin/data/uploads/vasi"
    output_dir = "/root/subskin/data/vasi_diagnostic"

    import glob
    images = sorted(glob.glob(os.path.join(upload_dir, "*.jpg")),
                    key=os.path.getmtime, reverse=True)

    for img_path in images[:2]:
        try:
            await process_image(img_path, output_dir)
        except Exception as e:
            print(f"\n❌ ERROR on {img_path}: {e}")
            import traceback
            traceback.print_exc()

    print(f"\n✅ All diagnostics saved to {output_dir}/")
    # List output files
    for f in sorted(os.listdir(output_dir)):
        print(f"   {f}")


if __name__ == "__main__":
    asyncio.run(main())
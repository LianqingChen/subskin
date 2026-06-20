"""
VASI 精度对比测试脚本

用法:
    cd /root/subskin
    source .venv/bin/activate
    python tests/test_vasi_accuracy.py [--image PATH] [--all] [--verbose]
"""
import argparse
import asyncio
import base64
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def find_test_images() -> list[str]:
    """Find all uploaded VASI test images."""
    vasi_dir = Path("data/uploads/vasi")
    if not vasi_dir.exists():
        print(f"Error: {vasi_dir} not found")
        return []
    images = sorted(vasi_dir.glob("*.jpg")) + sorted(vasi_dir.glob("*.png")) + sorted(vasi_dir.glob("*.jpeg"))
    return [str(p) for p in images]


async def test_vlm_analysis(image_path: str) -> Optional[Dict[str, Any]]:
    """Run VLM analysis on a single image and return results."""
    from web.backend.services.vasi import VASIService

    # Read image
    with open(image_path, "rb") as f:
        image_bytes = f.read()

    # Create a minimal service instance
    # We need a DB session to create VASIService, so we'll bypass the service
    # and call _call_vision_model directly
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from web.backend.database.database import get_db

    # Use in-memory SQLite for testing
    engine = create_engine("sqlite:///:memory:", echo=False)
    from web.backend.database.models import Base
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    try:
        service = VASIService(db)
        start = time.time()
        result = await service._call_vision_model(image_bytes)
        elapsed = time.time() - start

        if result is None:
            return None

        return {
            "image": image_path,
            "elapsed_seconds": round(elapsed, 2),
            "vasi_score": result.get("vasi_score"),
            "area_percentage": result.get("area_percentage"),
            "classification": result.get("classification"),
            "stage": result.get("stage"),
            "body_site": result.get("body_site"),
            "depigmentation_level": result.get("depigmentation_level"),
            "source": result.get("source"),
            "num_lesions": len(result.get("suspected_lesions", [])),
            "has_skin_bbox": bool(result.get("skin_region", {}).get("bbox")),
            "lesion_details": [
                {
                    "label": l.get("label"),
                    "has_bbox": bool(l.get("bbox")),
                    "has_edge_points": bool(l.get("edge_points")),
                    "bbox": l.get("bbox"),
                    "depigmentation": l.get("depigmentation_level"),
                    "confidence": l.get("confidence"),
                    "boundary_type": l.get("boundary_type"),
                    "contrast_to_skin": l.get("contrast_to_skin"),
                }
                for l in result.get("suspected_lesions", [])
            ],
            "visual_features_summary": {
                "visibility": result.get("visual_features", {}).get("visibility", {}).get("level"),
                "color_level": result.get("visual_features", {}).get("color", {}).get("level"),
                "border_level": result.get("visual_features", {}).get("border", {}).get("level"),
                "distribution": result.get("visual_features", {}).get("distribution", {}).get("pattern"),
                "fitzpatrick": result.get("visual_features", {}).get("color", {}).get("skin_fitzpatrick"),
            },
            "lighting_condition": result.get("skin_region", {}).get("lighting_condition"),
            "reference_objects": len(result.get("reference_objects", [])),
            "limitations": result.get("raw_response", {}).get("limitations", []),
            "details": result.get("details"),
        }
    finally:
        db.close()


async def test_full_pipeline(image_path: str, body_site: str = "hands") -> Optional[Dict[str, Any]]:
    """Run full VASI pipeline: preprocess → VLM → SAM → result."""
    import io
    from PIL import Image

    from web.backend.services.vasi import VASIService
    from web.backend.services.vasi_segmentation import segment_vitiligo_guided, segment_vitiligo
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine("sqlite:///:memory:", echo=False)
    from web.backend.database.models import Base
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    with open(image_path, "rb") as f:
        image_bytes = f.read()

    try:
        service = VASIService(db)

        total_start = time.time()

        # Step 1: Quality check
        quality_ok = True
        quality_info = {}
        if service.quality_checker and service.quality_checker.available:
            quality = service.quality_checker.check_all(image_bytes)
            quality_ok = quality.overall
            quality_info = {
                "overall": quality.overall,
                "suggestions": quality.suggestions,
                "blur_score": quality.blur_score,
            }

        # Step 2: Preprocess
        processed = image_bytes
        preprocess_time = 0
        if service.preprocessor and service.preprocessor.available:
            ps = time.time()
            processed = service.preprocessor.preprocess(image_bytes)
            preprocess_time = time.time() - ps

        # Step 3: VLM
        vlm_time = time.time()
        vlm_result = await service._call_vision_model(processed)
        vlm_elapsed = time.time() - vlm_time

        # Step 4: SAM
        sam_elapsed = 0
        contours_count = 0
        sam_source = "none"
        if vlm_result:
            skin_region = vlm_result.get("skin_region", {})
            skin_bbox = None
            if skin_region.get("bbox") and len(skin_region["bbox"]) == 4:
                side = skin_region["bbox"]
                if all(0 <= v <= 1.5 for v in side):
                    skin_bbox = [float(v) for v in skin_region["bbox"]]

            lesions = vlm_result.get("suspected_lesions", [])
            lesion_centers = [
                [float(l["center"][0]), float(l["center"][1])]
                for l in lesions if l.get("center") and len(l["center"]) == 2
            ] if lesions else None
            lesion_sizes = [
                float(l.get("estimated_size_percent", 5.0))
                for l in lesions if l.get("center") and len(l["center"]) == 2
            ] if lesions else None
            lesion_bboxes = vlm_result.get("lesion_bboxes")

            if skin_bbox or lesion_centers:
                ss = time.time()
                if lesion_bboxes:
                    seg_result = segment_vitiligo_guided(
                        processed, skin_bbox, lesion_centers, "quick",
                        lesion_sizes, lesion_bboxes,
                    )
                else:
                    seg_result = segment_vitiligo_guided(
                        processed, skin_bbox, lesion_centers, "quick",
                        lesion_sizes,
                    )
                sam_elapsed = time.time() - ss
                if seg_result["success"]:
                    contours_count = len(seg_result.get("contours", []))
                    sam_source = seg_result.get("source", "unknown")
            else:
                ss = time.time()
                seg_result = segment_vitiligo(processed, 0.005, 5, "quick")
                sam_elapsed = time.time() - ss
                if seg_result["success"]:
                    contours_count = len(seg_result.get("contours", []))
                    sam_source = seg_result.get("source", "unknown")

        total_elapsed = time.time() - total_start

        summary = {
            "image": os.path.basename(image_path),
            "total_seconds": round(total_elapsed, 2),
            "preprocess_seconds": round(preprocess_time, 3) if preprocess_time else None,
            "vlm_seconds": round(vlm_elapsed, 2),
            "sam_seconds": round(sam_elapsed, 2) if sam_elapsed else None,
            "quality_ok": quality_ok,
            "quality_info": quality_info,
            "vlm_source": vlm_result.get("source") if vlm_result else None,
            "vlm_score": vlm_result.get("vasi_score") if vlm_result else None,
            "vlm_area_pct": vlm_result.get("area_percentage") if vlm_result else None,
            "vlm_num_lesions": len(vlm_result.get("suspected_lesions", [])) if vlm_result else 0,
            "vlm_has_per_lesion_bbox": any(
                l.get("bbox") for l in (vlm_result.get("suspected_lesions", []) if vlm_result else [])
            ),
            "vlm_classification": vlm_result.get("classification") if vlm_result else None,
            "vlm_stage": vlm_result.get("stage") if vlm_result else None,
            "vlm_body_site": vlm_result.get("body_site") if vlm_result else None,
            "sam_contours_count": contours_count,
            "sam_source": sam_source,
        }

        if vlm_result:
            summary["vlm_lesion_details"] = [
                {
                    "label": l.get("label"),
                    "depigmentation": l.get("depigmentation_level"),
                    "confidence": l.get("confidence"),
                    "boundary": l.get("boundary_type"),
                    "contrast": l.get("contrast_to_skin"),
                    "has_bbox": bool(l.get("bbox")),
                    "has_edge_points": bool(l.get("edge_points")),
                }
                for l in vlm_result.get("suspected_lesions", [])
            ]
            # VLM→SAM yield: how many VLM lesions produced SAM contours
            vlm_count = len(vlm_result.get("suspected_lesions", []))
            summary["vlm_to_sam_yield_pct"] = round(100 * contours_count / max(vlm_count, 1), 1)
            # SAM-measured area percentage (pixel-based, not VLM estimate)
            if sam_source != "none":
                summary["sam_area_pct"] = seg_result.get("total_area_percent", 0)

        return summary

    finally:
        db.close()


async def test_production_flow(image_path: str) -> Optional[Dict[str, Any]]:
    """Run the full production pipeline: _call_vasi_api (includes formula scoring)."""
    from web.backend.services.vasi import VASIService
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine("sqlite:///:memory:", echo=False)
    from web.backend.database.models import Base
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    with open(image_path, "rb") as f:
        image_bytes = f.read()

    try:
        service = VASIService(db)
        total_start = time.time()
        result = await service._call_vasi_api(image_bytes, "quick")
        total_elapsed = time.time() - total_start

        if result is None:
            return None

        lesions = result.get("suspected_lesions", [])
        contours = result.get("contours", [])
        details = result.get("details", {})

        summary = {
            "image": os.path.basename(image_path),
            "total_seconds": round(total_elapsed, 2),
            "vasi_score": result.get("vasi_score"),
            "formula_score_set": True,
            "area_percentage": result.get("area_percentage"),
            "contrast_adj_area": result.get("area_percentage_contrast_adjusted"),
            "body_site": result.get("body_site"),
            "source": result.get("source"),
            "vlm_num_lesions": len(lesions),
            "sam_contours_count": len(contours),
            "vlm_to_sam_yield_pct": round(100 * len(contours) / max(len(lesions), 1), 1),
            "depig_method": details.get("vasi_score_depig_method"),
            "depig_weighted": details.get("vasi_score_depig"),
            "score_source": details.get("vasi_score_source"),
        }

        # Per-lesion detail
        summary["lesion_details"] = []
        for i, l in enumerate(lesions):
            c = contours[i] if i < len(contours) else {}
            summary["lesion_details"].append({
                "label": l.get("label"),
                "depigmentation": l.get("depigmentation_level"),
                "confidence": l.get("confidence"),
                "contrast": l.get("contrast_to_skin"),
                "has_bbox": bool(l.get("bbox")),
                "sam_area_pct": c.get("area_percent") if c else None,
                "contrast_factor": c.get("contrast_factor") if c else None,
            })

        return summary

    finally:
        db.close()


async def main():
    parser = argparse.ArgumentParser(description="VASI 精度对比测试")
    parser.add_argument("--image", type=str, help="测试单张图片")
    parser.add_argument("--all", action="store_true", help="测试所有图片")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    parser.add_argument("--pipeline", action="store_true", help="运行完整管线测试(含SAM)")
    parser.add_argument("--production", action="store_true", help="运行生产流程测试(含formula评分)")
    parser.add_argument("--count", type=int, default=3, help="测试图片数量 (默认3)")
    args = parser.parse_args()

    images = find_test_images()
    print(f"找到 {len(images)} 张测试图片")

    if args.image:
        test_images = [args.image]
    elif args.all:
        test_images = images
    else:
        test_images = images[:args.count]

    print(f"将测试 {len(test_images)} 张图片:")
    for img in test_images:
        print(f"  - {img}")

    results = []
    for i, img in enumerate(test_images):
        print(f"\n{'='*60}")
        print(f"[{i+1}/{len(test_images)}] 测试: {img}")
        print(f"{'='*60}")

        if args.production:
            result = await test_production_flow(img)
        elif args.pipeline:
            result = await test_full_pipeline(img)
        else:
            result = await test_vlm_analysis(img)

        if result is None:
            print(f"  ❌ 失败 (VLM 返回 None)")
            continue

        print(f"  ⏱️  耗时: {result.get('elapsed_seconds', result.get('total_seconds'))}s")
        if "formula_score_set" in result:
            print(f"  📊 Formula VASI评分: {result['vasi_score']}")
            print(f"  ⚖️  加权脱色: {result.get('depig_weighted')} ({result.get('depig_method')})")
            if result.get("contrast_adj_area"):
                print(f"  📏 对比度调整面积: {result['contrast_adj_area']}%")
        elif "vlm_score" in result:
            print(f"  📊 VASI评分: {result['vlm_score']}")
        if "area_percentage" in result:
            print(f"  📐 面积占比: {result['area_percentage']}%")
        if "num_lesions" in result:
            print(f"  🔍 检测到白斑: {result['num_lesions']} 处")
        if "vlm_num_lesions" in result:
            print(f"  🔍 VLM检测白斑: {result['vlm_num_lesions']} 处")
        if "sam_contours_count" in result:
            print(f"  ✂️ SAM分割轮廓: {result['sam_contours_count']} 个")
            yield_pct = result.get("vlm_to_sam_yield_pct", 0)
            if yield_pct:
                print(f"  📐 SAM→VLM命中率: {yield_pct}%")
        if "sam_area_pct" in result and result["sam_area_pct"]:
            print(f"  📏 SAM实测面积占比: {result['sam_area_pct']}%")
        if "vlm_has_per_lesion_bbox" in result:
            print(f"  🎯 VLM per-lesion bbox: {'✅ 有' if result['vlm_has_per_lesion_bbox'] else '❌ 无'}")
        if "classification" in result:
            print(f"  🏷️  分类: {result.get('classification') or result.get('vlm_classification')}")
        if "source" in result:
            print(f"  🔧 来源: {result.get('source') or result.get('vlm_source')}")

        if args.verbose:
            lesion_key = "lesion_details" if "lesion_details" in result else "vlm_lesion_details"
            lesions = result.get(lesion_key, [])
            if lesions:
                print(f"  📋 白斑详情:")
                for l in lesions:
                    has_bbox = "✅" if l.get("has_bbox") else "❌"
                    line = f"    - {l.get('label')}: 脱色{l.get('depigmentation')}级, " \
                           f"置信度{l.get('confidence')}, 边界{l.get('boundary')}, " \
                           f"bbox:{has_bbox}"
                    if l.get("contrast") is not None:
                        line += f", 对比度{l.get('contrast')}"
                    # Production test: per-lesion SAM area + contrast factor
                    if l.get("sam_area_pct") is not None:
                        line += f"\n      SAM面积={l['sam_area_pct']}%, 对比因子={l.get('contrast_factor', '-')}"
                    print(line)

        results.append(result)

    # Summary
    print(f"\n{'='*60}")
    print(f"测试总结")
    print(f"{'='*60}")
    success = len(results)
    total = len(test_images)
    print(f"  成功: {success}/{total}")
    if success > 0:
        # Pipeline test uses vlm_*/sam_* keys; VLM-only uses vasi_score/area_percentage;
        # Production test uses vasi_score/area_percentage with formula_score_set flag.
        is_prod = "formula_score_set" in (results[0] or {})
        scores = [r.get("vasi_score", 0) or r.get("vlm_score", 0) or 0 for r in results if r]
        areas = [r.get("area_percentage", 0) or r.get("vlm_area_pct", 0) or 0 for r in results if r]
        times = [r.get("elapsed_seconds", 0) or r.get("total_seconds", 0) or 0 for r in results if r]
        lesion_counts = [r.get("num_lesions", 0) or r.get("vlm_num_lesions", 0) or 0 for r in results if r]
        sam_contours = [r.get("sam_contours_count", 0) or 0 for r in results if r]
        yield_pcts = [r.get("vlm_to_sam_yield_pct", 0) or 0 for r in results if r]
        sam_areas = [r.get("sam_area_pct", 0) or 0 for r in results if r]
        depig_weights = [r.get("depig_weighted", 0) or 0 for r in results if r]
        contrast_adj_areas = [r.get("contrast_adj_area", 0) or 0 for r in results if r]

        vlm_key = "vlm_has_per_lesion_bbox"
        if vlm_key in results[0]:
            bbox_hits = sum(1 for r in results if r.get(vlm_key))
            print(f"  Per-lesion bbox: {bbox_hits}/{success} ({100*bbox_hits/success:.0f}%)")

        if scores:
            print(f"  VASI评分: avg={sum(scores)/len(scores):.1f}, range=[{min(scores):.0f}-{max(scores):.0f}]")
        if areas:
            print(f"  面积占比: avg={sum(areas)/len(areas):.1f}%")
        if lesion_counts:
            print(f"  白斑数量: avg={sum(lesion_counts)/len(lesion_counts):.1f}/image")
        if times:
            print(f"  平均耗时: {sum(times)/len(times):.1f}s")
        if yield_pcts and any(yield_pcts):
            print(f"  VLM->SAM hit: avg={sum(yield_pcts)/len(yield_pcts):.0f}%")
        if sam_areas and any(sam_areas):
            print(f"  SAM measured area: avg={sum(sam_areas)/len(sam_areas):.1f}%")
        if depig_weights and any(depig_weights):
            print(f"  Weighted depig: avg={sum(depig_weights)/len(depig_weights):.2f}")
        if contrast_adj_areas and any(contrast_adj_areas):
            print(f"  Contrast-adj area: avg={sum(contrast_adj_areas)/len(contrast_adj_areas):.1f}%")

    # Save results
    output_path = Path("data/vasi_accuracy_test.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str))
    print(f"\n📁 结果已保存到: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
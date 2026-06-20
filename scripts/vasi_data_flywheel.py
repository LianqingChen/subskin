#!/usr/bin/env python3
"""
VASI 数据飞轮 — 用户修正数据收集与训练集构建

从用户手动修正的白斑轮廓中自动提取 (图片, 标注mask) 对,
积累到训练集中, 供后续 nnU-Net 或专用模型训练。

用法:
    python scripts/vasi_data_flywheel.py [--export DIR] [--stats]
    python scripts/vasi_data_flywheel.py --dry-run     # 预览, 不导出
    python scripts/vasi_data_flywheel.py --export data/vasi_training_set/
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

import numpy as np

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_db_session():
    """Get a database session using the configured DB."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from web.backend.database.database import DATABASE_URL
    
    engine = create_engine(DATABASE_URL, echo=False)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def extract_corrected_samples(db_session) -> List[Dict[str, Any]]:
    """Query all user-corrected assessments with valid contour diffs."""
    from web.backend.models.vasi import VASIAssessment
    
    assessments = (
        db_session.query(VASIAssessment)
        .filter(
            VASIAssessment.is_user_corrected == True,
            VASIAssessment.contour_diff.isnot(None),
            VASIAssessment.user_lesion_layer.isnot(None),
        )
        .order_by(VASIAssessment.assessment_date.desc())
        .all()
    )
    
    samples = []
    for a in assessments:
        try:
            diff = json.loads(a.contour_diff) if a.contour_diff else {}
        except (json.JSONDecodeError, TypeError):
            diff = {}
        
        samples.append({
            "id": a.id,
            "user_id": a.user_id,
            "assessment_date": a.assessment_date.isoformat() if a.assessment_date else None,
            "image_url": a.image_url,
            "image_key": a.image_key,
            "body_site": a.body_site,
            "ai_vasi_score": a.vasi_score,
            "user_vasi_score": a.final_vasi_score,
            "ai_area_pct": a.area_percentage,
            "user_area_pct": a.final_area_percentage,
            "classification": a.classification,
            "stage": a.stage,
            "contour_diff": diff,
            "has_user_lesion_layer": bool(a.user_lesion_layer),
            "has_ai_lesion_layer": bool(a.ai_lesion_layer),
        })
    
    return samples


def extract_lesion_mask(lesion_layer_data_url: str) -> Optional[np.ndarray]:
    """Extract a binary mask from a base64 PNG data URL."""
    import base64
    from PIL import Image
    import io
    
    if not lesion_layer_data_url:
        return None
    
    try:
        # Data URL: data:image/png;base64,xxxxx
        if ',' in lesion_layer_data_url:
            b64_data = lesion_layer_data_url.split(',', 1)[1]
        else:
            b64_data = lesion_layer_data_url
        
        img_bytes = base64.b64decode(b64_data)
        img = Image.open(io.BytesIO(img_bytes)).convert('RGBA')
        # Extract alpha channel as mask (non-zero alpha = lesion)
        alpha = np.array(img)[:, :, 3]
        mask = (alpha > 40).astype(np.uint8) * 255
        return mask
    except Exception as e:
        print(f"  Warning: Failed to parse lesion layer: {e}")
        return None


def export_training_set(
    db_session,
    output_dir: str,
    min_area_pct: float = 0.0,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Export corrected samples as image+mask pairs for training.
    
    Directory structure:
        output_dir/
          images/    — original photos
          masks/     — binary user-corrected lesion masks (same name)
          metadata/  — per-sample JSON with body_site, scores, etc.
          dataset.json — index of all samples
    """
    samples = extract_corrected_samples(db_session)
    
    output_path = Path(output_dir)
    images_dir = output_path / "images"
    masks_dir = output_path / "masks"
    meta_dir = output_path / "metadata"
    
    if not dry_run:
        images_dir.mkdir(parents=True, exist_ok=True)
        masks_dir.mkdir(parents=True, exist_ok=True)
        meta_dir.mkdir(parents=True, exist_ok=True)
    
    exported = []
    stats = {
        "total_corrected": len(samples),
        "exported": 0,
        "skipped_no_image": 0,
        "skipped_no_mask": 0,
        "skipped_too_small": 0,
        "errors": 0,
        "body_sites": {},
        "total_pixels_annotated": 0,
    }
    
    for s in samples:
        # Check if image file exists
        image_path = None
        image_key = s.get("image_key", "")
        if image_key:
            # Try local upload path
            parts = image_key.split("/")
            local_name = parts[-1] if parts else ""
            if local_name:
                local_path = Path("data/uploads/vasi") / local_name
                if local_path.exists():
                    image_path = str(local_path)
        
        if not image_path:
            stats["skipped_no_image"] += 1
            continue
        
        # Get lesion mask from user_lesion_layer
        lesion_url = s.get("user_lesion_layer") or s.get("ai_lesion_layer")
        if not lesion_url:
            # Fallback: get user-corrected contours from contour_diff
            diff = s.get("contour_diff", {})
            user_contours = diff.get("user_contours", [])
            if not user_contours:
                stats["skipped_no_mask"] += 1
                continue
        
        lesion_mask = extract_lesion_mask(lesion_url)
        if lesion_mask is None:
            stats["skipped_no_mask"] += 1
            continue
        
        # Check minimum area
        lesion_pixels = int(lesion_mask.sum() / 255)
        total_pixels = lesion_mask.shape[0] * lesion_mask.shape[1]
        area_pct = 100 * lesion_pixels / max(total_pixels, 1)
        
        if area_pct < min_area_pct:
            stats["skipped_too_small"] += 1
            continue
        
        sample_id = f"vasi_{s['id']}"
        
        if not dry_run:
            # Copy image
            import shutil
            ext = Path(image_path).suffix or ".jpg"
            shutil.copy2(image_path, images_dir / f"{sample_id}{ext}")
            
            # Save mask
            from PIL import Image
            mask_img = Image.fromarray(lesion_mask, mode='L')
            mask_img.save(masks_dir / f"{sample_id}_mask.png")
            
            # Save metadata
            meta = {
                "sample_id": sample_id,
                "assessment_id": s["id"],
                "body_site": s["body_site"],
                "classification": s["classification"],
                "stage": s["stage"],
                "ai_score": s["ai_vasi_score"],
                "user_score": s["user_vasi_score"],
                "ai_area_pct": s["ai_area_pct"],
                "user_area_pct": s["user_area_pct"],
                "image_size": list(lesion_mask.shape),
                "lesion_pixels": lesion_pixels,
                "lesion_area_pct": round(area_pct, 2),
                "exported_at": datetime.now().isoformat(),
            }
            (meta_dir / f"{sample_id}.json").write_text(
                json.dumps(meta, indent=2, ensure_ascii=False)
            )
        
        exported.append({
            "sample_id": sample_id,
            "assessment_id": s["id"],
            "body_site": s["body_site"],
            "area_pct": round(area_pct, 2),
        })
        
        stats["exported"] += 1
        stats["total_pixels_annotated"] += lesion_pixels
        stats["body_sites"][s["body_site"]] = stats["body_sites"].get(s["body_site"], 0) + 1
    
    # Write dataset index
    if not dry_run:
        index = {
            "dataset_name": "vasi_user_corrected",
            "created_at": datetime.now().isoformat(),
            "total_samples": len(exported),
            "stats": stats,
            "samples": exported,
        }
        (output_path / "dataset.json").write_text(
            json.dumps(index, indent=2, ensure_ascii=False)
        )
    
    return stats


def compute_accuracy_stats(db_session) -> Dict[str, Any]:
    """Compute AI vs user accuracy statistics from contour_diff data."""
    samples = extract_corrected_samples(db_session)
    
    total = len(samples)
    if total == 0:
        return {"status": "no_data", "message": "No user-corrected assessments found"}
    
    # Collect metrics
    diffs = []
    score_deltas = []
    area_deltas = []
    modified_count = 0
    
    for s in samples:
        diff = s.get("contour_diff", {})
        summary = diff.get("summary", {})
        if summary.get("modified"):
            modified_count += 1
        
        avg_dist = summary.get("avg_point_distance")
        if avg_dist is not None:
            diffs.append(avg_dist)
        
        if s["ai_vasi_score"] and s["user_vasi_score"]:
            score_deltas.append(s["user_vasi_score"] - s["ai_vasi_score"])
        
        if s["ai_area_pct"] and s["user_area_pct"]:
            area_deltas.append(s["user_area_pct"] - s["ai_area_pct"])
    
    return {
        "total_corrected_assessments": total,
        "user_modified_pct": round(100 * modified_count / max(total, 1), 1),
        "avg_contour_distance": round(np.mean(diffs), 4) if diffs else None,
        "max_contour_distance": round(max(diffs), 4) if diffs else None,
        "avg_score_delta": round(np.mean(score_deltas), 1) if score_deltas else None,
        "avg_area_delta_pct": round(np.mean(area_deltas), 1) if area_deltas else None,
        "body_sites": {},
    }


def main():
    parser = argparse.ArgumentParser(
        description="VASI 数据飞轮 — 从用户修正中构建训练数据集"
    )
    parser.add_argument("--export", type=str, help="导出训练集目录")
    parser.add_argument("--stats", action="store_true", help="显示精度统计")
    parser.add_argument("--dry-run", action="store_true", help="预览但不导出")
    parser.add_argument("--min-area", type=float, default=0.0, 
                       help="最小白斑面积 % (默认0, 导出所有)")
    args = parser.parse_args()
    
    db = get_db_session()
    
    try:
        if args.stats:
            print("📊 计算 AI vs 用户修正精度统计...")
            stats = compute_accuracy_stats(db)
            print(json.dumps(stats, indent=2, ensure_ascii=False))
        
        if args.export or args.dry_run:
            output = args.export or "data/vasi_training_set"
            print(f"\n📦 导出训练集到: {output}")
            if args.dry_run:
                print("   (dry-run: 不实际写入文件)")
            
            result = export_training_set(
                db, output, min_area_pct=args.min_area, dry_run=args.dry_run
            )
            
            print(f"\n📈 导出统计:")
            print(f"   总修正评估: {result['total_corrected']}")
            print(f"   成功导出: {result['exported']} 样本")
            print(f"   跳过(无图片): {result['skipped_no_image']}")
            print(f"   跳过(无标注): {result['skipped_no_mask']}")
            print(f"   跳过(面积太小): {result['skipped_too_small']}")
            print(f"   错误: {result['errors']}")
            print(f"   总标注像素: {result['total_pixels_annotated']:,}")
            if result['body_sites']:
                print(f"   部位分布:")
                for site, count in sorted(result['body_sites'].items()):
                    print(f"     - {site}: {count}")
        
        if not args.stats and not args.export and not args.dry_run:
            # Default: show summary
            samples = extract_corrected_samples(db)
            print(f"📊 VASI 数据飞轮状态")
            print(f"   用户修正评估总数: {len(samples)}")
            
            if samples:
                latest = samples[0]
                print(f"   最近修正: {latest['assessment_date']} (ID:{latest['id']})")
                print(f"   部位: {latest['body_site']}")
            
            print(f"\n   用法:")
            print(f"     --stats   查看精度统计")
            print(f"     --export DIR  导出训练集")
            print(f"     --dry-run 预览导出")
    
    finally:
        db.close()


if __name__ == "__main__":
    main()
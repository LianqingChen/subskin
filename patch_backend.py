#!/usr/bin/env python3
"""Apply the backend patch to image_label.py"""
PATH = "/root/subskin/web/backend/api/image_label.py"
with open(PATH, "r") as f:
    content = f.read()

# ── Patch 1: Replace sync_from_assessments ──
OLD_SYNC_START = '@router.post("/admin/image-labels/sync-assessments")\nasync def sync_from_assessments('
OLD_SYNC_END = '    })\n\n\n@router.post("/admin/image-labels/training-export"'

new_sync = '''@router.post("/admin/image-labels/sync-assessments")
async def sync_from_assessments(
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """从现有 VASI 评估记录中同步创建打标记录
    
    将所有已有的评估图片导入打标系统，自动填充 AI 和用户标注数据。
    已同步过的记录不会重复创建。
    
    增强：同步用户的填涂图层（skin/lesion mask）作为预填充数据，
    管理员可以在用户的基础上修改，无需从零开始。
    """
    existing_hashes = set(
        row[0] for row in db.query(ImageLabel.image_hash).filter(ImageLabel.image_hash.isnot(None)).all()
    )
    existing_assessment_ids = set(
        row[0] for row in db.query(ImageLabel.assessment_id).filter(ImageLabel.assessment_id.isnot(None)).all()
    )

    assessments = db.query(VASIAssessment).order_by(VASIAssessment.assessment_date.desc()).all()
    created = 0
    skipped = 0
    user_annotations_created = 0

    for a in assessments:
        if a.id in existing_assessment_ids:
            skipped += 1
            continue

        image_hash = a.image_hash
        if image_hash and image_hash in existing_hashes:
            skipped += 1
            continue

        # Determine AI is_vitiligo
        ai_is_vit = (a.classification in ("节段型", "非节段型", "混合型", "未定型") if a.classification else True)

        label = ImageLabel(
            assessment_id=a.id,
            original_user_id=a.user_id,
            image_url=a.image_url,
            image_key=a.image_key,
            image_hash=image_hash,
            ai_body_site=a.body_site,
            ai_is_vitiligo=ai_is_vit,
            ai_vitiligo_type=a.classification if a.classification in ("节段型", "非节段型", "混合型", "未定型") else None,
            ai_vitiligo_stage=a.stage,
            ai_area_percentage=a.area_percentage if a.area_percentage is not None else (
                a.final_area_percentage if a.final_area_percentage is not None else None
            ),
            ai_vasi_score=a.vasi_score if a.vasi_score is not None else (
                a.final_vasi_score if a.final_vasi_score is not None else None
            ),
            ai_confidence=a.confidence,
            ai_details=a.details,
            user_body_site=a.body_site if a.is_user_corrected else None,
            user_is_vitiligo=ai_is_vit if a.is_user_corrected else None,
            user_vitiligo_type=a.classification if a.is_user_corrected else None,
            user_area_percentage=a.final_area_percentage if a.is_user_corrected else None,
            user_vasi_score=a.final_vasi_score if a.is_user_corrected else None,
            user_depigmentation_level=a.depigmentation_level if a.is_user_corrected else None,
            is_user_deleted=False,
        )
        db.add(label)
        db.flush()

        # ── Sync user's mask data ──
        user_has_data = False
        if a.user_skin_layer and isinstance(a.user_skin_layer, str) and len(a.user_skin_layer) > 100:
            user_ann = ImageLabelAnnotation(
                image_label_id=label.id,
                source="user",
                region_index=0,
                body_site=a.body_site,
                is_vitiligo=ai_is_vit,
                vitiligo_type=a.classification if a.classification in ("节段型", "非节段型", "混合型", "未定型") else None,
                area_percentage=a.final_area_percentage,
                depigmentation_level=a.depigmentation_level,
                skin_mask_data=a.user_skin_layer,
                mask_data=a.user_lesion_layer if a.user_lesion_layer else None,
                confidence=None,
                notes="用户测评页面填涂结果 — 管理员可在此基础上修改",
            )
            db.add(user_ann)
            user_has_data = True

        if a.user_lesion_layer and isinstance(a.user_lesion_layer, str) and len(a.user_lesion_layer) > 100 and not user_has_data:
            user_ann = ImageLabelAnnotation(
                image_label_id=label.id,
                source="user",
                region_index=0,
                body_site=a.body_site,
                is_vitiligo=ai_is_vit,
                vitiligo_type=a.classification if a.classification in ("节段型", "非节段型", "混合型", "未定型") else None,
                area_percentage=a.final_area_percentage,
                depigmentation_level=a.depigmentation_level,
                mask_data=a.user_lesion_layer,
                confidence=None,
                notes="用户测评页面填涂结果 — 管理员可在此基础上修改",
            )
            db.add(user_ann)
            user_has_data = True

        if a.ai_skin_layer and isinstance(a.ai_skin_layer, str) and len(a.ai_skin_layer) > 100:
            ai_ann = ImageLabelAnnotation(
                image_label_id=label.id,
                source="ai",
                region_index=0,
                body_site=a.body_site,
                is_vitiligo=ai_is_vit,
                vitiligo_type=a.classification if a.classification in ("节段型", "非节段型", "混合型", "未定型") else None,
                area_percentage=a.area_percentage,
                skin_mask_data=a.ai_skin_layer,
                mask_data=a.ai_lesion_layer if a.ai_lesion_layer else None,
                confidence=a.confidence,
                notes="AI 自动填涂图层（U-Net/SAM 推理结果）— 参考用",
            )
            db.add(ai_ann)

        if user_has_data:
            user_annotations_created += 1
        created += 1

    db.commit()

    return {
        "status": "ok",
        "created": created,
        "skipped": skipped,
        "total_assessments": len(assessments),
        "user_annotations_synced": user_annotations_created,
    }


@router.post("/admin/image-labels/training-export"'''

start_idx = content.find(OLD_SYNC_START)
end_idx = content.find(OLD_SYNC_END)
if start_idx == -1 or end_idx == -1:
    print(f"ERROR: start_idx={start_idx}, end_idx={end_idx}")
else:
    # Include the full old text through the end marker
    trail = content[end_idx + len(OLD_SYNC_END):]
    content = content[:start_idx] + new_sync + "\n" + trail
    print("Patch 1 applied: sync_from_assessments enhanced")

# ── Patch 2: Add user-annotations endpoint ──
OLD_ANNOTATIONS_END = '''            for a in annotations
        ],
    }


@router.delete("/admin/image-labels/{label_id}/annotations")'''

NEW_USER_ANN = '''

@router.get("/admin/image-labels/{label_id}/user-annotations")
async def get_user_annotations_for_admin(
    label_id: int,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """获取用户测评页面的填涂/标注数据 - 供管理员预填充画布使用"""
    label = db.query(ImageLabel).filter(ImageLabel.id == label_id).first()
    if not label:
        raise HTTPException(status_code=404, detail="标注记录不存在")
    
    result = {
        "label_id": label_id,
        "has_user_data": False,
        "has_ai_data": False,
        "user_annotations": [],
        "ai_annotations": [],
        "assessment_summary": None,
    }
    
    # Get user annotations
    user_anns = db.query(ImageLabelAnnotation).filter(
        ImageLabelAnnotation.image_label_id == label_id,
        ImageLabelAnnotation.source == "user",
    ).order_by(ImageLabelAnnotation.region_index.asc()).all()
    
    if user_anns:
        result["has_user_data"] = True
        result["user_annotations"] = [
            {
                "id": a.id, "source": a.source, "region_index": a.region_index,
                "body_site": a.body_site, "is_vitiligo": a.is_vitiligo,
                "vitiligo_type": a.vitiligo_type, "vitiligo_stage": a.vitiligo_stage,
                "area_percentage": a.area_percentage, "depigmentation_level": a.depigmentation_level,
                "skin_mask_data": a.skin_mask_data, "mask_data": a.mask_data,
                "confidence": a.confidence, "notes": a.notes,
            }
            for a in user_anns
        ]
    
    # Get AI annotations
    ai_anns = db.query(ImageLabelAnnotation).filter(
        ImageLabelAnnotation.image_label_id == label_id,
        ImageLabelAnnotation.source == "ai",
    ).order_by(ImageLabelAnnotation.region_index.asc()).all()
    
    if ai_anns:
        result["has_ai_data"] = True
        result["ai_annotations"] = [
            {
                "id": a.id, "source": a.source, "region_index": a.region_index,
                "body_site": a.body_site, "is_vitiligo": a.is_vitiligo,
                "vitiligo_type": a.vitiligo_type, "vitiligo_stage": a.vitiligo_stage,
                "area_percentage": a.area_percentage, "depigmentation_level": a.depigmentation_level,
                "skin_mask_data": a.skin_mask_data, "mask_data": a.mask_data,
                "confidence": a.confidence, "notes": a.notes,
            }
            for a in ai_anns
        ]
    
    # Also try live data from VASIAssessment
    if label.assessment_id:
        assessment = db.query(VASIAssessment).filter(
            VASIAssessment.id == label.assessment_id
        ).first()
        if assessment:
            result["assessment_summary"] = {
                "assessment_id": assessment.id,
                "is_user_corrected": assessment.is_user_corrected,
                "body_site": assessment.body_site,
                "classification": assessment.classification,
                "stage": assessment.stage,
                "vasi_score": assessment.vasi_score,
                "final_vasi_score": assessment.final_vasi_score,
                "area_percentage": assessment.area_percentage,
                "final_area_percentage": assessment.final_area_percentage,
                "depigmentation_level": assessment.depigmentation_level,
                "confidence": assessment.confidence,
            }
            
            if assessment.user_skin_layer and not result["has_user_data"]:
                result["has_user_data"] = True
                result["user_annotations"].append({
                    "source": "user", "region_index": 0,
                    "body_site": assessment.body_site,
                    "is_vitiligo": assessment.classification in ("节段型","非节段型","混合型","未定型") if assessment.classification else True,
                    "vitiligo_type": assessment.classification,
                    "area_percentage": assessment.final_area_percentage or assessment.area_percentage,
                    "depigmentation_level": assessment.depigmentation_level,
                    "skin_mask_data": assessment.user_skin_layer,
                    "mask_data": assessment.user_lesion_layer,
                    "notes": "用户测评页面填涂结果（实时数据）— 管理员可在此基础上修改",
                })
            
            if assessment.ai_skin_layer and not result["has_ai_data"]:
                result["has_ai_data"] = True
                result["ai_annotations"].append({
                    "source": "ai", "region_index": 0,
                    "body_site": assessment.body_site,
                    "is_vitiligo": assessment.classification in ("节段型","非节段型","混合型","未定型") if assessment.classification else True,
                    "vitiligo_type": assessment.classification,
                    "area_percentage": assessment.area_percentage,
                    "skin_mask_data": assessment.ai_skin_layer,
                    "mask_data": assessment.ai_lesion_layer,
                    "confidence": assessment.confidence,
                    "notes": "AI 自动填涂图层（实时数据）— 参考用",
                })
    
    return result
'''

idx2 = content.find(OLD_ANNOTATIONS_END)
if idx2 == -1:
    print("ERROR: Could not find annotations endpoint boundary")
else:
    content = content[:idx2] + NEW_USER_ANN + "\n\n" + content[idx2:]
    print("Patch 2 applied: user-annotations endpoint added")

with open(PATH, "w") as f:
    f.write(content)

print("Done! image_label.py patched successfully.")

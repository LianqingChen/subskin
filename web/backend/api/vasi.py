"""
VASI评估API
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from web.backend.database.database import get_db
from web.backend.services.auth import get_current_user
from web.backend.services.unified_auth import get_current_admin_user
from web.backend.services.vasi import VASIService, VASIAssessmentError
from web.backend.models.vasi import VASIAssessment, ImageQualityTag
from web.backend.database.models import User
from web.backend.api.models import (
    VASIAssessmentResponse,
    VASIHistoryResponse,
    VASITrendResponse,
)


router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/assess", response_model=VASIAssessmentResponse)
async def create_assessment(
    image: UploadFile = File(...),
    body_site: str = Form(...),
    precision: str = Form("quick"),
    has_reference: str = Form("false"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建VASI评估

    上传白斑照片，自动识别并计算VASI评分。
    precision: "quick" 快速评估(~10s) 或 "precise" 精确评估(~70s)
    """
    try:
        image_bytes = await image.read()
        image_type = image.content_type or "image/jpeg"
        image_filename = image.filename or "upload.jpg"

        service = VASIService(db)
        assessment = await service.assess_vasi(
            user_id=current_user.id,
            image_file=image_bytes,
            body_site=body_site,
            image_type=image_type,
            image_filename=image_filename,
            precision=precision,
        )

        if has_reference and has_reference.lower() in ("true", "1", "yes"):
            try:
                assessment.has_reference = True
                db.commit()
            except Exception:
                db.rollback()

        contours = []
        skin_layer_data_url = None
        lesion_layer_data_url = None
        suspected_lesions = None
        assessment_source = getattr(assessment, "assessment_source", None)
        if assessment.details:
            try:
                import json
                details_data = json.loads(assessment.details)
                contours = details_data.get("contours", [])
                skin_layer_data_url = details_data.get("skin_layer_data_url")
                lesion_layer_data_url = details_data.get("lesion_layer_data_url")
            except (json.JSONDecodeError, TypeError):
                pass

        # Extract suspected_lesions from raw_api_response (VLM stores them there)
        if assessment.raw_api_response:
            try:
                import json
                raw = json.loads(assessment.raw_api_response)
                suspected_lesions = raw.get("suspected_lesions")
                if not assessment_source:
                    assessment_source = raw.get("source")
            except (json.JSONDecodeError, TypeError):
                pass

        # Extract visual_features from dedicated column
        visual_features = None
        vis_json = getattr(assessment, "visual_features_json", None)
        if vis_json:
            try:
                visual_features = json.loads(vis_json)
            except (json.JSONDecodeError, TypeError):
                pass

        # Extract reference_objects and skin_fitzpatrick from raw_api_response
        reference_objects = None
        skin_fitzpatrick = None
        if assessment.raw_api_response:
            try:
                raw = json.loads(assessment.raw_api_response)
                reference_objects = raw.get("reference_objects")
                skin_region = raw.get("skin_region", {})
                skin_fitzpatrick = skin_region.get("fitzpatrick_type")
            except (json.JSONDecodeError, TypeError):
                pass

        return VASIAssessmentResponse(
            id=assessment.id,
            user_id=assessment.user_id,
            image_url=assessment.image_url,
            vasi_score=assessment.vasi_score,
            body_site=assessment.body_site,
            area_percentage=assessment.area_percentage,
            classification=assessment.classification,
            stage=assessment.stage,
            contours=contours,
            skin_layer_data_url=skin_layer_data_url,
            lesion_layer_data_url=lesion_layer_data_url,
            suspected_lesions=suspected_lesions,
            visual_features=visual_features,
            assessment_source=assessment_source,
            confidence=getattr(assessment, "confidence", None),
            final_vasi_score=getattr(assessment, "final_vasi_score", None),
            final_area_percentage=getattr(assessment, "final_area_percentage", None),
            is_user_corrected=bool(getattr(assessment, "is_user_corrected", False)),
            depigmentation_level=getattr(assessment, "depigmentation_level", None),
            reference_objects=reference_objects,
            skin_fitzpatrick=skin_fitzpatrick,
            assessment_date=assessment.assessment_date.isoformat()
            if assessment.assessment_date
            else "",
            created_at=assessment.created_at.isoformat()
            if assessment.created_at
            else "",
            precision_level=precision,
            precise_available=True,
        )

    except VASIAssessmentError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("VASI评估失败: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="服务暂时不可用，请稍后重试")


@router.get("/history", response_model=VASIHistoryResponse)
async def get_history(
    limit: int = 10,
    offset: int = 0,
    body_site: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取用户评估历史

    支持分页、部位筛选、日期范围筛选
    """
    try:
        # 解析日期参数
        start_dt = datetime.fromisoformat(start_date) if start_date else None
        end_dt = datetime.fromisoformat(end_date) if end_date else None

        # 限制分页大小
        limit = min(limit, 50)

        service = VASIService(db)
        total, assessments = service.get_user_history(
            user_id=current_user.id,
            limit=limit,
            offset=offset,
            body_site=body_site,
            start_date=start_dt,
            end_date=end_dt,
        )

        items = [
            {
                "id": a.id,
                "image_url": a.image_url,
                "vasi_score": a.final_vasi_score if a.final_vasi_score is not None else a.vasi_score,
                "area_percentage": a.final_area_percentage if a.final_area_percentage is not None else a.area_percentage,
                "body_site": a.body_site,
                "stage": a.stage,
                "assessment_date": a.assessment_date.isoformat(),
                "final_vasi_score": a.final_vasi_score,
                "final_area_percentage": a.final_area_percentage,
                "is_user_corrected": bool(a.is_user_corrected),
            }
            for a in assessments
        ]

        return VASIHistoryResponse(total=total, items=items)

    except Exception as e:
        logger.error("获取VASI历史失败: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="服务暂时不可用，请稍后重试")


@router.get("/assess/{assessment_id}", response_model=VASIAssessmentResponse)
async def get_assessment(
    assessment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取单条评估详情"""
    service = VASIService(db)
    assessment = service.get_assessment_by_id(assessment_id, current_user.id)

    if not assessment:
        raise HTTPException(status_code=404, detail="评估记录不存在")

    contours = []
    skin_layer_data_url = None
    lesion_layer_data_url = None
    if assessment.details:
        try:
            import json as _json
            details_data = _json.loads(assessment.details)
            contours = details_data.get("contours", [])
            skin_layer_data_url = details_data.get("skin_layer_data_url")
            lesion_layer_data_url = details_data.get("lesion_layer_data_url")
        except (Exception,):
            pass
    if assessment.user_contours:
        try:
            import json as _json
            user_polys = _json.loads(assessment.user_contours)
            if isinstance(user_polys, list) and user_polys:
                contours = user_polys
        except (Exception,):
            pass

    # Extract visual_features from dedicated column
    visual_features = None
    vis_json_val = getattr(assessment, "visual_features_json", None)
    if vis_json_val:
        try:
            import json as _json
            visual_features = _json.loads(vis_json_val)
        except (Exception,):
            pass

    return VASIAssessmentResponse(
        id=assessment.id,
        user_id=assessment.user_id,
        image_url=assessment.image_url,
        vasi_score=assessment.vasi_score,
        body_site=assessment.body_site,
        area_percentage=assessment.area_percentage,
        classification=assessment.classification,
        stage=assessment.stage,
        contours=contours,
        skin_layer_data_url=skin_layer_data_url,
        lesion_layer_data_url=lesion_layer_data_url,
        visual_features=visual_features,
        assessment_date=assessment.assessment_date.isoformat()
        if assessment.assessment_date
        else "",
        created_at=assessment.created_at.isoformat() if assessment.created_at else "",
        precision_level="quick",
        precise_available=True,
        confidence=getattr(assessment, "confidence", None),
        final_vasi_score=getattr(assessment, "final_vasi_score", None),
        final_area_percentage=getattr(assessment, "final_area_percentage", None),
        is_user_corrected=bool(getattr(assessment, "is_user_corrected", False)),
        depigmentation_level=getattr(assessment, "depigmentation_level", None),
    )


class PromptablePrepareRequest(BaseModel):
    cache_key: str


@router.post("/promptable/prepare")
async def promptable_prepare(
    image: UploadFile = File(...),
    cache_key: str = Form(...),
    current_user: User = Depends(get_current_user),
):
    image_bytes = await image.read()
    from web.backend.services.vasi_promptable import prepare_image

    user_scoped_key = f"user{current_user.id}:{cache_key}"
    meta = await __import__("asyncio").to_thread(prepare_image, user_scoped_key, image_bytes)
    if meta is None:
        raise HTTPException(status_code=503, detail="智能分割服务暂不可用，请稍后重试")
    return {"status": "ok", "cache_key": user_scoped_key, **meta}


class PromptablePoint(BaseModel):
    x: float
    y: float
    label: int = 1


class PromptableClickRequest(BaseModel):
    cache_key: str
    points: List[PromptablePoint]


@router.post("/promptable/click")
async def promptable_click(
    request: PromptableClickRequest,
    current_user: User = Depends(get_current_user),
):
    from web.backend.services.vasi_promptable import predict_by_points

    expected_prefix = f"user{current_user.id}:"
    if not request.cache_key.startswith(expected_prefix):
        raise HTTPException(status_code=403, detail="无效的 cache_key")

    if not request.points:
        raise HTTPException(status_code=400, detail="至少需要 1 个点")

    pts = [(p.x, p.y, p.label) for p in request.points]
    result = await __import__("asyncio").to_thread(
        predict_by_points, request.cache_key, pts, True,
    )
    if result is None:
        raise HTTPException(
            status_code=410,
            detail="图片缓存已失效，请重新准备图片",
        )
    return result


class CirclePrompt(BaseModel):
    center_x: float
    center_y: float
    radius_x: float
    radius_y: float


class RefineCircleRequest(BaseModel):
    cache_key: str
    circle: CirclePrompt


@router.post("/promptable/refine-circle")
async def promptable_refine_circle(
    request: RefineCircleRequest,
    current_user: User = Depends(get_current_user),
):
    from web.backend.services.vasi_promptable import predict_by_circle

    expected_prefix = f"user{current_user.id}:"
    if not request.cache_key.startswith(expected_prefix):
        raise HTTPException(status_code=403, detail="无效的 cache_key")

    result = await __import__("asyncio").to_thread(
        predict_by_circle,
        request.cache_key,
        (request.circle.center_x, request.circle.center_y),
        request.circle.radius_x,
        request.circle.radius_y,
    )
    if result is None:
        raise HTTPException(
            status_code=410,
            detail="图片缓存已失效，请重新准备图片",
        )
    return result


@router.get("/trend", response_model=VASITrendResponse)
async def get_trend(
    body_site: Optional[str] = None,
    days: int = 30,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取趋势数据（用于曲线图）

    返回指定天数内的VASI评分变化趋势，用于生成曲线图
    """
    try:
        # 限制天数范围
        days = min(max(days, 1), 365)

        service = VASIService(db)
        trend_data = service.get_trend_data(
            user_id=current_user.id, body_site=body_site, days=days
        )

        return VASITrendResponse(**trend_data)

    except Exception as e:
        logger.error("获取VASI趋势失败: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="服务暂时不可用，请稍后重试")


class ContourSubmitRequest(BaseModel):
    contours: List[Dict[str, Any]]
    mask_image: Optional[str] = None  # legacy single-layer mask (deprecated, kept for compat)
    skin_mask_image: Optional[str] = None  # 肤色层 data URL — defines the evaluation region (denominator)
    lesion_mask_image: Optional[str] = None  # 白斑层 data URL — the numerator
    depigmentation_level: Optional[float] = None  # 0-1, defaults to existing or 1.0


class BatchDeleteRequest(BaseModel):
    ids: List[int]


@router.delete("/assess/batch")
async def delete_assessments_batch(
    request: BatchDeleteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = VASIService(db)
    deleted = service.delete_assessments_batch(request.ids, current_user.id)
    return {"status": "ok", "deleted": deleted}


@router.delete("/assess/{assessment_id}")
async def delete_assessment(
    assessment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = VASIService(db)
    deleted = service.delete_assessment(assessment_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="评估记录不存在")
    return {"status": "ok", "message": "已删除"}


@router.post("/check-photo-quality")
async def check_photo_quality(image: UploadFile = File(...)):
    image_bytes = await image.read()
    from web.backend.services.vasi_quality import vasi_quality_checker

    quality = vasi_quality_checker.check_all(image_bytes)
    return {
        "overall": quality.overall,
        "blur_score": quality.blur_score,
        "blur_ok": quality.blur_ok,
        "skin_ratio": quality.skin_ratio,
        "skin_ok": quality.skin_ok,
        "brightness_mean": quality.brightness_mean,
        "lighting_ok": quality.lighting_ok,
        "resolution": quality.resolution,
        "size_ok": quality.size_ok,
        "suggestions": quality.suggestions,
    }


@router.post("/assess/{assessment_id}/contour")
async def submit_contour_correction(
    assessment_id: int,
    request: ContourSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """提交用户修正的白斑轮廓

    记录用户对AI轮廓的修改，计算差异，作为训练样本
    """
    import json

    service = VASIService(db)
    assessment = service.get_assessment_by_id(assessment_id, current_user.id)

    if not assessment:
        raise HTTPException(status_code=404, detail="评估记录不存在")

    user_contours = request.contours
    assessment.user_contours = json.dumps(user_contours)

    ai_contours = []
    if assessment.details:
        try:
            details_data = json.loads(assessment.details)
            ai_contours = details_data.get("contours", [])
        except (json.JSONDecodeError, TypeError):
            pass

    diff = _compute_contour_diff(ai_contours, user_contours)
    assessment.contour_diff = json.dumps(diff)

    final_area_pct: Optional[float] = None
    final_vasi_score: Optional[float] = None

    from web.backend.services.vasi_formula import (
        parse_mask_data_url,
        compute_mask_area_percent,
        compute_two_layer_area,
        compute_vasi_v2,
    )

    if request.skin_mask_image and request.lesion_mask_image:
        skin_parsed = parse_mask_data_url(request.skin_mask_image)
        lesion_parsed = parse_mask_data_url(request.lesion_mask_image)
        if skin_parsed and lesion_parsed:
            two_layer = compute_two_layer_area(skin_parsed[0], lesion_parsed[0])
            if two_layer is not None:
                final_area_pct = two_layer["area_percent_in_region"]
                if request.depigmentation_level is not None:
                    assessment.depigmentation_level = float(
                        max(0.0, min(1.0, request.depigmentation_level))
                    )
                depig = assessment.depigmentation_level or 1.0
                final_vasi_score = compute_vasi_v2(
                    body_site=assessment.body_site,
                    area_pct_in_region=final_area_pct,
                    depigmentation_level=depig,
                )
                assessment.final_area_percentage = final_area_pct
                assessment.final_vasi_score = final_vasi_score
                assessment.is_user_corrected = True
                assessment.user_mask_image = request.lesion_mask_image
                assessment.user_skin_layer = request.skin_mask_image
                assessment.user_lesion_layer = request.lesion_mask_image
                logger.info(
                    "submit_contour two-layer: area=%.2f%% lesion_px=%d region_px=%d",
                    final_area_pct, two_layer["lesion_pixels"], two_layer["region_pixels"],
                )
    elif request.mask_image:
        parsed = parse_mask_data_url(request.mask_image)
        if parsed:
            mask_bytes, _ = parsed
            mask_area_in_image = compute_mask_area_percent(mask_bytes)

            stored_skin_ratio: Optional[float] = None
            if assessment.details:
                try:
                    details_obj = json.loads(assessment.details)
                    stored_skin_ratio = details_obj.get("skin_region_ratio")
                except (json.JSONDecodeError, TypeError):
                    pass

            if mask_area_in_image is not None and stored_skin_ratio and stored_skin_ratio > 0:
                final_area_pct = round(mask_area_in_image / (stored_skin_ratio / 100), 2)
                final_area_pct = min(final_area_pct, 100.0)
            else:
                final_area_pct = mask_area_in_image

            if final_area_pct is not None:
                if request.depigmentation_level is not None:
                    assessment.depigmentation_level = float(
                        max(0.0, min(1.0, request.depigmentation_level))
                    )
                depig = assessment.depigmentation_level or 1.0
                final_vasi_score = compute_vasi_v2(
                    body_site=assessment.body_site,
                    area_pct_in_region=final_area_pct,
                    depigmentation_level=depig,
                )
                assessment.final_area_percentage = final_area_pct
                assessment.final_vasi_score = final_vasi_score
                assessment.is_user_corrected = True
                assessment.user_mask_image = request.mask_image

    # ── Phase 1A: Compute mask-based Dice + area error for training ──
    ai_mask = assessment.ai_lesion_layer
    user_mask = request.lesion_mask_image or request.mask_image
    mask_metrics = _compute_mask_dice_and_area(ai_mask, user_mask)
    if mask_metrics:
        diff["dice_score"] = mask_metrics.get("dice_score")
        diff["area_error_pct"] = mask_metrics.get("area_error_pct")
        diff["ai_pixels"] = mask_metrics.get("ai_pixels")
        diff["user_pixels"] = mask_metrics.get("user_pixels")
        diff["intersection_pixels"] = mask_metrics.get("intersection_pixels")
        assessment.contour_diff = json.dumps(diff)
        logger.info(
            "Contour mask metrics: dice=%.3f area_err=%.1f%% ai_px=%d user_px=%d",
            diff.get("dice_score", 0),
            diff.get("area_error_pct", 0),
            diff.get("ai_pixels", 0),
            diff.get("user_pixels", 0),
        )

    db.commit()

    # Phase 1: Record feedback signal and export training sample
    try:
        from web.backend.services.vasi_feedback import get_feedback_collector
        collector = get_feedback_collector(db)
        user_mask = request.lesion_mask_image or request.mask_image
        collector.record_explicit_correction(
            assessment_id=assessment_id,
            user_id=current_user.id,
            contour_diff_json=json.dumps(diff),
            user_mask_b64=user_mask,
        )
    except Exception as e:
        logger.warning("Feedback collector integration failed: %s", e)

    # Phase L2: Record correction to RL learner for online self-evolution
    try:
        dice_score = diff.get("dice_score", 0)
        if dice_score > 0:
            from web.backend.services.vasi_rl_optimizer import get_rl_learner

            # Load image bytes from stored file
            image_bytes = None
            if assessment.image_key:
                import os as _os
                from pathlib import Path as _Path
                # Resolve file path from image_key
                key = assessment.image_key
                if key.startswith("vasi/"):
                    # ImageKey format: "vasi/filename" → data/uploads/vasi/filename
                    file_path = _Path("data/uploads") / key
                    if file_path.exists():
                        image_bytes = file_path.read_bytes()
                elif key.startswith("vasi/admin_upload/"):
                    file_path = _Path("data/uploads/vasi") / key.replace("vasi/admin_upload/", "")
                    if file_path.exists():
                        image_bytes = file_path.read_bytes()

            if image_bytes:
                learner = get_rl_learner()
                triggered = learner.record_correction(
                    image_bytes=image_bytes,
                    pipeline_params=None,  # Use defaults for now
                    actual_dice=dice_score,
                )
                if triggered:
                    logger.info(
                        "RL training triggered: assmt=%d dice=%.3f buffer=%d updates=%d",
                        assessment_id, dice_score,
                        len(learner.buffer), learner.policy.total_updates,
                    )
            else:
                logger.debug("No image bytes available for RL training: assmt=%d", assessment_id)
    except Exception as e:
        logger.warning("RL learner recording failed (non-blocking): %s", e)

    response: Dict[str, Any] = {
        "status": "ok",
        "assessment_id": assessment_id,
        "ai_contour_count": len(ai_contours),
        "user_contour_count": len(user_contours),
        "diff_summary": diff.get("summary", {}),
    }
    if final_area_pct is not None:
        response["final_area_percentage"] = final_area_pct
    if final_vasi_score is not None:
        response["final_vasi_score"] = final_vasi_score
    return response


def _compute_contour_diff(ai_contours: list, user_contours: list) -> dict:
    """计算AI轮廓与用户轮廓的差异"""
    import math

    if not ai_contours and not user_contours:
        return {"summary": {"match": True, "iou": 1.0, "modified": False}}

    if not ai_contours or not user_contours:
        return {
            "summary": {
                "match": False,
                "iou": 0.0,
                "modified": True,
                "ai_count": len(ai_contours),
                "user_count": len(user_contours),
            }
        }

    total_point_diff = 0
    total_ai_points = 0

    for i, ai_c in enumerate(ai_contours):
        ai_poly = ai_c.get("polygon", [])
        total_ai_points += len(ai_poly)

        matched_user = None
        for u_c in user_contours:
            if u_c.get("label") == ai_c.get("label"):
                matched_user = u_c
                break
        if not matched_user and i < len(user_contours):
            matched_user = user_contours[i]

        if matched_user:
            user_poly = matched_user.get("polygon", [])
            max_len = max(len(ai_poly), len(user_poly))
            for j in range(min(len(ai_poly), len(user_poly))):
                dx = ai_poly[j][0] - user_poly[j][0]
                dy = ai_poly[j][1] - user_poly[j][1]
                total_point_diff += math.sqrt(dx * dx + dy * dy)
            total_point_diff += abs(len(ai_poly) - len(user_poly)) * 0.05

    avg_diff = total_point_diff / max(total_ai_points, 1)
    modified = avg_diff > 0.01

    return {
        "summary": {
            "match": not modified,
            "avg_point_distance": round(avg_diff, 4),
            "modified": modified,
            "ai_count": len(ai_contours),
            "user_count": len(user_contours),
        },
        "ai_contours": ai_contours,
        "user_contours": user_contours,
    }


def _compute_mask_dice_and_area(
    ai_mask_data_url: Optional[str],
    user_mask_data_url: Optional[str],
) -> dict:
    """Calculate Dice score and area error between AI and user masks.

    Both masks are expected as data URLs (PNG with alpha channel).
    Returns a dict with dice_score, area_error_pct, ai_pixels, user_pixels.
    Returns empty dict if masks can't be decoded.
    """
    import io
    import numpy as np
    from PIL import Image
    from web.backend.services.vasi_formula import parse_mask_data_url

    if not ai_mask_data_url or not user_mask_data_url:
        return {}

    try:
        ai_parsed = parse_mask_data_url(ai_mask_data_url)
        user_parsed = parse_mask_data_url(user_mask_data_url)
        if not ai_parsed or not user_parsed:
            return {}

        ai_img = Image.open(io.BytesIO(ai_parsed[0])).convert("RGBA")
        user_img = Image.open(io.BytesIO(user_parsed[0])).convert("RGBA")

        # Resize to match if dimensions differ
        if ai_img.size != user_img.size:
            user_img = user_img.resize(ai_img.size, Image.NEAREST)

        ai_alpha = np.array(ai_img.getchannel("A"))
        user_alpha = np.array(user_img.getchannel("A"))

        ai_mask = ai_alpha > 32
        user_mask = user_alpha > 32

        ai_pixels = int(ai_mask.sum())
        user_pixels = int(user_mask.sum())
        intersection = int(np.logical_and(ai_mask, user_mask).sum())

        # Dice coefficient
        denominator = ai_pixels + user_pixels
        dice_score = (2.0 * intersection / denominator) if denominator > 0 else 0.0

        # Area error: positive = AI over-estimated, negative = AI under-estimated
        area_error_pct = (
            ((ai_pixels - user_pixels) / user_pixels) * 100.0
            if user_pixels > 0
            else 0.0
        )

        return {
            "dice_score": round(dice_score, 4),
            "area_error_pct": round(area_error_pct, 2),
            "ai_pixels": ai_pixels,
            "user_pixels": user_pixels,
            "intersection_pixels": intersection,
        }

    except Exception as e:
        logger.warning("Mask dice computation failed: %s", e)
        return {}


# ── Admin: Image Quality Tagging ──────────────────────────────────────────

class TagRequest(BaseModel):
    quality_tag: str  # excellent / good / poor / reject
    notes: Optional[str] = None


class AdminAssessmentItem(BaseModel):
    id: int
    user_id: int
    image_url: str
    body_site: str
    vasi_score: float
    area_percentage: float
    stage: str
    classification: str
    is_user_corrected: bool
    has_ai_layers: bool
    has_user_layers: bool
    quality_tag: Optional[str] = None
    quality_notes: Optional[str] = None
    assessment_date: str


class AdminAssessmentListResponse(BaseModel):
    total: int
    items: List[AdminAssessmentItem]


@router.get("/admin/assessments", response_model=AdminAssessmentListResponse)
async def list_assessments_admin(
    limit: int = 20,
    offset: int = 0,
    quality_tag: Optional[str] = None,
    has_user_correction: Optional[bool] = None,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    query = db.query(VASIAssessment)

    if quality_tag is not None:
        query = query.join(ImageQualityTag, ImageQualityTag.assessment_id == VASIAssessment.id, isouter=True).filter(
            ImageQualityTag.quality_tag == quality_tag
        )
    if has_user_correction is True:
        query = query.filter(VASIAssessment.is_user_corrected == True)
    elif has_user_correction is False:
        query = query.filter(VASIAssessment.is_user_corrected == False)

    total = query.count()
    rows = query.order_by(VASIAssessment.assessment_date.desc()).offset(offset).limit(limit).all()

    items = []
    for a in rows:
        tag_row = db.query(ImageQualityTag).filter(ImageQualityTag.assessment_id == a.id).first()
        items.append(AdminAssessmentItem(
            id=a.id,
            user_id=a.user_id,
            image_url=a.image_url,
            body_site=a.body_site,
            vasi_score=a.final_vasi_score if a.final_vasi_score is not None else a.vasi_score,
            area_percentage=a.final_area_percentage if a.final_area_percentage is not None else a.area_percentage,
            stage=a.stage,
            classification=a.classification,
            is_user_corrected=a.is_user_corrected or False,
            has_ai_layers=bool(a.ai_skin_layer or a.ai_lesion_layer),
            has_user_layers=bool(a.user_skin_layer or a.user_lesion_layer),
            quality_tag=tag_row.quality_tag if tag_row else None,
            quality_notes=tag_row.notes if tag_row else None,
            assessment_date=a.assessment_date.isoformat() if a.assessment_date else "",
        ))

    return AdminAssessmentListResponse(total=total, items=items)


@router.post("/admin/assessments/{assessment_id}/tag")
async def tag_assessment(
    assessment_id: int,
    request: TagRequest,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    if request.quality_tag not in ("excellent", "good", "poor", "reject"):
        raise HTTPException(status_code=400, detail="quality_tag must be one of: excellent, good, poor, reject")

    assessment = db.query(VASIAssessment).filter(VASIAssessment.id == assessment_id).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="评估记录不存在")

    existing = db.query(ImageQualityTag).filter(ImageQualityTag.assessment_id == assessment_id).first()
    if existing:
        existing.quality_tag = request.quality_tag
        existing.notes = request.notes
        existing.tagged_by = admin_user.id
        existing.tagged_at = datetime.utcnow()
    else:
        tag = ImageQualityTag(
            assessment_id=assessment_id,
            quality_tag=request.quality_tag,
            tagged_by=admin_user.id,
            notes=request.notes,
        )
        db.add(tag)

    db.commit()
    return {"status": "ok", "assessment_id": assessment_id, "quality_tag": request.quality_tag}


@router.delete("/admin/assessments/{assessment_id}/tag")
async def remove_tag(
    assessment_id: int,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    tag = db.query(ImageQualityTag).filter(ImageQualityTag.assessment_id == assessment_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="该评估记录未被打标")
    db.delete(tag)
    db.commit()
    return {"status": "ok", "message": "标签已删除"}


# ══════════════════════════════════════════════════════════════════════════════
# Self-Evolving VASI — Phase 1: Feedback & Training Data APIs
# ══════════════════════════════════════════════════════════════════════════════

class FeedbackRatingRequest(BaseModel):
    rating: int  # 1-5
    comment: Optional[str] = None
    issues: Optional[List[str]] = None  # ["漏检", "误判", "面积偏大", "面积偏小"]


class FeedbackActiveQueryRequest(BaseModel):
    selected_option: str
    comment: Optional[str] = None


class FeedbackStayRequest(BaseModel):
    duration_seconds: float


@router.post("/assess/{assessment_id}/feedback/rating")
async def submit_feedback_rating(
    assessment_id: int,
    request: FeedbackRatingRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用户主动评分 (1-5星)"""
    service = VASIService(db)
    assessment = service.get_assessment_by_id(assessment_id, current_user.id)
    if not assessment:
        raise HTTPException(status_code=404, detail="评估记录不存在")

    from web.backend.services.vasi_feedback import get_feedback_collector
    collector = get_feedback_collector(db)
    collector.record_explicit_rating(
        assessment_id=assessment_id,
        user_id=current_user.id,
        rating=request.rating,
        comment=request.comment,
        issues=request.issues,
    )
    return {"status": "ok", "message": "感谢你的反馈！"}


@router.post("/assess/{assessment_id}/feedback/stay")
async def record_stay_duration(
    assessment_id: int,
    request: FeedbackStayRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """记录用户在结果页的停留时间（隐式信号）"""
    service = VASIService(db)
    assessment = service.get_assessment_by_id(assessment_id, current_user.id)
    if not assessment:
        raise HTTPException(status_code=404, detail="评估记录不存在")

    from web.backend.services.vasi_feedback import get_feedback_collector
    collector = get_feedback_collector(db)
    collector.record_implicit_stay(
        assessment_id=assessment_id,
        user_id=current_user.id,
        duration_seconds=request.duration_seconds,
    )
    return {"status": "ok"}


@router.post("/assess/{assessment_id}/feedback/share")
async def record_share(
    assessment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """记录用户分享结果（隐式信号）"""
    service = VASIService(db)
    assessment = service.get_assessment_by_id(assessment_id, current_user.id)
    if not assessment:
        raise HTTPException(status_code=404, detail="评估记录不存在")

    from web.backend.services.vasi_feedback import get_feedback_collector
    collector = get_feedback_collector(db)
    collector.record_implicit_share(assessment_id, current_user.id)
    return {"status": "ok"}


@router.get("/assess/{assessment_id}/feedback/prompt")
async def get_feedback_prompt(
    assessment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取主动询问弹窗：AI 是否需要向用户请求反馈？"""
    service = VASIService(db)
    assessment = service.get_assessment_by_id(assessment_id, current_user.id)
    if not assessment:
        raise HTTPException(status_code=404, detail="评估记录不存在")

    from web.backend.services.vasi_feedback import get_feedback_collector
    collector = get_feedback_collector(db)
    prompt = collector.should_request_feedback(assessment_id)
    return {
        "should_ask": prompt.should_ask,
        "confidence": prompt.confidence,
        "title": prompt.title,
        "question": prompt.question,
        "options": prompt.options,
        "reason": prompt.reason,
    }


@router.post("/assess/{assessment_id}/feedback/active-query")
async def submit_active_query_response(
    assessment_id: int,
    request: FeedbackActiveQueryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用户回复主动询问弹窗"""
    service = VASIService(db)
    assessment = service.get_assessment_by_id(assessment_id, current_user.id)
    if not assessment:
        raise HTTPException(status_code=404, detail="评估记录不存在")

    from web.backend.services.vasi_feedback import get_feedback_collector
    collector = get_feedback_collector(db)
    collector.record_active_query_response(
        assessment_id=assessment_id,
        user_id=current_user.id,
        selected_option=request.selected_option,
        comment=request.comment,
    )
    return {"status": "ok", "message": "感谢你的确认！"}


# ── Admin: Self-Evolving Stats ────────────────────────────────────────────

@router.get("/admin/feedback/stats")
async def get_feedback_stats(
    days: int = 30,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """管理员查看反馈统计数据"""
    from web.backend.services.vasi_feedback import get_feedback_collector
    collector = get_feedback_collector(db)
    stats = collector.get_feedback_stats(days=days)
    return stats


@router.get("/admin/training-samples")
async def list_training_samples(
    body_site: Optional[str] = None,
    quality_level: Optional[str] = None,
    min_dice: Optional[float] = None,
    limit: int = 50,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """管理员查看训练样本列表"""
    from web.backend.services.vasi_feedback import get_feedback_collector
    collector = get_feedback_collector(db)
    samples = collector.export_training_samples(
        body_site=body_site,
        quality_level=quality_level,
        min_dice=min_dice,
        limit=limit,
    )
    return {
        "total": len(samples),
        "items": [
            {
                "id": s.id,
                "image_hash": s.image_hash[:12],
                "body_site": s.body_site,
                "fitzpatrick_type": s.fitzpatrick_type,
                "quality_level": s.quality_level,
                "dice_score": s.dice_score,
                "area_error_pct": s.area_error_pct,
                "confidence": s.confidence,
                "usage_count": s.usage_count,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in samples
        ],
    }


# ══════════════════════════════════════════════════════════════════════════════
# Self-Evolving VASI — Phase 2: Prompt Evolution Admin APIs
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/admin/evolution/status")
async def get_evolution_status(
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """获取自我进化状态"""
    from web.backend.services.vasi_feedback import get_feedback_collector
    from web.backend.services.vasi_prompt_evolver import get_prompt_evolver

    collector = get_feedback_collector(db)
    evolver = get_prompt_evolver(db)

    feedback_stats = collector.get_feedback_stats(days=30)
    should_evolve, new_samples = evolver.should_evolve()

    current_version = evolver.get_current_version()
    return {
        "feedback": feedback_stats,
        "prompt_evolution": {
            "should_evolve": should_evolve,
            "new_samples_since_last": new_samples,
            "threshold": 20,
            "current_version": current_version.version_tag if current_version else "default (static)",
            "current_metrics": current_version.metrics if current_version else {},
        },
    }


@router.post("/admin/evolution/trigger")
async def trigger_evolution(
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """手动触发 Prompt 进化"""
    from web.backend.services.vasi_feedback import get_feedback_collector
    from web.backend.services.vasi_prompt_evolver import get_prompt_evolver

    collector = get_feedback_collector(db)
    evolver = get_prompt_evolver(db)

    # 收集所有可用样本
    samples = collector.export_training_samples(min_dice=0.4, limit=50)
    if len(samples) < 3:
        raise HTTPException(
            status_code=400,
            detail=f"训练样本不足: 需要至少3个高质量样本，当前有{len(samples)}个",
        )

    # 构建新 prompt（选择最相关的 few-shot 示例）
    new_prompt = evolver.build_prompt("面部", use_few_shot=True)

    # 获取 few-shot IDs
    examples = evolver.select_few_shot_examples("面部")
    few_shot_ids = [ex.sample_id for ex in examples]

    # 获取当前 prompt 用于对比
    old_prompt = evolver.get_current_prompt()

    # 部署新 prompt
    deployed = evolver.deploy_prompt(
        prompt_text=new_prompt,
        few_shot_ids=few_shot_ids,
        metrics={"sample_count": len(few_shot_ids)},
        deployed_by=admin_user.id,
    )

    return {
        "status": "ok" if deployed else "failed",
        "version_tag": evolver.get_current_version().version_tag if evolver.get_current_version() else None,
        "few_shot_count": len(few_shot_ids),
        "prompt_length_old": len(old_prompt),
        "prompt_length_new": len(new_prompt),
        "examples": [
            {
                "body_site": ex.body_site,
                "key_difference": ex.key_difference[:80],
                "lesson_learned": ex.lesson_learned[:80],
                "dice_score": ex.dice_score,
            }
            for ex in examples
        ],
    }


@router.post("/admin/evolution/rollback")
async def rollback_evolution(
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """回滚到上一个 Prompt 版本"""
    from web.backend.services.vasi_prompt_evolver import get_prompt_evolver

    evolver = get_prompt_evolver(db)
    success = evolver.rollback()

    if not success:
        raise HTTPException(status_code=400, detail="没有可回滚的版本")

    current = evolver.get_current_version()
    return {
        "status": "ok",
        "message": f"已回滚到版本 {current.version_tag}" if current else "已回滚到默认prompt",
    }


@router.get("/admin/evolution/history")
async def get_evolution_history(
    limit: int = 10,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """获取 Prompt 进化历史"""
    from web.backend.services.vasi_prompt_evolver import get_prompt_evolver

    evolver = get_prompt_evolver(db)
    history = evolver.get_evolution_history(limit=limit)
    return {"versions": history}

# ══════════════════════════════════════════════════════════════════════════════
# Self-Evolving VASI — Phase 4: Metrics & Evaluation APIs
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/admin/metrics/current")
async def get_current_metrics(
    days: int = 30,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """获取当前生产环境指标"""
    from web.backend.services.vasi_evaluator import get_evaluator
    evaluator = get_evaluator(db)
    metrics = evaluator.get_current_metrics(days=days)
    return metrics.to_dict()


@router.get("/admin/metrics/stratified")
async def get_stratified_metrics(
    days: int = 30,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """获取分层指标（按部位、肤色、质量）"""
    from web.backend.services.vasi_evaluator import get_evaluator
    evaluator = get_evaluator(db)
    return evaluator.get_stratified_metrics(days=days)


@router.get("/admin/metrics/trend")
async def get_metrics_trend(
    days: int = 90,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """获取指标趋势"""
    from web.backend.services.vasi_evaluator import get_evaluator
    evaluator = get_evaluator(db)
    return {"trend": evaluator.get_metrics_trend(days=days)}


@router.get("/admin/param-optimizer/stats")
async def get_param_optimizer_stats(
    admin_user: User = Depends(get_current_admin_user),
):
    """获取参数优化器统计"""
    from web.backend.services.vasi_param_optimizer import get_param_optimizer
    opt = get_param_optimizer()
    return {
        "optimizer_stats": opt.get_all_stats(),
        "presets": opt.get_preset_params(),
    }

# ══════════════════════════════════════════════════════════════════════════════
# Self-Evolving VASI — Phase 5: Evolution Orchestrator APIs
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/admin/evolution/status-v2")
async def get_evolution_status_v2(
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """获取完整进化状态（Phase 5 统一入口）"""
    from web.backend.services.vasi_evolution import get_orchestrator
    orch = get_orchestrator(db)
    status = orch.get_status()
    return {
        "feedback": status.feedback_stats,
        "prompt": {
            "should_evolve": status.prompt_should_evolve,
            "new_samples_since_last": status.prompt_new_samples,
            "current_version": status.prompt_current_version,
        },
        "params": status.params_groups,
        "metrics": status.current_metrics,
        "degradation_warning": status.degradation_warning,
        "last_evolution": status.last_evolution,
    }


@router.post("/admin/evolution/run")
async def run_evolution(
    strategy: str = "auto",
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """手动执行一轮进化"""
    if strategy not in ("prompt", "params", "auto", "full"):
        raise HTTPException(status_code=400, detail="strategy must be: prompt, params, auto, full")

    from web.backend.services.vasi_evolution import get_orchestrator
    orch = get_orchestrator(db)
    result = await orch.evolve(strategy=strategy)
    return result.to_dict()


@router.post("/admin/evolution/rollback-v2")
async def rollback_evolution_v2(
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """回滚到上一个版本（Phase 5 统一入口）"""
    from web.backend.services.vasi_evolution import get_orchestrator
    orch = get_orchestrator(db)
    result = await orch.rollback()
    return result


@router.get("/admin/evolution/export-dataset")
async def export_training_dataset(
    min_dice: float = 0.4,
    limit: int = 200,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """导出训练数据集（用于 nnU-Net 训练）"""
    from web.backend.services.vasi_evolution import get_orchestrator
    orch = get_orchestrator(db)
    data = orch.export_training_dataset(min_dice=min_dice, limit=limit)
    return {
        "total": len(data),
        "samples": data,
        "ready_for_nnunet": len(data) >= 200,
    }

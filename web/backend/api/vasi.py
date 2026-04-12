"""
VASI评估API
"""

from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session

from web.backend.database.database import get_db
from web.backend.services.auth import get_current_user
from web.backend.services.vasi import VASIService, VASIAssessmentError
from web.backend.database.models import User
from web.backend.api.models import (
    VASIAssessmentResponse,
    VASIHistoryResponse,
    VASITrendResponse,
)


router = APIRouter()


@router.post("/assess", response_model=VASIAssessmentResponse)
async def create_assessment(
    image: UploadFile = File(...),
    body_site: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建VASI评估

    上传白斑照片，自动识别并计算VASI评分
    """
    try:
        # 读取图片文件
        image_bytes = await image.read()
        image_type = image.content_type or "image/jpeg"
        image_filename = image.filename or "upload.jpg"

        # 执行评估
        service = VASIService(db)
        assessment = await service.assess_vasi(
            user_id=current_user.id,
            image_file=image_bytes,
            body_site=body_site,
            image_type=image_type,
            image_filename=image_filename,
        )

        return VASIAssessmentResponse(
            id=assessment.id,
            user_id=assessment.user_id,
            image_url=assessment.image_url,
            vasi_score=assessment.vasi_score,
            body_site=assessment.body_site,
            area_percentage=assessment.area_percentage,
            classification=assessment.classification,
            stage=assessment.stage,
            assessment_date=assessment.assessment_date,
            created_at=assessment.created_at,
        )

    except VASIAssessmentError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"评估失败: {str(e)}")


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
                "vasi_score": a.vasi_score,
                "body_site": a.body_site,
                "area_percentage": a.area_percentage,
                "stage": a.stage,
                "assessment_date": a.assessment_date.isoformat(),
            }
            for a in assessments
        ]

        return VASIHistoryResponse(total=total, items=items)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取历史失败: {str(e)}")


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

    return VASIAssessmentResponse(
        id=assessment.id,
        user_id=assessment.user_id,
        image_url=assessment.image_url,
        vasi_score=assessment.vasi_score,
        body_site=assessment.body_site,
        area_percentage=assessment.area_percentage,
        classification=assessment.classification,
        stage=assessment.stage,
        assessment_date=assessment.assessment_date,
        created_at=assessment.created_at,
    )


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
        raise HTTPException(status_code=500, detail=f"获取趋势失败: {str(e)}")

"""
VASI评估API响应模型
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class VASIAssessmentResponse(BaseModel):
    """VASI评估评估响应"""
    id: int
    user_id: int
    image_url: str
    vasi_score: float = Field(..., description="VASI总分 (0-100)")
    body_site: str = Field(..., description="评估部位")
    area_percentage: float = Field(..., description="白斑面积百分比")
    classification: str = Field(..., description="分型")
    stage: str = Field(..., description="病情阶段")
    assessment_date: str
    created_at: str


class VASIHistoryItem(BaseModel):
    """VASI历史记录项"""
    id: int
    image_url: str
    vasi_score: float
    body_site: str
    area_percentage: float
    stage: str
    assessment_date: str


class VASIHistoryResponse(BaseModel):
    """VASI历史记录响应"""
    total: int
    items: List[VASIHistoryItem]


class VASITrendDataPoint(BaseModel):
    """趋势数据点"""
    date: str
    vasi_score: float
    stage: str


class VASITrendSummary(BaseModel):
    """趋势总结"""
    first_score: Optional[float]
    last_score: Optional[float]
    change: Optional[float]
    change_percent: Optional[float]
    trend: str = Field(..., description="好转/稳定/恶化")


class VASITrendResponse(BaseModel):
    """VASI趋势数据响应"""
    body_site: str
    period: Dict[str, str]
    data: List[VASITrendDataPoint]
    summary: VASITrendSummary


class VASIErrorResponse(BaseModel):
    """VASI错误响应"""
    error: str
    message: str

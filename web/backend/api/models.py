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
    contours: List[Dict[str, Any]] = Field(default_factory=list, description="白斑轮廓数据")
    assessment_date: str
    created_at: str
    # nnU-Net enhanced fields
    confidence: Optional[float] = None
    quality_report: Optional[Dict[str, Any]] = None
    # Two-tier precision fields
    precision_level: str = Field("quick", description="评估精度: quick/precise")
    precise_available: bool = Field(True, description="是否可进行精确评估")
    # B6 — VASI v2 corrected scores (present when user has refined the mask)
    final_vasi_score: Optional[float] = Field(None, description="用户修正后的VASI分数")
    final_area_percentage: Optional[float] = Field(None, description="用户修正后的面积百分比")
    is_user_corrected: Optional[bool] = Field(False, description="是否经用户修正")
    depigmentation_level: Optional[float] = Field(None, description="去色素度 0-1")
    # L — two-layer mask design (skin layer + lesion layer)
    skin_layer_data_url: Optional[str] = Field(None, description="AI 预填的肤色层 PNG data URL")
    lesion_layer_data_url: Optional[str] = Field(None, description="AI 预填的白斑层 PNG data URL")
    # Phase A — VLM-guided detection metadata
    assessment_source: Optional[str] = Field(None, description="AI识别来源: vlm-guided / auto-sam / mock")
    suspected_lesions: Optional[List[Dict[str, Any]]] = Field(None, description="VLM检测到的疑似白斑列表")
    skin_region_ratio: Optional[float] = Field(None, description="皮肤区域占图片百分比")
    # Phase A — 白斑视觉特征分析（非诊断性观察描述）
    visual_features: Optional[Dict[str, Any]] = Field(None, description="6维视觉特征分析结果")


class VASIHistoryItem(BaseModel):
    """VASI历史记录项"""
    id: int
    image_url: str
    vasi_score: float
    body_site: str
    area_percentage: float
    stage: str
    assessment_date: str
    final_vasi_score: Optional[float] = None
    final_area_percentage: Optional[float] = None
    is_user_corrected: Optional[bool] = None


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

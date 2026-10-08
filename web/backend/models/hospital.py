"""医评（/hospitals）模块的请求/响应模型。

命名与前端 `web/app/src/types/hospital.ts` 保持一致（snake_case 字段）。
"""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

# 评价对象类型：医院 / 医生 / 治疗方案 / 治疗经历
REVIEW_TARGETS = ("hospital", "doctor", "treatment", "experience")

# 凭证图标签白名单：只允许"非病情"的就诊凭证（明确禁止病情照片）
REVIEW_IMAGE_LABELS = ("费用单", "挂号单", "处方", "检查单")
MAX_REVIEW_IMAGES = 3


class HospitalReviewImage(BaseModel):
    """评价凭证图（费用单/挂号单/处方/检查单）。"""

    url: str = Field(..., max_length=500)
    label: str = Field(..., max_length=20, description="费用单/挂号单/处方/检查单")


class TagCount(BaseModel):
    tag: str
    count: int = 0


class HospitalBase(BaseModel):
    name: str = Field(..., max_length=200, description="医院/院区全称")
    province: str = Field(..., max_length=50)
    city: str = Field(..., max_length=50)
    district: Optional[str] = Field(None, max_length=50, description="区/县")
    address: Optional[str] = Field(None, max_length=300, description="详细地址/院区")
    department: Optional[str] = Field(None, max_length=100, description="就诊科室")
    kind: Optional[str] = Field(None, max_length=50, description="综合医院/皮肤病专科/其他")
    features: List[str] = Field(default_factory=list, description="诊疗服务标签")
    summary: Optional[str] = Field(None, max_length=1000)
    source: Optional[str] = Field(None, max_length=500, description="官方来源链接")
    lat: Optional[float] = None
    lng: Optional[float] = None
    checked_at: Optional[str] = Field(None, max_length=20)


class HospitalCreate(BaseModel):
    """病友补充医院（origin=community，前端必须标注「病友补充·待核实」）。"""

    name: str = Field(..., max_length=200)
    province: str = Field(..., max_length=50)
    city: str = Field(..., max_length=50)
    district: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = Field(None, max_length=300)
    department: Optional[str] = Field(None, max_length=100)
    kind: Optional[str] = Field(None, max_length=50)
    source: Optional[str] = Field(None, max_length=500)
    note: Optional[str] = Field(None, max_length=500, description="补充说明（写进 summary）")
    confirm_no_pii: bool = Field(
        False, description="用户确认内容不含个人联系方式（未确认时自动脱敏）"
    )


class ExperienceDimensionCount(BaseModel):
    """单个体验维度的档位计数（「没体验过」档保留，用于抑制刷分）。"""

    dimension: str
    total: int = 0
    satisfied: int = 0
    neutral: int = 0
    unsatisfied: int = 0
    na: int = 0


class HospitalRatingStats(BaseModel):
    review_count: int = 0
    rating_count: int = 0
    # 保留字段但 v3 起不再用于任何 UI 展示与排序（设计文档 2.3）
    rating_avg: Optional[float] = None
    doctor_review_count: int = 0
    treatment_review_count: int = 0
    # 各评价对象类型的条数 {"hospital": n, "doctor": n, "treatment": n, "experience": n}
    targets: Dict[str, int] = Field(default_factory=dict)
    # 中性标签聚合（病友常提到），只做展示不做排名
    top_tags: List[TagCount] = Field(default_factory=list)
    # 6 维体验提及分布（替代平均分：计数型，无可被截图当作"医院得分"的数字）
    dimension_distribution: List[ExperienceDimensionCount] = Field(default_factory=list)


class HospitalResponse(HospitalBase):
    id: int
    slug: str
    origin: str = "official"
    status: str = "visible"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    stats: Optional[HospitalRatingStats] = None

    class Config:
        from_attributes = True


class HospitalListResponse(BaseModel):
    total: int
    items: List[HospitalResponse]


class HospitalReviewCreate(BaseModel):
    """发布一条公开评价/分享。target 决定需要哪些字段。"""

    target: str = Field("hospital", description="hospital/doctor/treatment/experience")
    doctor_name: Optional[str] = Field(None, max_length=40, description="仅姓氏或称呼，如「张医生」")
    doctor_title: Optional[str] = Field(None, max_length=40, description="职称")
    doctor_department: Optional[str] = Field(None, max_length=60, description="科室")
    treatment_name: Optional[str] = Field(None, max_length=120, description="治疗方案/用药名称")
    treatment_detail: Optional[str] = Field(None, max_length=500)
    visit_month: Optional[str] = Field(None, max_length=7, description="就诊月份 YYYY-MM")
    duration: Optional[str] = Field(None, max_length=20)
    cost: Optional[str] = Field(None, max_length=20)
    outcome: Optional[str] = Field(None, max_length=20)
    ratings: Dict[str, int] = Field(default_factory=dict, description="旧版 1-5 星评分（保留兼容，不再新增）")
    experience_scores: Dict[str, str] = Field(
        default_factory=dict,
        description="统一 6 维体验档位：satisfied/neutral/unsatisfied/na",
    )
    health_consent: bool = Field(
        False,
        description="PIPL 第 28/29 条单独同意：评价可能包含健康相关信息，需明示同意（禁止默认勾选）",
    )
    risk_ack: bool = Field(
        False,
        description="发布前冷静确认：已确认内容基于真实经历、不含侮辱性言辞",
    )
    tags: List[str] = Field(default_factory=list)
    content: str = Field(..., max_length=2000, description="至少 20 字，由服务层校验并给出中文提示")
    images: List[HospitalReviewImage] = Field(
        default_factory=list, description="凭证图（费用单/挂号单/处方/检查单），≤3 张"
    )
    images_confirmed: bool = Field(
        False, description="用户已确认图片不含病情照片并遮盖了姓名/手机号/病历号"
    )
    confirm_pii: bool = Field(
        False, description="用户显式确认保留含个人信息原文（留审计记录）"
    )


class HospitalReviewAuthor(BaseModel):
    id: int
    username: Optional[str] = None
    avatar_url: Optional[str] = None

    class Config:
        from_attributes = True


class HospitalReviewResponse(BaseModel):
    id: int
    hospital_id: int
    hospital_name: Optional[str] = None
    hospital_city: Optional[str] = None
    target: str
    doctor_name: Optional[str] = None
    doctor_title: Optional[str] = None
    doctor_department: Optional[str] = None
    treatment_name: Optional[str] = None
    treatment_detail: Optional[str] = None
    visit_month: Optional[str] = None
    duration: Optional[str] = None
    cost: Optional[str] = None
    outcome: Optional[str] = None
    ratings: Dict[str, int] = Field(default_factory=dict)
    experience_scores: Dict[str, str] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)
    images: List[HospitalReviewImage] = Field(default_factory=list)
    # 凭证图只回「已上传」徽标，不回可访问 URL（仅作者/管理员可读原图）
    credential_labels: List[str] = Field(default_factory=list)
    content: str
    moderation_status: str = "approved"
    # 仅作者本人可见：受限/驳回原因（其余人拿到 None）
    restricted_reason: Optional[str] = None
    status: str = "visible"
    helpful_count: int = 0
    is_helpful: bool = False
    detail_score: int = Field(0, description="结构化信息完整度：用于「完整分享」徽标")
    author: Optional[HospitalReviewAuthor] = None
    is_mine: bool = False
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class HospitalReviewListResponse(BaseModel):
    total: int
    items: List[HospitalReviewResponse]
    summary: HospitalRatingStats = Field(default_factory=HospitalRatingStats)


class HospitalReviewCreateResult(BaseModel):
    review: HospitalReviewResponse
    pii_redacted: bool = False
    pii_types: List[str] = Field(default_factory=list)
    claims_flagged: List[str] = Field(default_factory=list)
    # v3 风控：风险档位与可解释标签 + 聚合冷处理提示
    risk_level: str = "safe"
    risk_score: int = 0
    risk_categories: List[str] = Field(default_factory=list)
    author_hints: List[str] = Field(default_factory=list)
    aggregate_pending: bool = False
    message: str = ""


class HospitalReviewReportCreate(BaseModel):
    """举报一条评价。"""

    reason_code: str = Field(..., max_length=30, description="fake/abuse/privacy/ad/promotion/other")
    detail: Optional[str] = Field(None, max_length=500)


class HospitalReviewReportResponse(BaseModel):
    id: int
    review_id: int
    reason_code: str
    detail: Optional[str] = None
    status: str = "pending"
    created_at: Optional[datetime] = None
    report_count: int = 0


class HospitalReviewAppealCreate(BaseModel):
    """申诉（被评价方 / 被误判作者）。公开可达，不要求登录。"""

    review_id: int
    claimant_type: str = Field(..., max_length=20, description="hospital/doctor/author/other")
    claimant_name: str = Field(..., max_length=80)
    contact: str = Field(..., max_length=120, description="仅管理员可见")
    reason: str = Field(..., max_length=2000)
    evidence_urls: List[str] = Field(default_factory=list)


class HospitalReviewAppealResponse(BaseModel):
    id: int
    review_id: int
    claimant_type: str
    claimant_name: str
    status: str = "pending"
    resolution: Optional[str] = None
    resolved_action: Optional[str] = None
    due_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    overdue: bool = False


class HospitalRiskAdminItem(BaseModel):
    """管理后台风控看板条目。"""

    review_id: int
    hospital_id: int
    hospital_name: Optional[str] = None
    target: str
    risk_score: int = 0
    risk_level: str = "safe"
    risk_flags: List[str] = Field(default_factory=list)
    moderation_status: str = "approved"
    report_count: int = 0
    appeal_count: int = 0
    content_excerpt: str = ""
    created_at: Optional[datetime] = None


class HospitalRiskAdminResponse(BaseModel):
    total: int
    pending_reports: int = 0
    pending_appeals: int = 0
    overdue_appeals: int = 0
    high_risk_count: int = 0
    items: List[HospitalRiskAdminItem] = Field(default_factory=list)


class HospitalReviewImageUploadResponse(BaseModel):
    url: str


class HospitalReviewHelpfulResponse(BaseModel):
    review_id: int
    helpful_count: int
    is_helpful: bool

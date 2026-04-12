"""
VASI评估数据模型
"""

from datetime import datetime
from sqlalchemy import (
    Boolean,
    Column,
    Float,
    ForeignKey,
    Integer,
    String,
    DateTime,
    Text,
)
from sqlalchemy.orm import relationship

from web.backend.database.database import Base
from web.backend.database.models import User


class VASIAssessment(Base):
    """VASI评估记录

    VASI (Vitiligo Area Severity Index) - 白癜风面积严重程度指数
    """

    __tablename__ = "vasi_assessments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # 图片信息
    image_url = Column(String, nullable=False)  # 图片存储URL
    image_key = Column(String, nullable=True)  # 对象存储key
    image_hash = Column(String, nullable=True)  # 图片hash（用于去重）

    # 评估结果
    vasi_score = Column(Float, nullable=False)  # VASI总分 (0-100)
    body_site = Column(
        String, nullable=False, index=True
    )  # 评估部位（面部、颈部、躯干、四肢等）
    area_percentage = Column(Float, nullable=False)  # 白斑面积百分比
    classification = Column(String, nullable=False)  # 分型（节段型/非节段型/混合型）
    stage = Column(String, nullable=False)  # 病情阶段（好转/稳定/扩散）

    # 详细评估数据（可选）
    details = Column(Text, nullable=True)  # JSON格式的详细评估数据

    # 原始API响应（用于调试和审计）
    raw_api_response = Column(Text, nullable=True)  # JSON格式

    # 评估来源（用于追踪不同识别API的效果）
    assessment_source = Column(String, nullable=True)  # 识别服务提供商

    # 时间戳
    assessment_date = Column(DateTime, default=datetime.utcnow, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    user = relationship("User", backref="vasi_assessments")

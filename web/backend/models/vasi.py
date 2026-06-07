"""
VASI评估数据模型
"""

import logging
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
    inspect,
)
from sqlalchemy.orm import relationship

from web.backend.database.database import Base
from web.backend.database.models import User

logger = logging.getLogger(__name__)


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

    # 用户修正轮廓数据
    user_contours = Column(Text, nullable=True)  # 用户修改后的轮廓JSON
    contour_diff = Column(Text, nullable=True)  # AI轮廓vs用户轮廓的差异JSON

    # 白斑视觉特征分析（非诊断性观察描述）
    visual_features_json = Column(Text, nullable=True)  # 6维视觉特征分析JSON

    # nnU-Net enhanced fields (Phase A migration)
    confidence = Column(Float, nullable=True)  # AI confidence score (0-1)
    quality_report_json = Column(Text, nullable=True)  # QualityReport JSON
    preprocessed = Column(Boolean, default=False)  # Image was preprocessed
    has_reference = Column(Boolean, default=False)  # Reference object detected
    scale_factor = Column(Float, nullable=True)  # pixels/mm ratio

    # VASI v2 fields (Phase B6 — real VASI formula + user-mask recompute)
    final_vasi_score = Column(Float, nullable=True)  # VASI after user correction (preferred when present)
    final_area_percentage = Column(Float, nullable=True)  # Area % recomputed from user mask
    depigmentation_level = Column(Float, nullable=True, default=1.0)  # 0-1; 1.0 = complete
    is_user_corrected = Column(Boolean, default=False)
    user_mask_image = Column(Text, nullable=True)  # base64 PNG of final mask (for audit/training)

    # L — Two-layer mask storage (AI + User corrected layers)
    ai_skin_layer = Column(Text, nullable=True)  # AI识别的皮肤层 PNG data URL
    ai_lesion_layer = Column(Text, nullable=True)  # AI识别的白斑层 PNG data URL
    user_skin_layer = Column(Text, nullable=True)  # 用户修正后的皮肤层 PNG data URL
    # 测评状态: draft(未完成) | active(已确认) | abandoned(已放弃)
    status = Column(String, default='active', nullable=False, index=True)
    user_lesion_layer = Column(Text, nullable=True)  # 用户修正后的白斑层 PNG data URL

    # 测评流程状态: draft(未确认草稿) | active(已确认) | abandoned(已放弃)

    # VASI 自进化 — per-lesion contour diff metrics (RL reward signal)
    # JSON array: [{"lesion_id":0, "dice_score":0.85, "area_error_pct":12.3}, ...]
    final_contour_diff_metrics = Column(Text, nullable=True)

    # 测评状态: draft(未确认) | active(已确认) | abandoned(已放弃)

    # 时间戳
    assessment_date = Column(DateTime, default=datetime.utcnow, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    user = relationship("User", backref="vasi_assessments")
    quality_tag = relationship("ImageQualityTag", backref="assessment", uselist=False)


class ImageQualityTag(Base):
    """图片质量标注 — 管理员对评估图片的质量打标

    用于筛选高质量图片作为AI白斑识别模型的训练样本
    """

    __tablename__ = "image_quality_tags"

    id = Column(Integer, primary_key=True, index=True)
    assessment_id = Column(Integer, ForeignKey("vasi_assessments.id"), nullable=False, unique=True, index=True)

    quality_tag = Column(String, nullable=False)  # excellent / good / poor / reject
    tagged_by = Column(Integer, ForeignKey("users.id"), nullable=False)  # 管理员 user_id
    notes = Column(Text, nullable=True)  # 管理员备注
    tagged_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    tagger = relationship("User", foreign_keys=[tagged_by])


def ensure_vasi_columns() -> None:
    """Add nnU-Net Phase A columns to vasi_assessments if they don't exist.

    Safe to call multiple times — only adds missing columns.
    Uses raw ALTER TABLE for SQLite/PostgreSQL compatibility.
    """
    from web.backend.database.database import engine, Base

    columns_to_check = {
        "confidence": ("FLOAT", None),
        "quality_report_json": ("TEXT", None),
        "preprocessed": ("BOOLEAN", "0"),
        "has_reference": ("BOOLEAN", "0"),
        "scale_factor": ("FLOAT", None),
        "final_vasi_score": ("FLOAT", None),
        "final_area_percentage": ("FLOAT", None),
        "depigmentation_level": ("FLOAT", "1.0"),
        "is_user_corrected": ("BOOLEAN", "0"),
        "user_mask_image": ("TEXT", None),
        "ai_skin_layer": ("TEXT", None),
        "ai_lesion_layer": ("TEXT", None),
        "user_skin_layer": ("TEXT", None),
        "user_lesion_layer": ("TEXT", None),
        "status": ("TEXT", "'active'"),
        "visual_features_json": ("TEXT", None),
        "final_contour_diff_metrics": ("TEXT", None),
    }

    try:
        insp = inspect(engine)
        existing_columns = {c["name"] for c in insp.get_columns("vasi_assessments")}

        for col_name, (col_type, default_val) in columns_to_check.items():
            if col_name in existing_columns:
                continue
            try:
                default_clause = f" DEFAULT {default_val}" if default_val else ""
                sql = f"ALTER TABLE vasi_assessments ADD COLUMN {col_name} {col_type}{default_clause}"
                with engine.connect() as conn:
                    conn.exec_driver_sql(sql)
                    conn.commit()
                logger.info("Added column vasi_assessments.%s (%s)", col_name, col_type)
            except Exception as e:
                logger.warning("Failed to add column vasi_assessments.%s: %s", col_name, e)
    except Exception as e:
        logger.warning("vasi_assessments migration check failed: %s", e)


# ══════════════════════════════════════════════════════════════════════════════
# Self-Evolving VASI — Phase 1: Feedback & Training Data Models
# ══════════════════════════════════════════════════════════════════════════════

class VasiFeedbackSignal(Base):
    """VASI 反馈信号 — 用户对评估结果的多维度反馈"""

    __tablename__ = "vasi_feedback_signals"

    id = Column(Integer, primary_key=True, index=True)
    assessment_id = Column(Integer, ForeignKey("vasi_assessments.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    signal_type = Column(String, nullable=False, index=True)
    # signal_type values:
    #   'explicit_correction'  — 用户手动修正了轮廓
    #   'explicit_rating'      — 用户主动评分 (1-5)
    #   'explicit_comment'     — 用户文字反馈
    #   'implicit_stay'        — 用户在结果页停留 > 10s
    #   'implicit_reupload'    — 用户短时间内重新上传同部位
    #   'implicit_share'       — 用户分享了结果
    #   'implicit_correction_again' — 用户修正后又再次修正
    #   'active_query'         — AI主动询问后的用户回复
    signal_value = Column(Text, nullable=True)
    # JSON: {"rating": 4, "comment": "...", "ai_accurate": true, "issues": ["漏检"]}
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    assessment = relationship("VASIAssessment", backref="feedback_signals")
    user = relationship("User", foreign_keys=[user_id])


class VasiTrainingSample(Base):
    """VASI 训练样本 — 去重后的高质量训练数据"""

    __tablename__ = "vasi_training_samples"

    id = Column(Integer, primary_key=True, index=True)
    image_hash = Column(String, unique=True, nullable=False, index=True)
    image_key = Column(String, nullable=False)
    body_site = Column(String, nullable=False, index=True)
    fitzpatrick_type = Column(String, nullable=True)  # I-VI
    quality_level = Column(String, nullable=True)  # good / acceptable / poor
    sample_source = Column(String, nullable=True, index=True)  # user_correction | admin_labeling | admin_review
    vitiligo_type = Column(String, nullable=True)  # 节段型/非节段型/混合型
    stage = Column(String, nullable=True)  # 好转/稳定/扩散 (vitiligo_stage)
    lesion_size_category = Column(String, nullable=True)  # small / medium / large / huge
    pixel_area = Column(Integer, nullable=True)  # 皮损像素面积

    # AI 原始分割结果
    ai_mask_b64 = Column(Text, nullable=True)  # AI分割mask PNG data URL
    ai_contours_json = Column(Text, nullable=True)  # AI轮廓 JSON

    # 用户修正后的分割结果 (ground truth)
    user_mask_b64 = Column(Text, nullable=True)  # 用户修正mask PNG data URL
    user_contours_json = Column(Text, nullable=True)  # 用户修正轮廓 JSON

    # 管理员精标注 (gold standard — 最高优先级)
    admin_mask_b64 = Column(Text, nullable=True)  # 管理员标注mask PNG data URL
    admin_label_id = Column(Integer, nullable=True)  # FK to image_label_annotations.id

    # 差异分析
    contour_diff_json = Column(Text, nullable=True)  # AI vs 用户差异 JSON
    dice_score = Column(Float, nullable=True)  # AI mask vs User mask Dice coefficient
    area_error_pct = Column(Float, nullable=True)  # AI 面积误差百分比

    # RL Pipeline 参数追踪
    pipeline_params_json = Column(Text, nullable=True)  # RL参数快照: {"pred_iou_thresh":0.88,...}

    # 元信息
    confidence = Column(Float, nullable=True)  # AI原始置信度
    assessment_source = Column(String, nullable=True)  # 识别服务提供商
    usage_count = Column(Integer, default=0)  # 被用作few-shot示例的次数
    last_used_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class VasiModelVersion(Base):
    """VASI 模型版本 — 追踪每次进化"""

    __tablename__ = "vasi_model_versions"

    id = Column(Integer, primary_key=True, index=True)
    version_tag = Column(String, unique=True, nullable=False)  # 'v3.1.0-prompt-opt-20260601'
    description = Column(Text, nullable=True)
    evolution_layer = Column(String, nullable=False)
    # 'prompt' | 'parameters' | 'model_weights' | 'ensemble'

    # 变更详情
    changes_json = Column(Text, nullable=True)
    # {"prompt_hash": "...", "params": {"vitiligo_l_offset": 14.0}, ...}

    # 评估指标
    metrics_json = Column(Text, nullable=True)
    # {"recall": 0.72, "precision": 0.85, "f1": 0.78, "dice": 0.65, "mape": 0.18}
    sample_count = Column(Integer, default=0)  # 评估使用的样本数

    # 部署状态
    is_active = Column(Boolean, default=False)
    deployed_at = Column(DateTime, nullable=True)
    deployed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    rollback_from_version_id = Column(Integer, nullable=True)  # 如果是回滚，记录来自哪个版本

    # 元信息
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    deployer = relationship("User", foreign_keys=[deployed_by])


def ensure_feedback_columns() -> None:
    """Ensure all self-evolving feedback tables exist, and add new columns."""
    from web.backend.database.database import engine

    try:
        # Create tables if they don't exist
        Base.metadata.create_all(bind=engine, tables=[
            VasiFeedbackSignal.__table__,
            VasiTrainingSample.__table__,
            VasiModelVersion.__table__,
        ])
        logger.info("Self-evolving feedback tables ensured")
    except Exception as e:
        logger.warning("Feedback tables creation check: %s", e)

    # ── Phase 1A: Add new columns to existing vasi_training_samples table ──
    try:
        insp = inspect(engine)
        existing_columns = {c["name"] for c in insp.get_columns("vasi_training_samples")}
        new_columns = {
            "sample_source": ("VARCHAR(32)", None),
            "vitiligo_type": ("VARCHAR(32)", None),
            "stage": ("VARCHAR(32)", None),
            "lesion_size_category": ("VARCHAR(32)", None),
            "pixel_area": ("INTEGER", None),
            "admin_mask_b64": ("TEXT", None),
            "admin_label_id": ("INTEGER", None),
            "pipeline_params_json": ("TEXT", None),
        }
        for col_name, (col_type, default_val) in new_columns.items():
            if col_name in existing_columns:
                continue
            try:
                default_clause = f" DEFAULT {default_val}" if default_val else ""
                sql = f"ALTER TABLE vasi_training_samples ADD COLUMN {col_name} {col_type}{default_clause}"
                with engine.connect() as conn:
                    conn.exec_driver_sql(sql)
                    conn.commit()
                logger.info("Added column vasi_training_samples.%s (%s)", col_name, col_type)
            except Exception as e:
                logger.warning("Failed to add column vasi_training_samples.%s: %s", col_name, e)
    except Exception as e:
        logger.warning("vasi_training_samples migration check failed: %s", e)

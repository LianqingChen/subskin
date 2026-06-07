"""
图片打标数据模型 — 管理员对用户上传的白斑图片进行专业标注

设计理念:
  1. 三级标注数据来源: AI自动识别 → 用户手动校准 → 管理员审核标注
  2. 隐私保护: 图片与用户信息脱敏，仅通过 image_hash 关联原始数据（管理员可追溯）
  3. 保留策略: 用户删除的图片仍保留用于训练，但不再向用户展示
  4. 预留训练数据导出接口，方便未来 VASI 大模型训练和校准
"""

import logging
from datetime import datetime
from typing import Optional, List

from sqlalchemy import (
    Boolean,
    Column,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    DateTime,
    Text,
    inspect,
)
from sqlalchemy.orm import relationship

from web.backend.database.database import Base

logger = logging.getLogger(__name__)

# ── 身体部位枚举 ────────────────────────────────────────────────
BODY_SITE_CHOICES = [
    "面部",
    "颈部",
    "头皮",
    "躯干前面",
    "躯干后面",
    "上肢近端",
    "上肢远端",
    "手部",
    "下肢近端",
    "下肢远端",
    "足部",
    "生殖器",
    "其他",
]

# ── 白癜风分型 ──────────────────────────────────────────────────
VITILIGO_TYPE_CHOICES = [
    "非节段型(寻常型)",
    "节段型",
    "混合型",
    "未确定",
    "非白癜风",
]

# ── 病情阶段 ────────────────────────────────────────────────────
STAGE_CHOICES = [
    "进展期",
    "稳定期",
    "好转期",
    "不确定",
]


class ImageLabel(Base):
    """图片打标主表 — 每张用户上传的评估图片一条记录
    
    这张表既关联了原始 VASI 评估记录，又提供了独立的管理员标注能力。
    字段设计参考 VASI 评分体系，同时为训练数据导出预留结构化数据。
    """

    __tablename__ = "image_labels"
    __table_args__ = (
        Index("idx_image_labels_status", "label_status"),
        Index("idx_image_labels_assessment", "assessment_id"),
        Index("idx_image_labels_user", "original_user_id"),
        Index("idx_image_labels_created", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)

    # ── 关联 ──────────────────────────────────────────────────
    assessment_id = Column(
        Integer, ForeignKey("vasi_assessments.id"), nullable=True, index=True,
        comment="关联的 VASI 评估记录（可为空，支持独立上传的图片）",
    )
    original_user_id = Column(
        Integer, ForeignKey("users.id"), nullable=True, index=True,
        comment="图片原始上传者（脱敏后仅管理员可见）",
    )

    # ── 图片信息 ────────────────────────────────────────────────
    image_url = Column(String, nullable=False, comment="图片存储 URL")
    image_key = Column(String, nullable=True, comment="对象存储 key")
    image_hash = Column(String, nullable=True, unique=True, comment="图片 SHA-256 哈希（唯一标识 + 反篡改）")
    
    # ── 隐私与保留 ──────────────────────────────────────────────
    is_user_deleted = Column(Boolean, default=False, nullable=False, comment="用户是否已删除原始评估记录")
    is_face_detected = Column(Boolean, default=False, comment="图片中是否检测到人脸（自动标记）")
    is_face_blurred = Column(Boolean, default=False, comment="是否已做人脸模糊处理")
    is_phi_removed = Column(Boolean, default=False, comment="是否已脱敏处理（去除 EXIF 等元数据）")

    # ── AI 自动识别结果（自动填充）──────────────────────────────
    ai_body_site = Column(String, nullable=True, comment="AI 识别的身体部位")
    ai_is_vitiligo = Column(Boolean, nullable=True, comment="AI 是否判定为白癜风")
    ai_vitiligo_type = Column(String, nullable=True, comment="AI 判定的白癜风分型")
    ai_vitiligo_stage = Column(String, nullable=True, comment="AI 判定的病情阶段")
    ai_area_percentage = Column(Float, nullable=True, comment="AI 估算的白斑面积占比 (0-100)")
    ai_vasi_score = Column(Float, nullable=True, comment="AI 计算 VASI 评分")
    ai_confidence = Column(Float, nullable=True, comment="AI 识别置信度 (0-1)")
    ai_details = Column(Text, nullable=True, comment="AI 识别详细数据 JSON（轮廓、区域等）")

    # ── 用户手动校准结果 ────────────────────────────────────────
    user_body_site = Column(String, nullable=True, comment="用户校准的身体部位")
    user_is_vitiligo = Column(Boolean, nullable=True, comment="用户校准是否为白癜风")
    user_vitiligo_type = Column(String, nullable=True, comment="用户校准白癜风分型")
    user_area_percentage = Column(Float, nullable=True, comment="用户校准白斑面积占比")
    user_vasi_score = Column(Float, nullable=True, comment="用户校准后 VASI 评分")
    user_depigmentation_level = Column(Float, nullable=True, comment="用户校准脱色程度 (0-1)")
    user_notes = Column(Text, nullable=True, comment="用户备注说明")

    # ── 管理员审核标注（最终结果）───────────────────────────────
    admin_body_site = Column(String, nullable=True, comment="管理员标注的身体部位")
    admin_is_vitiligo = Column(Boolean, nullable=True, comment="管理员标注是否为白癜风")
    admin_vitiligo_type = Column(String, nullable=True, comment="管理员标注白癜风分型")
    admin_vitiligo_stage = Column(String, nullable=True, comment="管理员标注病情阶段")
    admin_area_percentage = Column(Float, nullable=True, comment="管理员标注白斑面积占比")
    admin_vasi_score = Column(Float, nullable=True, comment="管理员标注 VASI 评分")
    admin_depigmentation_level = Column(Float, nullable=True, comment="管理员标注脱色程度")
    admin_notes = Column(Text, nullable=True, comment="管理员备注（解读、建议等）")
    labeled_by = Column(Integer, ForeignKey("users.id"), nullable=True, comment="打标管理员 user_id")
    labeled_at = Column(DateTime, nullable=True, comment="管理员打标时间")

    # ── 打标状态 ───────────────────────────────────────────────
    label_status = Column(
        String(20), default="pending", nullable=False, comment="pending/labeled/skipped/rejected"
    )
    
    # ── 训练数据标记 ─────────────────────────────────────────────
    training_eligible = Column(Boolean, default=False, comment="是否适合作为训练数据（管理员决定）")
    training_set_split = Column(String(10), nullable=True, comment="train/val/test — 训练集划分标记")
    training_exported_at = Column(DateTime, nullable=True, comment="最近一次导出训练数据的时间")

    # ── 标注产物路径 ───────────────────────────────────────────
    annotated_image_path = Column(String, nullable=True, comment="管理员标注合成图本地路径")
    annotated_image_url = Column(String, nullable=True, comment="管理员标注合成图访问 URL")
    annotated_layers_path = Column(String, nullable=True, comment="管理员标注图层数据 JSON 路径（含 skin/lesion mask 路径）")

    # ── 时间戳 ──────────────────────────────────────────────────
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # ── 关系 ────────────────────────────────────────────────────
    assessment = relationship("VASIAssessment", backref="image_labels")
    original_user = relationship("User", foreign_keys=[original_user_id], backref="uploaded_image_labels")
    labeler = relationship("User", foreign_keys=[labeled_by])
    annotations = relationship(
        "ImageLabelAnnotation", back_populates="image_label", cascade="all, delete-orphan"
    )


class ImageLabelAnnotation(Base):
    """图片标注明细表 — 支持多处白斑的独立标注
    
    一张图片可能包含多处白斑，每处白斑独立记录位置、面积、类型等信息。
    这为细粒度训练数据提供了结构化支持。
    """

    __tablename__ = "image_label_annotations"
    __table_args__ = (
        Index("idx_anno_image_label", "image_label_id"),
        Index("idx_anno_source", "source"),
    )

    id = Column(Integer, primary_key=True, index=True)
    image_label_id = Column(
        Integer, ForeignKey("image_labels.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # ── 标注来源 ────────────────────────────────────────────────
    source = Column(String(10), nullable=False, comment="ai/user/admin — 谁做的标注")
    
    # ── 白斑位置 ────────────────────────────────────────────────
    region_index = Column(Integer, default=0, comment="同图片中第几处白斑（从0开始）")
    body_site = Column(String, nullable=True, comment="身体部位")
    
    # ── 白斑特征 ────────────────────────────────────────────────
    is_vitiligo = Column(Boolean, nullable=True, comment="是否为白癜风")
    vitiligo_type = Column(String, nullable=True, comment="白癜风分型")
    vitiligo_stage = Column(String, nullable=True, comment="病情阶段")
    area_percentage = Column(Float, nullable=True, comment="白斑面积占比")
    depigmentation_level = Column(Float, nullable=True, comment="脱色程度 (0-1)")
    
    # ── 轮廓/区域数据 ───────────────────────────────────────────
    region_contour = Column(Text, nullable=True, comment="白斑轮廓 JSON（多边形顶点）")
    region_bbox = Column(Text, nullable=True, comment="白斑边界框 JSON {x, y, w, h}")
    mask_data = Column(Text, nullable=True, comment="分割掩码 PNG data URL (白斑区域)")
    skin_mask_data = Column(Text, nullable=True, comment="皮肤区域掩码 PNG data URL")

    # ── 置信度 ─────────────────────────────────────────────────
    confidence = Column(Float, nullable=True, comment="标注置信度 (0-1)")
    notes = Column(Text, nullable=True, comment="备注")
    
    # ── 时间戳 ──────────────────────────────────────────────────
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # ── 关系 ────────────────────────────────────────────────────
    image_label = relationship("ImageLabel", back_populates="annotations")


class ImageLabelLog(Base):
    """打标操作日志 — 记录所有标注变更历史
    
    不可删除、不可修改，确保训练数据的审计追溯性。
    """

    __tablename__ = "image_label_logs"
    __table_args__ = (
        Index("idx_label_log_image", "image_label_id"),
        Index("idx_label_log_operator", "operator_id"),
        Index("idx_label_log_created", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    image_label_id = Column(Integer, ForeignKey("image_labels.id"), nullable=False, index=True)
    operator_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="操作人（管理员）")
    
    action = Column(String(30), nullable=False, comment="create/update/skip/reject/export")
    field_name = Column(String, nullable=True, comment="变更字段名")
    old_value = Column(Text, nullable=True, comment="旧值")
    new_value = Column(Text, nullable=True, comment="新值")
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # ── 关系 ────────────────────────────────────────────────────
    operator = relationship("User", foreign_keys=[operator_id])


def ensure_image_label_columns() -> None:
    """Add image label tables and missing columns to the database.

    Safe to call multiple times — creates missing tables and columns only.
    """
    from web.backend.database.database import engine

    try:
        Base.metadata.create_all(bind=engine, tables=[
            ImageLabel.__table__,
            ImageLabelAnnotation.__table__,
            ImageLabelLog.__table__,
        ])

        # ── Add missing columns for existing tables (SQLite safe) ──
        import sqlite3
        from pathlib import Path

        db_path = Path(engine.url.database) if engine.url.database else None
        if db_path and db_path.exists():
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            # ImageLabel new columns
            cursor.execute("PRAGMA table_info(image_labels)")
            il_cols = [row[1] for row in cursor.fetchall()]
            for col_name in ("annotated_image_path", "annotated_image_url", "annotated_layers_path"):
                if col_name not in il_cols:
                    cursor.execute(f"ALTER TABLE image_labels ADD COLUMN {col_name} VARCHAR")
                    logger.info("Added column image_labels.%s", col_name)

            # ImageLabelAnnotation new columns
            cursor.execute("PRAGMA table_info(image_label_annotations)")
            ila_cols = [row[1] for row in cursor.fetchall()]
            if "skin_mask_data" not in ila_cols:
                cursor.execute("ALTER TABLE image_label_annotations ADD COLUMN skin_mask_data TEXT")
                logger.info("Added column image_label_annotations.skin_mask_data")

            conn.commit()
            conn.close()

        logger.info("Image label tables ensured")
    except Exception as e:
        logger.warning("Image label table creation check failed: %s", e)
"""打标提交版本 — 每次提交一行，不可覆盖；复核结论写在同一行。

掩膜本体是不可变快照文件 ``data/rgb_segmentation/admin_labels/{label_id}/{revision}/``
（``labels.png`` 五类类别图 + 兼容旧读取的 normal_skin/lesion），本表只存元数据。
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text

from web.backend.database.database import Base

# submitted → approved（成为金标准）/ returned（退回）/ superseded（被同一标签的新提交取代）
SUBMISSION_STATUSES = ("submitted", "approved", "returned", "superseded")
PREFILL_SOURCES = ("none", "ai", "user", "previous")
REVIEW_MODES = ("dual", "single_review")


class LabelSubmission(Base):
    __tablename__ = "label_submissions"
    __table_args__ = (
        Index("idx_label_sub_label", "image_label_id"),
        Index("idx_label_sub_author", "author_id"),
        Index("idx_label_sub_status", "status"),
    )

    id = Column(Integer, primary_key=True)
    image_label_id = Column(Integer, ForeignKey("image_labels.id"), nullable=False)
    revision = Column(String(64), nullable=False, comment="快照目录名（元数据 SHA-256）")
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String(16), nullable=False, default="submitted")

    prefill_source = Column(String(16), nullable=False, default="none")
    blind = Column(Boolean, nullable=False, default=False)
    duration_ms = Column(Integer, nullable=True)
    guideline_version = Column(String(16), nullable=True)
    attributes = Column(Text, nullable=True, comment="图像级属性 JSON（质量/肤色/体征等）")
    stats = Column(Text, nullable=True, comment="类别像素数、白斑占比、与 AI/用户版本的 Dice")

    reviewer_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    review_mode = Column(String(16), nullable=True)
    review_note = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

"""Durable, owner-scoped RGB segmentation tasks (additive table only)."""

from datetime import datetime
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from web.backend.database.database import Base


class RGBSegmentationJob(Base):
    __tablename__ = "rgb_segmentation_jobs"
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_rgb_owner_request"),
    )

    id = Column(String(32), primary_key=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    idempotency_key = Column(String(80), nullable=False)
    request_hash = Column(String(64), nullable=False)
    source_bytes = Column(Integer, nullable=False, default=0)
    state = Column(String(20), nullable=False, default="queued", index=True)
    stage = Column(String(24), nullable=False, default="queued")
    context_json = Column(Text, nullable=False)
    result_json = Column(Text, nullable=True)
    error_code = Column(String(40), nullable=True)
    lease = Column(String(32), nullable=True)
    assessment_id = Column(
        Integer,
        ForeignKey("vasi_assessments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    revision = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    deadline_at = Column(DateTime, nullable=False)

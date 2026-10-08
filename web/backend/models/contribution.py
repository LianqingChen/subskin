"""Minimal, append-only contribution honours; no photos or clinical facts."""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint

from web.backend.database.database import Base


class ContributionCredit(Base):
    """One award per user, evidence fingerprint and task, across retries."""

    __tablename__ = "contribution_credits"
    __table_args__ = (
        UniqueConstraint("user_id", "event_key", name="uq_contribution_credit_event"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_key = Column(String(64), nullable=False)
    kind = Column(String(32), nullable=False)
    points = Column(Integer, nullable=False)
    rule_version = Column(String(20), nullable=False)
    awarded_at = Column(DateTime, default=datetime.utcnow, nullable=False)

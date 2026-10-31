"""持久化限流事件表：进程重启、多 worker 下计数不丢失（仅增量新表）。"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Index, Integer, String

from web.backend.database.database import Base


class RateLimitEvent(Base):
    __tablename__ = "rate_limit_events"
    __table_args__ = (Index("idx_rle_bucket_key_time", "bucket", "key", "created_at"),)

    id = Column(Integer, primary_key=True)
    bucket = Column(String(40), nullable=False)
    key = Column(String(128), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

"""基于数据库的滑动窗口限流：计数存在 rate_limit_events 表，重启不清零。"""

import logging
import random
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from web.backend.exceptions import RateLimitExceededError
from web.backend.models.rate_limit import RateLimitEvent

logger = logging.getLogger(__name__)

RETENTION = timedelta(days=2)
_PRUNE_PROBABILITY = 0.01


def count_in_window(db: Session, bucket: str, key: str, window_seconds: int) -> int:
    since = datetime.utcnow() - timedelta(seconds=window_seconds)
    return (
        db.query(RateLimitEvent)
        .filter(
            RateLimitEvent.bucket == bucket,
            RateLimitEvent.key == key,
            RateLimitEvent.created_at >= since,
        )
        .count()
    )


def hit(db: Session, bucket: str, key: str) -> None:
    db.add(RateLimitEvent(bucket=bucket, key=key[:128], created_at=datetime.utcnow()))
    db.commit()
    if random.random() < _PRUNE_PROBABILITY:
        prune(db)


def prune(db: Session) -> int:
    cutoff = datetime.utcnow() - RETENTION
    deleted = (
        db.query(RateLimitEvent)
        .filter(RateLimitEvent.created_at < cutoff)
        .delete(synchronize_session=False)
    )
    db.commit()
    return int(deleted or 0)


def check_and_hit(
    db: Session,
    bucket: str,
    key: str,
    limit: int,
    window_seconds: int,
    message: str = "操作过于频繁，请稍后再试",
) -> None:
    """超限抛 RateLimitExceededError；未超限则记一次。"""
    if count_in_window(db, bucket, key, window_seconds) >= limit:
        logger.info("rate limit hit: bucket=%s", bucket)
        raise RateLimitExceededError(message)
    hit(db, bucket, key)

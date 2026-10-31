"""Per-user daily quotas for LLM / vision features.

Counts rows the user already created in the last 24h, so quotas survive restarts
and need no extra tables. Admins are exempt.
"""
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, NamedTuple

from sqlalchemy.orm import Session

from web.backend.database.models import (
    Conversation,
    DiaryEntry,
    MedicalReport,
    Message,
    SkinReport,
    User,
)
from web.backend.models.vasi import VASIAssessment
from web.backend.utils.llm_guard import QuotaExceeded

logger = logging.getLogger(__name__)


class _Quota(NamedTuple):
    env: str
    default: int
    label: str
    count: Callable[[Session, int, datetime], int]


def _count_vasi(db: Session, user_id: int, since: datetime) -> int:
    return (
        db.query(VASIAssessment)
        .filter(VASIAssessment.user_id == user_id, VASIAssessment.created_at >= since)
        .count()
    )


def _count_skin_reports(db: Session, user_id: int, since: datetime) -> int:
    return (
        db.query(SkinReport)
        .filter(SkinReport.user_id == user_id, SkinReport.created_at >= since)
        .count()
    )


def _count_diary(db: Session, user_id: int, since: datetime) -> int:
    return (
        db.query(DiaryEntry)
        .filter(DiaryEntry.user_id == user_id, DiaryEntry.created_at >= since)
        .count()
    )


def _count_medical_reports(db: Session, user_id: int, since: datetime) -> int:
    return (
        db.query(MedicalReport)
        .filter(MedicalReport.user_id == user_id, MedicalReport.created_at >= since)
        .count()
    )


def _count_chat(db: Session, user_id: int, since: datetime) -> int:
    return (
        db.query(Message)
        .join(Conversation, Conversation.conversation_id == Message.conversation_id)
        .filter(
            Conversation.user_id == user_id,
            Message.role == "user",
            Message.created_at >= since,
        )
        .count()
    )


QUOTAS: Dict[str, _Quota] = {
    "vasi": _Quota("QUOTA_VASI_DAILY", 30, "皮肤评估", _count_vasi),
    "skin_report": _Quota("QUOTA_SKIN_REPORT_DAILY", 5, "对比报告", _count_skin_reports),
    "diary_ai": _Quota("QUOTA_DIARY_AI_DAILY", 30, "日记 AI 整理", _count_diary),
    "medical_report": _Quota("QUOTA_MEDICAL_REPORT_DAILY", 10, "体检报告解读", _count_medical_reports),
    "chat": _Quota("QUOTA_CHAT_DAILY", 200, "AI 问答", _count_chat),
}


def daily_limit(kind: str) -> int:
    quota = QUOTAS[kind]
    try:
        return max(0, int(os.getenv(quota.env, str(quota.default))))
    except ValueError:
        return quota.default


def _since() -> datetime:
    # Stored timestamps are naive UTC strings in SQLite.
    return datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=24)


def has_daily_quota(db: Session, user: User, kind: str) -> bool:
    if user is None or getattr(user, "is_admin", False):
        return True
    used = QUOTAS[kind].count(db, user.id, _since())
    return used < daily_limit(kind)


def enforce_daily_quota(db: Session, user: User, kind: str) -> None:
    """Raise ``QuotaExceeded`` when the user used up today's allowance for ``kind``."""
    if has_daily_quota(db, user, kind):
        return
    quota = QUOTAS[kind]
    logger.info("daily quota hit: user=%s kind=%s limit=%s", user.id, kind, daily_limit(kind))
    raise QuotaExceeded(f"今日{quota.label}次数已达上限（{daily_limit(kind)}次），请明天再试")

"""IM 反欺诈规则"""

import logging
from datetime import datetime, timezone
from typing import List

from sqlalchemy.orm import Session

from web.backend.database.models import ImMessage, ImConversationMember

logger = logging.getLogger(__name__)


def detect_spam_pattern(
    messages: List[ImMessage], user_id: int, db: Session
) -> bool:
    if not messages:
        return False

    unique_conversations = set(m.conversation_id for m in messages)
    if len(unique_conversations) > 5:
        same_content = {}
        for m in messages:
            if m.content:
                same_content.setdefault(m.content, set()).add(m.conversation_id)
        for _content, convs in same_content.items():
            if len(convs) > 5:
                return True

    one_hour_ago = datetime.now(timezone.utc).replace(
        minute=0, second=0, microsecond=0
    )
    recent_count = sum(
        1
        for m in messages
        if m.created_at and m.created_at > one_hour_ago
    )
    if recent_count > 100:
        return True

    return False


def detect_bot_behavior(user_id: int, db: Session) -> float:
    recent_messages = (
        db.query(ImMessage)
        .filter(ImMessage.sender_id == user_id)
        .order_by(ImMessage.created_at.desc())
        .limit(50)
        .all()
    )

    if len(recent_messages) < 5:
        return 0.0

    intervals = []
    for i in range(len(recent_messages) - 1):
        if recent_messages[i].created_at and recent_messages[i + 1].created_at:
            delta = (
                recent_messages[i].created_at - recent_messages[i + 1].created_at
            ).total_seconds()
            intervals.append(delta)

    if not intervals:
        return 0.0

    avg_interval = sum(intervals) / len(intervals)
    if avg_interval < 1.0:
        return 0.8

    variance = sum((x - avg_interval) ** 2 for x in intervals) / len(intervals)
    if variance < 1.0 and avg_interval < 5.0:
        return 0.6

    unique_content = len(set(m.content for m in recent_messages if m.content))
    total_content = sum(1 for m in recent_messages if m.content)
    if total_content > 0:
        diversity_ratio = unique_content / total_content
        if diversity_ratio < 0.1:
            return 0.7

    return 0.0

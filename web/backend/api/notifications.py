"""
通知 API
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import Optional

from web.backend.database.database import get_db
from web.backend.database.models import UserNotification, User
from web.backend.services.unified_auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Schemas ──

class NotificationOut(BaseModel):
    id: int
    type: str
    title: str
    body: Optional[str] = None
    ref_type: Optional[str] = None
    ref_id: Optional[int] = None
    is_read: bool
    actor: Optional[dict] = None
    created_at: str

    class Config:
        from_attributes = True


class NotificationListOut(BaseModel):
    items: list[NotificationOut]
    total: int
    unread_count: int


# ── Helpers ──

NOTIFICATION_TITLES = {
    "like": "赞了你的帖子",
    "comment": "评论了你的帖子",
    "follow": "关注了你",
    "bookmark": "收藏了你的帖子",
    "collect": "收藏了你的帖子",
    "friend_accepted": "通过了你的好友请求",
    "message": "发来一条私信",
    "system": "系统通知",
    "moderation": "账号状态通知",
}


def _actor_dict(user: Optional[User]) -> Optional[dict]:
    if not user:
        return None
    return {
        "id": user.id,
        "username": user.username,
        "avatar_url": user.avatar_url,
    }


def _notification_out(n: UserNotification, actor_user: Optional[User] = None) -> NotificationOut:
    actor = actor_user or n.actor
    return NotificationOut(
        id=n.id,
        type=n.type,
        title=n.title or NOTIFICATION_TITLES.get(n.type, "新的通知"),
        body=n.content,
        ref_type=n.ref_type,
        ref_id=n.ref_id,
        is_read=n.is_read,
        actor=_actor_dict(actor),
        created_at=n.created_at.isoformat() if n.created_at else "",
    )


def create_notification(
    db: Session,
    user_id: int,
    type: str,
    title: Optional[str] = None,
    body: Optional[str] = None,
    actor_id: Optional[int] = None,
    ref_type: Optional[str] = None,
    ref_id: Optional[int] = None,
) -> Optional[UserNotification]:
    """创建通知（供其他模块调用）"""
    if actor_id and actor_id == user_id:
        return None  # 不给自己发通知
    n = UserNotification(
        user_id=user_id,
        actor_id=actor_id,
        type=type,
        title=title or NOTIFICATION_TITLES.get(type, "新的通知"),
        content=body,
        ref_type=ref_type,
        ref_id=ref_id,
    )
    db.add(n)
    db.commit()
    db.refresh(n)
    return n


# ── Routes ──

@router.get("")
async def list_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NotificationListOut:
    query = db.query(UserNotification).filter(UserNotification.user_id == current_user.id)
    if unread_only:
        query = query.filter(UserNotification.is_read == False)

    total = query.count()
    unread_count = (
        db.query(UserNotification)
        .filter(UserNotification.user_id == current_user.id, UserNotification.is_read == False)
        .count()
    )
    items = (
        query.order_by(desc(UserNotification.created_at))
        .offset(offset)
        .limit(limit)
        .all()
    )
    return NotificationListOut(
        items=[_notification_out(n) for n in items],
        total=total,
        unread_count=unread_count,
    )


@router.get("/unread-count")
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    count = (
        db.query(UserNotification)
        .filter(UserNotification.user_id == current_user.id, UserNotification.is_read == False)
        .count()
    )
    return {"unread_count": count}


@router.post("/{notification_id}/read")
async def mark_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    n = (
        db.query(UserNotification)
        .filter(UserNotification.id == notification_id, UserNotification.user_id == current_user.id)
        .first()
    )
    if not n:
        raise HTTPException(status_code=404, detail="通知不存在")
    n.is_read = True
    db.commit()
    return {"status": "ok"}


@router.post("/read-all")
async def mark_all_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db.query(UserNotification).filter(
        UserNotification.user_id == current_user.id, UserNotification.is_read == False
    ).update({"is_read": True})
    db.commit()
    return {"status": "ok"}

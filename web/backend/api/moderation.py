from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from web.backend.database.database import get_db
from web.backend.database.models import (
    ContentModeration,
    Post,
    User,
    UserNotification,
    UserViolation,
    UserViolationLog,
)
from web.backend.services.admin_auth import get_admin_user
from web.backend.services.auth import auth


router = APIRouter(prefix="/api/moderation", tags=["内容审核"])


class ModerationItem(BaseModel):
    id: int
    post_id: Optional[int] = None
    user_id: int
    content_type: str
    content_snapshot: Optional[str] = None
    risk_level: str
    risk_categories: Optional[list] = None
    auto_action: str
    ai_reason: Optional[str] = None
    ai_confidence: Optional[float] = None
    status: str
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    review_note: Optional[str] = None
    created_at: datetime
    author_username: Optional[str] = None
    post_title: Optional[str] = None

    class Config:
        from_attributes = True


class ModerationListResponse(BaseModel):
    total: int
    items: List[ModerationItem]


class ReviewRequest(BaseModel):
    action: str = Field(..., description="approved/rejected/escalated")
    note: Optional[str] = Field(None, description="审核备注")
    mute_hours: Optional[int] = Field(None, description="禁言时长(小时)，仅rejected时有效")
    ban: Optional[bool] = Field(None, description="是否封号，仅rejected时有效")


class ViolationLogItem(BaseModel):
    id: int
    user_id: int
    action: str
    duration_hours: Optional[int] = None
    reason: Optional[str] = None
    operated_by: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class UserProfileModeration(BaseModel):
    user_id: int
    username: str
    user_status: str
    violation_count: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    muted_until: Optional[datetime] = None
    banned_at: Optional[datetime] = None
    ban_reason: Optional[str] = None
    recent_logs: List[ViolationLogItem] = []


class NotificationItem(BaseModel):
    id: int
    type: str
    title: str
    content: Optional[str] = None
    is_read: bool
    related_id: Optional[int] = None
    ref_type: Optional[str] = None
    ref_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationListResponse(BaseModel):
    total: int
    items: List[NotificationItem]


@router.get("/pending", response_model=ModerationListResponse)
async def get_pending_moderations(
    risk_level: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    current_user: User = Depends(auth),
    db: Session = Depends(get_db),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    query = db.query(ContentModeration).filter(ContentModeration.status == "pending")
    if risk_level:
        query = query.filter(ContentModeration.risk_level == risk_level)

    total = query.count()
    records = query.order_by(ContentModeration.created_at.desc()).offset(offset).limit(min(limit, 50)).all()

    items = []
    for r in records:
        author = db.query(User).filter(User.id == r.user_id).first()
        post = db.query(Post).filter(Post.id == r.post_id).first() if r.post_id else None
        items.append(ModerationItem(
            id=r.id, post_id=r.post_id, user_id=r.user_id,
            content_type=r.content_type, content_snapshot=r.content_snapshot,
            risk_level=r.risk_level, risk_categories=r.risk_categories,
            auto_action=r.auto_action, ai_reason=r.ai_reason,
            ai_confidence=r.ai_confidence, status=r.status,
            reviewed_by=r.reviewed_by, reviewed_at=r.reviewed_at,
            review_note=r.review_note, created_at=r.created_at,
            author_username=author.username if author else None,
            post_title=post.title if post else None,
        ))
    return ModerationListResponse(total=total, items=items)


@router.post("/{moderation_id}/review")
async def review_moderation(
    moderation_id: int,
    req: ReviewRequest,
    current_user: User = Depends(auth),
    db: Session = Depends(get_db),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    moderation = db.query(ContentModeration).filter(ContentModeration.id == moderation_id).first()
    if not moderation:
        raise HTTPException(status_code=404, detail="审核记录不存在")

    moderation.status = req.action
    moderation.reviewed_by = current_user.id
    moderation.reviewed_at = datetime.now(timezone.utc)
    moderation.review_note = req.note

    if req.action == "approved":
        if moderation.post_id:
            post = db.query(Post).filter(Post.id == moderation.post_id).first()
            if post:
                post.moderation_status = "approved"
        db.add(UserNotification(
            user_id=moderation.user_id, type="post_approved",
            title="内容审核通过", content="您发布的内容已通过审核，现已正常展示。",
            related_id=moderation.id,
        ))

    elif req.action == "rejected":
        if moderation.post_id:
            post = db.query(Post).filter(Post.id == moderation.post_id).first()
            if post:
                post.moderation_status = "blocked"

        user = db.query(User).filter(User.id == moderation.user_id).first()
        violation = db.query(UserViolation).filter(UserViolation.user_id == moderation.user_id).first()

        if req.ban and user:
            user.user_status = "banned"
            user.is_active = False
            user.banned_at = datetime.now(timezone.utc)
            user.ban_reason = req.note or "管理员确认严重违规，封号处理"
            if violation:
                violation.status = "banned"
                violation.banned_at = datetime.now(timezone.utc)
                violation.ban_reason = user.ban_reason
            db.add(UserViolationLog(
                user_id=moderation.user_id, moderation_id=moderation.id,
                action="ban", reason=user.ban_reason, operated_by=current_user.id,
            ))
            db.add(UserNotification(
                user_id=moderation.user_id, type="ban",
                title="账号封禁通知", content=f"您因违反社区规范，账号已被封禁。原因：{req.note or '管理员确认违规'}",
                related_id=moderation.id,
            ))
        elif req.mute_hours and user:
            from datetime import timedelta
            user.user_status = "muted"
            user.muted_until = datetime.now(timezone.utc) + timedelta(hours=req.mute_hours)
            if violation:
                violation.status = "muted"
                violation.muted_until = user.muted_until
            db.add(UserViolationLog(
                user_id=moderation.user_id, moderation_id=moderation.id,
                action="mute", duration_hours=req.mute_hours,
                reason=req.note or "管理员确认违规，禁言处理", operated_by=current_user.id,
            ))
            db.add(UserNotification(
                user_id=moderation.user_id, type="mute",
                title="账号禁言通知", content=f"您因违反社区规范，已被禁言{req.mute_hours}小时。原因：{req.note or '管理员确认违规'}",
                related_id=moderation.id,
            ))
        else:
            db.add(UserNotification(
                user_id=moderation.user_id, type="post_rejected",
                title="内容审核未通过", content=f"您发布的内容未通过审核。原因：{req.note or '内容违反社区规范'}",
                related_id=moderation.id,
            ))

    elif req.action == "escalated":
        pass

    db.commit()
    return {"status": "ok", "action": req.action}


@router.get("/user/{user_id}", response_model=UserProfileModeration)
async def get_user_moderation_profile(
    user_id: int,
    current_user: User = Depends(auth),
    db: Session = Depends(get_db),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    violation = db.query(UserViolation).filter(UserViolation.user_id == user_id).first()
    logs = db.query(UserViolationLog).filter(UserViolationLog.user_id == user_id).order_by(UserViolationLog.created_at.desc()).limit(10).all()

    return UserProfileModeration(
        user_id=user.id, username=user.username, user_status=user.user_status or "normal",
        violation_count=user.violation_count or 0, critical_count=user.critical_count or 0,
        high_count=violation.high_count if violation else 0,
        medium_count=violation.medium_count if violation else 0,
        low_count=violation.low_count if violation else 0,
        muted_until=user.muted_until, banned_at=user.banned_at,
        ban_reason=user.ban_reason,
        recent_logs=[ViolationLogItem(
            id=l.id, user_id=l.user_id, action=l.action,
            duration_hours=l.duration_hours, reason=l.reason,
            operated_by=l.operated_by, created_at=l.created_at,
        ) for l in logs],
    )


@router.post("/user/{user_id}/action")
async def admin_user_action(
    user_id: int,
    action: str = Query(..., description="mute/unmute/ban/unban"),
    hours: Optional[int] = Query(None, description="禁言时长(小时)"),
    reason: Optional[str] = Query(None, description="操作原因"),
    current_user: User = Depends(auth),
    db: Session = Depends(get_db),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    violation = db.query(UserViolation).filter(UserViolation.user_id == user_id).first()

    if action == "mute" and hours:
        user.user_status = "muted"
        user.muted_until = datetime.now(timezone.utc) + __import__("datetime").timedelta(hours=hours)
        if violation:
            violation.status = "muted"
            violation.muted_until = user.muted_until
        db.add(UserViolationLog(user_id=user_id, action="mute", duration_hours=hours, reason=reason, operated_by=current_user.id))
        db.add(UserNotification(user_id=user_id, type="mute", title="账号禁言通知", content=f"管理员对您进行了禁言{hours}小时处理。原因：{reason or '违反社区规范'}"))
    elif action == "unmute":
        user.user_status = "normal"
        user.muted_until = None
        if violation:
            violation.status = "normal"
            violation.muted_until = None
        db.add(UserViolationLog(user_id=user_id, action="unmute", reason=reason, operated_by=current_user.id))
        db.add(UserNotification(user_id=user_id, type="moderation_warning", title="禁言已解除", content="您的禁言已被管理员解除，请遵守社区规范。"))
    elif action == "ban":
        user.user_status = "banned"
        user.is_active = False
        user.banned_at = datetime.now(timezone.utc)
        user.ban_reason = reason or "管理员封号处理"
        if violation:
            violation.status = "banned"
            violation.banned_at = user.banned_at
            violation.ban_reason = user.ban_reason
        db.add(UserViolationLog(user_id=user_id, action="ban", reason=reason, operated_by=current_user.id))
        db.add(UserNotification(user_id=user_id, type="ban", title="账号封禁通知", content=f"您的账号已被管理员封禁。原因：{reason or '严重违反社区规范'}"))
    elif action == "unban":
        user.user_status = "normal"
        user.is_active = True
        user.banned_at = None
        user.ban_reason = None
        if violation:
            violation.status = "normal"
            violation.banned_at = None
            violation.ban_reason = None
        db.add(UserViolationLog(user_id=user_id, action="unban", reason=reason, operated_by=current_user.id))
        db.add(UserNotification(user_id=user_id, type="moderation_warning", title="封禁已解除", content="您的账号已被管理员解封，请遵守社区规范。"))
    else:
        raise HTTPException(status_code=400, detail="无效操作")

    db.commit()
    return {"status": "ok", "action": action}



@router.get("/notifications", response_model=NotificationListResponse)
async def get_notifications(
    limit: int = 20,
    offset: int = 0,
    current_user: User = Depends(auth),
    db: Session = Depends(get_db),
):
    query = db.query(UserNotification).filter(UserNotification.user_id == current_user.id)
    total = query.count()
    records = query.order_by(UserNotification.created_at.desc()).offset(offset).limit(min(limit, 50)).all()
    return NotificationListResponse(total=total, items=[NotificationItem(
        id=n.id, type=n.type, title=n.title, content=n.content,
        is_read=n.is_read, related_id=n.related_id, ref_type=n.ref_type, ref_id=n.ref_id, created_at=n.created_at,
    ) for n in records])


@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(auth),
    db: Session = Depends(get_db),
):
    n = db.query(UserNotification).filter(
        UserNotification.id == notification_id,
        UserNotification.user_id == current_user.id,
    ).first()
    if not n:
        raise HTTPException(status_code=404, detail="通知不存在")
    n.is_read = True
    db.commit()
    return {"status": "ok"}


@router.get("/notifications/unread-count")
async def get_unread_count(
    current_user: User = Depends(auth),
    db: Session = Depends(get_db),
):
    count = db.query(UserNotification).filter(
        UserNotification.user_id == current_user.id,
        UserNotification.is_read == False,
    ).count()
    return {"unread_count": count}



@router.get("/history", response_model=ModerationListResponse)
async def get_moderation_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    _ = admin
    query = db.query(ModerationRecord).filter(
        ModerationRecord.status.in_(["approved", "rejected", "punished"])
    )
    if status:
        query = query.filter(ModerationRecord.status == status)

    total = query.count()
    records = query.order_by(ModerationRecord.reviewed_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    items = []
    for r in records:
        author = db.query(User).filter(User.id == r.user_id).first()
        post = db.query(Post).filter(Post.id == r.post_id).first() if r.post_id else None
        items.append(
            ModerationItem(
                id=r.id,
                post_id=r.post_id,
                user_id=r.user_id,
                content_type=r.content_type,
                content_snapshot=r.content_snapshot,
                risk_level=r.risk_level,
                risk_categories=json.loads(r.risk_categories) if r.risk_categories else [],
                auto_action=r.auto_action,
                ai_reason=r.ai_reason,
                ai_confidence=r.ai_confidence,
                status=r.status,
                reviewed_by=r.reviewed_by,
                reviewed_at=r.reviewed_at.isoformat() if r.reviewed_at else None,
                review_note=r.review_note,
                created_at=r.created_at.isoformat() if r.created_at else None,
                author_username=author.username if author else None,
                post_title=post.title if post else None,
            )
        )
    return ModerationListResponse(total=total, items=items)

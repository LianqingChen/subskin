"""IM 管理员审核 API"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from web.backend.database.database import get_db
from web.backend.database.models import (
    ImMessageModeration,
    ImMessage,
    User,
    UserViolation,
    UserViolationLog,
)
from web.backend.services.auth import auth

router = APIRouter(prefix="/api/admin/im/moderation", tags=["管理员-IM审核"])


class ReviewAction(BaseModel):
    action: str  # approved / rejected / escalated
    note: Optional[str] = None


@router.get("/pending")
async def list_pending_im_moderations(
    risk_level: str = None,
    limit: int = 20,
    offset: int = 0,
    current_user: User = Depends(auth),
    db: Session = Depends(get_db),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    query = db.query(ImMessageModeration).filter(
        ImMessageModeration.status == "pending"
    )
    if risk_level:
        query = query.filter(ImMessageModeration.risk_level == risk_level)

    moderations = query.order_by(ImMessageModeration.created_at.desc()).offset(offset).limit(limit).all()

    result = []
    for mod in moderations:
        sender = db.query(User).filter(User.id == mod.sender_id).first()
        msg = db.query(ImMessage).filter(ImMessage.id == mod.message_id).first()
        result.append(
            {
                "id": mod.id,
                "message_id": mod.message_id,
                "sender": (
                    {
                        "id": sender.id,
                        "username": sender.username,
                    }
                    if sender
                    else None
                ),
                "content_snapshot": mod.content_snapshot,
                "risk_level": mod.risk_level,
                "risk_categories": mod.risk_categories,
                "auto_action": mod.auto_action,
                "ai_reason": mod.ai_reason,
                "ai_confidence": mod.ai_confidence,
                "message_content": msg.content if msg else None,
                "created_at": (
                    mod.created_at.isoformat() if mod.created_at else None
                ),
            }
        )
    return {"items": result, "total": len(result)}


@router.post("/{moderation_id}/review")
async def review_im_moderation(
    moderation_id: int,
    req: ReviewAction,
    current_user: User = Depends(auth),
    db: Session = Depends(get_db),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    mod = (
        db.query(ImMessageModeration)
        .filter(ImMessageModeration.id == moderation_id)
        .first()
    )
    if not mod:
        raise HTTPException(status_code=404, detail="审核记录不存在")

    mod.status = req.action
    mod.reviewed_by = current_user.id

    if req.action == "approved":
        msg = db.query(ImMessage).filter(ImMessage.id == mod.message_id).first()
        if msg and msg.content == "[该消息因违规已被屏蔽]":
            msg.content = mod.content_snapshot

    elif req.action == "rejected":
        violation = (
            db.query(UserViolation)
            .filter(UserViolation.user_id == mod.sender_id)
            .first()
        )
        if violation:
            violation.warning_count += 1
        log = UserViolationLog(
            user_id=mod.sender_id,
            action="warn",
            reason=f"IM消息审核拒绝: {req.note or mod.ai_reason}",
        )
        db.add(log)

    db.commit()
    return {"status": "ok", "action": req.action}

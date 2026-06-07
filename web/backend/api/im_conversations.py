"""IM 会话管理 API"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from web.backend.database.database import get_db
from web.backend.database.models import ImConversationMember, User
from web.backend.services.auth import auth
from web.backend.services.im_service import ImService

router = APIRouter(prefix="/api/im/conversations", tags=["IM会话"])


class CreatePrivateConvRequest(BaseModel):
    user_id: int


@router.get("")
async def list_conversations(
    current_user: User = Depends(auth), db: Session = Depends(get_db)
):
    service = ImService(db)
    return {"items": service.get_conversations(current_user.id)}


@router.post("/private")
async def create_private(
    req: CreatePrivateConvRequest,
    current_user: User = Depends(auth),
    db: Session = Depends(get_db),
):
    try:
        service = ImService(db)
        conv = service.get_or_create_private_conversation(
            current_user.id, req.user_id
        )
        return {"conversation_id": conv.id, "type": conv.type}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{conversation_id}/messages")
async def get_messages(
    conversation_id: int,
    before_id: int = None,
    limit: int = 50,
    current_user: User = Depends(auth),
    db: Session = Depends(get_db),
):
    service = ImService(db)
    try:
        return {
            "items": service.get_messages(
                conversation_id, current_user.id, before_id, limit
            )
        }
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/{conversation_id}/read")
async def mark_read(
    conversation_id: int,
    current_user: User = Depends(auth),
    db: Session = Depends(get_db),
):
    member = (
        db.query(ImConversationMember)
        .filter(
            ImConversationMember.conversation_id == conversation_id,
            ImConversationMember.user_id == current_user.id,
        )
        .first()
    )
    if member:
        member.last_read_at = datetime.now(timezone.utc)
        db.commit()
    return {"status": "ok"}


@router.post("/{conversation_id}/pin")
async def toggle_pin(
    conversation_id: int,
    current_user: User = Depends(auth),
    db: Session = Depends(get_db),
):
    member = (
        db.query(ImConversationMember)
        .filter(
            ImConversationMember.conversation_id == conversation_id,
            ImConversationMember.user_id == current_user.id,
        )
        .first()
    )
    if not member:
        raise HTTPException(status_code=404, detail="会话不存在")
    member.is_pinned = not member.is_pinned
    db.commit()
    return {"is_pinned": member.is_pinned}

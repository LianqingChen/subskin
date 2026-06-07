"""IM 消息 API"""

import time
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from web.backend.database.database import get_db
from web.backend.database.models import User
from web.backend.services.auth import auth
from web.backend.services.im_service import ImService

router = APIRouter(prefix="/api/im/messages", tags=["IM消息"])

_rate_limits: dict = defaultdict(list)

MAX_MESSAGES_PER_MINUTE = 30


def check_rate_limit(user_id: int, max_per_minute: int = MAX_MESSAGES_PER_MINUTE) -> bool:
    now = time.time()
    window = now - 60
    _rate_limits[user_id] = [t for t in _rate_limits[user_id] if t > window]
    if len(_rate_limits[user_id]) >= max_per_minute:
        return False
    _rate_limits[user_id].append(now)
    return True


class SendMessageRequest(BaseModel):
    conversation_id: int
    msg_type: str = "text"
    content: Optional[str] = None
    metadata: Optional[dict] = None
    reply_to_id: Optional[int] = None


@router.post("")
async def send_message(
    req: SendMessageRequest,
    current_user: User = Depends(auth),
    db: Session = Depends(get_db),
):
    if not check_rate_limit(current_user.id):
        raise HTTPException(
            status_code=429, detail="发送过于频繁，请稍后再试"
        )
    service = ImService(db)
    try:
        msg = service.send_message(
            req.conversation_id,
            current_user.id,
            req.msg_type,
            req.content,
            req.metadata,
            req.reply_to_id,
        )
        return service._serialize_message(msg)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{message_id}/recall")
async def recall_message(
    message_id: int,
    current_user: User = Depends(auth),
    db: Session = Depends(get_db),
):
    service = ImService(db)
    try:
        service.recall_message(message_id, current_user.id)
        return {"status": "ok"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

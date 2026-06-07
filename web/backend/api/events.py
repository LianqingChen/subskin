"""用户行为事件追踪 API"""

import json
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from web.backend.database.database import get_db
from web.backend.database.models import User, UserEvent
from web.backend.services.auth import get_current_user_optional
from web.backend.utils.redact import mask_ip

logger = logging.getLogger(__name__)
router = APIRouter()


class TrackEvent(BaseModel):
    event_type: str = Field(..., max_length=50)
    element_id: Optional[str] = Field(None, max_length=200)
    page_path: Optional[str] = Field(None, max_length=500)
    element_text: Optional[str] = Field(None, max_length=500)
    extra_data: Optional[dict[str, Any]] = None
    session_id: Optional[str] = Field(None, max_length=64)


class TrackBatch(BaseModel):
    events: list[TrackEvent] = Field(..., max_length=50)


@router.post("/track")
async def track_event(
    data: TrackEvent,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    uid = current_user.uid if current_user else None
    client_fingerprint = request.headers.get("X-Client-Fingerprint")
    ip_address = mask_ip(request.client.host) if request.client else None
    user_agent = request.headers.get("user-agent", "")[:500]

    event = UserEvent(
        uid=uid,
        session_id=data.session_id or "",
        event_type=data.event_type,
        element_id=data.element_id,
        page_path=data.page_path,
        element_text=data.element_text,
        extra_data=json.dumps(data.extra_data) if data.extra_data else None,
        client_fingerprint=client_fingerprint,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(event)
    db.commit()
    return {"status": "ok"}


@router.post("/track/batch")
async def track_batch(
    data: TrackBatch,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    uid = current_user.uid if current_user else None
    client_fingerprint = request.headers.get("X-Client-Fingerprint")
    ip_address = mask_ip(request.client.host) if request.client else None
    user_agent = request.headers.get("user-agent", "")[:500]

    events = []
    for event_data in data.events:
        events.append(
            UserEvent(
                uid=uid,
                session_id=event_data.session_id or "",
                event_type=event_data.event_type,
                element_id=event_data.element_id,
                page_path=event_data.page_path,
                element_text=event_data.element_text,
                extra_data=json.dumps(event_data.extra_data)
                if event_data.extra_data
                else None,
                client_fingerprint=client_fingerprint,
                ip_address=ip_address,
                user_agent=user_agent,
            )
        )
    db.add_all(events)
    db.commit()
    return {"status": "ok", "count": len(events)}

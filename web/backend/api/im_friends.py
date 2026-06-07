"""IM 好友系统 API"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from web.backend.database.database import get_db
from web.backend.database.models import ImFriendRequest, User
from web.backend.services.auth import auth
from web.backend.services.im_service import ImService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/im/friends", tags=["IM好友"])


class FriendRequestReq(BaseModel):
    user_id: int
    message: Optional[str] = None


@router.post("/request")
async def send_request(
    req: FriendRequestReq,
    current_user: User = Depends(auth),
    db: Session = Depends(get_db),
):
    target = db.query(User).filter(User.id == req.user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")
    if not target.privacy_mode:
        raise HTTPException(status_code=403, detail="对方已开启隐私保护，暂无法添加好友")
    service = ImService(db)
    try:
        r = service.send_friend_request(current_user.id, req.user_id, req.message)
        return {"id": r.id, "status": r.status}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/requests")
async def list_requests(
    current_user: User = Depends(auth), db: Session = Depends(get_db)
):
    received = (
        db.query(ImFriendRequest)
        .filter(
            ImFriendRequest.to_user_id == current_user.id,
            ImFriendRequest.status == "pending",
        )
        .all()
    )
    sent = (
        db.query(ImFriendRequest)
        .filter(
            ImFriendRequest.from_user_id == current_user.id,
            ImFriendRequest.status == "pending",
        )
        .all()
    )

    def fmt(r, user_lookup):
        u = db.query(User).filter(User.id == user_lookup(r)).first()
        return {
            "id": r.id,
            "user": (
                {
                    "id": u.id,
                    "username": u.username,
                    "avatar_url": u.avatar_url,
                }
                if u
                else None
            ),
            "message": r.message,
            "created_at": (
                r.created_at.isoformat() if r.created_at else None
            ),
        }

    return {
        "received": [fmt(r, lambda x: x.from_user_id) for r in received],
        "sent": [fmt(r, lambda x: x.to_user_id) for r in sent],
    }


@router.post("/requests/{request_id}/accept")
async def accept_request(
    request_id: int,
    current_user: User = Depends(auth),
    db: Session = Depends(get_db),
):
    service = ImService(db)
    try:
        req = service.accept_friend_request(request_id, current_user.id)
        try:
            from web.backend.api.notifications import create_notification
            create_notification(
                db,
                user_id=req.from_user_id,
                type="friend_accepted",
                title="通过了你的好友请求",
                body="",
                actor_id=current_user.id,
                ref_type="user",
                ref_id=current_user.id,
            )
        except Exception:
            logger.warning("Failed to create friend accept notification for request %s", request_id, exc_info=True)
        return {"status": "ok"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/requests/{request_id}/decline")
async def decline_request(
    request_id: int,
    current_user: User = Depends(auth),
    db: Session = Depends(get_db),
):
    req = (
        db.query(ImFriendRequest)
        .filter(
            ImFriendRequest.id == request_id,
            ImFriendRequest.to_user_id == current_user.id,
        )
        .first()
    )
    if not req:
        raise HTTPException(status_code=404, detail="请求不存在")
    req.status = "declined"
    db.commit()
    return {"status": "ok"}


@router.get("")
async def list_friends(
    current_user: User = Depends(auth), db: Session = Depends(get_db)
):
    service = ImService(db)
    return {"items": service.get_friends(current_user.id)}

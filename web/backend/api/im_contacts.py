"""IM 通讯录匹配 API — 隐私安全设计"""

import hashlib
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from web.backend.database.database import get_db
from web.backend.database.models import User, UserCredential, ImFriendRequest
from web.backend.services.auth import auth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/im/contacts", tags=["IM通讯录"])


class PhoneHashItem(BaseModel):
    hash: str  # SHA256(phone_normalized)
    name: Optional[str] = None  # 本地通讯录中的名字，仅用于客户端展示


class MatchContactsRequest(BaseModel):
    phone_hashes: List[PhoneHashItem]


def _hash_phone(phone: str) -> str:
    normalized = phone.strip().replace("-", "").replace(" ", "").replace("+86", "")
    return hashlib.sha256(normalized.encode()).hexdigest()


def _precompute_user_phone_hashes(db: Session) -> dict:
    """Build {hash: user_id} for users who allow phone discovery."""
    credentials = (
        db.query(UserCredential)
        .join(User, UserCredential.user_id == User.id)
        .filter(
            UserCredential.cred_type == "phone",
            User.phone_discoverable == True,  # noqa: E712
            User.privacy_mode == True,  # noqa: E712 — visible/discoverable
        )
        .all()
    )
    mapping = {}
    for cred in credentials:
        phone = cred.cred_id.strip()
        h = _hash_phone(phone)
        mapping[h] = cred.user_id
    return mapping


@router.post("/match")
async def match_contacts(
    req: MatchContactsRequest,
    current_user: User = Depends(auth),
    db: Session = Depends(get_db),
):
    """Match user's phone contacts against SubSkin users via SHA256 hashes.
    Client sends SHA256(phone) — raw phone numbers never leave the device."""
    if len(req.phone_hashes) > 2000:
        raise HTTPException(status_code=400, detail="一次最多匹配2000个联系人")

    phone_hash_map = _precompute_user_phone_hashes(db)

    friend_ids = set()
    sent = db.query(ImFriendRequest).filter(
        ImFriendRequest.from_user_id == current_user.id,
        ImFriendRequest.status == "accepted",
    ).all()
    received = db.query(ImFriendRequest).filter(
        ImFriendRequest.to_user_id == current_user.id,
        ImFriendRequest.status == "accepted",
    ).all()
    for r in sent:
        friend_ids.add(r.to_user_id)
    for r in received:
        friend_ids.add(r.from_user_id)

    pending_sent_ids = set()
    pending = db.query(ImFriendRequest).filter(
        ImFriendRequest.from_user_id == current_user.id,
        ImFriendRequest.status == "pending",
    ).all()
    for r in pending:
        pending_sent_ids.add(r.to_user_id)

    matched = []
    seen_user_ids = set()
    matched_user_ids = set()
    for item in req.phone_hashes:
        user_id = phone_hash_map.get(item.hash)
        if not user_id or user_id == current_user.id:
            continue
        if user_id in seen_user_ids:
            if item.name:
                for m in matched:
                    if m["user_id"] == user_id and not m.get("contact_name"):
                        m["contact_name"] = item.name
            continue
        seen_user_ids.add(user_id)
        matched_user_ids.add(user_id)

    users_map = {}
    if matched_user_ids:
        users = db.query(User).filter(
            User.id.in_(matched_user_ids),
            User.is_active == True,  # noqa: E712
            User.user_status != "banned",
        ).all()
        for u in users:
            users_map[u.id] = u

    for item in req.phone_hashes:
        user_id = phone_hash_map.get(item.hash)
        if not user_id or user_id == current_user.id or user_id not in users_map:
            continue
        if any(m["user_id"] == user_id for m in matched):
            continue

        user = users_map[user_id]
        matched.append({
            "user_id": user.id,
            "username": user.username,
            "avatar_url": user.avatar_url,
            "contact_name": item.name,
            "is_friend": user.id in friend_ids,
            "request_pending": user.id in pending_sent_ids,
        })

    return {"items": matched}


@router.get("/search")
async def search_users(
    q: str = "",
    limit: int = 20,
    current_user: User = Depends(auth),
    db: Session = Depends(get_db),
):
    """Search SubSkin users by username for adding friends."""
    if not q.strip() or len(q.strip()) < 2:
        return {"items": []}

    friend_ids = set()
    sent = db.query(ImFriendRequest).filter(
        ImFriendRequest.from_user_id == current_user.id,
        ImFriendRequest.status == "accepted",
    ).all()
    received = db.query(ImFriendRequest).filter(
        ImFriendRequest.to_user_id == current_user.id,
        ImFriendRequest.status == "accepted",
    ).all()
    for r in sent:
        friend_ids.add(r.to_user_id)
    for r in received:
        friend_ids.add(r.from_user_id)

    pending_sent_ids = set()
    pending = db.query(ImFriendRequest).filter(
        ImFriendRequest.from_user_id == current_user.id,
        ImFriendRequest.status == "pending",
    ).all()
    for r in pending:
        pending_sent_ids.add(r.to_user_id)

    users = (
        db.query(User)
        .filter(
            User.username.contains(q.strip()),
            User.id != current_user.id,
            User.is_active == True,  # noqa: E712
            User.privacy_mode == True,  # noqa: E712 — visible/discoverable only
        )
        .limit(limit)
        .all()
    )

    return {
        "items": [
            {
                "user_id": u.id,
                "username": u.username,
                "avatar_url": u.avatar_url,
                "is_friend": u.id in friend_ids,
                "request_pending": u.id in pending_sent_ids,
            }
            for u in users
        ]
    }

"""IM 群聊管理 API"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List
from sqlalchemy.orm import Session

from web.backend.database.database import get_db
from web.backend.database.models import User, ImConversation, ImConversationMember
from web.backend.services.auth import auth

router = APIRouter(prefix="/api/im/groups", tags=["IM群聊"])


class CreateGroupRequest(BaseModel):
    name: str
    member_ids: List[int]


class AddMembersRequest(BaseModel):
    user_ids: List[int]


@router.post("")
async def create_group(
    req: CreateGroupRequest,
    current_user: User = Depends(auth),
    db: Session = Depends(get_db),
):
    if len(req.member_ids) < 1:
        raise HTTPException(status_code=400, detail="至少邀请1位成员")
    conv = ImConversation(type="group", name=req.name, owner_id=current_user.id)
    db.add(conv)
    db.flush()
    db.add(
        ImConversationMember(
            conversation_id=conv.id, user_id=current_user.id, role="owner"
        )
    )
    for uid in req.member_ids:
        if uid != current_user.id:
            db.add(
                ImConversationMember(
                    conversation_id=conv.id, user_id=uid, role="member"
                )
            )
    db.commit()
    return {"id": conv.id, "name": conv.name, "type": conv.type}


@router.get("/{group_id}/members")
async def list_members(
    group_id: int,
    current_user: User = Depends(auth),
    db: Session = Depends(get_db),
):
    members = (
        db.query(ImConversationMember)
        .filter(ImConversationMember.conversation_id == group_id)
        .all()
    )
    result = []
    for m in members:
        user = db.query(User).filter(User.id == m.user_id).first()
        if user:
            result.append(
                {
                    "user_id": user.id,
                    "username": user.username,
                    "avatar_url": user.avatar_url,
                    "role": m.role,
                }
            )
    return {"items": result}


@router.post("/{group_id}/members")
async def add_members(
    group_id: int,
    req: AddMembersRequest,
    current_user: User = Depends(auth),
    db: Session = Depends(get_db),
):
    member = (
        db.query(ImConversationMember)
        .filter(
            ImConversationMember.conversation_id == group_id,
            ImConversationMember.user_id == current_user.id,
            ImConversationMember.role.in_(["owner", "admin"]),
        )
        .first()
    )
    if not member:
        raise HTTPException(status_code=403, detail="无权限")
    for uid in req.user_ids:
        existing = (
            db.query(ImConversationMember)
            .filter(
                ImConversationMember.conversation_id == group_id,
                ImConversationMember.user_id == uid,
            )
            .first()
        )
        if not existing:
            db.add(ImConversationMember(conversation_id=group_id, user_id=uid))
    db.commit()
    return {"status": "ok"}


@router.delete("/{group_id}/members/{user_id}")
async def remove_member(
    group_id: int,
    user_id: int,
    current_user: User = Depends(auth),
    db: Session = Depends(get_db),
):
    if user_id == current_user.id:
        member = (
            db.query(ImConversationMember)
            .filter(
                ImConversationMember.conversation_id == group_id,
                ImConversationMember.user_id == user_id,
            )
            .first()
        )
        if member:
            db.delete(member)
        db.commit()
        return {"status": "ok"}
    admin = (
        db.query(ImConversationMember)
        .filter(
            ImConversationMember.conversation_id == group_id,
            ImConversationMember.user_id == current_user.id,
            ImConversationMember.role.in_(["owner", "admin"]),
        )
        .first()
    )
    if not admin:
        raise HTTPException(status_code=403, detail="无权限")
    member = (
        db.query(ImConversationMember)
        .filter(
            ImConversationMember.conversation_id == group_id,
            ImConversationMember.user_id == user_id,
        )
        .first()
    )
    if member:
        db.delete(member)
    db.commit()
    return {"status": "ok"}


@router.put("/{group_id}/info")
async def update_group_info(
    group_id: int,
    name: str = None,
    announcement: str = None,
    current_user: User = Depends(auth),
    db: Session = Depends(get_db),
):
    member = (
        db.query(ImConversationMember)
        .filter(
            ImConversationMember.conversation_id == group_id,
            ImConversationMember.user_id == current_user.id,
            ImConversationMember.role.in_(["owner", "admin"]),
        )
        .first()
    )
    if not member:
        raise HTTPException(status_code=403, detail="无权限")
    conv = db.query(ImConversation).filter(ImConversation.id == group_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="群聊不存在")
    if name is not None:
        conv.name = name
    if announcement is not None:
        conv.announcement = announcement
    db.commit()
    return {"status": "ok"}

"""IM 即时通讯核心业务逻辑"""

import logging
from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import func
from sqlalchemy.orm import Session

from web.backend.database.models import (
    User,
    ImConversation,
    ImConversationMember,
    ImMessage,
    ImMessageRead,
    ImFriendRequest,
    UserBlock,
)

from web.backend.api.notifications import create_notification

logger = logging.getLogger(__name__)


class ImService:
    def __init__(self, db: Session):
        self.db = db

    # ── 会话管理 ──

    def get_or_create_private_conversation(
        self, user_id: int, peer_id: int
    ) -> ImConversation:
        if user_id == peer_id:
            raise ValueError("不能和自己创建会话")

        block = (
            self.db.query(UserBlock)
            .filter(
                (
                    (UserBlock.blocker_id == user_id)
                    & (UserBlock.blocked_id == peer_id)
                )
                | (
                    (UserBlock.blocker_id == peer_id)
                    & (UserBlock.blocked_id == user_id)
                )
            )
            .first()
        )
        if block:
            raise ValueError("无法发送消息：用户已拉黑或被拉黑")

        members_subq = (
            self.db.query(ImConversationMember.conversation_id)
            .filter(ImConversationMember.user_id.in_([user_id, peer_id]))
            .group_by(ImConversationMember.conversation_id)
            .having(func.count() == 2)
            .subquery()
        )
        conv = (
            self.db.query(ImConversation)
            .join(
                members_subq,
                ImConversation.id == members_subq.c.conversation_id,
            )
            .filter(ImConversation.type == "private")
            .first()
        )
        if conv:
            return conv

        conv = ImConversation(type="private")
        self.db.add(conv)
        self.db.flush()
        self.db.add_all(
            [
                ImConversationMember(
                    conversation_id=conv.id, user_id=user_id
                ),
                ImConversationMember(
                    conversation_id=conv.id, user_id=peer_id
                ),
            ]
        )
        self.db.commit()
        return conv

    def get_conversations(self, user_id: int) -> List[dict]:
        subq = (
            self.db.query(ImConversationMember.conversation_id)
            .filter(ImConversationMember.user_id == user_id)
            .subquery()
        )
        conversations = (
            self.db.query(ImConversation)
            .join(subq, ImConversation.id == subq.c.conversation_id)
            .order_by(ImConversation.last_message_at.desc().nullslast())
            .all()
        )

        result = []
        for conv in conversations:
            last_msg = (
                self.db.query(ImMessage)
                .filter(ImMessage.conversation_id == conv.id)
                .order_by(ImMessage.created_at.desc())
                .first()
            )
            member = (
                self.db.query(ImConversationMember)
                .filter(
                    ImConversationMember.conversation_id == conv.id,
                    ImConversationMember.user_id == user_id,
                )
                .first()
            )
            unread = 0
            if member and member.last_read_at:
                unread = (
                    self.db.query(ImMessage)
                    .filter(
                        ImMessage.conversation_id == conv.id,
                        ImMessage.created_at > member.last_read_at,
                        ImMessage.sender_id != user_id,
                        ImMessage.is_recalled == False,  # noqa: E712
                    )
                    .count()
                )
            elif member:
                unread = (
                    self.db.query(ImMessage)
                    .filter(
                        ImMessage.conversation_id == conv.id,
                        ImMessage.sender_id != user_id,
                        ImMessage.is_recalled == False,  # noqa: E712
                    )
                    .count()
                )

            peer = None
            if conv.type == "private":
                peer_member = (
                    self.db.query(ImConversationMember)
                    .filter(
                        ImConversationMember.conversation_id == conv.id,
                        ImConversationMember.user_id != user_id,
                    )
                    .first()
                )
                if peer_member:
                    peer = (
                        self.db.query(User)
                        .filter(User.id == peer_member.user_id)
                        .first()
                    )

            result.append(
                {
                    "id": conv.id,
                    "type": conv.type,
                    "name": conv.name,
                    "avatar": conv.avatar,
                    "peer_user": (
                        {
                            "id": peer.id,
                            "username": peer.username,
                            "avatar_url": peer.avatar_url,
                        }
                        if peer
                        else None
                    ),
                    "last_message": (
                        self._serialize_message(last_msg) if last_msg else None
                    ),
                    "unread_count": unread,
                    "is_pinned": member.is_pinned if member else False,
                    "is_muted": (
                        bool(
                            member.mute_until
                            and member.mute_until > datetime.now(timezone.utc)
                        )
                        if member
                        else False
                    ),
                    "last_message_at": (
                        conv.last_message_at.isoformat()
                        if conv.last_message_at
                        else None
                    ),
                }
            )
        return result

    def _serialize_message(self, msg: ImMessage) -> dict:
        sender = self.db.query(User).filter(User.id == msg.sender_id).first()
        return {
            "id": msg.id,
            "conversation_id": msg.conversation_id,
            "sender_id": msg.sender_id,
            "sender_name": sender.username if sender else "Unknown",
            "msg_type": msg.msg_type,
            "content": msg.content,
            "metadata": msg.metadata_json,
            "status": msg.status,
            "is_recalled": msg.is_recalled,
            "created_at": (
                msg.created_at.isoformat() if msg.created_at else None
            ),
        }

    # ── 消息收发 ──

    def send_message(
        self,
        conversation_id: int,
        sender_id: int,
        msg_type: str,
        content: Optional[str] = None,
        metadata: Optional[dict] = None,
        reply_to_id: Optional[int] = None,
    ) -> ImMessage:
        member = (
            self.db.query(ImConversationMember)
            .filter(
                ImConversationMember.conversation_id == conversation_id,
                ImConversationMember.user_id == sender_id,
            )
            .first()
        )
        if not member:
            raise ValueError("不是会话成员")

        if member.mute_until and member.mute_until > datetime.now(
            timezone.utc
        ):
            raise ValueError("已被禁言")

        msg = ImMessage(
            conversation_id=conversation_id,
            sender_id=sender_id,
            msg_type=msg_type,
            content=content,
            metadata_json=metadata,
            reply_to_id=reply_to_id,
        )
        self.db.add(msg)

        conv = (
            self.db.query(ImConversation)
            .filter(ImConversation.id == conversation_id)
            .first()
        )
        if conv:
            conv.last_message_at = msg.created_at

        self.db.commit()

        # Notify other conversation members (not the sender)
        try:
            sender = self.db.query(User).filter(User.id == sender_id).first()
            sender_name = sender.username if sender else "用户"
            other_members = (
                self.db.query(ImConversationMember)
                .filter(
                    ImConversationMember.conversation_id == conversation_id,
                    ImConversationMember.user_id != sender_id,
                )
                .all()
            )
            for member in other_members:
                create_notification(
                    self.db,
                    user_id=member.user_id,
                    type="message",
                    title=f"{sender_name} 发来一条私信",
                    body=content[:100] if content else "[图片]",
                    actor_id=sender_id,
                    ref_type="conversation",
                    ref_id=conversation_id,
                )
        except Exception as e:
            logger.warning("Failed to create message notification: %s", e)

        return msg

    def get_messages(
        self,
        conversation_id: int,
        user_id: int,
        before_id: Optional[int] = None,
        limit: int = 50,
    ) -> List[dict]:
        member = (
            self.db.query(ImConversationMember)
            .filter(
                ImConversationMember.conversation_id == conversation_id,
                ImConversationMember.user_id == user_id,
            )
            .first()
        )
        if not member:
            raise ValueError("无权查看此会话")

        query = self.db.query(ImMessage).filter(
            ImMessage.conversation_id == conversation_id
        )
        if before_id:
            query = query.filter(ImMessage.id < before_id)

        messages = query.order_by(ImMessage.created_at.desc()).limit(limit).all()
        return [self._serialize_message(m) for m in reversed(messages)]

    def recall_message(self, message_id: int, user_id: int) -> bool:
        msg = (
            self.db.query(ImMessage)
            .filter(ImMessage.id == message_id)
            .first()
        )
        if not msg:
            raise ValueError("消息不存在")
        if msg.sender_id != user_id:
            raise ValueError("只能撤回自己的消息")
        elapsed = (datetime.now(timezone.utc) - msg.created_at).total_seconds()
        if elapsed > 120:
            raise ValueError("超过2分钟无法撤回")
        msg.is_recalled = True
        msg.content = "[消息已撤回]"
        self.db.commit()
        return True

    # ── 好友系统 ──

    def send_friend_request(
        self, from_user_id: int, to_user_id: int, message: str = None
    ) -> ImFriendRequest:
        if from_user_id == to_user_id:
            raise ValueError("不能添加自己为好友")
        existing = (
            self.db.query(ImFriendRequest)
            .filter(
                (
                    (ImFriendRequest.from_user_id == from_user_id)
                    & (ImFriendRequest.to_user_id == to_user_id)
                )
                | (
                    (ImFriendRequest.from_user_id == to_user_id)
                    & (ImFriendRequest.to_user_id == from_user_id)
                )
            )
            .first()
        )
        if existing:
            if existing.status == "accepted":
                raise ValueError("已经是好友")
            if existing.status == "pending":
                raise ValueError("已有待处理的好友请求")
        req = ImFriendRequest(
            from_user_id=from_user_id,
            to_user_id=to_user_id,
            message=message,
        )
        self.db.add(req)
        self.db.commit()
        return req

    def accept_friend_request(
        self, request_id: int, user_id: int
    ) -> ImFriendRequest:
        req = (
            self.db.query(ImFriendRequest)
            .filter(ImFriendRequest.id == request_id)
            .first()
        )
        if not req or req.to_user_id != user_id:
            raise ValueError("请求不存在")
        req.status = "accepted"
        req.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        return req

    def get_friends(self, user_id: int) -> List[dict]:
        sent = (
            self.db.query(ImFriendRequest)
            .filter(
                ImFriendRequest.from_user_id == user_id,
                ImFriendRequest.status == "accepted",
            )
            .all()
        )
        received = (
            self.db.query(ImFriendRequest)
            .filter(
                ImFriendRequest.to_user_id == user_id,
                ImFriendRequest.status == "accepted",
            )
            .all()
        )
        friend_ids = set()
        for r in sent:
            friend_ids.add(r.to_user_id)
        for r in received:
            friend_ids.add(r.from_user_id)

        friends = (
            self.db.query(User).filter(User.id.in_(friend_ids)).all()
            if friend_ids
            else []
        )
        return [
            {
                "id": u.id,
                "username": u.username,
                "avatar_url": u.avatar_url,
            }
            for u in friends
        ]

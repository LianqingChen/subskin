"""WebSocket 实时消息"""

import json
import logging
from typing import Dict

from fastapi import WebSocket, WebSocketDisconnect

from web.backend.services.auth import verify_token_ws

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self.active: Dict[int, WebSocket] = {}

    async def connect(self, user_id: int, ws: WebSocket):
        await ws.accept()
        self.active[user_id] = ws
        logger.info(f"WS connected: user {user_id}, total {len(self.active)}")

    async def disconnect(self, user_id: int):
        if user_id in self.active:
            del self.active[user_id]
            logger.info(f"WS disconnected: user {user_id}")

    async def send_to_user(self, user_id: int, event: dict):
        if user_id in self.active:
            try:
                await self.active[user_id].send_json(event)
            except Exception:
                await self.disconnect(user_id)

    async def broadcast_unread_count(self, user_id: int, count: int):
        await self.send_to_user(
            user_id,
            {"type": "unread_update", "data": {"total_unread": count}},
        )


manager = ConnectionManager()


async def chat_websocket_endpoint(websocket: WebSocket, token: str):
    user = verify_token_ws(token)
    if not user:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await manager.connect(user.id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            event = json.loads(data)
            if event.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
            elif event.get("type") == "read":
                from web.backend.database.database import SessionLocal
                from web.backend.database.models import (
                    ImMessage,
                    ImMessageRead,
                    ImConversationMember,
                )
                from datetime import datetime, timezone

                db = SessionLocal()
                try:
                    for mid in event.get("message_ids", []):
                        # Verify the user is a member of the message's
                        # conversation before recording a read receipt.
                        msg = db.query(ImMessage).filter(ImMessage.id == mid).first()
                        if msg is None:
                            continue
                        is_member = (
                            db.query(ImConversationMember)
                            .filter(
                                ImConversationMember.conversation_id == msg.conversation_id,
                                ImConversationMember.user_id == user.id,
                            )
                            .first()
                        )
                        if not is_member:
                            continue
                        existing = (
                            db.query(ImMessageRead)
                            .filter(
                                ImMessageRead.message_id == mid,
                                ImMessageRead.user_id == user.id,
                            )
                            .first()
                        )
                        if not existing:
                            db.add(
                                ImMessageRead(
                                    message_id=mid,
                                    user_id=user.id,
                                    read_at=datetime.now(timezone.utc),
                                )
                            )
                    db.commit()
                except Exception as e:
                    logger.error(f"WS read error: {e}")
                finally:
                    db.close()
    except WebSocketDisconnect:
        await manager.disconnect(user.id)
    except Exception as e:
        logger.error(f"WS error: {e}")
        await manager.disconnect(user.id)

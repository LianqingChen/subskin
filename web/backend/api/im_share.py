"""IM 帖子分享 API"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from web.backend.database.database import get_db
from web.backend.database.models import Post, User
from web.backend.services.auth import auth
from web.backend.services.audit import AuditLogService
from web.backend.services.im_service import ImService

router = APIRouter(prefix="/api/im/share", tags=["IM分享"])


class SharePostRequest(BaseModel):
    post_id: int
    conversation_id: int


@router.post("/post")
async def share_post(
    req: SharePostRequest,
    current_user: User = Depends(auth),
    db: Session = Depends(get_db),
):
    post = db.query(Post).filter(Post.id == req.post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")

    service = ImService(db)
    try:
        msg = service.send_message(
            conversation_id=req.conversation_id,
            sender_id=current_user.id,
            msg_type="share_post",
            metadata={
                "post_id": post.id,
                "title": post.title,
                "thumbnail": post.cover_image_url if hasattr(post, 'cover_image_url') else None,
            },
        )
        try:
            AuditLogService.log(
                db=db,
                action="community.share_post",
                actor_id=current_user.id,
                target_type="post",
                target_id=post.id,
                details={"conversation_id": req.conversation_id},
                revokeable=True,
            )
        except Exception:
            pass
        return service._serialize_message(msg)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

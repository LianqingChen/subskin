"""
评论管理 API（管理员）
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from web.backend.database.database import get_db
from web.backend.database.models import User, Comment as DBComment
from web.backend.models.comment import Comment
from web.backend.services.comment import get_pending_comments, approve_comment
from web.backend.services.auth import auth

router = APIRouter()


@router.get("/pending", response_model=List[Comment])
def list_pending(
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(auth),
):
    """获取待审核评论列表，仅管理员可访问"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限"
        )
    db_comments = get_pending_comments(db, skip, limit)
    result = []
    for c in db_comments:
        result.append(
            Comment(
                id=c.id,
                content=c.content,
                page_path=c.page_path,
                user_id=c.user_id,
                username=c.author.username if c.author else "匿名",
                created_at=c.created_at,
                approved=c.approved,
            )
        )
    return result


@router.post("/{comment_id}/approve")
def approve(
    comment_id: int,
    approved: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(auth),
):
    """批准/拒绝评论，仅管理员"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限"
        )
    comment = approve_comment(db, comment_id, approved)
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="评论不存在")
    return {"status": "ok", "approved": approved}

"""
评论服务
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from datetime import datetime

from web.backend.database.models import Comment as DBComment
from web.backend.database.models import User
from web.backend.models.comment import Comment, CommentCreate


def get_comments_by_page(db: Session, page_path: str) -> List[Comment]:
    """获取页面所有已批准评论"""
    db_comments = (
        db.query(DBComment)
        .filter(DBComment.page_path == page_path)
        .filter(DBComment.approved == True)
        .order_by(DBComment.created_at.desc())
        .all()
    )

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


def create_comment(db: Session, comment: CommentCreate, current_user: User) -> Comment:
    """创建新评论（需要审核）"""
    db_comment = DBComment(
        content=comment.content,
        page_path=comment.page_path,
        user_id=current_user.id,
        approved=False,  # 默认需要审核
    )
    db.add(db_comment)
    db.commit()
    db.refresh(db_comment)

    return Comment(
        id=db_comment.id,
        content=db_comment.content,
        page_path=db_comment.page_path,
        user_id=db_comment.user_id,
        username=current_user.username,
        created_at=db_comment.created_at,
        approved=db_comment.approved,
    )


def get_pending_comments(db: Session, skip: int = 0, limit: int = 20):
    """获取待审核评论（管理员）"""
    return (
        db.query(DBComment)
        .filter(DBComment.approved == False)
        .order_by(DBComment.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def approve_comment(db: Session, comment_id: int, approved: Optional[bool] = True):
    """审核通过/拒绝评论"""
    comment = db.query(DBComment).filter(DBComment.id == comment_id).first()
    if comment:
        comment.approved = approved
        db.commit()
        db.refresh(comment)
    return comment

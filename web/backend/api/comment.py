"""
评论相关 API
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException

from database.database import get_db
from sqlalchemy.orm import Session
from models.comment import Comment, CommentCreate
from services.comment import get_comments_by_page, create_comment
from services.auth import auth
from database.models import User

router = APIRouter()


@router.get("/{page_path}", response_model=List[Comment])
def list_comments(page_path: str, db: Session = Depends(get_db)):
    """获取页面已批准评论列表"""
    return get_comments_by_page(db, page_path)


@router.post("/", response_model=Comment)
def add_comment(
    comment: CommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(auth)
):
    """添加新评论，需要登录，新评论需要审核"""
    return create_comment(db, comment, current_user)

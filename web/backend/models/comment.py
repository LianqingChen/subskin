"""
评论数据模型
"""

from pydantic import BaseModel
from datetime import datetime


class CommentBase(BaseModel):
    content: str
    page_path: str


class CommentCreate(CommentBase):
    pass


class Comment(CommentBase):
    id: int
    user_id: int
    username: str
    created_at: datetime
    approved: bool

    class Config:
        from_attributes = True

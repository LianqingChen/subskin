"""
小白百科数据库模型 — 用户协作 + 修订历史 + 评论 + 投票

将此代码追加到 web/backend/database/models.py 末尾
"""

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship

from .database import Base


def _utcnow():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)


class EncyclopediaArticle(Base):
    """百科文章主表"""
    
    __tablename__ = "encyclopedia_articles"
    __table_args__ = (
        Index("idx_enc_articles_category", "category"),
        Index("idx_enc_articles_published", "is_published"),
    )

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String(255), unique=True, nullable=False, index=True)  # URL 路径
    title = Column(String(255), nullable=False)
    category = Column(String(50), nullable=False)  # 分类
    content = Column(Text, nullable=False)  # Markdown 内容
    summary = Column(String(500), nullable=True)  # 摘要
    icon = Column(String(20), nullable=True)  # 分类图标 emoji
    order = Column(Integer, default=0)  # 排序权重
    is_published = Column(Boolean, default=True, index=True)
    view_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    revisions = relationship("EncyclopediaRevision", back_populates="article", cascade="all, delete-orphan")
    comments = relationship("EncyclopediaComment", back_populates="article", cascade="all, delete-orphan")


class EncyclopediaRevision(Base):
    """百科修订记录"""
    
    __tablename__ = "encyclopedia_revisions"
    __table_args__ = (
        Index("idx_enc_rev_article", "article_id"),
        Index("idx_enc_rev_status", "status"),
        Index("idx_enc_rev_user", "user_id"),
        Index("idx_enc_rev_article_status", "article_id", "status"),
    )

    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(Integer, ForeignKey("encyclopedia_articles.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # 修订内容
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)  # 修订后的 Markdown
    change_summary = Column(String(500), nullable=True)  # 修订说明
    
    # 变更类型
    change_type = Column(String(20), nullable=False, default="suggest")
    # suggest=建议修订, approved=已采纳, rejected=已拒绝, rollback=回滚
    
    # 审核状态
    status = Column(String(20), nullable=False, default="pending")
    # pending=待审核, approved=已采纳, rejected=已拒绝
    
    # 差异信息
    diff_preview = Column(Text, nullable=True)  # 简化版 diff 摘要
    
    # 审核信息
    created_at = Column(DateTime, default=_utcnow)
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    review_comment = Column(String(500), nullable=True)  # 审核意见
    
    # 投票统计
    upvotes = Column(Integer, default=0)
    downvotes = Column(Integer, default=0)
    
    article = relationship("EncyclopediaArticle", back_populates="revisions", foreign_keys=[article_id])
    author = relationship("User", foreign_keys=[user_id])
    reviewer = relationship("User", foreign_keys=[reviewed_by])
    votes = relationship("EncyclopediaVote", back_populates="revision", cascade="all, delete-orphan")


class EncyclopediaComment(Base):
    """百科评论/讨论"""
    
    __tablename__ = "encyclopedia_comments"
    __table_args__ = (
        Index("idx_enc_comment_article", "article_id"),
        Index("idx_enc_comment_parent", "parent_id"),
        Index("idx_enc_comment_user", "user_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(Integer, ForeignKey("encyclopedia_articles.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    parent_id = Column(Integer, ForeignKey("encyclopedia_comments.id"), nullable=True)  # 回复父评论
    content = Column(Text, nullable=False)
    is_approved = Column(Boolean, default=False)  # 需要审核
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    article = relationship("EncyclopediaComment", back_populates="comments", remote_side=[id])
    author = relationship("User", foreign_keys=[user_id])
    replies = relationship("EncyclopediaComment", back_populates="parent_comment", remote_side=[parent_id])
    parent_comment = relationship("EncyclopediaComment", back_populates="replies", remote_side=[id])


class EncyclopediaVote(Base):
    """修订投票/评估"""
    
    __tablename__ = "encyclopedia_votes"
    __table_args__ = (
        UniqueConstraint("revision_id", "user_id", name="uq_enc_vote_revision_user"),
        Index("idx_enc_vote_revision", "revision_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    revision_id = Column(Integer, ForeignKey("encyclopedia_revisions.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    vote_type = Column(String(10), nullable=False)  # up / down
    comment = Column(String(500), nullable=True)  # 简短评价
    created_at = Column(DateTime, default=_utcnow)

    revision = relationship("EncyclopediaRevision", back_populates="votes")
    voter = relationship("User", foreign_keys=[user_id])

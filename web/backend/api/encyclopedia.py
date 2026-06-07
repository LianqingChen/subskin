"""小白百科 API 路由。

提供百科文章查询、修订提交、审核、投票、评论等功能。
"""

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from web.backend.database.database import get_db
from web.backend.database.models import (
    EncyclopediaArticle,
    EncyclopediaRevision,
    EncyclopediaComment,
    EncyclopediaVote,
    User,
)
from web.backend.services.unified_auth import get_current_user


router = APIRouter(prefix="/api/encyclopedia", tags=["小白百科"])


# ── Pydantic Schemas ──

class ArticleSummary(BaseModel):
    id: int
    slug: str
    title: str
    category: str
    icon: Optional[str]
    summary: Optional[str]
    view_count: int
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class ArticleDetail(BaseModel):
    id: int
    slug: str
    title: str
    category: str
    icon: Optional[str]
    content: str
    summary: Optional[str]
    view_count: int
    updated_at: Optional[datetime]
    revision_count: int = 0

    class Config:
        from_attributes = True


class CategoryTreeItem(BaseModel):
    category: str
    icon: str
    articles: List[ArticleSummary]


class RevisionSubmit(BaseModel):
    title: str
    content: str = Field(..., min_length=10)
    change_summary: str = Field(..., min_length=5, max_length=500)


class RevisionResponse(BaseModel):
    id: int
    article_id: int
    user_id: int
    title: str
    content: str
    change_summary: Optional[str]
    change_type: str
    status: str
    diff_preview: Optional[str]
    created_at: datetime
    upvotes: int
    downvotes: int

    class Config:
        from_attributes = True


class ReviewAction(BaseModel):
    action: str = Field(..., pattern="^(approve|reject)$")
    comment: Optional[str] = Field(None, max_length=500)


class VoteRequest(BaseModel):
    vote_type: str = Field(..., pattern="^(up|down)$")
    comment: Optional[str] = Field(None, max_length=500)


class CommentCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)
    parent_id: Optional[int] = None


class CommentResponse(BaseModel):
    id: int
    article_id: int
    user_id: int
    parent_id: Optional[int]
    content: str
    username: Optional[str]
    is_approved: bool
    created_at: datetime
    replies: List["CommentResponse"] = []

    class Config:
        from_attributes = True


CommentResponse.model_rebuild()


# ── Helper Functions ──

def _get_article_or_404(db: Session, slug: str) -> EncyclopediaArticle:
    article = db.query(EncyclopediaArticle).filter(
        EncyclopediaArticle.slug == slug,
        EncyclopediaArticle.is_published == True,
    ).first()
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")
    return article


def _build_diff_preview(old_content: str, new_content: str, max_lines: int = 10) -> str:
    """生成简化的 diff 预览。"""
    old_lines = old_content.split("\n")
    new_lines = new_content.split("\n")

    changes = []
    max_len = max(len(old_lines), len(new_lines))

    for i in range(max_len):
        old_line = old_lines[i] if i < len(old_lines) else ""
        new_line = new_lines[i] if i < len(new_lines) else ""

        if old_line != new_line:
            if old_line:
                changes.append(f"- {old_line}")
            if new_line:
                changes.append(f"+ {new_line}")

        if len(changes) >= max_lines * 2:
            changes.append("... (更多变更)")
            break

    return "\n".join(changes) if changes else "无内容变更"


# ── Article Endpoints ──

@router.get("/articles", response_model=List[CategoryTreeItem])
def list_articles(db: Session = Depends(get_db)):
    """获取百科文章分类树。"""
    articles = (
        db.query(EncyclopediaArticle)
        .filter(EncyclopediaArticle.is_published == True)
        .order_by(EncyclopediaArticle.category, EncyclopediaArticle.order, EncyclopediaArticle.title)
        .all()
    )

    category_map = {}
    for article in articles:
        if article.category not in category_map:
            category_map[article.category] = {
                "category": article.category,
                "icon": article.icon or "ri-file-text-line",
                "articles": [],
            }
        category_map[article.category]["articles"].append(ArticleSummary(
            id=article.id,
            slug=article.slug,
            title=article.title,
            category=article.category,
            icon=article.icon,
            summary=article.summary,
            view_count=article.view_count,
            updated_at=article.updated_at,
        ))

    return list(category_map.values())


@router.get("/articles/{slug:path}", response_model=ArticleDetail)
def get_article(slug: str, db: Session = Depends(get_db)):
    """获取百科文章详情。"""
    article = _get_article_or_404(db, slug)

    # 增加浏览次数
    article.view_count += 1
    db.commit()

    revision_count = db.query(EncyclopediaRevision).filter(
        EncyclopediaRevision.article_id == article.id,
        EncyclopediaRevision.status == "approved",
    ).count()

    return ArticleDetail(
        id=article.id,
        slug=article.slug,
        title=article.title,
        category=article.category,
        icon=article.icon,
        content=article.content,
        summary=article.summary,
        view_count=article.view_count,
        updated_at=article.updated_at,
        revision_count=revision_count,
    )


# ── Revision Endpoints ──

@router.post("/articles/{slug:path}/revision", response_model=RevisionResponse)
def submit_revision(
    slug: str,
    body: RevisionSubmit,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """提交百科修订建议。"""
    article = _get_article_or_404(db, slug)

    diff_preview = _build_diff_preview(article.content, body.content)

    revision = EncyclopediaRevision(
        article_id=article.id,
        user_id=current_user.id,
        title=body.title,
        content=body.content,
        change_summary=body.change_summary,
        change_type="suggest",
        status="pending",
        diff_preview=diff_preview,
    )

    db.add(revision)
    db.commit()
    db.refresh(revision)

    return RevisionResponse(
        id=revision.id,
        article_id=revision.article_id,
        user_id=revision.user_id,
        title=revision.title,
        content=revision.content,
        change_summary=revision.change_summary,
        change_type=revision.change_type,
        status=revision.status,
        diff_preview=revision.diff_preview,
        created_at=revision.created_at,
        upvotes=revision.upvotes,
        downvotes=revision.downvotes,
    )


@router.get("/articles/{slug:path}/revisions", response_model=List[RevisionResponse])
def list_revisions(
    slug: str,
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """获取百科文章修订历史。"""
    article = _get_article_or_404(db, slug)

    query = db.query(EncyclopediaRevision).filter(
        EncyclopediaRevision.article_id == article.id
    )

    if status:
        query = query.filter(EncyclopediaRevision.status == status)

    revisions = query.order_by(EncyclopediaRevision.created_at.desc()).all()

    return [
        RevisionResponse(
            id=r.id,
            article_id=r.article_id,
            user_id=r.user_id,
            title=r.title,
            content=r.content,
            change_summary=r.change_summary,
            change_type=r.change_type,
            status=r.status,
            diff_preview=r.diff_preview,
            created_at=r.created_at,
            upvotes=r.upvotes,
            downvotes=r.downvotes,
        )
        for r in revisions
    ]


@router.post("/revisions/{revision_id}/review")
def review_revision(
    revision_id: int,
    body: ReviewAction,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """审核员审核修订（需要管理员权限）。"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    revision = db.query(EncyclopediaRevision).filter(
        EncyclopediaRevision.id == revision_id
    ).first()

    if not revision:
        raise HTTPException(status_code=404, detail="修订记录不存在")

    if revision.status != "pending":
        raise HTTPException(status_code=400, detail="该修订已被处理")

    now = datetime.now(timezone.utc)

    if body.action == "approve":
        revision.status = "approved"
        revision.change_type = "approved"

        # 更新文章内容
        article = db.query(EncyclopediaArticle).filter(
            EncyclopediaArticle.id == revision.article_id
        ).first()
        if article:
            article.content = revision.content
            article.title = revision.title
            article.updated_at = now

    elif body.action == "reject":
        revision.status = "rejected"
        revision.change_type = "rejected"

    revision.reviewed_at = now
    revision.reviewed_by = current_user.id
    revision.review_comment = body.comment

    db.commit()

    return {
        "status": "ok",
        "action": body.action,
        "revision_id": revision_id,
    }


@router.post("/revisions/{revision_id}/rollback")
def rollback_revision(
    revision_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """回滚到指定修订版本（需要管理员权限）。"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    revision = db.query(EncyclopediaRevision).filter(
        EncyclopediaRevision.id == revision_id
    ).first()

    if not revision:
        raise HTTPException(status_code=404, detail="修订记录不存在")

    # 创建回滚记录
    rollback_revision = EncyclopediaRevision(
        article_id=revision.article_id,
        user_id=current_user.id,
        title=revision.title,
        content=revision.content,
        change_summary=f"回滚到修订 #{revision_id} ({revision.change_summary or ''})",
        change_type="rollback",
        status="approved",
        diff_preview="回滚操作",
    )

    # 更新文章内容
    article = db.query(EncyclopediaArticle).filter(
        EncyclopediaArticle.id == revision.article_id
    ).first()
    if article:
        article.content = revision.content
        article.title = revision.title

    db.add(rollback_revision)
    db.commit()

    return {"status": "ok", "action": "rollback", "revision_id": revision_id}


# ── Vote Endpoints ──

@router.post("/revisions/{revision_id}/vote")
def vote_revision(
    revision_id: int,
    body: VoteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """对修订进行投票评估。"""
    revision = db.query(EncyclopediaRevision).filter(
        EncyclopediaRevision.id == revision_id
    ).first()

    if not revision:
        raise HTTPException(status_code=404, detail="修订记录不存在")

    # 检查是否已投票
    existing_vote = db.query(EncyclopediaVote).filter(
        EncyclopediaVote.revision_id == revision_id,
        EncyclopediaVote.user_id == current_user.id,
    ).first()

    if existing_vote:
        if existing_vote.vote_type == body.vote_type:
            # 取消投票
            if body.vote_type == "up":
                revision.upvotes = max(0, revision.upvotes - 1)
            else:
                revision.downvotes = max(0, revision.downvotes - 1)
            db.delete(existing_vote)
        else:
            # 切换投票
            if body.vote_type == "up":
                revision.upvotes += 1
                revision.downvotes = max(0, revision.downvotes - 1)
            else:
                revision.downvotes += 1
                revision.upvotes = max(0, revision.upvotes - 1)
            existing_vote.vote_type = body.vote_type
            existing_vote.comment = body.comment
    else:
        # 新投票
        vote = EncyclopediaVote(
            revision_id=revision_id,
            user_id=current_user.id,
            vote_type=body.vote_type,
            comment=body.comment,
        )
        db.add(vote)

        if body.vote_type == "up":
            revision.upvotes += 1
        else:
            revision.downvotes += 1

    db.commit()

    return {
        "status": "ok",
        "upvotes": revision.upvotes,
        "downvotes": revision.downvotes,
    }


# ── Comment Endpoints ──

@router.get("/articles/{slug:path}/comments")
def get_comments(
    slug: str,
    db: Session = Depends(get_db),
):
    """获取百科文章评论列表。"""
    article = _get_article_or_404(db, slug)

    # 获取顶级评论
    top_comments = (
        db.query(EncyclopediaComment)
        .filter(
            EncyclopediaComment.article_id == article.id,
            EncyclopediaComment.parent_id == None,
            EncyclopediaComment.is_approved == True,
        )
        .order_by(EncyclopediaComment.created_at.desc())
        .all()
    )

    def build_comment_tree(comment: EncyclopediaComment) -> dict:
        replies = (
            db.query(EncyclopediaComment)
            .filter(
                EncyclopediaComment.parent_id == comment.id,
                EncyclopediaComment.is_approved == True,
            )
            .order_by(EncyclopediaComment.created_at.asc())
            .all()
        )

        return {
            "id": comment.id,
            "article_id": comment.article_id,
            "user_id": comment.user_id,
            "parent_id": comment.parent_id,
            "content": comment.content,
            "username": comment.author.username if comment.author else "匿名用户",
            "is_approved": comment.is_approved,
            "created_at": comment.created_at,
            "replies": [build_comment_tree(r) for r in replies],
        }

    return [build_comment_tree(c) for c in top_comments]


@router.post("/articles/{slug:path}/comments")
def create_comment(
    slug: str,
    body: CommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """发表百科评论。"""
    article = _get_article_or_404(db, slug)

    # 如果有 parent_id，验证父评论存在
    if body.parent_id:
        parent = db.query(EncyclopediaComment).filter(
            EncyclopediaComment.id == body.parent_id,
            EncyclopediaComment.article_id == article.id,
        ).first()
        if not parent:
            raise HTTPException(status_code=404, detail="父评论不存在")

    comment = EncyclopediaComment(
        article_id=article.id,
        user_id=current_user.id,
        parent_id=body.parent_id,
        content=body.content,
        is_approved=False,  # 需要审核
    )

    db.add(comment)
    db.commit()
    db.refresh(comment)

    return {
        "status": "ok",
        "message": "评论已提交，等待审核",
        "comment_id": comment.id,
    }

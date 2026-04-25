# pyright: reportArgumentType=false, reportGeneralTypeIssues=false, reportUndefinedVariable=false

import json
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, status
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from web.backend.database.database import get_db
from web.backend.database.models import User, Tag, PostTag, PostAudio, PostAttachment
from web.backend.services.auth import auth, get_current_user, get_current_user_optional
from web.backend.services.community import CommunityService
from web.backend.services.recommendation import RecommendationService
from web.backend.services.audit import AuditLogService

logger = logging.getLogger(__name__)
from web.backend.models.community import (
    Post as PostModel,
    PostCreate,
    PostUpdate,
    PostListResponse,
    PostComment as PostCommentModel,
    PostCommentCreate,
    PostCommentAuthor,
    PostCommentListResponse,
    Category as CategoryModel,
    PostAuthor,
    PostImage as PostImageModel,
    PostAudio as PostAudioModel,
    PostAttachment as PostAttachmentModel,
    Tag as TagModel,
    LikeResponse,
    ImageUploadResponse,
    AudioUploadResponse,
    FileUploadResponse,
    CollectionCreate,
    CollectionUpdate,
    CollectionItemAdd,
    CollectionResponse,
    CollectionItemResponse,
    CollectionItemListResponse,
    CollectionListResponse,
    BookmarkResponse,
    PostVersionResponse,
    PostVersionListResponse,
)
from web.backend.database.models import (
    Bookmark,
    PostImage as PostImageORM,
    CommunityCategory as CategoryORM,
    PostComment,
    Post as PostORM,
)


router = APIRouter()

EXAGGERATED_WORDS = [
    "根治", "治愈", "包治", "断根", "永不复发", "100%治愈", "百治百愈",
    "偏方根治", "祖传秘方", "特效药", "包好", "药到病除", "一劳永逸",
    "彻底治愈", "永不扩散", "保证治好",
]


def check_exaggerated_claims(title: str, content: str) -> list[str]:
    import re
    text = (title + " " + re.sub(r"<[^>]+>", "", content)).lower()
    found = [w for w in EXAGGERATED_WORDS if w in text]
    return found


@router.post("/check-claims")
async def check_claims(
    body: dict,
):
    title = body.get("title", "")
    content = body.get("content", "")
    found = check_exaggerated_claims(title, content)
    return {"has_claims": len(found) > 0, "words": found}


# ── Tag Management ──


@router.put("/posts/{post_id}/tags", response_model=PostModel)
async def update_post_tags(
    post_id: int,
    body: dict,
    request: Request,
    current_user: User = Depends(auth),
    db: Session = Depends(get_db),
):
    tag_names = body.get("tag_names", [])
    service = CommunityService(db)
    try:
        post = service.update_post_tags(
            post_id=post_id, user_id=current_user.id, tag_names=tag_names
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return _post_to_model(post, current_user.id, db)


@router.get("/tags/hot", response_model=List[TagModel])
async def get_hot_tags(limit: int = 20, db: Session = Depends(get_db)):
    service = CommunityService(db)
    tags = service.get_hot_tags(limit=limit)
    return [TagModel(id=t.id, name=t.name, usage_count=t.usage_count) for t in tags]


# ── Interaction Logging ──


@router.post("/posts/{post_id}/interact")
async def log_interaction(
    post_id: int,
    body: dict,
    current_user: User = Depends(auth),
    db: Session = Depends(get_db),
):
    action_type = body.get("action_type", "click")
    rec_svc = RecommendationService(db)
    rec_svc.log_interaction(
        user_id=current_user.id, post_id=post_id, action_type=action_type
    )
    return {"status": "ok"}


@router.post("/posts", response_model=PostModel)
async def create_post(
    post_data: PostCreate,
    request: Request,
    current_user: User = Depends(auth),
    db: Session = Depends(get_db),
):
    service = CommunityService(db)
    exaggerated = check_exaggerated_claims(post_data.title, post_data.content)
    if exaggerated:
        logger.warning(
            "User %s used exaggerated claims: %s in post '%s'",
            current_user.id, exaggerated, post_data.title[:50],
        )
    post = service.create_post(
        user_id=current_user.id,
        title=post_data.title,
        content=post_data.content,
        category_id=post_data.category_id,
        content_json=post_data.content_json,
        image_urls=post_data.images,
        tag_names=post_data.tag_names,
        is_private=post_data.is_private,
        diary_date=post_data.diary_date,
        mood=post_data.mood,
        is_anonymous=post_data.is_anonymous,
        post_type=post_data.post_type,
        video_url=post_data.video_url,
        video_thumbnail=post_data.video_thumbnail,
        city=post_data.city,
    )
    # Audit: user published a post
    try:
        AuditLogService(db).create_log(
            user_id=current_user.id,
            action="publish",
            target_type="post",
            target_id=post.id,
            scope="private" if post.is_private else "public",
            detail=json.dumps({"title": post_data.title[:100]}, ensure_ascii=False),
            ip_address=request.client.host if request.client else None,
        )
    except Exception:
        logger.warning("Audit log failed for post creation %s", post.id, exc_info=True)
    return _post_to_model(post, current_user.id, db)


@router.get("/posts", response_model=PostListResponse)
async def list_posts(
    category_id: Optional[int] = None,
    tag: Optional[str] = None,
    post_type: Optional[str] = None,
    feed_type: Optional[str] = None,
    city: Optional[str] = None,
    is_private: Optional[bool] = None,
    limit: int = 20,
    offset: int = 0,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    user_id = current_user.id if current_user else None
    if is_private is True and user_id is None:
        raise HTTPException(status_code=401, detail="请先登录后查看私密帖子")

    if feed_type and feed_type in ("recommend", "hot", "following", "local"):
        rec_svc = RecommendationService(db)
        total, posts = rec_svc.get_feed(
            user_id=user_id,
            page=offset // max(limit, 1),
            page_size=limit,
            feed_type=feed_type,
            city=city,
        )
    else:
        service = CommunityService(db)
        total, posts = service.get_posts(
            category_id=category_id,
            tag_name=tag,
            post_type=post_type,
            feed_type=feed_type,
            limit=limit,
            offset=offset,
            user_id=user_id,
            is_private=is_private,
        )
    items = [_post_to_model(post, user_id, db) for post in posts]
    return PostListResponse(total=total, items=items)


@router.get("/my-diaries", response_model=PostListResponse)
async def get_my_diaries(
    limit: int = 20,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    diary_category = (
        db.query(CategoryORM).filter(CategoryORM.name == "白白日记").first()
    )
    if not diary_category:
        return PostListResponse(total=0, items=[])

    query = (
        db.query(PostORM)
        .filter(
            PostORM.user_id == current_user.id,
            PostORM.category_id == diary_category.id,
        )
        .order_by(desc(PostORM.diary_date), desc(PostORM.created_at))
    )
    total = query.count()
    posts = query.offset(offset).limit(min(limit, 50)).all()
    items = [_post_to_model(post, current_user.id, db) for post in posts]
    return PostListResponse(total=total, items=items)


@router.get("/posts/{post_id}", response_model=PostModel)
async def get_post(
    post_id: int,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    service = CommunityService(db)
    user_id = current_user.id if current_user else None
    post = service.get_post_by_id(post_id, user_id=user_id)
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")
    return _post_to_model(post, user_id, db)


@router.put("/posts/{post_id}", response_model=PostModel)
async def update_post(
    post_id: int,
    post_data: PostUpdate,
    request: Request,
    current_user: User = Depends(auth),
    db: Session = Depends(get_db),
):
    service = CommunityService(db)
    try:
        post = service.update_post(
            post_id=post_id,
            user_id=current_user.id,
            title=post_data.title,
            content=post_data.content,
            category_id=post_data.category_id,
            content_json=post_data.content_json,
            tag_names=post_data.tag_names,
            is_private=post_data.is_private,
            diary_date=post_data.diary_date,
            mood=post_data.mood,
            is_anonymous=post_data.is_anonymous,
            post_type=post_data.post_type,
            video_url=post_data.video_url,
            video_thumbnail=post_data.video_thumbnail,
            city=post_data.city,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    try:
        AuditLogService(db).create_log(
            user_id=current_user.id,
            action="publish",
            target_type="post",
            target_id=post_id,
            scope="private" if post.is_private else "public",
            detail=json.dumps({"action": "update"}, ensure_ascii=False),
            ip_address=request.client.host if request.client else None,
        )
    except Exception:
        logger.warning("Audit log failed for post update %s", post_id, exc_info=True)
    return _post_to_model(post, current_user.id, db)


@router.delete("/posts/{post_id}")
async def delete_post(
    post_id: int,
    request: Request,
    current_user: User = Depends(auth),
    db: Session = Depends(get_db),
):
    service = CommunityService(db)
    try:
        success = service.delete_post(post_id=post_id, user_id=current_user.id)
    except Exception as e:
        logger.error("删除帖子失败 post_id=%s: %s", post_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"删除帖子失败，请稍后重试")
    if not success:
        raise HTTPException(status_code=404, detail="帖子不存在或无权删除")
    try:
        AuditLogService(db).create_log(
            user_id=current_user.id,
            action="delete",
            target_type="post",
            target_id=post_id,
            scope="private",
            revokeable=False,
            ip_address=request.client.host if request.client else None,
        )
    except Exception:
        logger.warning("Audit log failed for post deletion %s", post_id, exc_info=True)
    return {"status": "ok"}


@router.post("/posts/{post_id}/like", response_model=LikeResponse)
async def toggle_like(
    post_id: int,
    current_user: User = Depends(auth),
    db: Session = Depends(get_db),
):
    service = CommunityService(db)
    try:
        liked, like_count = service.toggle_like(
            post_id=post_id, user_id=current_user.id
        )
        return LikeResponse(liked=liked, like_count=like_count)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/posts/{post_id}/comments", response_model=PostCommentModel)
async def add_comment(
    post_id: int,
    comment_data: PostCommentCreate,
    request: Request,
    current_user: User = Depends(auth),
    db: Session = Depends(get_db),
):
    service = CommunityService(db)
    try:
        comment = service.add_comment(
            post_id=post_id,
            user_id=current_user.id,
            content=comment_data.content,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    try:
        AuditLogService(db).create_log(
            user_id=current_user.id,
            action="publish",
            target_type="comment",
            target_id=comment.id,
            scope="public",
            detail=json.dumps({"post_id": post_id}, ensure_ascii=False),
            ip_address=request.client.host if request.client else None,
        )
    except Exception:
        logger.warning("Audit log failed for comment creation", exc_info=True)
    return _comment_to_model(comment)


@router.get("/posts/{post_id}/comments", response_model=PostCommentListResponse)
async def list_comments(
    post_id: int,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    service = CommunityService(db)
    total, comments = service.get_post_comments(
        post_id=post_id, limit=limit, offset=offset
    )
    items = [_comment_to_model(comment) for comment in comments]
    return PostCommentListResponse(total=total, items=items)


@router.get("/categories", response_model=List[CategoryModel])
async def list_categories(db: Session = Depends(get_db)):
    service = CommunityService(db)
    categories = service.get_categories()
    return [_category_to_model(category, db) for category in categories]


@router.get("/tags", response_model=List[TagModel])
async def list_tags(
    q: Optional[str] = None,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    query = db.query(Tag)
    if q:
        query = query.filter(Tag.name.ilike(f"%{q}%"))
    tags = query.order_by(Tag.usage_count.desc()).limit(limit).all()
    return [TagModel(id=t.id, name=t.name, usage_count=t.usage_count) for t in tags]


@router.post("/upload", response_model=ImageUploadResponse)
async def upload_image(
    image: UploadFile = File(...),
    current_user: User = Depends(auth),
    db: Session = Depends(get_db),
):
    service = CommunityService(db)
    try:
        content = await image.read()
        image_url = service.upload_image(
            user_id=current_user.id,
            filename=image.filename or "upload.jpg",
            content=content,
        )
        return ImageUploadResponse(image_url=image_url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")


@router.post("/upload/audio", response_model=AudioUploadResponse)
async def upload_audio(
    audio: UploadFile = File(...),
    current_user: User = Depends(auth),
    db: Session = Depends(get_db),
):
    service = CommunityService(db)
    try:
        content = await audio.read()
        result = service.upload_file(
            user_id=current_user.id,
            filename=audio.filename or "audio.wav",
            content=content,
            subdir="audio",
        )
        return AudioUploadResponse(
            audio_url=result["url"],
            duration=0,
            file_size=len(content),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")


@router.post("/upload/file", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(auth),
    db: Session = Depends(get_db),
):
    service = CommunityService(db)
    try:
        content = await file.read()
        result = service.upload_file(
            user_id=current_user.id,
            filename=file.filename or "file.bin",
            content=content,
            subdir="files",
        )
        return FileUploadResponse(
            file_url=result["url"],
            file_name=file.filename or "file.bin",
            file_size=len(content),
            file_type=file.content_type or "",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")


def _post_to_model(post, user_id: Optional[int], db: Session) -> PostModel:
    service = CommunityService(db)
    like_count = service.get_like_count(post.id)
    comment_count = service.get_comment_count(post.id)
    is_liked = service.is_liked(post.id, user_id) if user_id else False
    is_bookmarked = service.is_bookmarked(post.id, user_id) if user_id else False

    images = (
        db.query(PostImageORM)
        .filter_by(post_id=post.id)
        .order_by(PostImageORM.order)
        .all()
    )

    audios = (
        db.query(PostAudio).filter_by(post_id=post.id).order_by(PostAudio.order).all()
    )

    attachments = (
        db.query(PostAttachment)
        .filter_by(post_id=post.id)
        .order_by(PostAttachment.order)
        .all()
    )

    post_tag_records = db.query(PostTag).filter_by(post_id=post.id).all()
    tag_ids = [pt.tag_id for pt in post_tag_records]
    tags = db.query(Tag).filter(Tag.id.in_(tag_ids)).all() if tag_ids else []

    return PostModel(
        id=post.id,
        title=post.title,
        content=post.content,
        content_json=post.content_json,
        post_type=getattr(post, "post_type", None),
        video_url=getattr(post, "video_url", None),
        video_thumbnail=getattr(post, "video_thumbnail", None),
        content_preview=getattr(post, "content_preview", None),
        read_count=getattr(post, "read_count", 0),
        category_id=post.category_id,
        is_private=post.is_private,
        diary_date=post.diary_date.isoformat() if post.diary_date else None,
        mood=post.mood,
        is_anonymous=post.is_anonymous,
        city=post.city,
        author=PostAuthor(
            id=post.author.id,
            username="匿名用户" if post.is_anonymous else post.author.username,
            avatar=None if post.is_anonymous else None,
            is_doctor=getattr(post.author, "is_doctor", False),
        ),
        category=_category_to_model(post.category, db),
        images=[
            PostImageModel(id=img.id, image_url=img.image_url, order=img.order)
            for img in images
        ],
        audios=[
            PostAudioModel(
                id=a.id,
                audio_url=a.audio_url,
                duration=a.duration,
                file_size=a.file_size,
                order=a.order,
            )
            for a in audios
        ],
        attachments=[
            PostAttachmentModel(
                id=a.id,
                file_url=a.file_url,
                file_name=a.file_name,
                file_size=a.file_size,
                file_type=a.file_type,
                order=a.order,
            )
            for a in attachments
        ],
        tags=[TagModel(id=t.id, name=t.name, usage_count=t.usage_count) for t in tags],
        like_count=like_count,
        comment_count=comment_count,
        is_liked=is_liked,
        is_bookmarked=is_bookmarked,
        created_at=post.created_at,
        updated_at=post.updated_at,
    )


def _category_to_model(category, db: Session) -> CategoryModel:
    post_count = (
        db.query(func.count(PostORM.id)).filter_by(category_id=category.id).scalar()
    )
    return CategoryModel(
        id=category.id,
        name=category.name,
        description=category.description,
        icon=category.icon,
        post_count=post_count,
    )


def _comment_to_model(comment) -> PostCommentModel:
    return PostCommentModel(
        id=comment.id,
        content=comment.content,
        author=PostCommentAuthor(
            id=comment.author.id, username=comment.author.username
        ),
        post_id=comment.post_id,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
    )


# ── Collections API ──


@router.post(
    "/collections",
    response_model=CollectionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_collection(
    body: CollectionCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = CommunityService(db)
    collection = svc.create_collection(
        user_id=user.id,
        name=body.name,
        description=body.description,
        icon=body.icon,
        is_public=body.is_public,
    )
    try:
        AuditLogService(db).create_log(
            user_id=user.id,
            action="publish" if body.is_public else "export",
            target_type="collection",
            target_id=collection.id,
            scope="public" if body.is_public else "private",
            detail=json.dumps(
                {"name": body.name, "is_public": body.is_public}, ensure_ascii=False
            ),
            revokeable=True,
            ip_address=request.client.host if request.client else None,
        )
    except Exception:
        logger.warning("Audit log failed for collection creation", exc_info=True)
    item_count = (
        db.query(func.count()).filter_by(collection_id=collection.id).scalar() or 0
    )
    return CollectionResponse(
        id=collection.id,
        name=collection.name,
        description=collection.description,
        icon=collection.icon,
        is_public=collection.is_public,
        share_slug=collection.share_slug,
        item_count=item_count,
        created_at=collection.created_at,
        updated_at=collection.updated_at,
    )


@router.get("/collections", response_model=CollectionListResponse)
async def list_collections(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    svc = CommunityService(db)
    collections = svc.get_user_collections(user_id=user.id)
    items = []
    for c in collections:
        item_count = db.query(func.count()).filter_by(collection_id=c.id).scalar() or 0
        items.append(
            CollectionResponse(
                id=c.id,
                name=c.name,
                description=c.description,
                icon=c.icon,
                is_public=c.is_public,
                share_slug=c.share_slug,
                item_count=item_count,
                created_at=c.created_at,
                updated_at=c.updated_at,
            )
        )
    return CollectionListResponse(items=items)


@router.get("/collections/{collection_id}", response_model=CollectionResponse)
async def get_collection(collection_id: int, db: Session = Depends(get_db)):
    from web.backend.database.models import Collection

    collection = db.query(Collection).filter_by(id=collection_id).first()
    if not collection:
        raise HTTPException(status_code=404, detail="收藏夹不存在")
    item_count = (
        db.query(func.count()).filter_by(collection_id=collection.id).scalar() or 0
    )
    return CollectionResponse(
        id=collection.id,
        name=collection.name,
        description=collection.description,
        icon=collection.icon,
        is_public=collection.is_public,
        share_slug=collection.share_slug,
        item_count=item_count,
        created_at=collection.created_at,
        updated_at=collection.updated_at,
    )


@router.put("/collections/{collection_id}", response_model=CollectionResponse)
async def update_collection(
    collection_id: int,
    body: CollectionUpdate,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = CommunityService(db)
    kwargs = {k: v for k, v in body.dict().items() if v is not None}
    try:
        collection = svc.update_collection(
            collection_id=collection_id, user_id=user.id, **kwargs
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    if "is_public" in kwargs:
        try:
            AuditLogService(db).create_log(
                user_id=user.id,
                action="publish" if kwargs["is_public"] else "revoke",
                target_type="collection",
                target_id=collection_id,
                scope="public" if kwargs["is_public"] else "private",
                detail=json.dumps(
                    {"name": collection.name, "is_public": kwargs["is_public"]},
                    ensure_ascii=False,
                ),
                revokeable=True,
                ip_address=request.client.host if request.client else None,
            )
        except Exception:
            logger.warning("Audit log failed for collection update", exc_info=True)
    item_count = (
        db.query(func.count()).filter_by(collection_id=collection.id).scalar() or 0
    )
    return CollectionResponse(
        id=collection.id,
        name=collection.name,
        description=collection.description,
        icon=collection.icon,
        is_public=collection.is_public,
        share_slug=collection.share_slug,
        item_count=item_count,
        created_at=collection.created_at,
        updated_at=collection.updated_at,
    )


@router.delete("/collections/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_collection(
    collection_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = CommunityService(db)
    if not svc.delete_collection(collection_id=collection_id, user_id=user.id):
        raise HTTPException(status_code=404, detail="收藏夹不存在或无权删除")
    try:
        AuditLogService(db).create_log(
            user_id=user.id,
            action="delete",
            target_type="collection",
            target_id=collection_id,
            scope="private",
            revokeable=False,
            ip_address=request.client.host if request.client else None,
        )
    except Exception:
        logger.warning("Audit log failed for collection deletion", exc_info=True)


@router.post(
    "/collections/{collection_id}/items",
    response_model=CollectionItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_to_collection(
    collection_id: int,
    body: CollectionItemAdd,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = CommunityService(db)
    try:
        item = svc.add_to_collection(
            collection_id=collection_id,
            post_id=body.post_id,
            note=body.note,
            user_id=user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    post = svc.get_post_by_id(item.post_id)
    return CollectionItemResponse(
        id=item.id,
        post_id=item.post_id,
        post=_post_to_model(post, user.id, db),
        note=item.note,
        sort_order=item.sort_order,
        created_at=item.created_at,
    )


@router.delete(
    "/collections/{collection_id}/items/{post_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_from_collection(
    collection_id: int,
    post_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = CommunityService(db)
    if not svc.remove_from_collection(
        collection_id=collection_id, post_id=post_id, user_id=user.id
    ):
        raise HTTPException(status_code=404, detail="条目不存在")


@router.get(
    "/collections/{collection_id}/items", response_model=CollectionItemListResponse
)
async def list_collection_items(
    collection_id: int,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(auth),
):
    svc = CommunityService(db)
    collection = svc.get_collection_by_id(collection_id)
    if not collection or (
        collection.user_id != current_user.id and not collection.is_public
    ):
        raise HTTPException(status_code=404, detail="收藏夹不存在")

    total, items = svc.get_collection_items(
        collection_id=collection_id, limit=limit, offset=offset
    )
    result = []
    for item in items:
        post = svc.get_post_by_id(item.post_id)
        if post:
            result.append(
                CollectionItemResponse(
                    id=item.id,
                    post_id=item.post_id,
                    post=_post_to_model(post, current_user.id, db),
                    note=item.note,
                    sort_order=item.sort_order,
                    created_at=item.created_at,
                )
            )
    return {"total": total, "items": result}


@router.get("/user-stats")
async def get_user_community_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(auth),
):
    post_count = (
        db.query(func.count(PostORM.id))
        .filter(PostORM.user_id == current_user.id)
        .scalar()
        or 0
    )
    bookmark_count = (
        db.query(func.count(Bookmark.id))
        .filter(Bookmark.user_id == current_user.id)
        .scalar()
        or 0
    )
    comment_count = (
        db.query(func.count(PostComment.id))
        .filter(PostComment.user_id == current_user.id)
        .scalar()
        or 0
    )

    return {
        "post_count": post_count,
        "bookmark_count": bookmark_count,
        "comment_count": comment_count,
    }


@router.get("/collections/slug/{share_slug}", response_model=CollectionResponse)
async def get_collection_by_slug(share_slug: str, db: Session = Depends(get_db)):
    svc = CommunityService(db)
    collection = svc.get_collection_by_slug(share_slug=share_slug)
    if not collection or not collection.is_public:
        raise HTTPException(status_code=404, detail="收藏夹不存在或未公开")
    item_count = (
        db.query(func.count()).filter_by(collection_id=collection.id).scalar() or 0
    )
    return CollectionResponse(
        id=collection.id,
        name=collection.name,
        description=collection.description,
        icon=collection.icon,
        is_public=collection.is_public,
        share_slug=collection.share_slug,
        item_count=item_count,
        created_at=collection.created_at,
        updated_at=collection.updated_at,
    )


# ── Bookmarks API ──


@router.post("/posts/{post_id}/bookmark", response_model=BookmarkResponse)
async def toggle_bookmark(
    post_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    svc = CommunityService(db)
    bookmarked = svc.toggle_bookmark(post_id=post_id, user_id=user.id)
    return BookmarkResponse(bookmarked=bookmarked, post_id=post_id)


@router.get("/bookmarks", response_model=PostListResponse)
async def list_bookmarks(
    limit: int = 20,
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = CommunityService(db)
    total, posts = svc.get_user_bookmarks(user_id=user.id, limit=limit, offset=offset)
    items = [_post_to_model(p, user.id, db) for p in posts]
    return PostListResponse(total=total, items=items)


# ── Post Versions API ──


@router.get("/posts/{post_id}/versions", response_model=PostVersionListResponse)
async def get_post_versions(
    post_id: int, limit: int = 20, offset: int = 0, db: Session = Depends(get_db)
):
    svc = CommunityService(db)
    total, versions = svc.get_post_versions(post_id=post_id, limit=limit, offset=offset)
    items = []
    for v in versions:
        items.append(
            PostVersionResponse(
                id=v.id,
                post_id=v.post_id,
                editor=PostAuthor(
                    id=v.editor.id, username=v.editor.username, avatar=None
                ),
                title=v.title,
                content=v.content,
                content_json=v.content_json,
                edit_summary=v.edit_summary,
                created_at=v.created_at,
            )
        )
    return PostVersionListResponse(total=total, items=items)

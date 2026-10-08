from web.backend.utils.timeutils import iso_utc
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
from web.backend.utils.pii_detect import detect_pii, redact_pii
from web.backend.services.recommendation import RecommendationService
from web.backend.services.audit import AuditLogService
from web.backend.services.content_safety import moderate_comment
from web.backend.app.middleware.rate_limit import ReadRateLimit, limit_write_for_user
from web.backend.utils.cursor import decode_cursor, encode_cursor_from_post
from web.backend.api.notifications import create_notification

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
    ShareResponse,
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

# ─── IP 地理定位端点（同城页面快速定位） ───

import asyncio
import time as _time
import requests as _requests

_IP_LOCATION_CACHE_TTL = 3600
_ip_location_cache: dict[str, tuple[float, dict[str, object]]] = {}


def _fetch_ip_location(ip: str) -> Optional[dict]:
    """同步调用 ipwho.is（HTTPS；2026-08-30 加固，原 ip-api.com 为明文 HTTP）"""
    try:
        resp = _requests.get(
            f"https://ipwho.is/{ip}?lang=zh-CN",
            timeout=3,
        )
        if resp.ok:
            data = resp.json()
            if data.get("success") and data.get("city"):
                return {
                    "city": str(data["city"]).replace("市", ""),
                    "latitude": data.get("latitude"),
                    "longitude": data.get("longitude"),
                    "region": (data.get("region") or {}).get("code") if isinstance(data.get("region"), dict) else data.get("region"),
                }
    except Exception as e:
        logger.warning("IP定位服务调用失败: %s", str(e))
    return None


def _get_client_ip(request: Request) -> str:
    """从请求中提取客户端IP"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _is_private_ip(ip: str) -> bool:
    """判断是否为内网IP（无法通过公网定位）"""
    if ip in ("127.0.0.1", "unknown", "::1", "localhost"):
        return True
    if ip.startswith(("192.168.", "10.", "172.16.", "172.17.", "172.18.", "172.19.",
                      "172.20.", "172.21.", "172.22.", "172.23.", "172.24.", "172.25.",
                      "172.26.", "172.27.", "172.28.", "172.29.", "172.30.", "172.31.")):
        return True
    return False


@router.get("/user-location")
async def get_user_location(request: Request):
    """基于请求IP的快速城市定位（用于同城页面）"""
    ip = _get_client_ip(request)

    # 内网IP无法定位
    if _is_private_ip(ip):
        return {"city": None, "latitude": None, "longitude": None, "region": None, "source": "ip"}

    cached = _ip_location_cache.get(ip)
    if cached and (_time.time() - cached[0]) < _IP_LOCATION_CACHE_TTL:
        return cached[1]

    # 调用 ip-api.com（免费、无需密钥、支持中文、响应~50ms）
    # 注意：requests 是同步阻塞调用，必须放入线程池，否则会卡死单 worker 事件循环
    try:
        data = await asyncio.to_thread(_fetch_ip_location, ip)
    except Exception as e:
        logger.warning("IP定位服务调用失败: %s", str(e))
        data = None
    if data:
        result = {
            "city": data["city"],
            "latitude": data["latitude"],
            "longitude": data["longitude"],
            "region": data["region"],
            "source": "ip",
        }
        _ip_location_cache[ip] = (_time.time(), result)
        return result

    return {"city": None, "latitude": None, "longitude": None, "region": None, "source": "ip"}


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
    await limit_write_for_user(request, current_user.id)
    if current_user.user_status == "banned":
        raise HTTPException(status_code=403, detail="账号已被封禁，无法发布内容")
    if current_user.user_status == "muted" and current_user.muted_until:
        from datetime import datetime as _dt, timezone as _tz
        if current_user.muted_until.replace(tzinfo=_tz.utc) > _dt.now(_tz.utc):
            remaining = current_user.muted_until.replace(tzinfo=_tz.utc) - _dt.now(_tz.utc)
            hours = int(remaining.total_seconds() / 3600)
            raise HTTPException(status_code=403, detail=f"账号已被禁言，剩余{hours}小时")

    # ── 2026-08-30 隐私加固：公开帖 PII 检测 ──
    # 命中手机号/邮箱/身份证等且用户未显式确认（confirm_pii）时，自动脱敏后发布，
    # 防止隐私信息在公开 feed 中泄露；用户确认保留原文时记录审计。
    pii_hits: list = []
    if not post_data.is_private:
        pii_hits = detect_pii(f"{post_data.title}\n{post_data.content}")
        if pii_hits and not post_data.confirm_pii:
            red_title, _t = redact_pii(post_data.title)
            red_content, _c = redact_pii(post_data.content)
            post_data = post_data.model_copy(
                update={"title": red_title, "content": red_content}
            )
            logger.info(
                "Post PII auto-redacted: user=%s types=%s", current_user.id, pii_hits
            )

    service = CommunityService(db)
    exaggerated = check_exaggerated_claims(post_data.title, post_data.content)
    if exaggerated:
        logger.warning(
            "User %s used exaggerated claims: %s in post '%s'",
            current_user.id, exaggerated, post_data.title[:50],
        )
    treatment_share_json: Optional[str] = None
    if post_data.treatment_share is not None:
        treatment_data = post_data.treatment_share.model_dump()
        treatment_data = service.enrich_treatment_share(current_user.id, treatment_data)
        treatment_share_json = service.serialize_treatment_share(treatment_data)
    post = service.create_post(
        user_id=current_user.id,
        title=post_data.title,
        content=post_data.content,
        category_id=post_data.category_id,
        content_json=post_data.content_json,
        image_urls=post_data.images,
        image_metas=(
            [m.model_dump() for m in post_data.image_metas]
            if post_data.image_metas
            else None
        ),
        tag_names=post_data.tag_names,
        is_private=post_data.is_private,
        diary_date=post_data.diary_date,
        diary_type=post_data.diary_type,
        mood=post_data.mood,
        is_anonymous=False,  # Anonymous posting removed
        post_type=post_data.post_type,
        video_url=post_data.video_url,
        video_thumbnail=post_data.video_thumbnail,
        city=post_data.city,
        treatment_share_json=treatment_share_json,
    )
    # Flag post with exaggerated claims for moderation review
    if exaggerated:
        post.moderation_status = "flagged"
        db.commit()
    # Audit: user published a post
    try:
        AuditLogService(db).create_log(
            user_id=current_user.id,
            action="publish",
            target_type="post",
            target_id=post.id,
            scope="private" if post.is_private else "public",
            detail=json.dumps(
                {
                    "title": post_data.title[:100],
                    "public_ack": bool(post_data.public_ack),
                    "pii_redacted": bool(pii_hits) and not post_data.confirm_pii,
                },
                ensure_ascii=False,
            ),
            ip_address=request.client.host if request.client else None,
        )
        if pii_hits and post_data.confirm_pii:
            # 用户显式确认保留含 PII 的原文发布 — 留不可篡改审计记录
            AuditLogService(db).create_log(
                user_id=current_user.id,
                action="community.pii_confirm",
                target_type="post",
                target_id=post.id,
                scope="public",
                detail=json.dumps({"pii_types": pii_hits}, ensure_ascii=False),
                ip_address=request.client.host if request.client else None,
            )
    except Exception:
        logger.warning("Audit log failed for post creation %s", post.id, exc_info=True)

    # ── 2026-08-30 隐私加固：私密帖不外送第三方 LLM ──
    # 内容安全审核（LLM）与 AI 增强（正文提取 + 视觉模型）都会把帖子内容发往
    # 第三方模型。私密日记/帖子属于 L3 健康数据，未经单独同意不外送，
    # 仅公开帖保留审核与 AI 增强。
    if post.is_private:
        logger.info("Private post %s: skip external LLM moderation/enhancement", post.id)
    else:
        try:
            import threading
            from web.backend.services.content_safety import moderate_post
            t = threading.Thread(target=moderate_post, args=(post.id,), daemon=True)
            t.start()
        except Exception:
            logger.warning("Content moderation launch failed for post %s", post.id, exc_info=True)

        # AI 增强：异步提取正文结构化信息 + 图片轻量视觉分析
        try:
            import threading as _t
            from web.backend.services.post_ai import (
                analyze_post_images_async,
                extract_post_structure,
            )
            _t.Thread(target=extract_post_structure, args=(post.id,), daemon=True).start()
            _t.Thread(target=analyze_post_images_async, args=(post.id,), daemon=True).start()
        except Exception:
            logger.warning("Post AI enhancement launch failed for post %s", post.id, exc_info=True)

    return _post_to_model(post, current_user.id, db)


@router.get("/posts", response_model=PostListResponse)
async def list_posts(
    request: Request,
    category_id: Optional[int] = None,
    tag: Optional[str] = None,
    post_type: Optional[str] = None,
    feed_type: Optional[str] = None,
    sort: Optional[str] = None,
    city: Optional[str] = None,
    user_lat: Optional[float] = None,
    user_lng: Optional[float] = None,
    is_private: Optional[bool] = None,
    limit: int = 20,
    offset: int = 0,
    after: Optional[str] = None,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
    _rate: None = Depends(ReadRateLimit()),
):
    user_id = current_user.id if current_user else None
    if is_private is True and user_id is None:
        raise HTTPException(status_code=401, detail="请先登录后查看私密帖子")

    # 显式排序（分享页排序胶囊）：综合/最新/最多浏览/最多点赞/最多收藏/最多转发。
    # 走 CommunityService 的确定性排序；关注/同城 Tab 同样支持显式排序，
    # 排序范围限定在对应 feed 子集内（无关注对象时按全局范围排序，与推荐服务
    # 的 hot 回退一致）；未指定 sort 时保持原有 feed_type 行为。
    VALID_SORTS = ("hot", "newest", "views", "likes", "bookmarks", "shares")

    next_cursor: Optional[str] = None
    if sort in VALID_SORTS:
        service = CommunityService(db)
        scoped_feed = feed_type if feed_type in ("following", "local") else None
        total, posts, next_cursor = service.get_posts(
            category_id=category_id,
            tag_name=tag,
            post_type=post_type,
            feed_type=scoped_feed,
            sort=sort,
            city=city,
            limit=limit,
            offset=offset,
            user_id=user_id,
            is_private=is_private,
            after=after,
        )
    elif feed_type and feed_type in ("recommend", "hot", "following", "local"):
        rec_svc = RecommendationService(db)
        page = 0 if after else (offset // max(limit, 1))
        total, posts, next_cursor = rec_svc.get_feed(
            user_id=user_id,
            page=page,
            page_size=limit,
            feed_type=feed_type,
            city=city,
            user_lat=user_lat,
            user_lng=user_lng,
            after=after,
        )
    else:
        service = CommunityService(db)
        total, posts, next_cursor = service.get_posts(
            category_id=category_id,
            tag_name=tag,
            post_type=post_type,
            feed_type=feed_type,
            limit=limit,
            offset=offset,
            user_id=user_id,
            is_private=is_private,
            after=after,
        )
    # Batched conversion avoids the N+1 per-post relation queries that
    # _post_to_model triggers (8–10 queries × N posts).
    service = CommunityService(db)
    items = service.posts_to_models(posts, user_id, user_lat=user_lat, user_lng=user_lng)
    if user_id is None:
        items = [i for i in items if i.moderation_status != "blocked"]
    elif not (current_user and current_user.is_admin):
        items = [i for i in items if i.moderation_status != "blocked" or i.author.id == user_id]
    return PostListResponse(total=total, items=items, next_cursor=next_cursor)


@router.get("/my-diaries", response_model=PostListResponse)
async def get_my_diaries(
    limit: int = 20,
    offset: int = 0,
    after: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = (
        db.query(PostORM)
        .filter(PostORM.user_id == current_user.id)
    )
    # "my-diaries" should return only the user's private diary entries, not
    # every post they've made (public community posts belong in the regular
    # profile/feed listings). A diary is a private post (optionally with a
    # diary_date). Exclude blocked/soft-deleted entries.
    query = query.filter(PostORM.is_private == True)  # noqa: E712
    query = query.filter(PostORM.moderation_status != "blocked")
    if after:
        cursor = decode_cursor(after)
        if cursor:
            cursor_ts, cursor_id = cursor
            query = query.filter(
                (PostORM.created_at < cursor_ts) |
                ((PostORM.created_at == cursor_ts) & (PostORM.id < cursor_id))
            )
    query = query.order_by(desc(PostORM.is_private), desc(PostORM.diary_date), desc(PostORM.created_at))
    total = query.count()
    posts = query.limit(min(limit, 50) + 1).all()
    has_more = len(posts) > min(limit, 50)
    if has_more:
        posts = posts[:min(limit, 50)]
    next_cursor = encode_cursor_from_post(posts[-1]) if has_more and posts else None
    # Batched conversion to avoid N+1 per-post relation queries.
    service = CommunityService(db)
    items = service.posts_to_models(posts, current_user.id)
    return PostListResponse(total=total, items=items, next_cursor=next_cursor)


@router.get("/diary-calendar")
async def get_diary_calendar(
    year: int,
    month: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return diary entries for a specific month (for calendar view)."""
    from datetime import date
    import calendar as cal

    # Validate month
    if not 1 <= month <= 12:
        raise HTTPException(status_code=400, detail="月份必须在 1-12 之间")

    # Get first and last day of the month
    first_day = date(year, month, 1)
    last_day_num = cal.monthrange(year, month)[1]
    last_day = date(year, month, last_day_num)

    # Query diary entries for this month
    posts = (
        db.query(PostORM)
        .filter(
            PostORM.user_id == current_user.id,
            PostORM.is_private == True,  # noqa: E712
            PostORM.diary_date >= first_day,
            PostORM.diary_date <= last_day,
            PostORM.moderation_status != "blocked",
        )
        .order_by(PostORM.diary_date)
        .all()
    )

    # Group by date
    calendar_data = {}
    for post in posts:
        date_str = iso_utc(post.diary_date)
        if date_str not in calendar_data:
            calendar_data[date_str] = []
        calendar_data[date_str].append({
            "id": post.id,
            "title": post.title,
            "diary_type": getattr(post, "diary_type", None),
            "mood": post.mood,
        })

    return {"year": year, "month": month, "entries": calendar_data}


@router.get("/posts/{post_id}", response_model=PostModel)
async def get_post(
    request: Request,
    post_id: int,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
    _rate: None = Depends(ReadRateLimit()),
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
    # 2026-08-30 隐私加固：公开帖编辑同样过 PII 检测，未显式确认时自动脱敏
    if post_data.title is not None or post_data.content is not None:
        from web.backend.database.models import Post as _ProbePost
        _probe_row = (
            db.query(_ProbePost)
            .filter(_ProbePost.id == post_id, _ProbePost.user_id == current_user.id)
            .first()
        )
        if _probe_row is None:
            raise HTTPException(status_code=404, detail="帖子不存在")
        _current_private = bool(_probe_row.is_private)
        will_be_public = not (
            post_data.is_private if post_data.is_private is not None else _current_private
        )
        if will_be_public:
            probe = "\n".join(x for x in (post_data.title, post_data.content) if x)
            if detect_pii(probe):
                updates = {}
                if post_data.title is not None:
                    updates["title"] = redact_pii(post_data.title)[0]
                if post_data.content is not None:
                    updates["content"] = redact_pii(post_data.content)[0]
                post_data = post_data.model_copy(update=updates)
                logger.info(
                    "Post update PII auto-redacted: user=%s post=%s",
                    current_user.id, post_id,
                )
    update_treatment_json: Optional[str] = None
    if post_data.treatment_share is not None:
        treatment_data = post_data.treatment_share.model_dump()
        treatment_data = service.enrich_treatment_share(current_user.id, treatment_data)
        update_treatment_json = service.serialize_treatment_share(treatment_data) or ""
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
            diary_type=post_data.diary_type,
            mood=post_data.mood,
            is_anonymous=False,  # Anonymous posting removed
            post_type=post_data.post_type,
            video_url=post_data.video_url,
            video_thumbnail=post_data.video_thumbnail,
            image_urls=post_data.images,
            city=post_data.city,
            treatment_share_json=update_treatment_json,
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
    request: Request,
    post_id: int,
    current_user: User = Depends(auth),
    db: Session = Depends(get_db),
):
    await limit_write_for_user(request, current_user.id)
    service = CommunityService(db)
    try:
        liked, like_count = service.toggle_like(
            post_id=post_id, user_id=current_user.id
        )
        from web.backend.database.models import Post as DBPost
        post = db.query(DBPost).filter(DBPost.id == post_id).first()
        try:
            AuditLogService.log(
                db=db,
                action="community.like" if liked else "community.unlike",
                actor_id=current_user.id,
                target_type="post",
                target_id=post_id,
                details={"like_count": like_count},
                revokeable=True,
            )
        except Exception:
            pass
        if post and liked and post.user_id != current_user.id:
            create_notification(
                db,
                user_id=post.user_id,
                type="like",
                actor_id=current_user.id,
                body=post.title or "",
                ref_type="post",
                ref_id=post_id,
            )
        return LikeResponse(liked=liked, like_count=like_count)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/posts/{post_id}/share", response_model=ShareResponse)
async def share_post(
    request: Request,
    post_id: int,
    current_user: User = Depends(auth),
    db: Session = Depends(get_db),
):
    """记录一次转发：转发数 +1 并写入交互日志（热度排序数据源）。"""
    await limit_write_for_user(request, current_user.id)
    service = CommunityService(db)
    try:
        count = service.share_post(post_id=post_id, user_id=current_user.id)
        try:
            AuditLogService.log(
                db=db,
                action="community.share",
                actor_id=current_user.id,
                target_type="post",
                target_id=post_id,
                details={"share_count": count},
                revokeable=False,
            )
        except Exception:
            pass
        return ShareResponse(share_count=count)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
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
    await limit_write_for_user(request, current_user.id)
    service = CommunityService(db)
    user_status = getattr(current_user, "user_status", "normal")
    if user_status == "banned":
        raise HTTPException(status_code=403, detail="账号已被封禁，无法评论")
    if user_status == "muted":
        muted_until = getattr(current_user, "muted_until", None)
        from datetime import datetime, timezone
        if muted_until and muted_until > datetime.now(timezone.utc):
            raise HTTPException(status_code=403, detail="账号处于禁言状态，无法评论")
    # 2026-08-30 隐私加固：评论一律做 PII 自动脱敏（评论区无保留原文的确认流程）
    safe_content, pii_hit = redact_pii(comment_data.content)
    if pii_hit:
        logger.info(
            "Comment PII auto-redacted: user=%s post=%s types=%s",
            current_user.id, post_id, pii_hit,
        )
    try:
        comment = service.add_comment(
            post_id=post_id,
            user_id=current_user.id,
            content=safe_content,
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    import threading
    thread = threading.Thread(target=moderate_comment, args=(comment.id, comment.content, current_user.id), daemon=True)
    thread.start()
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
    # 通知帖子作者（如果不是自己评论）
    from web.backend.database.models import Post as DBPost
    post = db.query(DBPost).filter(DBPost.id == post_id).first()
    if post and post.user_id != current_user.id:
        create_notification(
            db,
            user_id=post.user_id,
            type="comment",
            actor_id=current_user.id,
            body=comment_data.content[:100],
            ref_type="post",
            ref_id=post_id,
        )
    return _comment_to_model(comment)


@router.get("/posts/{post_id}/comments", response_model=PostCommentListResponse)
async def list_comments(
    post_id: int,
    limit: int = 50,
    offset: int = 0,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    service = CommunityService(db)
    user_id = current_user.id if current_user else None
    total, comments = service.get_post_comments(
        post_id=post_id, limit=limit, offset=offset, user_id=user_id
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
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("图片上传失败: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="上传失败，请稍后重试")


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
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("音频上传失败: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="上传失败，请稍后重试")


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
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("文件上传失败: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="上传失败，请稍后重试")


def _post_to_model(post, user_id: Optional[int], db: Session, user_lat: Optional[float] = None, user_lng: Optional[float] = None) -> PostModel:
    service = CommunityService(db)
    return service.post_to_model(post, user_id, user_lat=user_lat, user_lng=user_lng)


def _category_to_model(category, db: Session) -> CategoryModel:
    service = CommunityService(db)
    return service.category_to_model(category)


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
async def get_collection(
    collection_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    from web.backend.database.models import Collection

    collection = db.query(Collection).filter_by(id=collection_id).first()
    if not collection:
        raise HTTPException(status_code=404, detail="收藏夹不存在")
    # Collection metadata (name/description/slug) is private unless the owner
    # has explicitly shared it. Only the owner (or anyone via a public
    # share_slug) may view it — otherwise private collection names can be
    # enumerated by any caller, leaking L2 metadata.
    is_owner = current_user is not None and collection.user_id == current_user.id
    if not collection.is_public and not is_owner:
        raise HTTPException(status_code=403, detail="无权查看此收藏夹")
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
    request: Request, post_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    await limit_write_for_user(request, user.id)
    svc = CommunityService(db)
    bookmarked = svc.toggle_bookmark(post_id=post_id, user_id=user.id)
    if bookmarked:
        from web.backend.database.models import Post as DBPost
        post = db.query(DBPost).filter(DBPost.id == post_id).first()
        if post and post.user_id != user.id:
            try:
                create_notification(
                    db,
                    user_id=post.user_id,
                    type="bookmark",
                    actor_id=user.id,
                    body=post.title or "",
                    ref_type="post",
                    ref_id=post_id,
                )
            except Exception:
                logger.warning("Failed to create bookmark notification: user=%s post=%s", user.id, post_id, exc_info=True)
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
    post_id: int,
    limit: int = 20,
    offset: int = 0,
    current_user: User = Depends(auth),
    db: Session = Depends(get_db),
):
    svc = CommunityService(db)
    total, versions = svc.get_post_versions(
        post_id=post_id, limit=limit, offset=offset, user_id=current_user.id
    )
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

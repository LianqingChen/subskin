# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportGeneralTypeIssues=false, reportMissingTypeArgument=false

from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from sqlalchemy.exc import IntegrityError

from web.backend.database.models import (
    CommunityCategory,
    Post,
    PostImage,
    PostLike,
    PostComment,
    User,
    Tag,
    PostTag,
    PostAudio,
    PostAttachment,
    Collection,
    CollectionItem,
    PostVersion,
    Bookmark,
    UserInteractionLog,
    UserFollow,
)
from web.backend.services.recommendation import RecommendationService
from web.backend.utils.cursor import decode_cursor, encode_cursor_from_post
from web.backend.models.community import (
    Post as PostModel,
    PostComment as PostCommentModel,
    PostCommentAuthor,
    Category as CategoryModel,
    PostAuthor,
    PostImage as PostImageModel,
    PostAudio as PostAudioModel,
    PostAttachment as PostAttachmentModel,
    Tag as TagModel,
)


class CommunityService:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def can_access_post(post: Optional[Post], user_id: Optional[int]) -> bool:
        """Whether ``user_id`` may view/comment/like ``post``.

        Owners always see their own posts (including private and blocked).
        Others require the post to be public AND not blocked by moderation.
        Returns False for missing posts.
        """
        if post is None:
            return False
        if user_id is not None and post.user_id == user_id:
            return True
        if bool(post.is_private):
            return False
        if getattr(post, "moderation_status", "normal") == "blocked":
            return False
        return True

    def get_categories(self) -> List[CommunityCategory]:
        return self.db.query(CommunityCategory).order_by(CommunityCategory.order).all()

    def create_post(
        self,
        user_id: int,
        title: str,
        content: str,
        category_id: int,
        content_json: Optional[str] = None,
        image_urls: Optional[List[str]] = None,
        tag_names: Optional[List[str]] = None,
        is_private: bool = False,
        diary_date: Optional[str] = None,
        diary_type: Optional[str] = None,
        mood: Optional[str] = None,
        is_anonymous: bool = False,
        post_type: Optional[str] = None,
        video_url: Optional[str] = None,
        video_thumbnail: Optional[str] = None,
        city: Optional[str] = None,
    ) -> Post:
        category = self.db.query(CommunityCategory).filter_by(id=category_id).first()
        if not category:
            raise ValueError("分类不存在")

        import re

        content_text = re.sub(r"<[^>]+>", "", content) if content else content
        content_preview = content_text[:100] if content_text else None

        if not post_type:
            if video_url:
                post_type = "video"
            elif image_urls:
                post_type = "image"
            else:
                post_type = "long"

        post = Post(
            user_id=user_id,
            title=title,
            content=content,
            content_json=content_json,
            content_text=content_text,
            content_preview=content_preview,
            post_type=post_type,
            video_url=video_url,
            video_thumbnail=video_thumbnail,
            category_id=category_id,
            is_private=is_private,
            mood=mood,
            is_anonymous=is_anonymous,
            city=city,
        )
        if is_private:
            post.draft_expires_at = datetime.utcnow() + timedelta(days=30)
        if diary_date:
            try:
                post.diary_date = datetime.strptime(diary_date, "%Y-%m-%d").date()
            except ValueError:
                post.diary_date = None
        if diary_type:
            post.diary_type = diary_type
        self.db.add(post)
        self.db.commit()
        self.db.refresh(post)

        if image_urls:
            for order, url in enumerate(image_urls):
                image = PostImage(post_id=post.id, image_url=url, order=order)
                self.db.add(image)

        if tag_names:
            for name in tag_names[:5]:
                name = name.strip()
                if not name:
                    continue
                tag = self.db.query(Tag).filter_by(name=name).first()
                if not tag:
                    tag = Tag(name=name, usage_count=0)
                    self.db.add(tag)
                    self.db.flush()
                tag.usage_count += 1
                pt = PostTag(post_id=post.id, tag_id=tag.id)
                self.db.add(pt)

        self.db.commit()
        self.db.refresh(post)
        return post

    def get_posts(
        self,
        category_id: Optional[int] = None,
        tag_name: Optional[str] = None,
        post_type: Optional[str] = None,
        feed_type: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        user_id: Optional[int] = None,
        is_private: Optional[bool] = None,
        after: Optional[str] = None,
    ) -> Tuple[int, List[Post], Optional[str]]:
        query = self.db.query(Post)

        if is_private is True:
            if user_id is None:
                return 0, [], None
            query = query.filter(Post.user_id == user_id, Post.is_private.is_(True))
        else:
            # Public feed: exclude private posts and moderation-blocked posts.
            # Owners viewing their own blocked posts is handled via the
            # is_private=True branch above; the public feed never shows blocked.
            query = query.filter(Post.is_private.is_(False))
            query = query.filter(Post.moderation_status != "blocked")

        if category_id:
            query = query.filter_by(category_id=category_id)

        if post_type:
            query = query.filter(Post.post_type == post_type)

        if tag_name:
            tag = self.db.query(Tag).filter_by(name=tag_name).first()
            if tag:
                post_ids = [
                    pt.post_id
                    for pt in self.db.query(PostTag).filter_by(tag_id=tag.id).all()
                ]
                query = query.filter(Post.id.in_(post_ids))
            else:
                return 0, [], None

        if after:
            cursor = decode_cursor(after)
            if cursor:
                cursor_ts, cursor_id = cursor
                query = query.filter(
                    (Post.created_at < cursor_ts) |
                    ((Post.created_at == cursor_ts) & (Post.id < cursor_id))
                )

        if feed_type == "hot":
            weight = RecommendationService.post_score_expr(Post)
            query = query.order_by(weight.desc(), Post.created_at.desc())
        elif feed_type == "recommend":
            weight = RecommendationService.post_score_expr(Post)
            query = query.order_by(weight.desc(), Post.created_at.desc())
        else:
            query = query.order_by(desc(Post.created_at))

        total = query.count()
        posts = query.limit(limit + 1).all()
        has_more = len(posts) > limit
        if has_more:
            posts = posts[:limit]
        next_cursor = encode_cursor_from_post(posts[-1]) if has_more and posts else None
        return total, posts, next_cursor

    def get_post_by_id(
        self, post_id: int, user_id: Optional[int] = None
    ) -> Optional[Post]:
        post = self.db.query(Post).filter_by(id=post_id).first()
        if not post:
            return None
        if not self.can_access_post(post, user_id):
            return None
        return post

    def update_post(
        self,
        post_id: int,
        user_id: int,
        title: Optional[str] = None,
        content: Optional[str] = None,
        category_id: Optional[int] = None,
        content_json: Optional[str] = None,
        tag_names: Optional[List[str]] = None,
        is_private: Optional[bool] = None,
        diary_date: Optional[str] = None,
        diary_type: Optional[str] = None,
        mood: Optional[str] = None,
        is_anonymous: Optional[bool] = None,
        post_type: Optional[str] = None,
        video_url: Optional[str] = None,
        video_thumbnail: Optional[str] = None,
        city: Optional[str] = None,
        image_urls: Optional[List[str]] = None,
    ) -> Post:
        post = self.db.query(Post).filter_by(id=post_id, user_id=user_id).first()
        if not post:
            raise ValueError("帖子不存在或无权修改")

        old_content = post.content
        old_title = post.title
        old_content_json = post.content_json

        if title is not None:
            post.title = title
        if content is not None:
            post.content = content
            import re

            post.content_text = re.sub(r"<[^>]+>", "", content)
            post.content_preview = post.content_text[:100] if post.content_text else None
        if content_json is not None:
            post.content_json = content_json
        if category_id is not None:
            post.category_id = category_id
        if is_private is not None:
            post.is_private = is_private
            if is_private and not post.draft_expires_at:
                post.draft_expires_at = datetime.utcnow() + timedelta(days=30)
            elif not is_private:
                post.draft_expires_at = None
        if mood is not None:
            post.mood = mood
        if is_anonymous is not None:
            post.is_anonymous = is_anonymous
        if post_type is not None:
            post.post_type = post_type
        if video_url is not None:
            post.video_url = video_url
        if video_thumbnail is not None:
            post.video_thumbnail = video_thumbnail
        if diary_date is not None:
            try:
                post.diary_date = datetime.strptime(diary_date, "%Y-%m-%d").date()
            except ValueError:
                post.diary_date = None
        if diary_type is not None:
            post.diary_type = diary_type
        if city is not None:
            post.city = city
        if tag_names is not None:
            self.db.query(PostTag).filter_by(post_id=post.id).delete()
            for name in tag_names[:5]:
                name = name.strip()
                if not name:
                    continue
                tag = self.db.query(Tag).filter_by(name=name).first()
                if not tag:
                    tag = Tag(name=name, usage_count=0)
                    self.db.add(tag)
                    self.db.flush()
                tag.usage_count += 1
                pt = PostTag(post_id=post.id, tag_id=tag.id)
                self.db.add(pt)

        if image_urls is not None:
            self.db.query(PostImage).filter_by(post_id=post.id).delete()
            for order, url in enumerate(image_urls):
                image = PostImage(post_id=post.id, image_url=url, order=order)
                self.db.add(image)

        self.db.flush()

        if old_content or old_title:
            self.save_version(
                post_id=post.id,
                user_id=user_id,
                title=old_title,
                content=old_content,
                content_json=old_content_json,
                edit_summary=None,
            )

        post.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(post)
        return post

    def delete_post(self, post_id: int, user_id: int) -> bool:
        post = self.db.query(Post).filter_by(id=post_id, user_id=user_id).first()
        if not post:
            return False

        # Secondary table (not covered by ORM cascade)
        self.db.query(PostTag).filter_by(post_id=post_id).delete()

        # ORM cascade handles: PostImage, PostLike, PostComment,
        # PostAudio, PostAttachment, PostVersion, CollectionItem, Bookmark, UserInteractionLog
        self.db.delete(post)
        self.db.commit()
        return True

    def toggle_like(self, post_id: int, user_id: int) -> Tuple[bool, int]:
        post = self.db.query(Post).filter_by(id=post_id).first()
        if not post:
            raise ValueError("帖子不存在")
        if not self.can_access_post(post, user_id):
            raise PermissionError("无权点赞该帖子")

        existing_like = (
            self.db.query(PostLike).filter_by(post_id=post_id, user_id=user_id).first()
        )

        if existing_like:
            self.db.delete(existing_like)
            liked = False
        else:
            like = PostLike(post_id=post_id, user_id=user_id)
            self.db.add(like)
            liked = True

        try:
            self.db.commit()
        except IntegrityError:
            # Race: another concurrent request inserted the same (post_id,
            # user_id) between our check and commit. The unique constraint
            # rejected the duplicate. Treat as already-liked and recompute.
            self.db.rollback()
            liked = True
        like_count = (
            self.db.query(func.count(PostLike.id)).filter_by(post_id=post_id).scalar()
        )
        return liked, like_count

    def get_like_count(self, post_id: int) -> int:
        return (
            self.db.query(func.count(PostLike.id)).filter_by(post_id=post_id).scalar()
        )

    def is_liked(self, post_id: int, user_id: int) -> bool:
        like = (
            self.db.query(PostLike).filter_by(post_id=post_id, user_id=user_id).first()
        )
        return like is not None

    def add_comment(self, post_id: int, user_id: int, content: str) -> PostComment:
        post = self.db.query(Post).filter_by(id=post_id).first()
        if not post:
            raise ValueError("帖子不存在")
        if not self.can_access_post(post, user_id):
            raise PermissionError("无权评论该帖子")

        comment = PostComment(post_id=post_id, user_id=user_id, content=content)
        self.db.add(comment)
        self.db.commit()
        self.db.refresh(comment)
        return comment

    def get_post_comments(
        self, post_id: int, limit: int = 50, offset: int = 0,
        user_id: Optional[int] = None,
    ) -> Tuple[int, List[PostComment]]:
        post = self.db.query(Post).filter_by(id=post_id).first()
        if not post or not self.can_access_post(post, user_id):
            return 0, []
        query = self.db.query(PostComment).filter_by(post_id=post_id)
        total = query.count()
        comments = (
            query.order_by(PostComment.created_at).offset(offset).limit(limit).all()
        )
        return total, comments

    def get_comment_count(self, post_id: int) -> int:
        return (
            self.db.query(func.count(PostComment.id))
            .filter_by(post_id=post_id)
            .scalar()
        )

    # ── Upload validation constants ──
    # The community upload endpoints previously accepted any Content-Type with
    # no size or magic-byte check — a DoS vector (huge uploads) and a polyglot
    # risk (malicious files served with a .jpg extension). These limits and
    # signatures are enforced before the file is written to disk.
    MAX_IMAGE_UPLOAD_BYTES = 10 * 1024 * 1024   # 10 MB
    MAX_FILE_UPLOAD_BYTES = 50 * 1024 * 1024    # 50 MB (audio/files)
    ALLOWED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
    ALLOWED_FILE_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".pdf", ".txt", ".doc", ".docx"}
    _IMAGE_MAGIC = (
        (b"\xff\xd8\xff", "image/jpeg"),
        (b"\x89PNG\r\n\x1a\n", "image/png"),
        (b"RIFF", "image/webp"),  # RIFF....WEBP
        (b"GIF87a", "image/gif"),
        (b"GIF89a", "image/gif"),
    )

    @classmethod
    def _check_image_magic(cls, content: bytes) -> bool:
        if not content:
            return False
        for sig, _kind in cls._IMAGE_MAGIC:
            if content.startswith(sig):
                if sig == b"RIFF":
                    return len(content) >= 12 and content[8:12] == b"WEBP"
                return True
        return False

    def upload_image(self, user_id: int, filename: str, content: bytes) -> str:
        import hashlib
        from pathlib import Path

        if len(content) > self.MAX_IMAGE_UPLOAD_BYTES:
            raise ValueError(
                f"图片过大，最大支持 {self.MAX_IMAGE_UPLOAD_BYTES // (1024 * 1024)}MB"
            )
        ext = (Path(filename).suffix or "").lower()
        if ext not in self.ALLOWED_IMAGE_EXTS:
            raise ValueError(f"不支持的图片格式，支持: {', '.join(sorted(self.ALLOWED_IMAGE_EXTS))}")
        if not self._check_image_magic(content):
            raise ValueError("图片内容与声明格式不符（magic byte 校验失败）")

        upload_dir = Path("data/uploads/community")
        upload_dir.mkdir(parents=True, exist_ok=True)

        file_hash = hashlib.sha256(content).hexdigest()[:16]
        new_filename = f"{user_id}_{file_hash}{ext}"
        file_path = upload_dir / new_filename

        with open(file_path, "wb") as f:
            f.write(content)

        return f"/uploads/community/{new_filename}"

    def upload_file(
        self, user_id: int, filename: str, content: bytes, subdir: str = "files"
    ) -> dict:
        import hashlib
        from pathlib import Path

        if len(content) > self.MAX_FILE_UPLOAD_BYTES:
            raise ValueError(
                f"文件过大，最大支持 {self.MAX_FILE_UPLOAD_BYTES // (1024 * 1024)}MB"
            )
        ext = (Path(filename).suffix or "").lower()
        if ext not in self.ALLOWED_FILE_EXTS:
            raise ValueError(f"不支持的文件格式，支持: {', '.join(sorted(self.ALLOWED_FILE_EXTS))}")

        upload_dir = Path(f"data/uploads/{subdir}")
        upload_dir.mkdir(parents=True, exist_ok=True)

        file_hash = hashlib.sha256(content).hexdigest()[:16]
        new_filename = f"{user_id}_{file_hash}{ext}"
        file_path = upload_dir / new_filename

        with open(file_path, "wb") as f:
            f.write(content)

        return {
            "url": f"/uploads/{subdir}/{new_filename}",
            "filename": new_filename,
            "size": len(content),
        }

    # ── Collections (Knowledge Base) ──

    def create_collection(
        self,
        user_id: int,
        name: str,
        description: str = None,
        icon: str = None,
        is_public: bool = False,
    ) -> Collection:
        import secrets

        collection = Collection(
            user_id=user_id,
            name=name,
            description=description,
            icon=icon,
            is_public=is_public,
            share_slug=secrets.token_urlsafe(8) if is_public else None,
        )
        self.db.add(collection)
        self.db.commit()
        self.db.refresh(collection)
        return collection

    def get_user_collections(self, user_id: int) -> List[Collection]:
        return (
            self.db.query(Collection)
            .filter_by(user_id=user_id)
            .order_by(Collection.sort_order, Collection.created_at.desc())
            .all()
        )

    def get_collection_by_slug(self, share_slug: str) -> Optional[Collection]:
        return self.db.query(Collection).filter_by(share_slug=share_slug).first()

    def get_collection_by_id(self, collection_id: int) -> Optional[Collection]:
        return self.db.query(Collection).filter_by(id=collection_id).first()

    def update_collection(
        self, collection_id: int, user_id: int, **kwargs
    ) -> Collection:
        collection = (
            self.db.query(Collection)
            .filter_by(id=collection_id, user_id=user_id)
            .first()
        )
        if not collection:
            raise ValueError("收藏夹不存在或无权修改")
        import secrets

        for key, value in kwargs.items():
            if hasattr(collection, key):
                setattr(collection, key, value)
        if kwargs.get("is_public") and not collection.share_slug:
            collection.share_slug = secrets.token_urlsafe(8)
        if not kwargs.get("is_public", True):
            collection.share_slug = None
        self.db.commit()
        self.db.refresh(collection)
        return collection

    def delete_collection(self, collection_id: int, user_id: int) -> bool:
        collection = (
            self.db.query(Collection)
            .filter_by(id=collection_id, user_id=user_id)
            .first()
        )
        if not collection:
            return False
        self.db.delete(collection)
        self.db.commit()
        return True

    def add_to_collection(
        self, collection_id: int, post_id: int, note: str = None, user_id: int = None
    ) -> CollectionItem:
        collection = self.db.query(Collection).filter_by(id=collection_id).first()
        if not collection:
            raise ValueError("收藏夹不存在")
        if user_id and collection.user_id != user_id:
            raise ValueError("无权操作此收藏夹")
        # Verify the post is accessible to this user before allowing it to be
        # bookmarked. Without this, a user could add another user's private post
        # to their own collection, and the private post's content would then
        # leak via the collection's item listing.
        post = self.db.query(Post).filter_by(id=post_id).first()
        if not post:
            raise ValueError("帖子不存在")
        if not self.can_access_post(post, user_id):
            raise PermissionError("无权收藏该帖子")
        existing = (
            self.db.query(CollectionItem)
            .filter_by(collection_id=collection_id, post_id=post_id)
            .first()
        )
        if existing:
            if note is not None:
                existing.note = note
            self.db.commit()
            return existing
        max_order = (
            self.db.query(func.max(CollectionItem.sort_order))
            .filter_by(collection_id=collection_id)
            .scalar()
            or 0
        )
        item = CollectionItem(
            collection_id=collection_id,
            post_id=post_id,
            note=note,
            sort_order=max_order + 1,
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def remove_from_collection(
        self, collection_id: int, post_id: int, user_id: int
    ) -> bool:
        collection = (
            self.db.query(Collection)
            .filter_by(id=collection_id, user_id=user_id)
            .first()
        )
        if not collection:
            return False
        item = (
            self.db.query(CollectionItem)
            .filter_by(collection_id=collection_id, post_id=post_id)
            .first()
        )
        if not item:
            return False
        self.db.delete(item)
        self.db.commit()
        return True

    def get_collection_items(
        self, collection_id: int, limit: int = 50, offset: int = 0
    ) -> Tuple[int, List[CollectionItem]]:
        query = self.db.query(CollectionItem).filter_by(collection_id=collection_id)
        total = query.count()
        items = (
            query.order_by(CollectionItem.sort_order, CollectionItem.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return total, items

    # ── Bookmarks ──

    def toggle_bookmark(self, post_id: int, user_id: int) -> bool:
        existing = (
            self.db.query(Bookmark).filter_by(post_id=post_id, user_id=user_id).first()
        )
        if existing:
            self.db.delete(existing)
            self.db.commit()
            return False
        bookmark = Bookmark(post_id=post_id, user_id=user_id)
        self.db.add(bookmark)
        self.db.commit()
        return True

    def is_bookmarked(self, post_id: int, user_id: int) -> bool:
        return (
            self.db.query(Bookmark).filter_by(post_id=post_id, user_id=user_id).first()
            is not None
        )

    def get_user_bookmarks(
        self, user_id: int, limit: int = 20, offset: int = 0
    ) -> Tuple[int, List[Post]]:
        query = (
            self.db.query(Post)
            .join(Bookmark, Bookmark.post_id == Post.id)
            .filter(Bookmark.user_id == user_id)
        )
        total = query.count()
        posts = (
            query.order_by(Bookmark.created_at.desc()).offset(offset).limit(limit).all()
        )
        return total, posts

    # ── Post Versions ──

    def save_version(
        self,
        post_id: int,
        user_id: int,
        title: str,
        content: str,
        content_json: str = None,
        edit_summary: str = None,
    ) -> PostVersion:
        version = PostVersion(
            post_id=post_id,
            user_id=user_id,
            title=title,
            content=content,
            content_json=content_json,
            edit_summary=edit_summary,
        )
        self.db.add(version)
        self.db.commit()
        self.db.refresh(version)
        return version

    def get_post_versions(
        self, post_id: int, limit: int = 20, offset: int = 0,
        user_id: Optional[int] = None,
    ) -> Tuple[int, List[PostVersion]]:
        post = self.db.query(Post).filter_by(id=post_id).first()
        if not post or not self.can_access_post(post, user_id):
            return 0, []
        query = self.db.query(PostVersion).filter_by(post_id=post_id)
        total = query.count()
        versions = (
            query.order_by(PostVersion.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return total, versions

    # ── Interaction Logging ──

    def log_interaction(self, user_id: int, post_id: int, action_type: str) -> None:
        log = UserInteractionLog(
            user_id=user_id, post_id=post_id, action_type=action_type
        )
        self.db.add(log)
        if action_type == "click":
            post = self.db.query(Post).filter_by(id=post_id).first()
            if post:
                post.read_count = (post.read_count or 0) + 1
        self.db.commit()

    # ── Tag Management ──

    def update_post_tags(self, post_id: int, user_id: int, tag_names: List[str]) -> Post:
        post = self.db.query(Post).filter_by(id=post_id, user_id=user_id).first()
        if not post:
            raise ValueError("帖子不存在或无权修改")
        self.db.query(PostTag).filter_by(post_id=post.id).delete()
        for name in tag_names[:5]:
            name = name.strip()
            if not name:
                continue
            tag = self.db.query(Tag).filter_by(name=name).first()
            if not tag:
                tag = Tag(name=name, usage_count=0)
                self.db.add(tag)
                self.db.flush()
            tag.usage_count += 1
            pt = PostTag(post_id=post.id, tag_id=tag.id)
            self.db.add(pt)
        self.db.commit()
        self.db.refresh(post)
        return post

    def get_hot_tags(self, limit: int = 20) -> List[Tag]:
        return self.db.query(Tag).order_by(Tag.usage_count.desc()).limit(limit).all()

    @staticmethod
    def calc_distance(
        lat1: Optional[float], lng1: Optional[float],
        lat2: Optional[float], lng2: Optional[float],
    ) -> Optional[float]:
        if lat1 is None or lng1 is None or lat2 is None or lng2 is None:
            return None
        import math
        R = 6371
        dLat = (lat2 - lat1) * math.pi / 180
        dLng = (lng2 - lng1) * math.pi / 180
        a = math.sin(dLat / 2) ** 2 + math.cos(lat1 * math.pi / 180) * math.cos(lat2 * math.pi / 180) * math.sin(dLng / 2) ** 2
        return round(R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)), 1)

    def category_to_model(self, category) -> CategoryModel:
        post_count = (
            self.db.query(func.count(Post.id)).filter_by(category_id=category.id).scalar()
        )
        return CategoryModel(
            id=category.id,
            name=category.name,
            description=category.description,
            icon=category.icon,
            post_count=post_count,
        )

    def comment_to_model(self, comment) -> PostCommentModel:
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

    def post_to_model(
        self, post, user_id: Optional[int],
        user_lat: Optional[float] = None, user_lng: Optional[float] = None,
    ) -> PostModel:
        like_count = self.get_like_count(post.id)
        comment_count = self.get_comment_count(post.id)
        is_liked = self.is_liked(post.id, user_id) if user_id else False
        is_bookmarked = self.is_bookmarked(post.id, user_id) if user_id else False

        images = (
            self.db.query(PostImage)
            .filter_by(post_id=post.id)
            .order_by(PostImage.order)
            .all()
        )

        audios = (
            self.db.query(PostAudio).filter_by(post_id=post.id).order_by(PostAudio.order).all()
        )

        attachments = (
            self.db.query(PostAttachment)
            .filter_by(post_id=post.id)
            .order_by(PostAttachment.order)
            .all()
        )

        post_tag_records = self.db.query(PostTag).filter_by(post_id=post.id).all()
        tag_ids = [pt.tag_id for pt in post_tag_records]
        tags = self.db.query(Tag).filter(Tag.id.in_(tag_ids)).all() if tag_ids else []

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
            draft_expires_at=getattr(post, "draft_expires_at", None),
            diary_date=post.diary_date.isoformat() if post.diary_date else None,
            diary_type=getattr(post, "diary_type", None),
            mood=post.mood,
            is_anonymous=False,
            city=post.city,
            latitude=getattr(post, "latitude", None),
            longitude=getattr(post, "longitude", None),
            distance=self.calc_distance(user_lat, user_lng, getattr(post, "latitude", None), getattr(post, "longitude", None)),
            author=PostAuthor(
                id=post.author.id,
                username=post.author.username,
                avatar=post.author.avatar_url,
                is_doctor=getattr(post.author, "is_doctor", False),
                is_verified=getattr(post.author, "real_name_verified", False),
                is_followed=(
                    self.db.query(UserFollow)
                    .filter_by(followee_id=post.author.id, follower_id=user_id)
                    .first() is not None
                ) if user_id else False,
            ),
            category=self.category_to_model(post.category) if post.category else None,
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
            moderation_status=getattr(post, "moderation_status", "normal"),
            created_at=post.created_at,
            updated_at=post.updated_at,
        )

    def posts_to_models(
        self,
        posts: List[Post],
        user_id: Optional[int],
        user_lat: Optional[float] = None,
        user_lng: Optional[float] = None,
    ) -> List[PostModel]:
        """Batch-convert a list of Posts to PostModel with O(1) round-trips.

        ``post_to_model`` issues 8–10 queries per post (like/comment counts,
        is_liked/is_bookmarked, images, audios, attachments, tags, follow,
        category count) → 160+ round-trips for a 20-post page. This method
        pre-fetches every relation in a handful of bulk IN/group-by queries and
        assembles the models in memory, collapsing the N+1 to ~8 queries total.
        """
        if not posts:
            return []

        post_ids = [p.id for p in posts]
        author_ids = list({p.user_id for p in posts if p.user_id is not None})
        category_ids = list({p.category_id for p in posts if p.category_id is not None})

        # ── Bulk aggregates ──
        like_counts = {
            r[0]: r[1]
            for r in self.db.query(PostLike.post_id, func.count(PostLike.id))
            .filter(PostLike.post_id.in_(post_ids))
            .group_by(PostLike.post_id).all()
        }
        comment_counts = {
            r[0]: r[1]
            for r in self.db.query(PostComment.post_id, func.count(PostComment.id))
            .filter(PostComment.post_id.in_(post_ids))
            .group_by(PostComment.post_id).all()
        }
        liked_post_ids = set()
        if user_id:
            liked_post_ids = {
                r[0] for r in self.db.query(PostLike.post_id)
                .filter(PostLike.post_id.in_(post_ids), PostLike.user_id == user_id).all()
            }
        bookmarked_post_ids = set()
        if user_id:
            bookmarked_post_ids = {
                r[0] for r in self.db.query(Bookmark.post_id)
                .filter(Bookmark.post_id.in_(post_ids), Bookmark.user_id == user_id).all()
            }
        followed_author_ids = set()
        if user_id and author_ids:
            followed_author_ids = {
                r[0] for r in self.db.query(UserFollow.followee_id)
                .filter(UserFollow.followee_id.in_(author_ids), UserFollow.follower_id == user_id).all()
            }

        # ── Bulk relations ──
        all_images = (
            self.db.query(PostImage)
            .filter(PostImage.post_id.in_(post_ids))
            .order_by(PostImage.post_id, PostImage.order).all()
        )
        images_by_post: dict = {}
        for img in all_images:
            images_by_post.setdefault(img.post_id, []).append(img)

        all_audios = (
            self.db.query(PostAudio)
            .filter(PostAudio.post_id.in_(post_ids))
            .order_by(PostAudio.post_id, PostAudio.order).all()
        )
        audios_by_post: dict = {}
        for a in all_audios:
            audios_by_post.setdefault(a.post_id, []).append(a)

        all_attachments = (
            self.db.query(PostAttachment)
            .filter(PostAttachment.post_id.in_(post_ids))
            .order_by(PostAttachment.post_id, PostAttachment.order).all()
        )
        attachments_by_post: dict = {}
        for a in all_attachments:
            attachments_by_post.setdefault(a.post_id, []).append(a)

        all_post_tags = (
            self.db.query(PostTag).filter(PostTag.post_id.in_(post_ids)).all()
        )
        tag_ids = list({pt.tag_id for pt in all_post_tags})
        tags_by_id = {
            t.id: t for t in (self.db.query(Tag).filter(Tag.id.in_(tag_ids)).all() if tag_ids else [])
        }
        tags_by_post: dict = {}
        for pt in all_post_tags:
            t = tags_by_id.get(pt.tag_id)
            if t is not None:
                tags_by_post.setdefault(pt.post_id, []).append(t)

        # Category post counts (batched) — replaces per-category count query.
        cat_counts = {
            r[0]: r[1]
            for r in self.db.query(Post.category_id, func.count(Post.id))
            .filter(Post.category_id.in_(category_ids))
            .group_by(Post.category_id).all()
        } if category_ids else {}

        models: List[PostModel] = []
        for post in posts:
            like_count = like_counts.get(post.id, 0)
            comment_count = comment_counts.get(post.id, 0)
            is_liked = post.id in liked_post_ids
            is_bookmarked = post.id in bookmarked_post_ids
            images = images_by_post.get(post.id, [])
            audios = audios_by_post.get(post.id, [])
            attachments = attachments_by_post.get(post.id, [])
            tags = tags_by_post.get(post.id, [])

            author = post.author
            author_model = PostAuthor(
                id=author.id,
                username=author.username,
                avatar=author.avatar_url,
                is_doctor=getattr(author, "is_doctor", False),
                is_verified=getattr(author, "real_name_verified", False),
                is_followed=(author.id in followed_author_ids) if user_id else False,
            ) if author else None

            category_model = None
            if post.category is not None:
                category_model = CategoryModel(
                    id=post.category.id,
                    name=post.category.name,
                    description=post.category.description,
                    icon=post.category.icon,
                    post_count=cat_counts.get(post.category.id, 0),
                )

            models.append(PostModel(
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
                draft_expires_at=getattr(post, "draft_expires_at", None),
                diary_date=post.diary_date.isoformat() if post.diary_date else None,
                diary_type=getattr(post, "diary_type", None),
                mood=post.mood,
                is_anonymous=False,
                city=post.city,
                latitude=getattr(post, "latitude", None),
                longitude=getattr(post, "longitude", None),
                distance=self.calc_distance(user_lat, user_lng, getattr(post, "latitude", None), getattr(post, "longitude", None)),
                author=author_model,
                category=category_model,
                images=[
                    PostImageModel(id=img.id, image_url=img.image_url, order=img.order)
                    for img in images
                ],
                audios=[
                    PostAudioModel(id=a.id, audio_url=a.audio_url, duration=a.duration, file_size=a.file_size, order=a.order)
                    for a in audios
                ],
                attachments=[
                    PostAttachmentModel(id=a.id, file_url=a.file_url, file_name=a.file_name, file_size=a.file_size, file_type=a.file_type, order=a.order)
                    for a in attachments
                ],
                tags=[TagModel(id=t.id, name=t.name, usage_count=t.usage_count) for t in tags],
                like_count=like_count,
                comment_count=comment_count,
                is_liked=is_liked,
                is_bookmarked=is_bookmarked,
                moderation_status=getattr(post, "moderation_status", "normal"),
                created_at=post.created_at,
                updated_at=post.updated_at,
            ))
        return models

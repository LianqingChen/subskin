# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportGeneralTypeIssues=false, reportMissingTypeArgument=false

from datetime import datetime
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

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
)


class CommunityService:
    def __init__(self, db: Session):
        self.db = db

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
        if diary_date:
            try:
                post.diary_date = datetime.strptime(diary_date, "%Y-%m-%d").date()
            except ValueError:
                post.diary_date = None
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
    ) -> Tuple[int, List[Post]]:
        query = self.db.query(Post)

        if is_private is True:
            if user_id is None:
                return 0, []
            query = query.filter(Post.user_id == user_id, Post.is_private.is_(True))
        else:
            query = query.filter(Post.is_private.is_(False))

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
                return 0, []

        if feed_type == "hot":
            hot_weight = Post.like_count * 2 + Post.comment_count * 2.5 + Post.read_count * 0.1
            query = query.order_by(hot_weight.desc(), Post.created_at.desc())
        elif feed_type == "recommend":
            rec_weight = Post.like_count * 2 + Post.comment_count * 2.5 + Post.read_count * 0.1
            query = query.order_by(rec_weight.desc(), Post.created_at.desc())
        else:
            query = query.order_by(desc(Post.created_at))

        total = query.count()
        posts = query.offset(offset).limit(limit).all()
        return total, posts

    def get_post_by_id(
        self, post_id: int, user_id: Optional[int] = None
    ) -> Optional[Post]:
        post = self.db.query(Post).filter_by(id=post_id).first()
        if not post:
            return None
        if post.is_private and post.user_id != user_id:
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
        mood: Optional[str] = None,
        is_anonymous: Optional[bool] = None,
        post_type: Optional[str] = None,
        video_url: Optional[str] = None,
        video_thumbnail: Optional[str] = None,
        city: Optional[str] = None,
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

        self.db.commit()
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

        comment = PostComment(post_id=post_id, user_id=user_id, content=content)
        self.db.add(comment)
        self.db.commit()
        self.db.refresh(comment)
        return comment

    def get_post_comments(
        self, post_id: int, limit: int = 50, offset: int = 0
    ) -> Tuple[int, List[PostComment]]:
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

    def upload_image(self, user_id: int, filename: str, content: bytes) -> str:
        import hashlib
        from pathlib import Path

        upload_dir = Path("data/uploads/community")
        upload_dir.mkdir(parents=True, exist_ok=True)

        file_hash = hashlib.sha256(content).hexdigest()[:16]
        ext = Path(filename).suffix
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

        upload_dir = Path(f"data/uploads/{subdir}")
        upload_dir.mkdir(parents=True, exist_ok=True)

        file_hash = hashlib.sha256(content).hexdigest()[:16]
        ext = Path(filename).suffix
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
        self, post_id: int, limit: int = 20, offset: int = 0
    ) -> Tuple[int, List[PostVersion]]:
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

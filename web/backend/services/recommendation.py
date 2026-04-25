# pyright: reportArgumentType=false, reportAttributeAccessIssue=false

import math
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from web.backend.database.models import (
    Post,
    Tag,
    PostTag,
    PostLike,
    UserFollow,
    UserBlock,
    UserInteractionLog,
)


def _utcnow():
    return datetime.now(timezone.utc)


class RecommendationService:
    INTERACTION_WEIGHTS = {
        "click": 1.0,
        "read_end": 1.5,
        "like": 2.0,
        "bookmark": 3.0,
        "comment": 2.5,
        "share": 4.0,
        "skip": -0.5,
    }

    def __init__(self, db: Session):
        self.db = db

    def get_feed(
        self,
        user_id: Optional[int],
        page: int,
        page_size: int,
        feed_type: str = "recommend",
        city: Optional[str] = None,
    ) -> Tuple[int, List[Post]]:
        if feed_type == "hot":
            return self._hot_posts(page, page_size)
        if feed_type == "following" and user_id:
            return self._following_posts(user_id, page, page_size)
        if feed_type == "local" and city:
            return self._local_posts(city, page, page_size)
        return self._personalized_recommend(user_id, page, page_size)

    def _hot_posts(self, page: int, page_size: int) -> Tuple[int, List[Post]]:
        now = _utcnow()
        week_ago = now - timedelta(days=7)
        query = self.db.query(Post).filter(
            Post.is_private.is_(False),
            Post.created_at >= week_ago,
        )
        total = query.count()
        posts = (
            query.order_by(
                (func.coalesce(Post.read_count, 0) * 0.1).desc(),
                Post.created_at.desc(),
            )
            .offset(page * page_size)
            .limit(page_size)
            .all()
        )
        return total, posts

    def _personalized_recommend(
        self, user_id: Optional[int], page: int, page_size: int
    ) -> Tuple[int, List[Post]]:
        query = self.db.query(Post).filter(Post.is_private.is_(False))

        if user_id:
            user_tags = self._get_user_preference_tags(user_id)
            if user_tags:
                tag_ids = [t.id for t in user_tags]
                post_ids_with_tags = [
                    pt.post_id
                    for pt in self.db.query(PostTag).filter(PostTag.tag_id.in_(tag_ids)).all()
                ]
                interest_query = query.filter(Post.id.in_(post_ids_with_tags))
                explore_query = query.filter(~Post.id.in_(post_ids_with_tags))

                interest_posts = interest_query.order_by(
                    desc(func.coalesce(Post.read_count, 0)),
                    Post.created_at.desc(),
                ).limit(int(page_size * 0.8)).all()

                explore_posts = explore_query.order_by(
                    desc(Post.created_at)
                ).limit(int(page_size * 0.2) + 1).all()

                all_posts = interest_posts + explore_posts
                total = query.count()
                return total, all_posts[:page_size]

        total = query.count()
        posts = (
            query.order_by(
                desc(func.coalesce(Post.read_count, 0)),
                Post.created_at.desc(),
            )
            .offset(page * page_size)
            .limit(page_size)
            .all()
        )
        return total, posts

    def _following_posts(
        self, user_id: int, page: int, page_size: int
    ) -> Tuple[int, List[Post]]:
        # 获取真实关注用户
        follows = (
            self.db.query(UserFollow)
            .filter_by(follower_id=user_id)
            .all()
        )
        author_ids = [f.followee_id for f in follows]
        if not author_ids:
            return self._hot_posts(page, page_size)

        # 排除已拉黑的用户
        blocked = (
            self.db.query(UserBlock.blocked_id)
            .filter_by(blocker_id=user_id)
            .all()
        )
        blocked_ids = {b[0] for b in blocked}
        author_ids = [aid for aid in author_ids if aid not in blocked_ids]

        if not author_ids:
            return self._hot_posts(page, page_size)

        query = self.db.query(Post).filter(
            Post.is_private.is_(False),
            Post.user_id.in_(author_ids),
        )
        total = query.count()
        posts = (
            query.order_by(desc(Post.created_at))
            .offset(page * page_size)
            .limit(page_size)
            .all()
        )
        return total, posts

    def _local_posts(
        self, city: str, page: int, page_size: int
    ) -> Tuple[int, List[Post]]:
        query = self.db.query(Post).filter(
            Post.is_private.is_(False),
            Post.city.isnot(None),
            func.lower(Post.city) == city.strip().lower(),
        )
        total = query.count()
        posts = (
            query.order_by(
                desc(func.coalesce(Post.read_count, 0)),
                Post.created_at.desc(),
            )
            .offset(page * page_size)
            .limit(page_size)
            .all()
        )
        return total, posts

    def _get_user_preference_tags(self, user_id: int, limit: int = 10) -> List[Tag]:
        interactions = (
            self.db.query(UserInteractionLog)
            .filter(UserInteractionLog.user_id == user_id)
            .order_by(UserInteractionLog.created_at.desc())
            .limit(200)
            .all()
        )
        if not interactions:
            return []

        post_ids = list(set(i.post_id for i in interactions))
        tag_rows = (
            self.db.query(PostTag.tag_id, func.count(PostTag.tag_id).label("cnt"))
            .filter(PostTag.post_id.in_(post_ids))
            .group_by(PostTag.tag_id)
            .order_by(desc("cnt"))
            .limit(limit)
            .all()
        )
        tag_ids = [r.tag_id for r in tag_rows]
        if not tag_ids:
            return []
        return self.db.query(Tag).filter(Tag.id.in_(tag_ids)).all()

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

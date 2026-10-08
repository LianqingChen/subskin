# pyright: reportArgumentType=false, reportAttributeAccessIssue=false

import math
import time as _time
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from web.backend.database.models import (
    Post,
    Tag,
    PostTag,
    PostLike,
    PostComment,
    Bookmark,
    UserFollow,
    UserBlock,
    UserInteractionLog,
)
from web.backend.utils.cursor import decode_cursor, encode_cursor_from_post
from sqlalchemy import func as _func, select as _select, and_ as _and_


def _utcnow():
    return datetime.now(timezone.utc)


# 同城帖子缓存: {key: (timestamp, (total, post_ids))}, TTL 5分钟
# 只缓存帖子 ID，不缓存 ORM 对象：ORM 对象在 Session 关闭后处于 detached 状态，
# 跨请求复用会报 DetachedInstanceError 或读到陈旧数据，且可能长期持有 Session 引用。
_LOCAL_CACHE_TTL = 300  # seconds
_local_cache: Dict[str, Tuple[float, Tuple[int, List[int]]]] = {}


def _cache_key_local(city: str, page: int, page_size: int,
                     user_lat: Optional[float], user_lng: Optional[float]) -> str:
    lat_key = f"{user_lat:.2f}" if user_lat is not None else "n"
    lng_key = f"{user_lng:.2f}" if user_lng is not None else "n"
    return f"{city}:{page}:{page_size}:{lat_key}:{lng_key}"


class RecommendationService:
    # 小红书 CES 式互动权重：深度互动（转发/评论/收藏）远高于轻度互动（点赞/浏览）。
    # 浏览只给 0.1 —— 参考小红书「互动率优先」：单纯浏览多但无互动不推。
    INTERACTION_WEIGHTS = {
        "click": 0.1,
        "read_end": 1.5,
        "like": 1.0,
        "bookmark": 2.0,
        "comment": 3.0,
        "share": 4.0,
        "skip": -0.5,
    }

    # 热度时间衰减半衰期（天）：0.5^(age/7)。参考小红书热度榜约 7 天的内容窗口，
    # 让老帖自然下沉、新帖有机会露头（冷启动）。
    HEAT_HALF_LIFE_DAYS = 7.0

    @classmethod
    def count_expr(cls, model, post_col=Post):
        """COUNT 子查询：统计某类关联记录（点赞/评论/收藏）数量。"""
        return (
            _select(_func.count(model.id))
            .where(model.post_id == post_col.id)
            .correlate(post_col)
            .scalar_subquery()
        )

    @classmethod
    def post_score_expr(cls, post_col=Post, with_decay: bool = True):
        """小红书式 CES 热度分（含时间衰减）。

        heat   = 点赞×1 + 收藏×2 + 评论×3 + 转发×4 + 浏览×0.1
        decay  = 0.5 ^ (age_days / 7)
        score  = heat × decay

        ``with_decay=False`` 返回未衰减热度（用于调试或纯计数排序的对照）。
        """
        like_subq = cls.count_expr(PostLike, post_col)
        comment_subq = cls.count_expr(PostComment, post_col)
        bookmark_subq = cls.count_expr(Bookmark, post_col)
        heat = (
            like_subq * cls.INTERACTION_WEIGHTS["like"]
            + bookmark_subq * cls.INTERACTION_WEIGHTS["bookmark"]
            + comment_subq * cls.INTERACTION_WEIGHTS["comment"]
            + _func.coalesce(post_col.share_count, 0) * cls.INTERACTION_WEIGHTS["share"]
            + _func.coalesce(post_col.read_count, 0) * cls.INTERACTION_WEIGHTS["click"]
        )
        if not with_decay:
            return heat
        # julianday 将 UTC 时间字符串转为天数；'now' 为 SQLite 内置当前时间。
        age_days = _func.julianday("now") - _func.julianday(post_col.created_at)
        decay = _func.pow(0.5, age_days / cls.HEAT_HALF_LIFE_DAYS)
        return heat * decay

    def __init__(self, db: Session):
        self.db = db

    def get_feed(
        self,
        user_id: Optional[int],
        page: int,
        page_size: int,
        feed_type: str = "recommend",
        city: Optional[str] = None,
        user_lat: Optional[float] = None,
        user_lng: Optional[float] = None,
        after: Optional[str] = None,
    ) -> Tuple[int, List[Post], Optional[str]]:
        if feed_type == "hot":
            return self._hot_posts(page, page_size, after)
        if feed_type == "following" and user_id:
            return self._following_posts(user_id, page, page_size, after)
        if feed_type == "local" and city:
            return self._local_posts(city, page, page_size, user_lat, user_lng, after)
        return self._personalized_recommend(user_id, page, page_size, after)

    def _hot_posts(self, page: int, page_size: int, after: Optional[str] = None) -> Tuple[int, List[Post], Optional[str]]:
        now = _utcnow()
        week_ago = now - timedelta(days=7)
        query = self.db.query(Post).filter(
            Post.is_private.is_(False),
            Post.created_at >= week_ago,
        )
        if after:
            cursor = decode_cursor(after)
            if cursor:
                cursor_ts, cursor_id = cursor
                query = query.filter(
                    (Post.created_at < cursor_ts) |
                    ((Post.created_at == cursor_ts) & (Post.id < cursor_id))
                )
        total = query.count()
        score = self.post_score_expr()
        posts = (
            query.order_by(
                score.desc(),
                Post.created_at.desc(),
            )
            .limit(page_size + 1)
            .all()
        )
        has_more = len(posts) > page_size
        if has_more:
            posts = posts[:page_size]
        next_cursor = encode_cursor_from_post(posts[-1]) if has_more and posts else None
        return total, posts, next_cursor

    def _personalized_recommend(
        self, user_id: Optional[int], page: int, page_size: int, after: Optional[str] = None
    ) -> Tuple[int, List[Post], Optional[str]]:
        query = self.db.query(Post).filter(Post.is_private.is_(False))

        if after:
            cursor = decode_cursor(after)
            if cursor:
                cursor_ts, cursor_id = cursor
                query = query.filter(
                    (Post.created_at < cursor_ts) |
                    ((Post.created_at == cursor_ts) & (Post.id < cursor_id))
                )

        if user_id and not after:
            # Interest/explore split only on first page (no cursor)
            user_tags = self._get_user_preference_tags(user_id)
            if user_tags:
                tag_ids = [t.id for t in user_tags]
                post_ids_with_tags = [
                    pt.post_id
                    for pt in self.db.query(PostTag).filter(PostTag.tag_id.in_(tag_ids)).all()
                ]
                interest_query = query.filter(Post.id.in_(post_ids_with_tags))
                explore_query = query.filter(~Post.id.in_(post_ids_with_tags))

                score = self.post_score_expr()
                interest_posts = interest_query.order_by(
                    score.desc(),
                    Post.created_at.desc(),
                ).limit(int(page_size * 0.8)).all()

                explore_posts = explore_query.order_by(
                    desc(Post.created_at)
                ).limit(int(page_size * 0.2) + 1).all()

                all_posts = interest_posts + explore_posts
                total = query.count()
                next_c = encode_cursor_from_post(all_posts[-1]) if len(all_posts) > page_size and all_posts else None
                return total, all_posts[:page_size], next_c

        total = query.count()
        score = self.post_score_expr()
        posts = (
            query.order_by(
                score.desc(),
                Post.created_at.desc(),
            )
            .limit(page_size + 1)
            .all()
        )
        has_more = len(posts) > page_size
        if has_more:
            posts = posts[:page_size]
        next_cursor = encode_cursor_from_post(posts[-1]) if has_more and posts else None
        return total, posts, next_cursor

    def _following_posts(
        self, user_id: int, page: int, page_size: int, after: Optional[str] = None
    ) -> Tuple[int, List[Post], Optional[str]]:
        follows = (
            self.db.query(UserFollow)
            .filter_by(follower_id=user_id)
            .all()
        )
        author_ids = [f.followee_id for f in follows]
        if not author_ids:
            return self._hot_posts(page, page_size, after)

        blocked = (
            self.db.query(UserBlock.blocked_id)
            .filter_by(blocker_id=user_id)
            .all()
        )
        blocked_ids = {b[0] for b in blocked}
        author_ids = [aid for aid in author_ids if aid not in blocked_ids]

        if not author_ids:
            return self._hot_posts(page, page_size, after)

        query = self.db.query(Post).filter(
            Post.is_private.is_(False),
            Post.user_id.in_(author_ids),
        )
        if after:
            cursor = decode_cursor(after)
            if cursor:
                cursor_ts, cursor_id = cursor
                query = query.filter(
                    (Post.created_at < cursor_ts) |
                    ((Post.created_at == cursor_ts) & (Post.id < cursor_id))
                )
        total = query.count()
        posts = (
            query.order_by(desc(Post.created_at))
            .limit(page_size + 1)
            .all()
        )
        has_more = len(posts) > page_size
        if has_more:
            posts = posts[:page_size]
        next_cursor = encode_cursor_from_post(posts[-1]) if has_more and posts else None
        return total, posts, next_cursor

    def _local_posts(
        self, city: str, page: int, page_size: int,
        user_lat: Optional[float] = None, user_lng: Optional[float] = None,
        after: Optional[str] = None,
    ) -> Tuple[int, List[Post], Optional[str]]:
        # Check in-memory cache (TTL 5 min) — only for first page without cursor
        if not after:
            cache_key = _cache_key_local(city, page, page_size, user_lat, user_lng)
            cached = _local_cache.get(cache_key)
            if cached and (_time.time() - cached[0]) < _LOCAL_CACHE_TTL:
                total_c, post_ids_c = cached[1]
                # 按缓存顺序重新加载当前会话内的 ORM 对象（过滤已被删除/私密的帖子）
                posts_c = []
                if post_ids_c:
                    rows = (
                        self.db.query(Post)
                        .filter(Post.id.in_(post_ids_c))
                        .all()
                    )
                    by_id = {p.id: p for p in rows}
                    posts_c = [
                        by_id[pid] for pid in post_ids_c
                        if pid in by_id and not by_id[pid].is_private
                    ]
                if posts_c or not post_ids_c:
                    next_c = encode_cursor_from_post(posts_c[-1]) if len(posts_c) >= page_size and posts_c else None
                    return total_c, posts_c, next_c
                # 缓存的帖子已全部失效 → 丢弃缓存，走正常查询
                _local_cache.pop(cache_key, None)

        query = self.db.query(Post).filter(
            Post.is_private.is_(False),
            Post.city.isnot(None),
            func.lower(Post.city) == city.strip().lower(),
        )

        if after:
            cursor = decode_cursor(after)
            if cursor:
                cursor_ts, cursor_id = cursor
                query = query.filter(
                    (Post.created_at < cursor_ts) |
                    ((Post.created_at == cursor_ts) & (Post.id < cursor_id))
                )

        fetch_multiplier = 3 if user_lat is not None and user_lng is not None else 1

        posts = (
            query.order_by(
                desc(func.coalesce(Post.read_count, 0)),
                Post.created_at.desc(),
            )
            .limit(page_size * fetch_multiplier + 1)
            .all()
        )

        if user_lat is not None and user_lng is not None:
            from web.backend.services.community import CommunityService
            svc = CommunityService(self.db)
            posts_with_dist = []
            posts_no_dist = []
            for p in posts:
                d = svc.calc_distance(user_lat, user_lng, getattr(p, "latitude", None), getattr(p, "longitude", None))
                if d is not None:
                    posts_with_dist.append((p, d))
                else:
                    posts_no_dist.append(p)
            posts_with_dist.sort(key=lambda x: x[1])
            posts = [p for p, _ in posts_with_dist[:page_size + 1]] + posts_no_dist
            posts = posts[:page_size + 1]

        total = query.count()
        has_more = len(posts) > page_size
        if has_more:
            posts = posts[:page_size]
        next_cursor = encode_cursor_from_post(posts[-1]) if has_more and posts else None

        if not after:
            _local_cache[cache_key] = (_time.time(), (total, [p.id for p in posts]))
        return total, posts, next_cursor

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

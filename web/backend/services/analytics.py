"""Analytics aggregation service — excludes test accounts only, deduplicates by phone.
 
Admin users are real users and ARE included in all metrics.
Only test/internal accounts (is_test=True) are excluded.

Page/feature names: see web/shared/page-names.json (single source of truth).
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from sqlalchemy import func, or_, text
from sqlalchemy.orm import Session

from web.backend.database.models import MedicalReport, Post, PostComment, PostLike, User
from web.backend.database.models import Conversation, Message, UserEvent
from web.backend.models.vasi import VASIAssessment


def _load_page_names() -> dict[str, str]:
    """Load canonical page names from shared JSON config."""
    json_path = os.path.join(os.path.dirname(__file__), "..", "..", "shared", "page-names.json")
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("pages", {})
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


PAGE_NAME_MAP = _load_page_names()


# Phone numbers belonging to test / internal accounts — excluded from all metrics.
# Synthetic test numbers only (the 13800138000 / 1371111xxxx range are reserved test
# numbers). Real operator numbers are NOT listed here. Override via EXCLUDED_PHONES env.
DEFAULT_EXCLUDED_PHONES = frozenset({
    "13711113333", "13711114444",
    "15899998888", "15899997777", "15899996666",
    "13800138000", "13900139001",
})


def _load_excluded_phones() -> frozenset:
    raw = os.environ.get("EXCLUDED_PHONES", "").strip()
    if not raw:
        return DEFAULT_EXCLUDED_PHONES
    return frozenset(part.strip() for part in raw.split(",") if part.strip())


EXCLUDED_PHONES = _load_excluded_phones()

FEATURE_USE_ELEMENT_IDS = (
    "tracker_btn_assess",
    "report_upload_btn",
    "header_nav_AI助手",
    "header_nav_测评",
    "header_nav_发现",
    "header_nav_我的",
    "bottom_nav_AI助手",
    "bottom_nav_测评",
    "bottom_nav_发现",
    "bottom_nav_我的",
    "community_fab_create",
    "community_fab_login",
    "header_btn_login",
)


class AnalyticsService:
    def __init__(self, db: Session):
        self.db: Session = db
        # Pre-compute UIDs to exclude from event-based queries
        self._excluded_uids: set[str] = self._load_excluded_uids()

    # ── helpers ──

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _day_bounds(target_date: date) -> tuple[datetime, datetime]:
        start = datetime.combine(target_date, time.min, tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        return start, end

    def _load_excluded_uids(self) -> set[str]:
        uid_rows = (
            self.db.query(User.uid)
            .filter(
                or_(
                    User.is_test == True,  # noqa: E712
                    User.is_admin == True,  # noqa: E712 — admin traffic isn't real user traffic
                    User.phone.in_(EXCLUDED_PHONES),
                ),
                User.uid.isnot(None),
            )
            .all()
        )
        return {r.uid for r in uid_rows if r.uid}

    def _excluded_uid_filter(self):
        # Preserve anonymous events (uid IS NULL): SQL ``uid NOT IN (set)``
        # evaluates to NULL for NULL uids, which filters them out. Anonymous
        # visitors are real traffic and must remain counted in UV/journey
        # analytics, so explicitly keep NULL uids when the exclusion set is
        # non-empty.
        if self._excluded_uids:
            return or_(
                UserEvent.uid.is_(None),
                ~UserEvent.uid.in_(self._excluded_uids),
            )
        return True  # type: ignore[return-value]

    def _real_user_filter(self):
        # Count real users only: exclude test accounts, admin accounts, and
        # phones in the exclusion allowlist. Keep users whose phone is NULL but
        # who have an email or uid — ``~phone.in_(set)`` evaluates to NULL for
        # NULL phones and would otherwise drop legitimate email-only / guest
        # users from total_users / new_users_today.
        return (
            User.is_test == False,  # noqa: E712
            User.is_admin == False,  # noqa: E712
            or_(
                User.phone.is_(None),
                ~User.phone.in_(EXCLUDED_PHONES),
            ),
        )

    def _uv_query(self):
        """Count distinct real visitors (uid or fingerprint, excluding test)."""
        return func.count(
            func.distinct(func.coalesce(UserEvent.uid, UserEvent.client_fingerprint))
        )

    def _excluded_user_ids(self) -> set[int]:
        uid_rows = (
            self.db.query(User.id)
            .filter(
                or_(
                    User.is_test == True,  # noqa: E712
                    User.phone.in_(EXCLUDED_PHONES),
                ),
            )
            .all()
        )
        return {r.id for r in uid_rows}

    def _count_today_active_users(self, start: datetime, end: datetime) -> int:
        excluded = self._excluded_user_ids()
        active_ids: set[int] = set()

        # AI提问: messages with role='user' → conversation → user_id
        ai_user_ids = (
            self.db.query(Conversation.user_id)
            .join(Message, Message.conversation_id == Conversation.conversation_id)
            .filter(
                Message.role == "user",
                Message.created_at >= start,
                Message.created_at < end,
                Conversation.user_id.isnot(None),
            )
            .distinct()
            .all()
        )
        active_ids.update(r.user_id for r in ai_user_ids if r.user_id not in excluded)

        # 上传照片/评估: vasi_assessments
        vasi_ids = (
            self.db.query(VASIAssessment.user_id)
            .filter(
                VASIAssessment.created_at >= start,
                VASIAssessment.created_at < end,
                VASIAssessment.user_id.isnot(None),
            )
            .distinct()
            .all()
        )
        active_ids.update(r.user_id for r in vasi_ids if r.user_id not in excluded)

        # 上传体检报告: medical_reports
        report_ids = (
            self.db.query(MedicalReport.user_id)
            .filter(
                MedicalReport.created_at >= start,
                MedicalReport.created_at < end,
                MedicalReport.user_id.isnot(None),
            )
            .distinct()
            .all()
        )
        active_ids.update(r.user_id for r in report_ids if r.user_id not in excluded)

        # 写白白日记: posts
        post_ids = (
            self.db.query(Post.user_id)
            .filter(
                Post.created_at >= start,
                Post.created_at < end,
                Post.user_id.isnot(None),
            )
            .distinct()
            .all()
        )
        active_ids.update(r.user_id for r in post_ids if r.user_id not in excluded)

        # 评论: post_comments
        comment_ids = (
            self.db.query(PostComment.user_id)
            .filter(
                PostComment.created_at >= start,
                PostComment.created_at < end,
                PostComment.user_id.isnot(None),
            )
            .distinct()
            .all()
        )
        active_ids.update(r.user_id for r in comment_ids if r.user_id not in excluded)

        # 点赞: post_likes
        like_ids = (
            self.db.query(PostLike.user_id)
            .filter(
                PostLike.created_at >= start,
                PostLike.created_at < end,
                PostLike.user_id.isnot(None),
            )
            .distinct()
            .all()
        )
        active_ids.update(r.user_id for r in like_ids if r.user_id not in excluded)

        return len(active_ids)

    # ── overview ──

    def get_overview(self) -> dict[str, int]:
        now = self._now()
        today_start, tomorrow_start = self._day_bounds(now.date())

        total_users = (
            self.db.query(
                func.count(
                    func.distinct(
                        func.coalesce(User.phone, User.email, User.uid)
                    )
                )
            )
            .filter(*self._real_user_filter())
            .scalar()
        ) or 0

        today_uv = (
            self.db.query(self._uv_query())
            .filter(self._excluded_uid_filter())
            .filter(UserEvent.created_at >= today_start)
            .filter(UserEvent.created_at < tomorrow_start)
            .scalar()
        ) or 0

        today_pv = (
            self.db.query(func.count(UserEvent.id))
            .filter(self._excluded_uid_filter())
            .filter(UserEvent.event_type == "page_view")
            .filter(UserEvent.created_at >= today_start)
            .filter(UserEvent.created_at < tomorrow_start)
            .scalar()
        ) or 0

        new_users_today = (
            self.db.query(func.count(User.id))
            .filter(*self._real_user_filter())
            .filter(User.created_at >= today_start)
            .filter(User.created_at < tomorrow_start)
            .scalar()
        ) or 0

        today_active_users = self._count_today_active_users(today_start, tomorrow_start)

        return {
            "total_users": total_users,
            "today_uv": today_uv,
            "today_pv": today_pv,
            "new_users_today": new_users_today,
            "today_active_users": today_active_users,
        }

    # ── trend ────────────────────────────────────────────────────────

    def get_trend(self, days: int = 30) -> dict[str, Any]:
        today = self._now().date()
        items: list[dict[str, int | str]] = []

        for offset in range(days - 1, -1, -1):
            target_date = today - timedelta(days=offset)
            day_start, day_end = self._day_bounds(target_date)

            uv = (
                self.db.query(self._uv_query())
                .filter(self._excluded_uid_filter())
                .filter(UserEvent.created_at >= day_start)
                .filter(UserEvent.created_at < day_end)
                .scalar()
            ) or 0

            pv = (
                self.db.query(func.count(UserEvent.id))
                .filter(self._excluded_uid_filter())
                .filter(UserEvent.event_type == "page_view")
                .filter(UserEvent.created_at >= day_start)
                .filter(UserEvent.created_at < day_end)
                .scalar()
            ) or 0

            new_users = (
                self.db.query(func.count(User.id))
                .filter(*self._real_user_filter())
                .filter(User.created_at >= day_start)
                .filter(User.created_at < day_end)
                .scalar()
            ) or 0

            items.append({
                "date": target_date.isoformat(),
                "uv": uv,
                "pv": pv,
                "new_users": new_users,
            })

        return {"days": days, "items": items}

    # ── registration trend (North Star) ──────────────────────────────

    def get_registration_trend(self, days: int = 14) -> list[dict[str, Any]]:
        """Cumulative registered user count per day (real users only, phone-deduped)."""
        today = self._now().date()
        start_date = today - timedelta(days=days - 1)
        start_of_range = self._day_bounds(start_date)[0]

        # Base count: real users registered BEFORE the range starts
        base_count = (
            self.db.query(
                func.count(
                    func.distinct(
                        func.coalesce(User.phone, User.email, User.uid)
                    )
                )
            )
            .filter(*self._real_user_filter())
            .filter(User.created_at < start_of_range)
            .scalar()
        ) or 0

        items: list[dict[str, Any]] = []
        cumulative = base_count

        for offset in range(days):
            target_date = start_date + timedelta(days=offset)
            day_start, day_end = self._day_bounds(target_date)
            new_users = (
                self.db.query(func.count(User.id))
                .filter(*self._real_user_filter())
                .filter(User.created_at >= day_start)
                .filter(User.created_at < day_end)
                .scalar()
            ) or 0
            cumulative += new_users
            items.append({
                "date": target_date.isoformat(),
                "new_users": new_users,
                "cumulative_users": cumulative,
            })

        return items

    # ── user journey / path analysis ─────────────────────────────────

    def get_user_journeys(self, days: int = 7, limit: int = 50) -> dict[str, Any]:
        """User journey analysis from page_view events — builds Sankey data."""
        start_at = self._now() - timedelta(days=days)

        events = (
            self.db.query(
                UserEvent.uid,
                UserEvent.session_id,
                UserEvent.page_path,
                UserEvent.created_at,
            )
            .filter(
                UserEvent.event_type == "page_view",
                UserEvent.created_at >= start_at,
                self._excluded_uid_filter(),
                UserEvent.page_path.isnot(None),
            )
            .order_by(UserEvent.session_id, UserEvent.created_at)
            .all()
        )

        def _normalize(path: str) -> str:
            if path in PAGE_NAME_MAP:
                return PAGE_NAME_MAP[path]
            for prefix, name in PAGE_NAME_MAP.items():
                if prefix not in ("/", "/chat") and path.startswith(prefix):
                    return name
            return path.split("?")[0]

        # Group by session
        sessions: dict[str, list[str]] = defaultdict(list)
        for e in events:
            key = f"{e.uid or 'anon'}:{e.session_id}"
            sessions[key].append(_normalize(e.page_path))

        # Deduplicate consecutive same-page visits
        for key in sessions:
            deduped: list[str] = []
            for p in sessions[key]:
                if not deduped or deduped[-1] != p:
                    deduped.append(p)
            sessions[key] = deduped

        # Count transition pairs for Sankey
        transitions: dict[tuple[str, str], int] = defaultdict(int)
        path_counts: dict[str, int] = defaultdict(int)
        for pages in sessions.values():
            if len(pages) >= 1:
                path_counts[" → ".join(pages)] += 1
            for i in range(len(pages) - 1):
                transitions[(pages[i], pages[i + 1])] += 1

        # Top paths
        top_paths = sorted(path_counts.items(), key=lambda x: -x[1])[:20]

        # Sankey nodes + links
        node_set: set[str] = set()
        for src, tgt in transitions:
            node_set.add(src)
            node_set.add(tgt)
        nodes = sorted(node_set)
        node_index = {n: i for i, n in enumerate(nodes)}

        links = [
            {
                "source": node_index[src],
                "target": node_index[tgt],
                "value": count,
            }
            for (src, tgt), count in sorted(
                transitions.items(), key=lambda x: -x[1]
            )[:limit]
        ]

        return {
            "nodes": nodes,
            "links": links,
            "top_paths": [{"path": p, "count": c} for p, c in top_paths],
            "total_sessions": len(sessions),
        }

    # ── funnel ───────────────────────────────────────────────────────

    def get_funnel(self, days: int = 30) -> list[dict[str, Any]]:
        start_at = self._now() - timedelta(days=days)

        visit = (
            self.db.query(self._uv_query())
            .filter(self._excluded_uid_filter())
            .filter(UserEvent.event_type == "page_view")
            .filter(UserEvent.created_at >= start_at)
            .scalar()
        ) or 0

        register = (
            self.db.query(func.count(User.id))
            .filter(*self._real_user_filter())
            .filter(User.created_at >= start_at)
            .scalar()
        ) or 0

        login = (
            self.db.query(func.count(func.distinct(UserEvent.uid)))
            .filter(self._excluded_uid_filter())
            .filter(UserEvent.event_type == "login_success")
            .filter(UserEvent.uid.isnot(None))
            .filter(UserEvent.created_at >= start_at)
            .scalar()
        ) or 0

        feature_use_click_uids = (
            self.db.query(func.count(func.distinct(UserEvent.uid)))
            .filter(self._excluded_uid_filter())
            .filter(UserEvent.event_type == "click")
            .filter(UserEvent.uid.isnot(None))
            .filter(UserEvent.created_at >= start_at)
            .filter(UserEvent.element_id.in_(FEATURE_USE_ELEMENT_IDS))
            .scalar()
        ) or 0

        # AI问答 users from conversations/messages
        ai_chat_uids = (
            self.db.query(func.count(func.distinct(Conversation.user_id)))
            .join(Message, Message.conversation_id == Conversation.conversation_id)
            .filter(
                Message.role == "user",
                Message.created_at >= start_at,
                Conversation.user_id.isnot(None),
                ~Conversation.user_id.in_(self._excluded_user_ids()),
            )
            .scalar()
        ) or 0

        feature_use = feature_use_click_uids + ai_chat_uids

        steps: list[dict[str, Any]] = []
        previous: int | None = None
        for name, count in (
            ("访问UV", visit),
            ("注册用户", register),
            ("登录UV", login),
            ("使用功能UV", feature_use),
        ):
            rate = round(count / previous, 4) if previous else None
            steps.append({"name": name, "count": count, "rate_from_prev": rate})
            previous = count

        return steps

    # ── feature usage ────────────────────────────────────────────────

    def get_feature_usage(self, days: int = 7) -> list[dict[str, int | str]]:
        start_at = self._now() - timedelta(days=days)
        excluded = self._excluded_user_ids()

        # AI问答: conversations → messages where role='user'
        ai_uv = (
            self.db.query(func.count(func.distinct(Conversation.user_id)))
            .join(Message, Message.conversation_id == Conversation.conversation_id)
            .filter(
                Message.role == "user",
                Message.created_at >= start_at,
                Conversation.user_id.isnot(None),
                ~Conversation.user_id.in_(excluded),
            )
            .scalar()
        ) or 0
        ai_pv = (
            self.db.query(func.count(Message.id))
            .join(Conversation, Conversation.conversation_id == Message.conversation_id)
            .filter(
                Message.role == "user",
                Message.created_at >= start_at,
            )
            .scalar()
        ) or 0

        vasi_uv = (
            self.db.query(func.count(func.distinct(VASIAssessment.user_id)))
            .filter(VASIAssessment.created_at >= start_at)
            .scalar()
        ) or 0
        vasi_pv = (
            self.db.query(func.count(VASIAssessment.id))
            .filter(VASIAssessment.created_at >= start_at)
            .scalar()
        ) or 0

        report_uv = (
            self.db.query(func.count(func.distinct(MedicalReport.user_id)))
            .filter(MedicalReport.created_at >= start_at)
            .scalar()
        ) or 0
        report_pv = (
            self.db.query(func.count(MedicalReport.id))
            .filter(MedicalReport.created_at >= start_at)
            .scalar()
        ) or 0

        post_uv = (
            self.db.query(func.count(func.distinct(Post.user_id)))
            .filter(Post.created_at >= start_at)
            .scalar()
        ) or 0
        post_pv = (
            self.db.query(func.count(Post.id))
            .filter(Post.created_at >= start_at)
            .scalar()
        ) or 0

        comment_uv = (
            self.db.query(func.count(func.distinct(PostComment.user_id)))
            .filter(PostComment.created_at >= start_at)
            .scalar()
        ) or 0
        comment_pv = (
            self.db.query(func.count(PostComment.id))
            .filter(PostComment.created_at >= start_at)
            .scalar()
        ) or 0

        like_uv = (
            self.db.query(func.count(func.distinct(PostLike.user_id)))
            .filter(PostLike.created_at >= start_at)
            .scalar()
        ) or 0
        like_pv = (
            self.db.query(func.count(PostLike.id))
            .filter(PostLike.created_at >= start_at)
            .scalar()
        ) or 0

        encyclopedia_uv = (
            self.db.query(self._uv_query())
            .filter(self._excluded_uid_filter())
            .filter(UserEvent.event_type == "page_view")
            .filter(UserEvent.page_path.like("/encyclopedia%"))
            .filter(UserEvent.created_at >= start_at)
            .scalar()
        ) or 0
        encyclopedia_pv = (
            self.db.query(func.count(UserEvent.id))
            .filter(self._excluded_uid_filter())
            .filter(UserEvent.event_type == "page_view")
            .filter(UserEvent.page_path.like("/encyclopedia%"))
            .filter(UserEvent.created_at >= start_at)
            .scalar()
        ) or 0

        return [
            {"name": "AI问答", "uv": ai_uv, "pv": ai_pv},
            {"name": "追踪评估", "uv": vasi_uv, "pv": vasi_pv},
            {"name": "上传体检报告", "uv": report_uv, "pv": report_pv},
            {"name": "发帖", "uv": post_uv, "pv": post_pv},
            {"name": "评论", "uv": comment_uv, "pv": comment_pv},
            {"name": "点赞", "uv": like_uv, "pv": like_pv},
            {"name": "浏览百科", "uv": encyclopedia_uv, "pv": encyclopedia_pv},
        ]

    # ── page views ───────────────────────────────────────────────────

    def get_page_views(self, days: int = 7) -> list[dict[str, Any]]:
        start_at = self._now() - timedelta(days=days)
        excluded = self._excluded_user_ids()

        results = (
            self.db.query(
                UserEvent.page_path,
                func.count(func.distinct(UserEvent.uid)).label("uv"),
                func.count(UserEvent.id).label("pv"),
            )
            .filter(UserEvent.event_type == "page_view")
            .filter(UserEvent.created_at >= start_at)
            .filter(self._excluded_uid_filter())
            .group_by(UserEvent.page_path)
            .order_by(func.count(UserEvent.id).desc())
            .all()
        )
        return [
            {"page": row.page_path or "/", "uv": int(row.uv), "pv": int(row.pv)}
            for row in results
        ]

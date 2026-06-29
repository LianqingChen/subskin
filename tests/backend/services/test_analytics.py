from __future__ import annotations

from datetime import datetime, timedelta, timezone

from web.backend.database.models import User, UserEvent
from web.backend.services.analytics import AnalyticsService


def _user(
    *,
    username: str,
    uid: str,
    created_at: datetime,
    phone: str | None = None,
    email: str | None = None,
    is_test: bool = False,
    is_admin: bool = False,
) -> User:
    return User(
        username=username,
        uid=uid,
        phone=phone,
        email=email,
        hashed_password="hashed",  # pragma: allowlist secret
        is_active=True,
        is_test=is_test,
        is_admin=is_admin,
        created_at=created_at,
        updated_at=created_at,
    )


def _event(
    *,
    session_id: str,
    event_type: str,
    created_at: datetime,
    uid: str | None = None,
    page_path: str | None = None,
    client_fingerprint: str | None = None,
) -> UserEvent:
    return UserEvent(
        uid=uid,
        session_id=session_id,
        event_type=event_type,
        page_path=page_path,
        client_fingerprint=client_fingerprint,
        created_at=created_at,
    )


def test_get_overview_excludes_test_accounts_and_deduplicates_total_users(db_session):
    now = datetime.now(timezone.utc)
    today = now - timedelta(hours=1)

    # NOTE: users.phone has a UNIQUE constraint (see database/models.py), so the
    # historical "two real users sharing one phone" dedup scenario is impossible
    # under the current schema — phone binding is 1:1. Give each real user a
    # distinct phone; the analytics coalesce(phone, email, uid) dedup is still
    # exercised (phone→email→uid fallback for guest/email-only users).
    users = [
        _user(username="real-1", uid="real-1", phone="18600000001", created_at=today),
        _user(
            username="real-2",
            uid="real-2",
            phone="18600000002",
            created_at=today,
        ),
        _user(
            username="email-only",
            uid="email-1",
            email="person@example.com",
            created_at=today,
        ),
        _user(username="guest", uid="guest-1", created_at=today),
        _user(
            username="test-user",
            uid="test-uid",
            phone="13711113333",
            created_at=today,
            is_test=True,
        ),
        _user(
            username="admin-user",
            uid="admin-uid",
            phone="15810000000",
            created_at=today,
            is_admin=True,
        ),
        _user(
            username="internal-phone",
            uid="internal-phone-uid",
            phone="13800138000",
            created_at=today,
        ),
    ]
    db_session.add_all(users)
    db_session.commit()

    db_session.add_all(
        [
            _event(
                session_id="s-real-1",
                uid="real-1",
                event_type="page_view",
                page_path="/",
                created_at=now,
            ),
            _event(
                session_id="s-real-2",
                uid="real-2",
                event_type="page_view",
                page_path="/chat",
                created_at=now,
            ),
            _event(
                session_id="s-guest",
                event_type="page_view",
                page_path="/encyclopedia/article-1",
                client_fingerprint="fp-guest",
                created_at=now,
            ),
            _event(
                session_id="s-test",
                uid="test-uid",
                event_type="page_view",
                page_path="/community",
                created_at=now,
            ),
            _event(
                session_id="s-admin",
                uid="admin-uid",
                event_type="page_view",
                page_path="/dashboard",
                created_at=now,
            ),
        ]
    )
    db_session.commit()

    overview = AnalyticsService(db_session).get_overview()

    assert overview == {
        "total_users": 4,
        "today_uv": 3,
        "today_pv": 3,
        "new_users_today": 4,
        # No AI chat / VASI / report / community actions in the fixture, so the
        # action-based active-user count is 0. (Page-view activity is captured
        # separately by today_uv.)
        "today_active_users": 0,
    }


def test_get_registration_trend_returns_cumulative_deduplicated_counts(db_session):
    now = datetime.now(timezone.utc)
    today = now.date()
    start_date = today - timedelta(days=2)

    users = [
        _user(
            username="baseline",
            uid="baseline-uid",
            phone="18600000010",
            created_at=datetime.combine(
                start_date - timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc
            ),
        ),
        _user(
            username="day-1-a",
            uid="day-1-a-uid",
            phone="18600000011",
            created_at=datetime.combine(
                start_date, datetime.min.time(), tzinfo=timezone.utc
            )
            + timedelta(hours=1),
        ),
        _user(
            username="day-1-b",
            uid="day-1-b-uid",
            phone="18600000012",
            created_at=datetime.combine(
                start_date, datetime.min.time(), tzinfo=timezone.utc
            )
            + timedelta(hours=2),
        ),
        _user(
            username="day-2",
            uid="day-2-uid",
            email="day2@example.com",
            created_at=datetime.combine(
                start_date + timedelta(days=1),
                datetime.min.time(),
                tzinfo=timezone.utc,
            )
            + timedelta(hours=3),
        ),
        _user(
            username="day-3",
            uid="day-3-uid",
            created_at=datetime.combine(
                start_date + timedelta(days=2),
                datetime.min.time(),
                tzinfo=timezone.utc,
            )
            + timedelta(hours=4),
        ),
        _user(
            username="excluded-test",
            uid="excluded-test-uid",
            phone="13711114444",
            created_at=datetime.combine(
                start_date + timedelta(days=1),
                datetime.min.time(),
                tzinfo=timezone.utc,
            )
            + timedelta(hours=5),
            is_test=True,
        ),
        _user(
            username="excluded-admin",
            uid="excluded-admin-uid",
            phone="17319000000",
            created_at=datetime.combine(
                start_date + timedelta(days=2),
                datetime.min.time(),
                tzinfo=timezone.utc,
            )
            + timedelta(hours=6),
            is_admin=True,
        ),
    ]
    db_session.add_all(users)
    db_session.commit()

    items = AnalyticsService(db_session).get_registration_trend(3)

    assert items == [
        {
            "date": start_date.isoformat(),
            "new_users": 2,
            "cumulative_users": 3,
        },
        {
            "date": (start_date + timedelta(days=1)).isoformat(),
            "new_users": 1,
            "cumulative_users": 4,
        },
        {
            "date": (start_date + timedelta(days=2)).isoformat(),
            "new_users": 1,
            "cumulative_users": 5,
        },
    ]


def test_get_user_journeys_excludes_test_sessions_and_builds_transitions(db_session):
    now = datetime.now(timezone.utc)
    real_user = _user(
        username="journey-user",
        uid="journey-uid",
        phone="18600000021",
        created_at=now - timedelta(days=2),
    )
    test_user = _user(
        username="journey-test",
        uid="journey-test-uid",
        phone="15899998888",
        created_at=now - timedelta(days=2),
        is_test=True,
    )
    db_session.add_all([real_user, test_user])
    db_session.commit()

    db_session.add_all(
        [
            _event(
                session_id="session-1",
                uid="journey-uid",
                event_type="page_view",
                page_path="/",
                created_at=now - timedelta(hours=5),
            ),
            _event(
                session_id="session-1",
                uid="journey-uid",
                event_type="page_view",
                page_path="/encyclopedia/article-1",
                created_at=now - timedelta(hours=4, minutes=50),
            ),
            _event(
                session_id="session-1",
                uid="journey-uid",
                event_type="page_view",
                page_path="/chat",
                created_at=now - timedelta(hours=4, minutes=40),
            ),
            _event(
                session_id="session-1",
                uid="journey-uid",
                event_type="page_view",
                page_path="/chat",
                created_at=now - timedelta(hours=4, minutes=30),
            ),
            _event(
                session_id="session-1",
                uid="journey-uid",
                event_type="page_view",
                page_path="/tracker/weekly",
                created_at=now - timedelta(hours=4, minutes=20),
            ),
            _event(
                session_id="session-2",
                event_type="page_view",
                page_path="/community/topic-1",
                client_fingerprint="anon-fp",
                created_at=now - timedelta(hours=3),
            ),
            _event(
                session_id="session-2",
                event_type="page_view",
                page_path="/profile",
                client_fingerprint="anon-fp",
                created_at=now - timedelta(hours=2, minutes=50),
            ),
            _event(
                session_id="session-3",
                uid="journey-test-uid",
                event_type="page_view",
                page_path="/dashboard",
                created_at=now - timedelta(hours=1),
            ),
        ]
    )
    db_session.commit()

    result = AnalyticsService(db_session).get_user_journeys(days=7, limit=20)

    assert result["total_sessions"] == 2
    # Page names follow the canonical page-names.json single source of truth
    # (小白百科 / 测评 / 发现 / AI助手 / 个人中心), NOT the deprecated
    # 白白百科 / 病情追踪 / 病友社区 names listed in old_names_do_not_use.
    assert result["top_paths"] == [
        {"path": "AI助手 → 小白百科 → AI助手 → 测评", "count": 1},
        {"path": "发现 → 个人中心", "count": 1},
    ]

    assert result["nodes"] == ["AI助手", "个人中心", "发现", "小白百科", "测评"]
    assert result["links"] == [
        {"source": 0, "target": 3, "value": 1},
        {"source": 3, "target": 0, "value": 1},
        {"source": 0, "target": 4, "value": 1},
        {"source": 2, "target": 1, "value": 1},
    ]

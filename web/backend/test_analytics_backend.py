import asyncio
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("SECRET_KEY", "test-secret-key")

import pytest

from web.backend.api.user import _get_user_response
from web.backend.database.models import User, UserEvent
from web.backend.models.user import Token


def test_user_event_has_analytics_indexes():
    index_names = {index.name for index in UserEvent.__table__.indexes}

    assert "idx_events_created_type" in index_names
    assert "idx_events_created_type_path" in index_names
    assert "idx_events_created_uid" in index_names


def test_user_response_includes_is_admin_flag():
    user = User(
        id=1,
        uid="u_1",
        username="admin-user",
        is_active=True,
        is_admin=True,
    )

    response = _get_user_response(user, include_private=True, include_sensitive=True)

    assert response["is_admin"] is True


def test_token_response_model_supports_user_is_admin():
    payload = {
        "access_token": "access",
        "refresh_token": "refresh",
        "token_type": "bearer",
        "user": {
            "id": 1,
            "uid": "u_1",
            "username": "admin-user",
            "email": "admin@example.com",
            "phone": "15810000000",
            "avatar_url": None,
            "patient_relation": None,
            "wechat_id": None,
            "alipay_id": None,
            "privacy_mode": True,
            "is_active": True,
            "is_admin": True,
            "created_at": "2026-04-21T00:00:00+00:00",
        },
    }

    token = Token.model_validate(payload)

    assert token.model_dump()["user"]["is_admin"] is True


def test_analytics_router_is_registered_on_main_app():
    from web.backend.app.main import app

    route_paths = {
        path for route in app.routes if (path := getattr(route, "path", None)) is not None
    }

    assert "/api/analytics/overview" in route_paths
    assert "/api/analytics/trend" in route_paths
    assert "/api/analytics/page-views" in route_paths
    assert "/api/analytics/funnel" in route_paths
    assert "/api/analytics/feature-usage" in route_paths


def test_get_admin_user_rejects_non_admin_user():
    from web.backend.api.analytics import get_admin_user

    with pytest.raises(Exception) as exc_info:
        _ = asyncio.run(
            get_admin_user(User(id=2, username="plain", is_active=True, is_admin=False))
        )

    assert getattr(exc_info.value, "status_code", None) == 403


def test_backend_entrypoint_import_command_works_from_backend_dir():
    env = os.environ.copy()
    env.setdefault("SECRET_KEY", "test-secret-key")

    result = subprocess.run(
        [sys.executable, "-c", "from web.backend.app.main import app; print('OK')"],
        cwd=Path(__file__).resolve().parent,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().endswith("OK")

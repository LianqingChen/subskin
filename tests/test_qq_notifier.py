import json
import os
from typing import Any

import pytest
import requests

from src.notifications import qq_notifier as qq


class DummyResponse:
    def __init__(self, status_code: int, json_data: Any = None):
        self.status_code = status_code
        self._json = json_data or {}
        self.text = json.dumps(self._json)

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"Status {self.status_code}")


def test_qq_notifier_initialization():
    n = qq.QQBotNotifier(base_url="http://localhost:5700", token="tok", qq_id=12345)
    assert getattr(n, "base_url", None) == "http://localhost:5700"
    assert getattr(n, "token", None) == "tok"
    assert getattr(n, "qq_id", None) == 12345


def test_make_request_success(monkeypatch):
    n = qq.QQBotNotifier(base_url="http://localhost:5700", token="tok", qq_id=12345)

    dummy = DummyResponse(200, {"ret": 0, "data": {}})

    monkeypatch.setattr(requests, "post", lambda *a, **k: dummy)
    res = n._make_request("/send", {"message": "hi"})
    assert res is True or res == dummy


def test_make_request_429_retry(monkeypatch):
    n = qq.QQBotNotifier(base_url="http://localhost:5700", token="tok", qq_id=12345)

    # Side effect: first 429, then 200
    calls = {"count": 0}

    def side_effect(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            return DummyResponse(429, {"error": "Too Many Requests"})
        return DummyResponse(200, {"ret": 0, "data": {}})

    monkeypatch.setattr(requests, "post", side_effect)
    res = n._make_request("/send", {"message": "hi"})
    assert calls["count"] >= 2
    assert res is True or res == DummyResponse(200)


def test_send_private_message(monkeypatch):
    n = qq.QQBotNotifier(base_url="http://localhost:5700", token="tok", qq_id=12345)
    monkeypatch.setattr(n, "_make_request", lambda *args, **kwargs: True)
    ok = n.send_private_message(user_id=111, message="hello")
    assert ok is True


def test_send_group_message(monkeypatch):
    n = qq.QQBotNotifier(base_url="http://localhost:5700", token="tok", qq_id=12345)
    monkeypatch.setattr(n, "_make_request", lambda *args, **kwargs: True)
    ok = n.send_group_message(group_id=222, message="hello group")
    assert ok is True


def test_send_message_private_and_group(monkeypatch):
    n = qq.QQBotNotifier(base_url="http://localhost:5700", token="tok", qq_id=12345)
    monkeypatch.setattr(n, "_make_request", lambda *args, **kwargs: True)
    assert n.send_message(target_id=333, message="m", message_type="PRIVATE") is True
    assert n.send_message(target_id=444, message="m", message_type="GROUP") is True


def test_connection_method(monkeypatch):
    n = qq.QQBotNotifier(base_url="http://localhost:5700", token="tok", qq_id=12345)
    monkeypatch.setattr(n, "_make_request", lambda *a, **k: True)
    assert n.test_connection() is True


def test_format_functions():
    daily = {"date": "2026-01-01", "items": ["A", "B"]}
    assert isinstance(qq.format_daily_notification(daily), str)
    error = {"error": "Something went wrong"}
    assert isinstance(qq.format_error_notification(error), str)
    status = {"system": "OK"}
    assert isinstance(qq.format_system_status_notification(status), str)


def test_notification_manager_and_env(monkeypatch):
    mgr = qq.NotificationManager()
    n = qq.QQBotNotifier(base_url="http://localhost:5700", token="tok", qq_id=12345)
    mgr.register("qq", n)
    assert mgr.get("qq") is n

    # Test creation from environment with mocked getenv
    monkeypatch.setenv("QQ_BASE_URL", "http://localhost:5700")
    monkeypatch.setenv("QQ_TOKEN", "tok")
    monkeypatch.setenv("QQ_QQ_ID", "12345")
    created = qq.create_notifier_from_env()
    assert isinstance(created, qq.QQBotNotifier)

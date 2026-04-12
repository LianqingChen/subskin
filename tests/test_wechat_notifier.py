import pytest

from src.notifications import wechat_notifier as wechat


def test_wechat_notifier_initialization():
    w = wechat.WeChatNotifier(cli_path="/usr/local/bin/openclaw", api_key="dummy")
    assert w is not None


def test_send_message_with_mock(monkeypatch):
    w = wechat.WeChatNotifier(cli_path="/usr/local/bin/openclaw", api_key="dummy")

    class DummyProc:
        def __init__(self, returncode=0, stdout=b"ok"):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = b""

    def fake_run(*args, **kwargs):
        return DummyProc(0, b"ok")

    # patch the subprocess.run used inside wechat_notifier
    monkeypatch.setattr(wechat.subprocess, "run", fake_run, raising=False)
    ok = w.send_message(title="Daily", body="All good")
    assert ok is True


def test_format_daily_summary():
    summary = {"state": "ok", "text": "Everything is fine"}
    s = wechat.format_daily_summary(summary)
    assert isinstance(s, str)
    assert "Everything is fine" in s


def test_send_daily_summary(monkeypatch):
    w = wechat.WeChatNotifier(cli_path="/usr/local/bin/openclaw", api_key="dummy")
    monkeypatch.setattr(w, "send_message", lambda title, body: True)
    summary = {"state": "ok", "text": "All good"}
    assert w.send_daily_summary(summary) is True


def test_send_error_alert(monkeypatch):
    w = wechat.WeChatNotifier(cli_path="/usr/local/bin/openclaw", api_key="dummy")
    monkeypatch.setattr(w, "send_message", lambda title, body: True)
    error_info = {"error": "Something failed"}
    assert w.send_error_alert(error_info) is True


def test_subprocess_error_handling(monkeypatch):
    w = wechat.WeChatNotifier(cli_path="/usr/local/bin/openclaw", api_key="dummy")

    class FailProc:
        def __init__(self, *args, **kwargs):
            self.returncode = 1
            self.stdout = b""
            self.stderr = b"err"

    def fail_run(*args, **kwargs):
        return FailProc()

    monkeypatch.setattr(wechat.subprocess, "run", fail_run, raising=False)
    with pytest.raises(RuntimeError):
        w.send_message(title="Daily", body="Failed")


def test_message_formatting_various_states():
    s_ok = wechat.format_daily_summary({"state": "ok", "text": "All good"})
    s_warn = wechat.format_daily_summary({"state": "warn", "text": "Warning"})
    s_crit = wechat.format_daily_summary({"state": "critical", "text": "Critical"})
    assert isinstance(s_ok, str)
    assert isinstance(s_warn, str)
    assert isinstance(s_crit, str)
    assert "All good" in s_ok or "OK" in s_ok
    assert "Warning" in s_warn or "⚠" in s_warn
    assert "Critical" in s_crit or "❗" in s_crit

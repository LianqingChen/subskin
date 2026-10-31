"""接口层：验证码发送 IP 限流持久化、全站上限 429、注册年龄确认、健康授权门槛。"""

import io
from unittest.mock import patch

from PIL import Image

from web.backend.database.models import UserConsent
from web.backend.models.rate_limit import RateLimitEvent


@patch("web.backend.api.user.send_sms", return_value=(True, None))
def test_code_send_ip_limit_is_persisted(_send, client, db_session, monkeypatch):
    monkeypatch.setenv("CODE_SEND_IP_LIMIT", "2")
    for i in range(2):
        r = client.post("/api/user/send-sms", json={"phone": f"1380013800{i}"})
        assert r.status_code == 200, r.text
    r = client.post("/api/user/send-sms", json={"phone": "13800138009"})
    assert r.status_code == 429
    assert db_session.query(RateLimitEvent).filter_by(bucket="code_send_ip").count() == 2


@patch("web.backend.api.user.send_sms", return_value=(True, None))
def test_sms_global_cap_returns_429(_send, client, monkeypatch):
    monkeypatch.setenv("SMS_GLOBAL_DAILY_CAP", "1")
    assert client.post("/api/user/send-sms", json={"phone": "13900139000"}).status_code == 200
    r = client.post("/api/user/send-sms", json={"phone": "13900139001"})
    assert r.status_code == 429
    assert "短信服务今日繁忙" in r.json()["detail"]


@patch("web.backend.api.user.verify_sms_code", return_value=True)
def test_register_by_phone_records_age_consent(_verify, client, db_session):
    r = client.post(
        "/api/user/register-by-phone",
        json={"phone": "13700137000", "code": "123456", "age_confirmed": True},
    )
    assert r.status_code == 200, r.text
    rows = db_session.query(UserConsent).filter_by(consent_type="age_18").all()
    assert len(rows) == 1 and rows[0].is_active


@patch("web.backend.api.user.verify_sms_code", return_value=True)
def test_register_without_age_flag_still_works(_verify, client, db_session):
    r = client.post("/api/user/register-by-phone", json={"phone": "13700137001", "code": "123456"})
    assert r.status_code == 200, r.text
    assert db_session.query(UserConsent).filter_by(consent_type="age_18").count() == 0


def _jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), (180, 140, 120)).save(buf, format="JPEG")
    return buf.getvalue()


def test_vasi_upload_requires_health_consent_when_enforced(client, auth_headers, monkeypatch):
    monkeypatch.setenv("REQUIRE_HEALTH_DATA_CONSENT", "1")
    r = client.post(
        "/api/vasi/assess",
        headers=auth_headers,
        files={"image": ("a.jpg", _jpeg(), "image/jpeg")},
        data={"body_site": "face"},
    )
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "health_data_consent_required"


def test_rgb_upload_requires_health_consent_when_enforced(client, auth_headers, monkeypatch):
    monkeypatch.setenv("REQUIRE_HEALTH_DATA_CONSENT", "1")
    r = client.post(
        "/api/vasi/segmentation-jobs",
        headers=auth_headers,
        files={"image": ("a.jpg", _jpeg(), "image/jpeg")},
        data={"body_site": "face", "idempotency_key": "test-key-0001"},
    )
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "health_data_consent_required"


def test_rgb_upload_passes_consent_gate_after_consent(client, auth_headers, monkeypatch):
    monkeypatch.setenv("REQUIRE_HEALTH_DATA_CONSENT", "1")
    client.post(
        "/api/consent/record", headers=auth_headers,
        json={"consent_type": "health_data", "version": "1.0", "source": "vasi_upload"},
    )
    monkeypatch.setattr("web.backend.api.rgb_segmentation.worker_ready", lambda: False)
    r = client.post(
        "/api/vasi/segmentation-jobs",
        headers=auth_headers,
        files={"image": ("a.jpg", _jpeg(), "image/jpeg")},
        data={"body_site": "face", "idempotency_key": "test-key-0002"},
    )
    assert r.status_code == 503  # past the consent gate; stopped by the (stubbed) worker check


def test_consent_record_accepts_health_data_and_rejects_unknown(client, auth_headers):
    ok = client.post(
        "/api/consent/record", headers=auth_headers,
        json={"consent_type": "health_data", "version": "1.0", "source": "vasi_upload"},
    )
    assert ok.status_code == 200, ok.text
    status = client.get("/api/consent/status", headers=auth_headers).json()
    assert status["health_data"]["version"] == "1.0"
    bad = client.post(
        "/api/consent/record", headers=auth_headers,
        json={"consent_type": "anything", "version": "1.0"},
    )
    assert bad.status_code == 400

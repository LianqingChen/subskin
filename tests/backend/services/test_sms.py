"""
Tests for SMS service
"""

import os
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from web.backend.services.sms import (
    generate_code,
    create_sms_code,
    verify_sms_code,
    send_sms,
    _mark_local_code_used,
    _increment_local_attempt,
)
from web.backend.database.models import SMSCode


# ── generate_code ──


def test_generate_code_length():
    code = generate_code()
    assert len(code) == 6
    assert isinstance(code, str)


def test_generate_code_format():
    code = generate_code()
    assert code.isdigit()


def test_generate_code_random_unique():
    codes = set()
    for _ in range(100):
        codes.add(generate_code())
    assert len(codes) > 50


# ── create_sms_code ──


def test_create_sms_code_format(db_session):
    code = create_sms_code(db_session, "13800138000")
    assert len(code) == 6
    assert code.isdigit()


def test_create_sms_code_invalidates_previous(db_session):
    phone = "13800138000"
    first_code = create_sms_code(db_session, phone)

    # Patch rate limit to allow second request within 60s
    with patch("web.backend.services.sms.check_sms_rate_limit"):
        second_code = create_sms_code(db_session, phone)

    first_sms = (
        db_session.query(SMSCode)
        .filter(SMSCode.phone == phone, SMSCode.code == first_code)
        .first()
    )
    assert first_sms is not None
    assert first_sms.used is True

    second_sms = (
        db_session.query(SMSCode)
        .filter(SMSCode.phone == phone, SMSCode.code == second_code)
        .first()
    )
    assert second_sms is not None
    assert second_sms.used is False


def test_create_sms_code_saves_to_db(db_session):
    phone = "13800138000"
    code = create_sms_code(db_session, phone)

    sms = (
        db_session.query(SMSCode)
        .filter(SMSCode.phone == phone, SMSCode.code == code)
        .first()
    )

    assert sms is not None
    assert sms.code == code
    assert sms.phone == phone
    assert sms.used is False
    assert sms.expired_at > datetime.utcnow()


def test_create_sms_code_custom_expiry(db_session):
    phone = "13800138000"
    expire_minutes = 10
    code = create_sms_code(db_session, phone, expire_minutes=expire_minutes)

    sms = (
        db_session.query(SMSCode)
        .filter(SMSCode.phone == phone, SMSCode.code == code)
        .first()
    )

    expected_expiry = datetime.utcnow() + timedelta(minutes=expire_minutes)
    time_diff = abs((sms.expired_at - expected_expiry).total_seconds())
    assert time_diff < 5


# ── verify_sms_code (local mode) ──


def test_verify_sms_code_valid(db_session, test_sms_code):
    with patch.dict(os.environ, {"SMS_PROVIDER": "log"}):
        result = verify_sms_code(db_session, test_sms_code.phone, test_sms_code.code)
    assert result is True

    db_session.refresh(test_sms_code)
    assert test_sms_code.used is True


def test_verify_sms_code_invalid_code(db_session, test_sms_code):
    with patch.dict(os.environ, {"SMS_PROVIDER": "log"}):
        result = verify_sms_code(db_session, test_sms_code.phone, "wrong_code")
    assert result is False


def test_verify_sms_code_invalid_phone(db_session):
    with patch.dict(os.environ, {"SMS_PROVIDER": "log"}):
        result = verify_sms_code(db_session, "99999999999", "123456")
    assert result is False


def test_verify_sms_code_expired(db_session, test_expired_sms_code):
    with patch.dict(os.environ, {"SMS_PROVIDER": "log"}):
        result = verify_sms_code(
            db_session, test_expired_sms_code.phone, test_expired_sms_code.code
        )
    assert result is False


def test_verify_sms_code_already_used(db_session, test_sms_code):
    test_sms_code.used = True
    db_session.commit()

    with patch.dict(os.environ, {"SMS_PROVIDER": "log"}):
        result = verify_sms_code(db_session, test_sms_code.phone, test_sms_code.code)
    assert result is False


def test_verify_sms_code_one_time_use(db_session, test_sms_code):
    with patch.dict(os.environ, {"SMS_PROVIDER": "log"}):
        result1 = verify_sms_code(db_session, test_sms_code.phone, test_sms_code.code)
    assert result1 is True

    with patch.dict(os.environ, {"SMS_PROVIDER": "log"}):
        result2 = verify_sms_code(db_session, test_sms_code.phone, test_sms_code.code)
    assert result2 is False


def test_verify_sms_code_locked(db_session, test_sms_code):
    test_sms_code.locked = True
    db_session.commit()

    with patch.dict(os.environ, {"SMS_PROVIDER": "log"}):
        result = verify_sms_code(db_session, test_sms_code.phone, test_sms_code.code)
    assert result is False


# ── send_sms ──


def test_send_sms_log_provider(monkeypatch):
    monkeypatch.setenv("SMS_PROVIDER", "log")
    success, code = send_sms("13800138000", "123456")
    assert success is True
    assert code == "123456"


def test_send_sms_log_returns_code(monkeypatch):
    monkeypatch.setenv("SMS_PROVIDER", "log")
    success, code = send_sms("13800138000", "654321")
    assert success is True
    assert code == "654321"


def test_send_sms_unknown_provider(monkeypatch):
    monkeypatch.setenv("SMS_PROVIDER", "unknown_provider")
    success, code = send_sms("13800138000", "123456")
    assert success is False
    assert code == ""


# ── aliyun_auth provider: verification is provider-agnostic (always local) ──
# The real verify_sms_code always uses local DB verification regardless of
# SMS_PROVIDER — aliyun_auth only changes the *send* path (verification codes
# are locally generated and stored). These tests confirm that provider selection
# does not change the verification behavior.


def test_verify_sms_code_aliyun_auth_uses_local_verification(db_session, test_sms_code):
    """aliyun_auth provider must still verify against the local DB."""
    with patch.dict(os.environ, {"SMS_PROVIDER": "aliyun_auth"}):
        result = verify_sms_code(
            db_session, test_sms_code.phone, test_sms_code.code
        )
    assert result is True
    db_session.refresh(test_sms_code)
    assert test_sms_code.used is True


def test_verify_sms_code_aliyun_auth_rejects_wrong_code(db_session, test_sms_code):
    with patch.dict(os.environ, {"SMS_PROVIDER": "aliyun_auth"}):
        result = verify_sms_code(
            db_session, test_sms_code.phone, "wrong_code"
        )
    assert result is False


def test_verify_sms_code_aliyun_auth_missing_config_still_verifies_locally(
    db_session, test_sms_code
):
    # Even with missing aliyun config, verification is local and must succeed.
    with patch.dict(
        os.environ,
        {
            "SMS_PROVIDER": "aliyun_auth",
            "SMS_ACCESS_KEY_ID": "",
            "SMS_ACCESS_KEY_SECRET": "",
        },
    ):
        result = verify_sms_code(
            db_session, test_sms_code.phone, test_sms_code.code
        )
    assert result is True


def test_mark_local_code_used(db_session, test_sms_code):
    assert test_sms_code.used is False
    _mark_local_code_used(db_session, test_sms_code.phone)
    db_session.refresh(test_sms_code)
    assert test_sms_code.used is True


def test_increment_local_attempt(db_session, test_sms_code):
    assert test_sms_code.attempt_count == 0
    _increment_local_attempt(db_session, test_sms_code.phone)
    db_session.refresh(test_sms_code)
    assert test_sms_code.attempt_count == 1


def test_increment_local_attempt_locks_after_five(db_session, test_sms_code):
    test_sms_code.attempt_count = 4
    db_session.commit()

    _increment_local_attempt(db_session, test_sms_code.phone)
    db_session.refresh(test_sms_code)
    assert test_sms_code.attempt_count == 5
    assert test_sms_code.locked is True

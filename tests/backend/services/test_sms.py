"""
Tests for SMS service
"""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from web.backend.services.sms import (
    generate_code,
    create_sms_code,
    verify_sms_code,
    send_sms,
)
from web.backend.database.models import SMSCode


def test_generate_code_length():
    """Test that generate_code returns 6-digit code"""
    code = generate_code()
    assert len(code) == 6
    assert isinstance(code, str)


def test_generate_code_format():
    """Test that generate_code returns only digits"""
    code = generate_code()
    assert code.isdigit()


def test_generate_code_random_unqiue():
    """Test that generate_code produces different codes (with high probability)"""
    codes = set()
    for _ in range(100):
        codes.add(generate_code())

    # With good random, 100 iterations should produce many unique codes
    assert len(codes) > 50


def test_create_sms_code_format(db_session):
    """Test that create_sms_code returns 6-digit code"""
    code = create_sms_code(db_session, "13800138000")
    assert len(code) == 6
    assert code.isdigit()


def test_create_sms_code_invalidates_previous(db_session):
    """Test that create_sms_code invalidates previous codes for same phone"""
    phone = "13800138000"

    # Create first code
    first_code = create_sms_code(db_session, phone)

    # Create second code (should invalidate first)
    second_code = create_sms_code(db_session, phone)

    # Verify first code is now used
    first_sms = (
        db_session.query(SMSCode)
        .filter(SMSCode.phone == phone, SMSCode.code == first_code)
        .first()
    )
    assert first_sms is not None
    assert first_sms.used is True

    # Verify second code is not used
    second_sms = (
        db_session.query(SMSCode)
        .filter(SMSCode.phone == phone, SMSCode.code == second_code)
        .first()
    )
    assert second_sms is not None
    assert second_sms.used is False


def test_create_sms_code_saves_to_db(db_session):
    """Test that create_sms_code saves to database"""
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
    """Test that create_sms_code uses custom expiry time"""
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
    assert time_diff < 5  # Allow 5 seconds tolerance


def test_verify_sms_code_valid(db_session, test_sms_code):
    """Test that verify_sms_code returns True for valid code"""
    result = verify_sms_code(db_session, test_sms_code.phone, test_sms_code.code)
    assert result is True

    # Verify code is now marked as used
    db_session.refresh(test_sms_code)
    assert test_sms_code.used is True


def test_verify_sms_code_invalid_code(db_session, test_sms_code):
    """Test that verify_sms_code returns False for wrong code"""
    result = verify_sms_code(db_session, test_sms_code.phone, "wrong_code")
    assert result is False


def test_verify_sms_code_invalid_phone(db_session):
    """Test that verify_sms_code returns False for non-existent phone"""
    result = verify_sms_code(db_session, "99999999999", "123456")
    assert result is False


def test_verify_sms_code_expired(db_session, test_expired_sms_code):
    """Test that verify_sms_code returns False for expired code"""
    result = verify_sms_code(
        db_session, test_expired_sms_code.phone, test_expired_sms_code.code
    )
    assert result is False


def test_verify_sms_code_already_used(db_session, test_sms_code):
    """Test that verify_sms_code returns False for already used code"""
    # Mark as used
    test_sms_code.used = True
    db_session.commit()

    result = verify_sms_code(db_session, test_sms_code.phone, test_sms_code.code)
    assert result is False


def test_verify_sms_code_one_time_use(db_session, test_sms_code):
    """Test that verify_sms_code can only be used once"""
    # First verification should succeed
    result1 = verify_sms_code(db_session, test_sms_code.phone, test_sms_code.code)
    assert result1 is True

    # Second verification should fail
    result2 = verify_sms_code(db_session, test_sms_code.phone, test_sms_code.code)
    assert result2 is False


def test_send_sms_log_provider(monkeypatch):
    """Test that send_sms returns True with log provider"""
    monkeypatch.setenv("SMS_PROVIDER", "log")

    result = send_sms("13800138000", "123456")
    assert result is True


def test_send_sms_prints_to_stdout(monkeypatch, capsys):
    """Test that send_sms prints code to stdout in log mode"""
    monkeypatch.setenv("SMS_PROVIDER", "log")

    phone = "13800138000"
    code = "123456"
    send_sms(phone, code)

    captured = capsys.readouterr()
    assert phone in captured.out
    assert code in captured.out


def test_send_sms_returns_true_by_default(monkeypatch):
    """Test that send_sms returns True by default (mock mode)"""
    result = send_sms("13800138000", "123456")
    assert result is True

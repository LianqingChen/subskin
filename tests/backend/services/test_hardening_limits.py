"""持久化限流、短信/邮件全站日上限、健康数据/年龄授权。"""

from datetime import datetime, timedelta

import pytest

from web.backend.database.models import AuditLog, EmailVerificationCode, SMSCode, UserConsent
from web.backend.exceptions import RateLimitExceededError
from web.backend.models.rate_limit import RateLimitEvent
from web.backend.services import persistent_rate_limit as prl
from web.backend.services.consent import (
    CONSENT_TYPE_AGE_18,
    CONSENT_TYPE_HEALTH_DATA,
    has_active_consent,
    health_data_consent_missing,
    record_consent,
)
from web.backend.services.email_service import check_email_global_daily_cap
from web.backend.services.sms import check_sms_global_daily_cap


def test_check_and_hit_blocks_after_limit(db_session):
    for _ in range(3):
        prl.check_and_hit(db_session, "b", "1.2.3.4", limit=3, window_seconds=60)
    with pytest.raises(RateLimitExceededError):
        prl.check_and_hit(db_session, "b", "1.2.3.4", limit=3, window_seconds=60)
    prl.check_and_hit(db_session, "b", "5.6.7.8", limit=3, window_seconds=60)
    prl.check_and_hit(db_session, "other", "1.2.3.4", limit=3, window_seconds=60)


def test_events_outside_window_do_not_count_and_get_pruned(db_session, monkeypatch):
    monkeypatch.setattr(prl, "_PRUNE_PROBABILITY", 0)
    old = datetime.utcnow() - timedelta(days=3)
    db_session.add_all([RateLimitEvent(bucket="b", key="k", created_at=old) for _ in range(5)])
    db_session.commit()
    assert prl.count_in_window(db_session, "b", "k", 3600) == 0
    prl.check_and_hit(db_session, "b", "k", limit=1, window_seconds=3600)
    assert prl.prune(db_session) == 5
    assert db_session.query(RateLimitEvent).count() == 1


def test_sms_global_cap(db_session, monkeypatch):
    monkeypatch.setenv("SMS_GLOBAL_DAILY_CAP", "3")
    now = datetime.utcnow()
    for i in range(2):
        db_session.add(SMSCode(phone=f"1380000000{i}", code="123456", expired_at=now + timedelta(minutes=5)))
    db_session.commit()
    check_sms_global_daily_cap(db_session)
    db_session.add(SMSCode(phone="13800000009", code="123456", expired_at=now + timedelta(minutes=5)))
    db_session.commit()
    with pytest.raises(RateLimitExceededError):
        check_sms_global_daily_cap(db_session)


def test_email_global_cap(db_session, monkeypatch):
    monkeypatch.setenv("EMAIL_GLOBAL_DAILY_CAP", "1")
    check_email_global_daily_cap(db_session)
    db_session.add(EmailVerificationCode(
        email="a@example.com", code="123456", purpose="login",
        expired_at=datetime.utcnow() + timedelta(minutes=10),
    ))
    db_session.commit()
    with pytest.raises(RateLimitExceededError):
        check_email_global_daily_cap(db_session)


def test_health_consent_grant_revoke_and_audit(db_session, test_user, monkeypatch):
    monkeypatch.setenv("REQUIRE_HEALTH_DATA_CONSENT", "1")
    assert health_data_consent_missing(db_session, test_user.id)

    record_consent(db_session, test_user.id, CONSENT_TYPE_HEALTH_DATA, "1.0", source="vasi_upload")
    assert not health_data_consent_missing(db_session, test_user.id)

    record_consent(db_session, test_user.id, CONSENT_TYPE_HEALTH_DATA, "revoked", is_active=False)
    assert health_data_consent_missing(db_session, test_user.id)

    actions = [a for (a,) in db_session.query(AuditLog.action).filter_by(user_id=test_user.id).order_by(AuditLog.id)]
    assert actions == ["consent_granted", "consent_revoked"]


def test_health_consent_enforcement_off_by_default(db_session, test_user, monkeypatch):
    monkeypatch.delenv("REQUIRE_HEALTH_DATA_CONSENT", raising=False)
    assert not health_data_consent_missing(db_session, test_user.id)


def test_age_consent_recorded(db_session, test_user):
    record_consent(db_session, test_user.id, CONSENT_TYPE_AGE_18, "1.0", source="register")
    assert has_active_consent(db_session, test_user.id, CONSENT_TYPE_AGE_18)
    assert db_session.query(UserConsent).filter_by(user_id=test_user.id).count() == 1

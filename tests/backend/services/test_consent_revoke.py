"""Consent revocation must actually stop consent from being reported as active.

Regression: ``/consent/revoke`` appends an ``is_active=False`` row, but the
lookup used to filter ``is_active == True`` first and take the newest of
those, so the revocation row was never seen and the old grant stayed effective.
Synthetic in-memory data only.
"""
import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from web.backend.api import consent as consent_api
from web.backend.database.models import User, UserConsent
from web.backend.services.consent import has_active_consent

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
def user(db_session):
    u = User(username="consent_user")
    db_session.add(u)
    db_session.commit()
    return u


def _add(db, user, ctype, minutes, active):
    db.add(
        UserConsent(
            user_id=user.id,
            consent_type=ctype,
            consent_version="v1" if active else "revoked",
            consented_at=T0 + timedelta(minutes=minutes),
            is_active=active,
        )
    )
    db.commit()


def test_grant_is_active(db_session, user):
    _add(db_session, user, "ai_data", 0, True)
    assert has_active_consent(db_session, user.id, "ai_data") is True


def test_revoke_after_grant_is_not_active(db_session, user):
    _add(db_session, user, "ai_data", 0, True)
    _add(db_session, user, "ai_data", 1, False)
    assert has_active_consent(db_session, user.id, "ai_data") is False


def test_regrant_after_revoke_is_active_again(db_session, user):
    _add(db_session, user, "ai_data", 0, True)
    _add(db_session, user, "ai_data", 1, False)
    _add(db_session, user, "ai_data", 2, True)
    assert has_active_consent(db_session, user.id, "ai_data") is True


def test_revoking_one_type_leaves_other_types(db_session, user):
    _add(db_session, user, "ai_data", 0, True)
    _add(db_session, user, "medical_photo", 0, True)
    _add(db_session, user, "ai_data", 1, False)
    assert has_active_consent(db_session, user.id, "ai_data") is False
    assert has_active_consent(db_session, user.id, "medical_photo") is True


def test_no_user_or_no_record_is_not_active(db_session, user):
    assert has_active_consent(db_session, None, "ai_data") is False
    assert has_active_consent(db_session, user.id, "ai_data") is False


def test_status_endpoint_omits_revoked_type(db_session, user):
    _add(db_session, user, "ai_data", 0, True)
    _add(db_session, user, "medical_photo", 0, True)
    _add(db_session, user, "ai_data", 1, False)
    status = asyncio.run(consent_api.get_consent_status(db=db_session, current_user=user))
    assert status.ai_data is None
    assert status.medical_photo is not None

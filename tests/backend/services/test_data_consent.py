"""Purpose-scoped data consent: default deny, scopes, withdrawal, tamper evidence.

Synthetic in-memory data only.
"""
from datetime import datetime, timedelta

import pytest

from web.backend.database.models import AuditLog, User
from web.backend.models import data_consent as dc_models  # noqa: F401  (register tables)
from web.backend.models.data_consent import (
    DataConsentEvent,
    DataConsentGrant,
    DataRightsJob,
)
from web.backend.models.vasi import VASIAssessment
from web.backend.services import data_consent as svc

V = svc.CURRENT_TEXT_VERSION


@pytest.fixture
def user(db_session):
    u = User(username="contributor")
    db_session.add(u)
    db_session.commit()
    return u


@pytest.fixture
def other(db_session):
    u = User(username="someone_else")
    db_session.add(u)
    db_session.commit()
    return u


def _assessment(db, user, created=None):
    a = VASIAssessment(
        user_id=user.id, image_url="/uploads/vasi/x.png", vasi_score=0.0, body_site="face",
        area_percentage=1.0, classification="x", stage="y",
        created_at=created or datetime.utcnow(),
    )
    db.add(a)
    db.commit()
    return a


def _grant(db, user, purpose="model_training", scope="all_records", **kw):
    return svc.create_grant(db, user.id, purpose, scope, text_version=V, **kw)


def test_default_is_deny(db_session, user):
    d = svc.can_use(db_session, user.id, "model_training")
    assert d.allowed is False and d.grant_id is None


def test_all_records_grant_allows_any_own_object(db_session, user):
    a = _assessment(db_session, user)
    g = _grant(db_session, user)
    d = svc.can_use(db_session, user.id, "model_training", object_type="assessment", object_id=a.id)
    assert d.allowed is True and d.grant_id == g.id


def test_grant_does_not_cross_purposes_or_users(db_session, user, other):
    _grant(db_session, user, "model_training")
    assert svc.can_use(db_session, user.id, "public_share").allowed is False
    assert svc.can_use(db_session, other.id, "model_training").allowed is False


def test_future_only_excludes_older_records(db_session, user):
    old = _assessment(db_session, user, created=datetime.utcnow() - timedelta(days=3))
    g = _grant(db_session, user, scope="future_only")
    new = _assessment(db_session, user, created=g.created_at + timedelta(seconds=5))
    assert not svc.can_use(db_session, user.id, "model_training", object_type="assessment",
                           object_id=old.id, object_created_at=old.created_at).allowed
    assert svc.can_use(db_session, user.id, "model_training", object_type="assessment",
                       object_id=new.id, object_created_at=new.created_at).allowed
    # unknown creation time under future_only must not be guessed
    assert not svc.can_use(db_session, user.id, "model_training", object_type="assessment",
                           object_id=new.id).allowed


def test_selected_scope_only_listed_objects(db_session, user):
    a, b = _assessment(db_session, user), _assessment(db_session, user)
    _grant(db_session, user, scope="selected", object_ids=[a.id])
    assert svc.can_use(db_session, user.id, "model_training", object_type="assessment", object_id=a.id).allowed
    assert not svc.can_use(db_session, user.id, "model_training", object_type="assessment", object_id=b.id).allowed
    # a user-level check (no object) must not be satisfied by a selected-only grant
    assert not svc.can_use(db_session, user.id, "model_training").allowed


def test_selected_scope_rejects_other_users_objects(db_session, user, other):
    theirs = _assessment(db_session, other)
    with pytest.raises(svc.ConsentError) as e:
        _grant(db_session, user, scope="selected", object_ids=[theirs.id])
    assert e.value.code == "FORBIDDEN_OBJECT"
    assert db_session.query(DataConsentGrant).count() == 0


def test_research_grant_is_project_specific(db_session, user):
    _grant(db_session, user, "research_project", project_id="proj-A")
    assert svc.can_use(db_session, user.id, "research_project", project_id="proj-A").allowed
    assert not svc.can_use(db_session, user.id, "research_project", project_id="proj-B").allowed
    assert not svc.can_use(db_session, user.id, "research_project").allowed


@pytest.mark.parametrize(
    "kwargs,code",
    [
        (dict(purpose="sell_data", scope="all_records"), "BAD_PURPOSE"),
        (dict(purpose="model_training", scope="everything"), "BAD_SCOPE"),
        (dict(purpose="research_project", scope="all_records"), "PROJECT_REQUIRED"),
        (dict(purpose="model_training", scope="all_records", project_id="x"), "PROJECT_NOT_ALLOWED"),
        (dict(purpose="model_training", scope="selected"), "OBJECTS_REQUIRED"),
    ],
)
def test_validation(db_session, user, kwargs, code):
    with pytest.raises(svc.ConsentError) as e:
        svc.create_grant(db_session, user.id, text_version=V, **kwargs)
    assert e.value.code == code


def test_stale_text_version_is_rejected(db_session, user):
    with pytest.raises(svc.ConsentError) as e:
        svc.create_grant(db_session, user.id, "model_training", "all_records", text_version="old")
    assert e.value.code == "STALE_TEXT"


def test_withdraw_stops_use_and_opens_job_and_audits(db_session, user):
    g = _grant(db_session, user)
    assert svc.can_use(db_session, user.id, "model_training").allowed
    svc.withdraw_grant(db_session, user.id, g.id)
    assert not svc.can_use(db_session, user.id, "model_training").allowed
    assert svc.grant_state(db_session, g) == "withdrawn"
    jobs = db_session.query(DataRightsJob).all()
    assert len(jobs) == 1 and jobs[0].grant_id == g.id and jobs[0].status == "pending"
    actions = [a.action for a in db_session.query(AuditLog).filter_by(user_id=user.id).all()]
    assert "authorize" in actions and "revoke" in actions


def test_withdraw_is_idempotent(db_session, user):
    g = _grant(db_session, user)
    svc.withdraw_grant(db_session, user.id, g.id)
    svc.withdraw_grant(db_session, user.id, g.id)
    assert db_session.query(DataConsentEvent).filter_by(grant_id=g.id, event_type="withdrawn").count() == 1
    assert db_session.query(DataRightsJob).count() == 1


def test_cannot_withdraw_someone_elses_grant(db_session, user, other):
    g = _grant(db_session, user)
    with pytest.raises(svc.ConsentError) as e:
        svc.withdraw_grant(db_session, other.id, g.id)
    assert e.value.code == "NOT_FOUND"
    assert svc.can_use(db_session, user.id, "model_training").allowed


def test_regrant_after_withdraw_creates_new_active_grant(db_session, user):
    g1 = _grant(db_session, user)
    svc.withdraw_grant(db_session, user.id, g1.id)
    g2 = _grant(db_session, user)
    assert g2.id != g1.id and svc.can_use(db_session, user.id, "model_training").grant_id == g2.id


def test_expired_grant_is_not_used(db_session, user):
    _grant(db_session, user, expires_at=datetime.utcnow() - timedelta(minutes=1))
    assert not svc.can_use(db_session, user.id, "model_training").allowed


def test_hash_chain_detects_tampering(db_session, user):
    g = _grant(db_session, user)
    svc.withdraw_grant(db_session, user.id, g.id)
    assert svc.verify_chain(db_session, g.id) is True
    first = db_session.query(DataConsentEvent).filter_by(grant_id=g.id).order_by(DataConsentEvent.id).first()
    first.actor = "system"
    db_session.commit()
    assert svc.verify_chain(db_session, g.id) is False


def test_summary_and_listing(db_session, user):
    g = _grant(db_session, user, "public_share")
    _grant(db_session, user, "model_training")
    svc.withdraw_grant(db_session, user.id, g.id)
    s = svc.active_summary(db_session, user.id)
    assert s == {"model_training": True, "research_project": False, "public_share": False, "clinician_review": False}
    rows = svc.list_grants(db_session, user.id)
    assert {r["purpose"]: r["state"] for r in rows} == {"public_share": "withdrawn", "model_training": "active"}


def test_withdraw_all_for_account_deletion(db_session, user):
    _grant(db_session, user, "model_training")
    _grant(db_session, user, "public_share")
    n = svc.withdraw_all(db_session, user.id, reason="account_deletion")
    assert n == 2 and not any(svc.active_summary(db_session, user.id).values())
    ev = db_session.query(DataConsentEvent).filter_by(event_type="withdrawn").all()
    assert {e.actor for e in ev} == {"system"}

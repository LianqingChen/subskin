"""Training paths must honour purpose-scoped consent. Synthetic in-memory data only."""
from datetime import datetime, timedelta

import pytest

from web.backend.api import image_label as api
from web.backend.database.models import User
from web.backend.models.image_label import ImageLabel, ImageLabelAnnotation
from web.backend.models.vasi import VASIAssessment, VasiTrainingSample
from web.backend.services import data_consent as dc
from web.backend.services import vasi_model_trainer as trainer
from web.backend.services.vasi_feedback import VasiFeedbackCollector

V = dc.CURRENT_TEXT_VERSION


@pytest.fixture
def user(db_session):
    u = User(username="owner")
    db_session.add(u)
    db_session.commit()
    return u


@pytest.fixture
def admin(db_session):
    u = User(username="adm", is_admin=True)
    db_session.add(u)
    db_session.commit()
    return u


def _label(db, user, *, owned=True, created=None, status="labeled"):
    a = None
    if owned:
        a = VASIAssessment(user_id=user.id, image_url="/uploads/vasi/x.png", vasi_score=0.0,
                           body_site="face", area_percentage=1.0, classification="x", stage="y",
                           created_at=created or datetime.utcnow())
        db.add(a)
        db.commit()
    lb = ImageLabel(assessment_id=a.id if a else None, original_user_id=user.id if owned else None,
                    image_url="/uploads/vasi/x.png", image_hash=f"h{datetime.utcnow().timestamp()}{id(a)}",
                    label_status=status, training_eligible=True)
    db.add(lb)
    db.commit()
    db.add(ImageLabelAnnotation(image_label_id=lb.id, source="admin", region_index=0, mask_data="data:image/png;base64,AA"))
    db.commit()
    return lb


def _grant(db, user, scope="all_records", **kw):
    return dc.create_grant(db, user.id, "model_training", scope, text_version=V, **kw)


def test_decision_matrix(db_session, user):
    lb = _label(db_session, user)
    assert dc.label_training_decision(db_session, lb).allowed is False       # default deny
    g = _grant(db_session, user)
    assert dc.label_training_decision(db_session, lb).allowed is True
    dc.withdraw_grant(db_session, user.id, g.id)
    assert dc.label_training_decision(db_session, lb).allowed is False       # withdrawn
    lb.is_user_deleted = True
    _grant(db_session, user)
    assert dc.label_training_decision(db_session, lb).allowed is False       # deleted wins


def test_admin_upload_without_owner_is_not_user_consent_gated(db_session, user):
    lb = _label(db_session, user, owned=False)
    d = dc.label_training_decision(db_session, lb)
    assert d.allowed and d.reason == "not_user_contributed"


def test_future_only_uses_assessment_time_not_label_time(db_session, user):
    old = _label(db_session, user, created=datetime.utcnow() - timedelta(days=5))
    _grant(db_session, user, scope="future_only")
    # label row is created *after* the grant, but the photo itself is older than the grant
    assert dc.label_training_decision(db_session, old).allowed is False


def test_add_to_training_refuses_without_consent_and_accepts_with(db_session, user, admin):
    lb = _label(db_session, user)
    lb.training_eligible = False
    db_session.commit()
    r = api._add_label_to_training(lb.id, admin, db_session)
    assert r["ok"] is False and r["status_code"] == 403
    db_session.refresh(lb)
    assert lb.training_eligible is False
    assert db_session.query(VasiTrainingSample).count() == 0

    _grant(db_session, user)
    r = api._add_label_to_training(lb.id, admin, db_session)
    assert r["ok"] is True
    assert db_session.query(VasiTrainingSample).count() == 1


def test_upsert_from_admin_label_requires_consent(db_session, user):
    lb = _label(db_session, user)
    c = VasiFeedbackCollector(db_session)
    assert c.upsert_from_admin_label(lb) is None
    _grant(db_session, user)
    assert c.upsert_from_admin_label(lb) is not None


def test_existing_sample_is_excluded_after_withdrawal(db_session, user, monkeypatch):
    lb = _label(db_session, user)
    db_session.add(VasiTrainingSample(image_hash="s1", image_key="k", body_site="face",
                                      admin_mask_b64="data:image/png;base64,AA", image_label_id=lb.id))
    db_session.commit()
    assert trainer.count_usable_samples(db_session) == 0
    g = _grant(db_session, user)
    assert trainer.count_usable_samples(db_session) == 1
    dc.withdraw_grant(db_session, user.id, g.id)
    assert trainer.count_usable_samples(db_session) == 0

    # collect_samples must also skip it even if the image could be loaded
    monkeypatch.setattr(api, "_load_image_from_label", lambda label: (_ for _ in ()).throw(AssertionError("loaded")))
    assert trainer.collect_samples(db_session) == []


def test_sync_samples_skips_unconsented(db_session, user, admin):
    import asyncio

    a = _label(db_session, user)
    b = _label(db_session, user)
    _grant(db_session, user, scope="selected", object_ids=[b.assessment_id])
    out = asyncio.run(api.sync_training_samples(admin_user=admin, db=db_session))
    assert out == {"synced": 1, "skipped_no_consent": 1}
    assert {s.image_label_id for s in db_session.query(VasiTrainingSample).all()} == {b.id}


def test_training_export_excludes_unconsented_and_reports_count(db_session, user, admin):
    """Only the all-excluded branch is exercised: the export writes its manifest to a
    hard-coded production data directory, which tests must not touch."""
    import asyncio

    for _ in range(2):
        lb = _label(db_session, user)
        lb.admin_is_vitiligo = True
    db_session.commit()
    res = asyncio.run(api.export_training_data(request=api.TrainingExportRequest(), admin_user=admin, db=db_session))
    assert res.total_count == 0 and res.excluded_no_consent == 2
    assert db_session.query(ImageLabel).filter(ImageLabel.training_set_split.isnot(None)).count() == 0

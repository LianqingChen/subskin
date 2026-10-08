"""Synthetic-only evidence, privacy, consent and idempotence tests."""

from datetime import datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from web.backend.api import contribution as api
from web.backend.database.database import get_db
from web.backend.database.models import MedicalReport, User
from web.backend.models.contribution import ContributionCredit
from web.backend.models.image_label import ImageLabel
from web.backend.models.vasi import VASIAssessment
from web.backend.services import contribution as service, data_consent as consent
from web.backend.utils.contribution_rules import body_site_code, membership


def label(db, owner, fingerprint="synthetic", site="face", corrected=True, **kw):
    record = VASIAssessment(
        user_id=owner.id,
        image_url="/synthetic/private.png",
        image_hash=fingerprint,
        vasi_score=0,
        body_site=site,
        area_percentage=0,
        classification="AI节段型",
        stage="stable",
        status="active",
        is_user_corrected=corrected,
        created_at=kw.pop("created", datetime.utcnow() - timedelta(days=2)),
    )
    db.add(record)
    db.flush()
    row = ImageLabel(
        original_user_id=owner.id,
        assessment_id=record.id,
        image_url=record.image_url,
        image_hash=fingerprint,
        label_status="labeled",
        training_eligible=True,
        admin_vitiligo_type="节段型",
        **kw,
    )
    db.add(row)
    db.commit()
    return row


def grant(db, owner, scope="all_records", **kw):
    return consent.create_grant(
        db,
        owner.id,
        "model_training",
        scope,
        text_version=consent.CURRENT_TEXT_VERSION,
        **kw,
    )


def test_no_consent_never_enters_library_or_earns_points(db_session, test_user):
    label(db_session, test_user)
    assert service.sync_credits(db_session, test_user.id) == 0
    mine = service.my_summary(db_session, test_user.id)
    assert mine["images"]["value"] == 0
    assert mine["uploaded"] == 1
    assert mine["personally_checked"] == 1
    assert mine["membership"]["points"] == 0


def test_idempotence_and_reconsent_preserve_honours(db_session, test_user):
    label(db_session, test_user)
    g = grant(db_session, test_user)
    assert service.sync_credits(db_session, test_user.id) == 2
    assert service.sync_credits(db_session, test_user.id) == 0
    assert service.my_summary(db_session, test_user.id)["membership"]["points"] == 15
    consent.withdraw_grant(db_session, test_user.id, g.id)
    assert service.my_summary(db_session, test_user.id)["images"]["value"] == 0
    assert service.my_summary(db_session, test_user.id)["membership"]["points"] == 15
    grant(db_session, test_user)
    assert service.sync_credits(db_session, test_user.id) == 0


def test_future_scope_uses_record_time_not_label_time(db_session, test_user):
    label(db_session, test_user)
    grant(db_session, test_user, scope="future_only")
    assert service.sync_credits(db_session, test_user.id) == 0
    label(db_session, test_user, fingerprint="new", created=datetime.utcnow())
    assert service.sync_credits(db_session, test_user.id) == 2


def test_selected_scope_only_awards_selected_record(db_session, test_user):
    a = label(db_session, test_user, fingerprint="a")
    label(db_session, test_user, fingerprint="b")
    grant(db_session, test_user, scope="selected", object_ids=[a.assessment_id])
    assert service.sync_credits(db_session, test_user.id) == 2
    assert service.my_summary(db_session, test_user.id)["images"]["value"] == 1


@pytest.mark.parametrize(
    "change",
    [
        "deleted",
        "draft",
        "rejected",
        "unapproved",
        "wrong_owner",
        "no_hash",
        "wrong_hash",
    ],
)
def test_missing_or_invalid_evidence_does_not_award(
    db_session, test_user, test_admin_user, change
):
    row = label(db_session, test_user)
    grant(db_session, test_user)
    if change == "deleted":
        row.is_user_deleted = True
    if change == "draft":
        row.assessment.status = "draft"
    if change == "rejected":
        row.label_status = "rejected"
    if change == "unapproved":
        row.training_eligible = False
    if change == "wrong_owner":
        row.assessment.user_id = test_admin_user.id
    if change == "no_hash":
        row.image_hash = None
    if change == "wrong_hash":
        row.assessment.image_hash = "another-photo"
    db_session.commit()
    assert service.sync_credits(db_session, test_user.id) == 0


def test_automatically_finalized_record_is_not_user_checked(db_session, test_user):
    row = label(db_session, test_user, corrected=False)
    row.assessment.auto_finalized = True
    db_session.commit()
    grant(db_session, test_user)
    assert service.sync_credits(db_session, test_user.id) == 1
    assert service.my_summary(db_session, test_user.id)["membership"]["points"] == 10


def test_admin_and_ai_diagnoses_never_become_doctor_reference(db_session, test_user):
    label(db_session, test_user)
    grant(db_session, test_user)
    mine = service.my_summary(db_session, test_user.id)
    assert mine["doctor"]["value"] is None
    assert mine["impact"]["value"] is None
    assert service.distribution(db_session)["types"]["status"] == "unavailable"
    assert service.overview(db_session)["doctor_ratio"]["value"] is None


def test_reports_count_records_not_pages_and_do_not_award(db_session, test_user):
    db_session.add(MedicalReport(user_id=test_user.id, title="synthetic report"))
    db_session.commit()
    mine = service.my_summary(db_session, test_user.id)
    assert mine["reports"]["value"] == 1
    assert mine["report_contribution"]["value"] is None
    assert service.sync_credits(db_session, test_user.id) == 0


def test_entire_distribution_suppressed_prevents_complement_inference(
    db_session, test_user
):
    for n in range(5):
        label(db_session, test_user, fingerprint=str(n), site="hands")
    label(db_session, test_user, fingerprint="small", site="face")
    grant(db_session, test_user)
    matrix = service.distribution(db_session)
    assert matrix["status"] == "suppressed"
    assert all(row["count"] is None for row in matrix["rows"])
    assert service.overview(db_session)["contributors"]["status"] == "suppressed"
    assert service.overview(db_session)["images"]["value"] == 6


def test_supported_broad_sites_not_guessed_and_missing_is_zero(db_session, test_user):
    assert body_site_code("left_arm") == "arms"
    assert body_site_code("abdomen") == "front"
    assert body_site_code("impossible") == "unknown"
    matrix = service.distribution(db_session)
    assert matrix["status"] == "available"
    assert all(row["count"] == 0 for row in matrix["rows"])
    assert matrix["coverage"]["value"] is None


def test_large_bucket_and_test_user_filter(db_session, test_user):
    for n in range(5):
        label(db_session, test_user, fingerprint=str(n), site="left_arm")
    grant(db_session, test_user)
    matrix = service.distribution(db_session)
    assert matrix["status"] == "available"
    assert next(x for x in matrix["rows"] if x["code"] == "arms")["count"] == 5
    test_user.is_test = True
    db_session.commit()
    assert service.overview(db_session)["images"]["value"] == 0


def test_membership_boundaries():
    assert membership(99)["remaining"] == 1
    assert membership(100)["current"]["level"] == 2
    assert membership(5000)["next"] is None
    assert membership(5000)["progress"] == 100


def test_owner_scoped_endpoints_and_read_only_gets(
    db_session, test_user, test_admin_user
):
    label(db_session, test_user)
    grant(db_session, test_user)
    app = FastAPI()
    app.include_router(api.router, prefix="/api/contributions")
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    assert client.get("/api/contributions/me").status_code == 401
    assert client.post("/api/contributions/me/sync").status_code == 401
    public = client.get("/api/contributions/overview")
    assert public.status_code == 200
    assert public.headers["cache-control"] == "no-store"
    assert "private.png" not in public.text
    app.dependency_overrides[api.get_current_user] = lambda: test_admin_user
    assert (
        client.get(f"/api/contributions/me?user_id={test_user.id}").json()["uploaded"]
        == 0
    )
    app.dependency_overrides[api.get_current_user] = lambda: test_user
    assert client.get("/api/contributions/me").status_code == 200
    assert db_session.query(ContributionCredit).count() == 0
    assert (
        client.post("/api/contributions/me/sync", json={"points": 9999}).json()["added"]
        == 2
    )
    events = client.get("/api/contributions/me/events?limit=1").json()
    assert events["total"] == 2 and len(events["items"]) == 1
    assert "event_key" not in events["items"][0]
    assert client.get("/api/contributions/me/events?limit=5000").status_code == 422

"""Synthetic chart evidence, timezone, ownership and inference checks."""

from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from web.backend.api import contribution as api
from web.backend.database.database import get_db
from web.backend.database.models import User
from web.backend.models.contribution import ContributionCredit
from web.backend.models.image_label import ImageLabelLog
from web.backend.services import contribution_charts as charts, data_consent as consent
from tests.backend.services.test_contribution import grant, label


@pytest.fixture(autouse=True)
def fixed_months(monkeypatch):
    monkeypatch.setattr(
        charts,
        "month_keys",
        lambda: ["2026-05", "2026-06", "2026-07", "2026-08", "2026-09", "2026-10"],
    )


def log(
    db, row, operator, at, action="update", field="training_eligible", value="True"
):
    db.add(
        ImageLabelLog(
            image_label_id=row.id,
            operator_id=operator.id,
            action=action,
            field_name=field,
            new_value=value,
            created_at=at,
        )
    )
    db.commit()


def cohort(db, admin, n=6, date=datetime(2026, 9, 15)):
    rows = []
    for index in range(n):
        owner = User(username=f"synthetic-owner-{index}")
        db.add(owner)
        db.commit()
        row = label(db, owner, fingerprint=f"synthetic-cohort-{index}")
        grant(db, owner)
        log(db, row, admin, date)
        rows.append(row)
    return rows


def test_empty_history_is_zero_not_missing(db_session):
    result = charts.timeline(db_session)
    assert result["status"] == "available"
    assert all(x["total"] == 0 and x["mine"] is None for x in result["periods"])


def test_first_log_beats_mutable_label_date_and_credit_backfill(
    db_session, test_user, test_admin_user
):
    row = label(db_session, test_user)
    grant(db_session, test_user)
    row.labeled_at = datetime(2026, 10, 1)
    db_session.add(
        ContributionCredit(
            user_id=test_user.id,
            event_key="synthetic",
            kind="image_accepted",
            points=10,
            rule_version="2026-10-v1",
            awarded_at=datetime(2026, 10, 1),
        )
    )
    db_session.commit()
    log(db_session, row, test_admin_user, datetime(2026, 6, 1), action="save_draft")
    log(db_session, row, test_admin_user, datetime(2026, 7, 1))
    log(
        db_session,
        row,
        test_admin_user,
        datetime(2026, 9, 1),
        action="add_training_sample",
    )
    personal = charts.personal_visuals(db_session, test_user.id)
    assert (
        next(x for x in personal["timeline"]["periods"] if x["month"] == "2026-07")[
            "mine"
        ]
        == 1
    )
    assert (
        next(x for x in personal["timeline"]["periods"] if x["month"] == "2026-10")[
            "mine"
        ]
        == 0
    )


def test_timezone_month_boundary(db_session, test_user, test_admin_user):
    row = label(db_session, test_user)
    grant(db_session, test_user)
    log(db_session, row, test_admin_user, datetime(2026, 8, 31, 16, 1))
    assert charts.acceptance_months(db_session, [row])[row.id] == "2026-09"


def test_missing_log_never_uses_upload_or_labeled_at(db_session, test_user):
    row = label(db_session, test_user)
    row.labeled_at = datetime(2026, 9, 1)
    db_session.commit()
    grant(db_session, test_user)
    assert charts.acceptance_months(db_session, [row]) == {}
    personal = charts.personal_visuals(db_session, test_user.id)
    assert all(x["mine"] == 0 for x in personal["timeline"]["periods"])
    assert personal["timeline"]["own_unknown_dates"]["value"] == 1
    assert next(x for x in personal["body_sites"] if x["code"] == "face")["count"] == 1


def test_five_images_one_person_do_not_publish_month(
    db_session, test_user, test_admin_user
):
    for index in range(5):
        row = label(db_session, test_user, fingerprint=f"single-{index}")
        log(db_session, row, test_admin_user, datetime(2026, 9, 1))
    grant(db_session, test_user)
    result = charts.timeline(db_session)
    assert result["status"] == "suppressed"
    assert all(x["total"] is None for x in result["periods"])
    own = charts.personal_visuals(db_session, test_user.id)
    assert (
        next(x for x in own["timeline"]["periods"] if x["month"] == "2026-09")["mine"]
        == 5
    )


def test_safe_public_cohort_and_exact_personal_split(db_session, test_admin_user):
    rows = cohort(db_session, test_admin_user)
    result = charts.timeline(db_session, rows[0].original_user_id)
    september = next(x for x in result["periods"] if x["month"] == "2026-09")
    assert result["status"] == "available"
    assert september == {"month": "2026-09", "total": 6, "mine": 1, "others": 5}


def test_small_residual_not_explicitly_stacked(db_session, test_admin_user):
    rows = cohort(db_session, test_admin_user, n=5)
    result = charts.timeline(db_session, rows[0].original_user_id)
    september = next(x for x in result["periods"] if x["month"] == "2026-09")
    assert september["mine"] == 1
    assert september["others"] is None


def test_unknown_remainder_suppresses_whole_public_history(
    db_session, test_admin_user, test_user
):
    cohort(db_session, test_admin_user)
    label(db_session, test_user, fingerprint="unknown")
    grant(db_session, test_user)
    result = charts.timeline(db_session)
    assert result["status"] == "suppressed"
    assert all(x["total"] is None for x in result["periods"])
    assert result["unknown_dates"]["value"] is None


def test_earlier_remainder_also_suppressed(db_session, test_admin_user, test_user):
    cohort(db_session, test_admin_user)
    row = label(db_session, test_user, fingerprint="earlier")
    grant(db_session, test_user)
    log(db_session, row, test_admin_user, datetime(2026, 1, 1))
    result = charts.timeline(db_session)
    assert result["status"] == "suppressed" and result["earlier"]["value"] is None


def test_withdrawal_updates_private_distribution_and_history(
    db_session, test_user, test_admin_user
):
    row = label(db_session, test_user)
    g = grant(db_session, test_user)
    log(db_session, row, test_admin_user, datetime(2026, 9, 1))
    consent.withdraw_grant(db_session, test_user.id, g.id)
    result = charts.personal_visuals(db_session, test_user.id)
    assert all(x["count"] == 0 for x in result["body_sites"])
    assert all(x["mine"] == 0 for x in result["timeline"]["periods"])


def test_private_chart_endpoint_cannot_select_other_user(
    db_session, test_user, test_admin_user
):
    label(db_session, test_user)
    grant(db_session, test_user)
    app = FastAPI()
    app.include_router(api.router, prefix="/api/contributions")
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    assert client.get("/api/contributions/me/visuals").status_code == 401
    app.dependency_overrides[api.get_current_user] = lambda: test_admin_user
    response = client.get(f"/api/contributions/me/visuals?user_id={test_user.id}")
    assert (
        response.status_code == 200 and response.headers["cache-control"] == "no-store"
    )
    assert all(x["count"] == 0 for x in response.json()["body_sites"])
    assert "original_user_id" not in response.text and "image_hash" not in response.text


def test_month_window_crosses_year():
    # Call the unpatched implementation from its own source module separately.
    import importlib.util

    spec = importlib.util.spec_from_file_location("chart_month_window", charts.__file__)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.month_keys(datetime(2026, 1, 1, tzinfo=timezone.utc)) == [
        "2025-08",
        "2025-09",
        "2025-10",
        "2025-11",
        "2025-12",
        "2026-01",
    ]


def test_future_log_is_unknown_not_a_predicted_acceptance(
    db_session, test_user, test_admin_user
):
    row = label(db_session, test_user)
    grant(db_session, test_user)
    log(db_session, row, test_admin_user, datetime(2099, 1, 1))
    assert charts.acceptance_months(db_session, [row]) == {}
    assert (
        charts.personal_visuals(db_session, test_user.id)["timeline"][
            "own_unknown_dates"
        ]["value"]
        == 1
    )

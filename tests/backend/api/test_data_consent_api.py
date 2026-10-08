"""HTTP-level tests for data consent and self-report APIs. Synthetic data only."""
from datetime import datetime

import pytest

from web.backend.database.models import User
from web.backend.models.vasi import VASIAssessment
from web.backend.services import data_consent as dc

BASE = "/api/data-consents"
V = dc.CURRENT_TEXT_VERSION


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setenv("DATA_CONSENT_GRANTS_ENABLED", "true")


def _body(**kw):
    return {"purpose": "model_training", "scope": "all_records", "text_version": V, **kw}


def test_requires_login(client):
    for method, path in [("get", BASE), ("post", BASE), ("get", f"{BASE}/status"),
                         ("post", "/api/self-report/next"), ("get", "/api/self-report/facts")]:
        assert getattr(client, method)(path).status_code in (401, 403), path


def test_new_grants_are_off_by_default(client, auth_headers, monkeypatch):
    monkeypatch.delenv("DATA_CONSENT_GRANTS_ENABLED", raising=False)
    r = client.post(BASE, json=_body(), headers=auth_headers)
    assert r.status_code == 503 and r.json()["detail"]["code"] == "GRANTS_DISABLED"
    assert client.get(f"{BASE}/purposes", headers=auth_headers).json()["grants_enabled"] is False


def test_create_list_status_withdraw_flow(client, auth_headers, enabled):
    r = client.post(BASE, json=_body(), headers=auth_headers)
    assert r.status_code == 201
    gid = r.json()["id"]
    assert r.json()["state"] == "active"
    assert client.get(f"{BASE}/status", headers=auth_headers).json()["active"]["model_training"] is True
    assert [g["id"] for g in client.get(BASE, headers=auth_headers).json()] == [gid]

    w = client.post(f"{BASE}/{gid}/withdraw", headers=auth_headers)
    assert w.status_code == 200 and w.json()["state"] == "withdrawn"
    assert w.json()["withdrawal_status"] == "pending"
    assert client.get(f"{BASE}/status", headers=auth_headers).json()["active"]["model_training"] is False
    assert client.post(f"{BASE}/{gid}/withdraw", headers=auth_headers).status_code == 200  # idempotent


def test_withdraw_works_even_when_new_grants_are_disabled(client, auth_headers, monkeypatch):
    monkeypatch.setenv("DATA_CONSENT_GRANTS_ENABLED", "true")
    gid = client.post(BASE, json=_body(), headers=auth_headers).json()["id"]
    monkeypatch.setenv("DATA_CONSENT_GRANTS_ENABLED", "false")
    assert client.post(f"{BASE}/{gid}/withdraw", headers=auth_headers).json()["state"] == "withdrawn"


def test_stale_text_and_validation_errors(client, auth_headers, enabled):
    r = client.post(BASE, json=_body(text_version="old"), headers=auth_headers)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "STALE_TEXT"
    r = client.post(BASE, json=_body(purpose="sell_data"), headers=auth_headers)
    assert r.status_code == 400 and r.json()["detail"]["code"] == "BAD_PURPOSE"
    r = client.post(BASE, json=_body(purpose="research_project"), headers=auth_headers)
    assert r.json()["detail"]["code"] == "PROJECT_REQUIRED"


def test_cannot_grant_or_withdraw_other_users_data(client, db_session, auth_headers, enabled):
    stranger = User(username="stranger")
    db_session.add(stranger)
    db_session.commit()
    theirs = VASIAssessment(user_id=stranger.id, image_url="/uploads/vasi/x.png", vasi_score=0.0,
                            body_site="face", area_percentage=1.0, classification="x", stage="y",
                            created_at=datetime.utcnow())
    db_session.add(theirs)
    db_session.commit()
    r = client.post(BASE, json=_body(scope="selected", object_ids=[theirs.id]), headers=auth_headers)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "FORBIDDEN_OBJECT"

    other_grant = dc.create_grant(db_session, stranger.id, "model_training", "all_records", text_version=V)
    assert client.post(f"{BASE}/{other_grant.id}/withdraw", headers=auth_headers).status_code == 404
    assert client.get(BASE, headers=auth_headers).json() == []


def test_self_report_flow(client, db_session, auth_headers, test_user):
    db_session.add(VASIAssessment(user_id=test_user.id, image_url="/uploads/vasi/x.png", vasi_score=0.0,
                                  body_site="face", area_percentage=1.0, classification="x", stage="y"))
    db_session.commit()
    r = client.post("/api/self-report/next", json={"trigger": "record_saved", "body_site": "face",
                                                    "session_id": "s1"}, headers=auth_headers)
    assert [q["id"] for q in r.json()["questions"]] == ["Q1"]
    assert "unknown" in [o["value"] for o in r.json()["questions"][0]["options"]]

    r = client.post("/api/self-report/answer", json={"question_id": "Q1", "answer": "1to3y",
                                                      "body_site": "face"}, headers=auth_headers)
    assert r.status_code == 201 and r.json()["answer"] == "1to3y"
    facts = client.get("/api/self-report/facts", headers=auth_headers).json()
    assert [(f["question_id"], f["answer"]) for f in facts] == [("Q1", "1to3y")]

    bad = client.post("/api/self-report/answer", json={"question_id": "Q1", "answer": "forever",
                                                        "body_site": "face"}, headers=auth_headers)
    assert bad.status_code == 400 and bad.json()["detail"]["code"] == "BAD_ANSWER"
    assert client.post("/api/self-report/dismiss", json={"question_id": "Q2", "body_site": "face"},
                       headers=auth_headers).status_code == 204
    assert client.post("/api/self-report/next", json={"trigger": "nonsense"},
                       headers=auth_headers).status_code == 400

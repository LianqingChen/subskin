"""Knowledge hub: review gate, preview isolation, seed idempotence, k≥5 research counts."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from web.backend.api import knowledge as api
from web.backend.api import knowledge_admin as admin_api
from web.backend.database.database import get_db
from web.backend.models.knowledge import KnowledgeCard, KnowledgeReviewLog
from web.backend.services import data_consent as consent
from web.backend.services import knowledge as service
from web.backend.services.admin_auth import get_admin_user
from web.backend.utils import knowledge_seed

SEED = {
    "version": "test-1",
    "topics": [{"key": "basics", "label": "认识白癜风"}],
    "cards": [
        {
            "slug": "what-is-vitiligo",
            "topic": "basics",
            "title": "白癜风是什么？",
            "summary": "一种常见的色素脱失性皮肤病。",
            "body_md": "## 是什么\n内容 [1]",
            "evidence_level": "A",
            "sources": [{"type": "pmid", "ref": "1", "title": "t", "url": "https://x", "year": 2024}],
            "related": ["hidden-card"],
            "reviewer_notes": "internal",
        },
        {
            "slug": "hidden-card",
            "topic": "basics",
            "title": "草稿",
            "summary": "s",
            "body_md": "b",
            "evidence_level": "Z",
        },
    ],
    "pipeline": [{"key": "drug-a", "drug_zh": "药A", "phase": "III期", "checked_at": "2026-11-07"}],
    "digests": [{"key": "paper-a", "title_zh": "论文A", "one_liner": "一句话", "published_on": "2026-10"}],
    "entities": [
        {"key": "vitiligo", "type": "Disease", "name_zh": "白癜风", "aliases": ["白驳风"],
         "external_ids": {"MONDO": "MONDO:0008661"}},
        {"key": "jak-stat", "type": "Mechanism", "name_zh": "JAK-STAT 通路"},
    ],
    "relations": [
        {"subject": "vitiligo", "predicate": "involves_mechanism", "object": "jak-stat",
         "evidence_level": "B", "sources": [{"type": "pmid", "ref": "2", "quote": "q"}]},
        {"subject": "vitiligo", "predicate": "treated_by", "object": "missing"},
    ],
}


def publish(db, kind, item_id, actor):
    for to in ("editor_reviewed", "medical_reviewed", "published"):
        service.transition(db, kind, item_id, to, actor, reviewer_label="张医生 · 皮肤科主治")


def card_id(db, slug):
    return db.query(KnowledgeCard).filter_by(slug=slug).one().id


def test_seed_loads_everything_as_draft_and_skips_unknown_entities(db_session):
    stats = service.load_seed(db_session, SEED)
    assert stats["cards"] == {"created": 2}
    assert stats["relations"] == {"created": 1, "skipped_unknown_entity": 1}
    assert {c.status for c in db_session.query(KnowledgeCard)} == {"draft"}
    assert db_session.query(KnowledgeCard).filter_by(slug="hidden-card").one().evidence_level == "D"


def test_public_sees_nothing_until_medically_reviewed_and_published(db_session, test_admin_user):
    service.load_seed(db_session, SEED)
    labels = {"basics": "认识白癜风"}
    assert service.list_cards(db_session, None, False, labels)["items"] == []
    cid = card_id(db_session, "what-is-vitiligo")
    service.transition(db_session, "cards", cid, "editor_reviewed", test_admin_user.id)
    assert service.list_cards(db_session, None, False, labels)["items"] == []
    with pytest.raises(service.KnowledgeError) as missing_reviewer:
        service.transition(db_session, "cards", cid, "medical_reviewed", test_admin_user.id)
    assert missing_reviewer.value.code == "INVALID_REQUEST"
    service.transition(db_session, "cards", cid, "medical_reviewed", test_admin_user.id,
                       reviewer_label="张医生 · 皮肤科主治")
    service.transition(db_session, "cards", cid, "published", test_admin_user.id)
    items = service.list_cards(db_session, None, False, labels)["items"]
    assert [c["slug"] for c in items] == ["what-is-vitiligo"]
    detail = service.get_card(db_session, "what-is-vitiligo", False)
    assert detail["related"] == []  # unpublished related cards never leak
    assert "reviewer_notes" not in detail
    assert detail["disclaimer"].startswith("本文不构成医疗建议")
    assert db_session.query(KnowledgeReviewLog).count() == 3


def test_cannot_skip_review_steps_and_return_to_draft_voids_review(db_session, test_admin_user):
    service.load_seed(db_session, SEED)
    cid = card_id(db_session, "what-is-vitiligo")
    with pytest.raises(service.KnowledgeError):
        service.transition(db_session, "cards", cid, "published", test_admin_user.id)
    publish(db_session, "cards", cid, test_admin_user.id)
    with pytest.raises(service.KnowledgeError):
        service.transition(db_session, "cards", cid, "draft", test_admin_user.id)  # note required
    service.transition(db_session, "cards", cid, "draft", test_admin_user.id, note="来源需更新")
    row = db_session.get(KnowledgeCard, cid)
    assert row.medical_reviewed_at is None and row.published_at is None


def test_reloading_seed_never_touches_reviewed_rows(db_session, test_admin_user):
    service.load_seed(db_session, SEED)
    cid = card_id(db_session, "what-is-vitiligo")
    publish(db_session, "cards", cid, test_admin_user.id)
    changed = {**SEED, "cards": [{**SEED["cards"][0], "title": "改过的标题"}, SEED["cards"][1]]}
    stats = service.load_seed(db_session, changed)
    assert stats["cards"] == {"kept": 1, "updated": 1}
    assert db_session.get(KnowledgeCard, cid).title == "白癜风是什么？"


def test_research_counts_are_suppressed_below_five(db_session, test_user):
    consent.create_grant(db_session, test_user.id, "model_training", "all_records",
                         text_version=consent.CURRENT_TEXT_VERSION)
    purposes = {p["purpose"]: p for p in service.research_overview(db_session)["purposes"]}
    assert purposes["model_training"]["active"] == {
        "value": None, "status": "suppressed", "note": "人数较少暂不公开"}
    assert purposes["research_project"]["open"] is False
    assert purposes["research_project"]["active"]["status"] == "unavailable"


def test_entity_graph_resolves_alias_and_hides_draft_edges(db_session, test_admin_user):
    service.load_seed(db_session, SEED)
    assert service.entity_graph(db_session, "白驳风", False)["edges"] == []
    preview = service.entity_graph(db_session, "白驳风", True)
    assert preview["entity"]["external_ids"] == {"MONDO": "MONDO:0008661"}
    assert [e["predicate"] for e in preview["edges"]] == ["involves_mechanism"]


def _client(db_session, user, admin=None):
    app = FastAPI()
    app.include_router(api.router, prefix="/api/knowledge")
    app.include_router(admin_api.router)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[api.get_current_user_optional] = lambda: user
    if admin is not None:
        app.dependency_overrides[get_admin_user] = lambda: admin
    return TestClient(app)


def test_preview_flag_only_works_for_admins(db_session, test_user, test_admin_user, monkeypatch):
    monkeypatch.setattr(knowledge_seed, "read_seed", lambda path=None: SEED)
    service.load_seed(db_session, SEED)
    anon = _client(db_session, None).get("/api/knowledge/cards?preview=1")
    assert anon.json()["items"] == []
    assert anon.headers["cache-control"].startswith("public")
    member = _client(db_session, test_user).get("/api/knowledge/cards?preview=1").json()
    assert member["items"] == []
    admin = _client(db_session, test_admin_user).get("/api/knowledge/cards?preview=1")
    assert {c["status"] for c in admin.json()["items"]} == {"draft"}
    assert admin.headers["cache-control"] == "no-store"
    assert _client(db_session, None).get("/api/knowledge/cards/what-is-vitiligo").status_code == 404


def test_admin_transition_endpoint(db_session, test_admin_user):
    service.load_seed(db_session, SEED)
    client = _client(db_session, test_admin_user, admin=test_admin_user)
    cid = card_id(db_session, "what-is-vitiligo")
    ok = client.post(f"/api/admin/knowledge/cards/{cid}/transition", json={"to": "editor_reviewed"})
    assert ok.status_code == 200 and ok.json()["status"] == "editor_reviewed"
    bad = client.post(f"/api/admin/knowledge/cards/{cid}/transition", json={"to": "published"})
    assert bad.status_code == 409
    assert client.get("/api/admin/knowledge/bogus").status_code == 400
    logs = client.get(f"/api/admin/knowledge/cards/{cid}/logs").json()["items"]
    assert [entry["to"] for entry in logs] == ["editor_reviewed"]

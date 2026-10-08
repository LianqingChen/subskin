"""Discovery regression: in-memory data only; no real patient fixtures."""
from datetime import datetime, timedelta

import pytest

from web.backend.database.models import Hospital, HospitalReview, User
from web.backend.services.hospital import list_reviews
from web.backend.services.hospital_experience import experience_summary, wilson_lower

NOW = datetime(2026, 9, 16, 12)
DIMENSION = "医患沟通"


def hospital(db, slug="sample"):
    row = Hospital(slug=slug, name="测试医院", province="测试地区", city="测试城市", origin="official", status="visible")
    db.add(row)
    db.flush()
    return row


def review(db, hid, uid, level="satisfied", **kwargs):
    values = dict(hospital_id=hid, user_id=uid, content="仅供测试的就诊过程记录，不包含任何真实用户信息。", target="experience",
                  experience_scores={DIMENSION: level}, health_consent=True, moderation_status="approved", status="visible", created_at=NOW - timedelta(days=1))
    values.update(kwargs)
    row = HospitalReview(**values)
    db.add(row)
    db.flush()
    return row


def stats(db):
    result = experience_summary(db, NOW)
    return result.items[0].dimensions[2]


def test_threshold_dedup_latest_na_and_retraction(db_session):
    h = hospital(db_session)
    for uid in range(1, 20):
        review(db_session, h.id, uid)
    assert stats(db_session).answered == 19
    assert stats(db_session).reference_score is None
    repeated = review(db_session, h.id, 1, "unsatisfied", created_at=NOW)
    assert stats(db_session).answered == 19
    assert stats(db_session).unsatisfied == 1
    twentieth = review(db_session, h.id, 20)
    assert stats(db_session).eligible
    assert stats(db_session).answered == 20
    twentieth.status = "deleted"
    db_session.flush()
    assert not stats(db_session).eligible
    repeated.experience_scores = {DIMENSION: "na"}
    db_session.flush()
    assert stats(db_session).answered == 18
    assert stats(db_session).na == 1


@pytest.mark.parametrize("changes", [
    {"created_at": NOW - timedelta(days=366)}, {"created_at": NOW + timedelta(seconds=1)},
    {"status": "deleted"}, {"moderation_status": "blocked"}, {"moderation_status": "restricted"},
    {"moderation_status": "flagged"}, {"health_consent": False}, {"aggregate_after": NOW + timedelta(hours=1)},
])
def test_ineligible_reviews_do_not_enter_statistics(db_session, changes):
    h = hospital(db_session)
    review(db_session, h.id, 1, **changes)
    assert stats(db_session).answered == 0


def test_window_boundary_and_hidden_hospital(db_session):
    h = hospital(db_session)
    review(db_session, h.id, 1, created_at=NOW - timedelta(days=365), aggregate_after=NOW)
    assert stats(db_session).answered == 1
    h.status = "hidden"
    db_session.flush()
    assert experience_summary(db_session, NOW).items == []


def test_wilson_prefers_more_evidence_at_same_fraction():
    assert wilson_lower(20, 20) > wilson_lower(1, 1)
    assert wilson_lower(0, 20) == pytest.approx(0)
    assert 0 < wilson_lower(12, 20) < 0.6


def test_feed_hides_removed_hospitals_and_private_credentials(db_session):
    user = User(username="discovery_test", is_active=True)
    db_session.add(user)
    db_session.flush()
    h = hospital(db_session)
    r = review(db_session, h.id, user.id, images=[{"url": "/private-test-image", "label": "费用单"}])
    total, items, _ = list_reviews(db_session, None)
    assert total == 1 and items[0].hospital_name == h.name
    assert items[0].images == []
    r.moderation_status = "blocked"
    db_session.flush()
    assert list_reviews(db_session, None)[0] == 0
    r.moderation_status = "approved"
    h.status = "hidden"
    db_session.flush()
    assert list_reviews(db_session, None)[0] == 0

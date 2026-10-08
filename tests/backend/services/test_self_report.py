"""Micro-ask scheduling and self-reported facts (08 design). Synthetic data only."""
from datetime import datetime, timedelta

import pytest

from web.backend.database.models import PatientProfile, User
from web.backend.models import self_report as sr_models  # noqa: F401  (register tables)
from web.backend.models.self_report import MicroAskLog, SelfReportFact
from web.backend.models.vasi import VASIAssessment
from web.backend.services import self_report as svc

SITE = "face"


@pytest.fixture
def user(db_session):
    u = User(username="reporter")
    db_session.add(u)
    db_session.commit()
    return u


def _records(db, user, n, site=SITE, first_age_days=0):
    for i in range(n):
        db.add(VASIAssessment(
            user_id=user.id, image_url="/uploads/vasi/x.png", vasi_score=0.0, body_site=site,
            area_percentage=1.0, classification="x", stage="y",
            created_at=datetime.utcnow() - timedelta(days=first_age_days if i == 0 else 0),
        ))
    db.commit()


def _next(db, user, trigger, session="s1", site=SITE, now=None):
    return svc.next_questions(db, user.id, trigger, body_site=site, session_id=session, now=now)


def _ids(qs):
    return [q["id"] for q in qs]


def test_no_records_no_question(db_session, user):
    assert _next(db_session, user, "record_saved") == []


def test_first_record_asks_q1_only(db_session, user):
    _records(db_session, user, 1)
    assert _ids(_next(db_session, user, "record_saved")) == ["Q1"]


def test_every_question_offers_unknown(db_session):
    for q in svc.QUESTIONS.values():
        assert "unknown" in [o["value"] for o in q["options"]], q["id"]


def test_at_most_one_question_per_session(db_session, user):
    _records(db_session, user, 2)
    first = _next(db_session, user, "record_saved", session="a")
    assert len(first) == 1
    assert _next(db_session, user, "record_saved", session="a") == []
    assert len(_next(db_session, user, "record_saved", session="b")) == 1


def test_weekly_cap_is_three(db_session, user):
    _records(db_session, user, 2)
    for qid in ("Q1", "Q2", "Q3"):
        db_session.add(MicroAskLog(user_id=user.id, question_id=qid, event="shown", session_id="old"))
    db_session.commit()
    assert _next(db_session, user, "record_saved", session="new") == []


def test_old_shown_events_do_not_count_toward_weekly_cap(db_session, user):
    _records(db_session, user, 1)
    for qid in ("Q1", "Q2", "Q3"):
        db_session.add(MicroAskLog(user_id=user.id, question_id=qid, event="shown", session_id="old",
                                   created_at=datetime.utcnow() - timedelta(days=8)))
    db_session.commit()
    assert _ids(_next(db_session, user, "record_saved", session="new")) == ["Q1"]


def test_answered_question_is_not_asked_again(db_session, user):
    _records(db_session, user, 1)
    svc.record_answer(db_session, user.id, "Q1", "gt3y", body_site=SITE)
    assert _next(db_session, user, "record_saved") == []


def test_skip_cools_down_for_14_days(db_session, user):
    _records(db_session, user, 1)
    t0 = datetime.utcnow()
    svc.dismiss(db_session, user.id, "Q1", body_site=SITE, now=t0)
    # Q2 legitimately becomes eligible after a week; the skipped Q1 must stay quiet
    assert "Q1" not in _ids(_next(db_session, user, "record_saved", session="x", now=t0 + timedelta(days=13)))
    assert _ids(_next(db_session, user, "record_saved", session="y", now=t0 + timedelta(days=15))) == ["Q1"]


def test_q2_needs_second_record_or_a_week(db_session, user):
    _records(db_session, user, 1)
    svc.record_answer(db_session, user.id, "Q1", "unknown", body_site=SITE)
    assert _next(db_session, user, "record_saved") == []
    _records(db_session, user, 1)
    assert _ids(_next(db_session, user, "record_saved", session="n")) == ["Q2"]


def test_q2_can_repeat_after_four_weeks(db_session, user):
    _records(db_session, user, 2)
    svc.record_answer(db_session, user.id, "Q1", "unknown", body_site=SITE)
    svc.record_answer(db_session, user.id, "Q2", "unchanged", body_site=SITE)
    assert _next(db_session, user, "record_saved", session="a") == []
    later = datetime.utcnow() + timedelta(days=29)
    assert _ids(_next(db_session, user, "record_saved", session="b", now=later)) == ["Q2"]


def test_compare_viewed_asks_treatment(db_session, user):
    _records(db_session, user, 2)
    assert _ids(_next(db_session, user, "compare_viewed")) == ["Q3"]


def test_checklist_lists_unanswered_without_caps_and_gates_q5(db_session, user):
    _records(db_session, user, 2)
    qs = _next(db_session, user, "checklist")
    assert _ids(qs) == ["Q4", "Q3", "Q6", "Q7"]
    svc.record_answer(db_session, user.id, "Q4", "yes")
    assert _ids(_next(db_session, user, "checklist", session="again")) == ["Q5", "Q3", "Q6", "Q7"]
    svc.record_answer(db_session, user.id, "Q4", "no")  # changed answer
    assert "Q5" not in _ids(_next(db_session, user, "checklist", session="third"))


def test_checklist_does_not_consume_weekly_budget(db_session, user):
    _records(db_session, user, 2)
    _next(db_session, user, "checklist")
    assert db_session.query(MicroAskLog).filter_by(event="shown").count() == 0


@pytest.mark.parametrize(
    "qid,answer,site",
    [
        ("Q9", "yes", None),            # unknown question
        ("Q1", "forever", SITE),        # option not in catalog
        ("Q1", ["gt3y"], SITE),         # list for a single-choice question
        ("Q3", "topical", None),        # scalar for a multi-choice question
        ("Q3", ["topical", "none"], None),    # 'none' is exclusive
        ("Q3", ["topical", "unknown"], None), # 'unknown' is exclusive
        ("Q1", "gt3y", None),           # site-scoped question needs a site
    ],
)
def test_answer_validation(db_session, user, qid, answer, site):
    with pytest.raises(svc.SelfReportError):
        svc.record_answer(db_session, user.id, qid, answer, body_site=site)
    assert db_session.query(SelfReportFact).count() == 0


def test_multi_answer_is_deduped_and_stored(db_session, user):
    svc.record_answer(db_session, user.id, "Q3", ["topical", "phototherapy", "topical"])
    facts = svc.latest_facts(db_session, user.id)
    assert facts[0]["answer"] == ["topical", "phototherapy"]


def test_latest_answer_wins_and_history_is_kept(db_session, user):
    svc.record_answer(db_session, user.id, "Q4", "no")
    svc.record_answer(db_session, user.id, "Q4", "yes")
    assert [f["answer"] for f in svc.latest_facts(db_session, user.id)] == ["yes"]
    assert db_session.query(SelfReportFact).count() == 2


def test_profile_must_belong_to_user(db_session, user):
    other = User(username="not_me")
    db_session.add(other)
    db_session.commit()
    theirs = PatientProfile(user_id=other.id, name="x")
    db_session.add(theirs)
    db_session.commit()
    with pytest.raises(svc.SelfReportError):
        svc.record_answer(db_session, user.id, "Q4", "yes", profile_id=theirs.id)


def test_facts_are_per_user(db_session, user):
    other = User(username="another")
    db_session.add(other)
    db_session.commit()
    svc.record_answer(db_session, other.id, "Q4", "yes")
    assert svc.latest_facts(db_session, user.id) == []

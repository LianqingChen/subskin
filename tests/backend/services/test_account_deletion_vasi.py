"""Account deletion must not crash on diaries and must erase VASI photo data.

Regressions: (1) the file-collection query used a non-existent
``DiaryImage.diary_id`` so any user with a diary image crashed; (2) VASI
assessment rows, their mask layers, RGB job artifacts, private images and
label masks were left behind. Synthetic in-memory data and tmp dirs only.
"""
import json
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from web.backend.database import models as m
from web.backend.models.contribution import ContributionCredit
from web.backend.models import self_report as _self_report_models  # noqa: F401 (register tables before fixtures)
from web.backend.models.image_label import ImageLabel, ImageLabelAnnotation
from web.backend.models.rgb_segmentation import RGBSegmentationJob
from web.backend.models.vasi import (
    ImageQualityTag,
    VASIAssessment,
    VasiFeedbackSignal,
    VasiTrainingSample,
)
from web.backend.services import account_deletion
from web.backend.services.rgb_segmentation import artifacts

JOB = "a" * 32


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """Run the service with CWD and RGB artifact roots under tmp."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(artifacts, "ROOT", tmp_path / "data" / "rgb_segmentation")
    monkeypatch.setattr(artifacts, "PROJECT_ROOT", tmp_path)
    return tmp_path


def _touch(path: Path, data: bytes = b"x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


@pytest.fixture
def populated(db_session, sandbox):
    db = db_session
    user = m.User(username="gone", email="a@example.invalid")
    other = m.User(username="stays")
    db.add_all([user, other])
    db.commit()

    # diary with an image (crashed on DiaryImage.diary_id)
    diary = m.DiaryEntry(user_id=user.id, raw_text="synthetic", entry_date=date(2026, 1, 1))
    db.add(diary)
    db.commit()
    diary_file = _touch(sandbox / "data/uploads/diary/d1.jpg")
    db.add(m.DiaryImage(diary_entry_id=diary.id, user_id=user.id, image_url="/uploads/diary/d1.jpg"))

    # RGB-path assessment: public image + private artifacts
    rgb_png = _touch(sandbox / f"data/uploads/vasi/rgb_{JOB}.png")
    source = _touch(artifacts.ROOT / "jobs" / JOB / "source.bin")
    assess = VASIAssessment(
        user_id=user.id, image_url=f"/uploads/vasi/rgb_{JOB}.png", image_key=f"rgb_{JOB}",
        image_hash="hash-gone", vasi_score=0.0, body_site="face",
        area_percentage=1.0, classification="x", stage="y",
        user_lesion_layer="data:image/png;base64,SECRET", details=json.dumps({"k": "v"}),
    )
    db.add(assess)
    db.commit()
    db.add(RGBSegmentationJob(
        id=JOB, user_id=user.id, idempotency_key="k", request_hash="h", context_json="{}",
        assessment_id=assess.id, deadline_at=datetime.utcnow() + timedelta(hours=1),
    ))
    label = ImageLabel(
        assessment_id=assess.id, original_user_id=user.id, image_url=assess.image_url,
        image_key=assess.image_key, image_hash="hash-gone", ai_details='{"secret": 1}',
        user_notes="private note", admin_notes="n", training_eligible=True,
    )
    db.add(label)
    db.commit()
    db.add_all([
        ImageLabelAnnotation(image_label_id=label.id, source="user", region_index=0, mask_data="MASK"),
        ImageQualityTag(assessment_id=assess.id, quality_tag="good", tagged_by=other.id),
        VasiFeedbackSignal(assessment_id=assess.id, user_id=user.id, signal_type="explicit_correction"),
        VasiTrainingSample(image_hash="hash-gone", image_key=assess.image_key, body_site="face",
                           user_mask_b64="MASK", image_label_id=label.id),
        VasiTrainingSample(image_hash="hash-other", image_key="rgb_other", body_site="face"),
    ])
    db.commit()
    return {"user": user, "other": other, "assess": assess, "label": label,
            "files": [diary_file, rgb_png, source]}


def test_deletion_with_diary_image_does_not_crash(db_session, populated):
    db_session.add(ContributionCredit(user_id=populated["user"].id, event_key="synthetic",
                                     kind="image_accepted", points=10, rule_version="2026-10-v1"))
    db_session.commit()
    detail = account_deletion.delete_user_account(db_session, populated["user"])
    assert detail["user_id"] == populated["user"].id
    assert db_session.query(m.DiaryImage).count() == 0
    assert db_session.query(m.DiaryEntry).count() == 0
    assert db_session.query(ContributionCredit).count() == 0
    assert detail["contribution_credits_deleted"] == 1


def test_vasi_rows_and_dependents_are_erased(db_session, populated):
    account_deletion.delete_user_account(db_session, populated["user"])
    assert db_session.query(VASIAssessment).count() == 0
    assert db_session.query(RGBSegmentationJob).count() == 0
    assert db_session.query(ImageQualityTag).count() == 0
    assert db_session.query(VasiFeedbackSignal).count() == 0
    samples = db_session.query(VasiTrainingSample).all()
    assert [s.image_hash for s in samples] == ["hash-other"]


def test_private_files_are_erased(db_session, populated):
    account_deletion.delete_user_account(db_session, populated["user"])
    for f in populated["files"]:
        assert not f.exists(), f
    assert not (artifacts.ROOT / "jobs" / JOB).exists()


def test_image_label_becomes_anonymous_tombstone(db_session, populated):
    account_deletion.delete_user_account(db_session, populated["user"])
    label = db_session.query(ImageLabel).one()
    assert label.is_user_deleted is True
    assert label.training_eligible is False
    assert label.original_user_id is None and label.assessment_id is None
    assert label.ai_details is None and label.user_notes is None
    assert label.image_key is None
    assert db_session.query(ImageLabelAnnotation).count() == 0


def test_other_users_data_is_untouched(db_session, populated, sandbox):
    other_assess = VASIAssessment(
        user_id=populated["other"].id, image_url="/uploads/vasi/keep.png", image_key="keep",
        vasi_score=1.0, body_site="hand", area_percentage=2.0, classification="x", stage="y",
    )
    db_session.add(other_assess)
    db_session.commit()
    keep = _touch(sandbox / "data/uploads/vasi/keep.png")
    account_deletion.delete_user_account(db_session, populated["user"])
    assert db_session.query(VASIAssessment).filter_by(user_id=populated["other"].id).count() == 1
    assert keep.exists()


def test_deletion_withdraws_grants_and_erases_self_report(db_session, populated):
    from web.backend.models.data_consent import DataConsentEvent
    from web.backend.models.self_report import MicroAskLog, SelfReportFact
    from web.backend.services import data_consent as dc
    from web.backend.services import self_report as sr

    user, other = populated["user"], populated["other"]
    dc.create_grant(db_session, user.id, "model_training", "all_records", text_version=dc.CURRENT_TEXT_VERSION)
    dc.create_grant(db_session, other.id, "public_share", "all_records", text_version=dc.CURRENT_TEXT_VERSION)
    sr.record_answer(db_session, user.id, "Q4", "yes")
    sr.record_answer(db_session, other.id, "Q4", "no")

    detail = account_deletion.delete_user_account(db_session, user)

    assert detail["grants_withdrawn"] == 1
    assert not any(dc.active_summary(db_session, user.id).values())
    assert dc.active_summary(db_session, other.id)["public_share"] is True  # others untouched
    assert db_session.query(SelfReportFact).filter_by(user_id=user.id).count() == 0
    assert db_session.query(MicroAskLog).filter_by(user_id=user.id).count() == 0
    assert db_session.query(SelfReportFact).filter_by(user_id=other.id).count() == 1
    assert db_session.query(DataConsentEvent).filter_by(event_type="withdrawn", actor="system").count() == 1

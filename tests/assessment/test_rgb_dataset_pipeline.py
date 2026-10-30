"""User upload → admin gold → dataset export → registry gate. Synthetic only."""

import json
from types import SimpleNamespace
import numpy as np
import pytest
from test_rgb_segmentation import photo, isolated  # noqa: F401  (fixtures)
from web.backend.database.models import User
from web.backend.exceptions import RGBSegmentationError
from web.backend.models.image_label import ImageLabel, ImageLabelLog
from web.backend.models.rgb_segmentation import RGBSegmentationJob
from web.backend.models.vasi import VasiTrainingSample
from web.backend.services import data_consent as dc
from web.backend.services.annotation_contract import encode_layer
from web.backend.services.rgb_segmentation import dataset_pipeline as dp
from web.backend.services.rgb_segmentation import pipeline
from web.backend.services.rgb_segmentation.images import png_bytes
from web.backend.services.rgb_segmentation.jobs import claim_job, create_job, serialize_job
from web.backend.services.rgb_segmentation.label_review import save_admin_reference


def run_for(factory, user_id, rgb):
    with factory() as db:
        if not db.get(User, user_id):
            db.add(User(id=user_id, username="synthetic-%d" % user_id, is_active=True))
            db.commit()
        jid = create_job(db, user_id, "synthetic-request-%d" % user_id, png_bytes(rgb), "face", {"capture_date": "2026-09-01"}).id
    with factory() as db:
        lease = claim_job(db).lease
    pipeline.process_job(jid, lease)
    with factory() as db:
        return serialize_job(db.get(RGBSegmentationJob, jid))


def admin_submit(db, label, shape, draft=False):
    skin = np.zeros(shape, bool)
    skin[100:500, 100:700] = True
    lesion = np.zeros(shape, bool)
    lesion[200:300, 300:500] = True
    anns = [{"source": "admin", "skin_mask_data": encode_layer(skin & ~lesion, (147, 197, 253)),
             "mask_data": encode_layer(lesion, (249, 168, 212))}]
    save_admin_reference(db, label, 99, anns, draft)
    label.label_status = "pending" if draft else "labeled"
    db.commit()


def grant(db, user_id):
    dc.create_grant(db, user_id, "model_training", "all_records", text_version=dc.CURRENT_TEXT_VERSION)


def test_gold_requires_submitted_snapshot_and_training_consent(isolated, photo):
    factory, _, _ = isolated
    run_for(factory, 1, photo[0])
    with factory() as db:
        label = db.query(ImageLabel).one()
        with pytest.raises(RGBSegmentationError):
            dp.approve_gold(db, label, 99)  # no snapshot yet
        admin_submit(db, label, photo[0].shape[:2], draft=True)
        with pytest.raises(RGBSegmentationError):
            dp.approve_gold(db, label, 99)  # draft only
        admin_submit(db, label, photo[0].shape[:2])
        with pytest.raises(RGBSegmentationError) as denied:
            dp.approve_gold(db, label, 99)
        assert denied.value.code == "CONSENT_REQUIRED"
        grant(db, 1)
        gold = dp.approve_gold(db, label, 99)
        db.commit()
        state = dp.gold_state(db, label)
        assert state["gold_current"] and state["consent_allowed"]
        assert gold["revision"] == state["snapshot_revision"]
        assert label.training_eligible is False
        assert db.query(ImageLabelLog).filter_by(action="rgb-gold-approved").count() == 1
        dp.revoke_gold(db, label, 99)
        db.commit()
        assert dp.gold_state(db, label)["gold"] is None


def test_legacy_training_paths_never_take_rgb_labels(isolated, photo):
    from web.backend.api import image_label as admin_api

    factory, http, app = isolated
    run_for(factory, 1, photo[0])
    app.include_router(admin_api.router)
    app.dependency_overrides[admin_api.get_current_admin_user] = lambda: SimpleNamespace(id=99)
    with factory() as db:
        label = db.query(ImageLabel).one()
        admin_submit(db, label, photo[0].shape[:2])
        grant(db, 1)
        lid = label.id
    # Gold now only comes from reviewing a versioned submission in the workbench.
    response = http.post("/admin/image-labels/%d/training-sample" % lid)
    assert response.status_code == 409
    assert http.post("/admin/image-labels/%d/label" % lid, json={"training_eligible": True}).status_code == 409
    response = http.post("/admin/training/sync-samples")
    assert response.status_code == 200
    with factory() as db:
        label = db.get(ImageLabel, lid)
        assert db.query(VasiTrainingSample).count() == 0
        assert label.training_eligible is False
        assert dp.gold_state(db, label)["gold"] is None
    detail = http.get("/admin/image-labels/%d" % lid).json()
    assert detail["rgb"]["is_rgb"] and not detail["rgb"]["gold_current"]


def test_export_pseudonymises_splits_by_subject_and_rechecks_consent(isolated, photo):
    factory, _, _ = isolated
    for uid in (1, 2, 3, 4):
        rgb = photo[0].copy()
        rgb[0, 0] = (uid, uid, uid)  # distinct photos
        run_for(factory, uid, rgb)
    with factory() as db:
        for label in db.query(ImageLabel).all():
            admin_submit(db, label, photo[0].shape[:2])
            grant(db, label.original_user_id)
            dp.approve_gold(db, label, 99)
        db.commit()
        withdrawn = db.query(ImageLabel).filter_by(original_user_id=4).one()
        dc.withdraw_grant(db, 4, dc.list_grants(db, 4)[0]["id"])
        report = dp.export_dataset(db, 99)
        status = dp.dataset_status(db)
    assert report["valid"], report["error"]
    assert report["subjects"] == 3
    assert all(report["counts"].values())
    manifest = json.loads((dp.datasets_dir() / report["dataset_id"] / "manifest.json").read_text())
    text = json.dumps(manifest)
    assert "synthetic-1" not in text and '"user_id"' not in text
    subjects = {}
    for item in manifest["items"]:
        subjects.setdefault(item["subject_id"], set()).add(item["split"])
        assert item["subject_id"].startswith("subject_")
    assert all(len(v) == 1 for v in subjects.values())
    assert status["gold"] == 4 and status["gold_consented"] == report["items"]


def test_export_with_too_few_subjects_is_reported_invalid(isolated, photo):
    factory, _, _ = isolated
    run_for(factory, 1, photo[0])
    with factory() as db:
        label = db.query(ImageLabel).one()
        admin_submit(db, label, photo[0].shape[:2])
        grant(db, 1)
        dp.approve_gold(db, label, 99)
        db.commit()
        report = dp.export_dataset(db, 99)
    assert report["valid"] is False and "split" in report["error"]
    with pytest.raises(RGBSegmentationError):
        dp.start_training(report["dataset_id"], 99)


def test_registration_is_refused_below_gate(tmp_path, monkeypatch):
    from web.backend.services.rgb_segmentation import artifacts

    monkeypatch.setattr(artifacts, "ROOT", tmp_path / "private")
    monkeypatch.setattr(artifacts, "PROJECT_ROOT", tmp_path / "project")
    run = dp.runs_dir() / "rgbrun-1"
    run.mkdir(parents=True)
    (run / "status.json").write_text(json.dumps({"run_id": "rgbrun-1", "state": "completed"}))
    rows = [{"subject_id": "subject_%08d" % i} for i in range(3)]
    (run / "eval-model.json").write_text(json.dumps({"synthetic": False, "rows": rows, "summary": {
        "images": 3, "dice": {"mean": 0.9}, "skin_dice": {"mean": 0.95}}}))
    gate = dp.gate_result(run)
    assert not gate["passed"] and len(gate["reasons"]) == 2
    with pytest.raises(RGBSegmentationError) as refused:
        dp.register_run("rgbrun-1", 99)
    assert refused.value.code == "GATE_FAILED"
    assert not dp.registry_path().exists()
    with pytest.raises(RGBSegmentationError):
        dp.register_run("../escape", 99)

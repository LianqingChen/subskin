"""Synthetic RGB to admin lineage and retention regressions, isolated DB/files."""

import json
from datetime import datetime, timedelta
from types import SimpleNamespace
import numpy as np
import pytest
from test_rgb_segmentation import photo, isolated, create_and_run
from web.backend.models.image_label import (
    ImageLabel,
    ImageLabelAnnotation,
    ImageLabelLog,
)
from web.backend.models.rgb_segmentation import RGBSegmentationJob
from web.backend.models.vasi import VASIAssessment
from web.backend.services.rgb_segmentation import artifacts, cleanup, pipeline
from web.backend.services.rgb_segmentation.label_sync import sync_rgb_label
from web.backend.services.rgb_segmentation.label_review import save_admin_reference
from web.backend.services.rgb_segmentation.review import review_job, decode_editor_mask
from web.backend.services.annotation_contract import encode_layer
from web.backend.services.vasi_feedback import VasiFeedbackCollector
from web.backend.exceptions import RGBSegmentationError


def user_review(factory, job, photo):
    skin = np.ones(photo[0].shape[:2], bool)
    lesion = np.zeros_like(skin)
    lesion[200:300, 300:500] = True
    with factory() as db:
        result = review_job(
            db,
            job["id"],
            1,
            job["result"]["mask_revision"],
            encode_layer(skin, (96, 165, 250)),
            encode_layer(lesion, (0, 170, 100)),
            True,
        )
    return result, skin, lesion


def test_completion_syncs_ai_once_with_original_and_source_revision(
    isolated, photo, monkeypatch
):
    candidate = np.zeros(photo[0].shape[:2], bool)
    candidate[200:300, 300:500] = True
    monkeypatch.setattr(
        pipeline,
        "infer_rgb",
        lambda rgb: (
            {
                "skin": np.ones(candidate.shape, bool),
                "lesion": np.zeros_like(candidate),
                "uncertain": candidate,
                "excluded": np.zeros_like(candidate),
            },
            {
                "source": "interactive_rgb_reference",
                "model_id": None,
                "automatic_measurement": False,
            },
        ),
    )
    factory, _, _ = isolated
    job = create_and_run(factory, photo)
    with factory() as db:
        label = db.query(ImageLabel).one()
        details = json.loads(label.ai_details)
        assert (
            label.assessment_id == job["assessment_id"] and not label.training_eligible
        )
        assert details["rgb_sync"]["ai_revision"] == job["result"]["mask_revision"]
        assert artifacts.read_input(job["id"]) == photo[1]
        ai = db.query(ImageLabelAnnotation).filter_by(source="ai").one()
        n = decode_editor_mask(ai.skin_mask_data, photo[0].shape[:2])
        l = decode_editor_mask(ai.mask_data, photo[0].shape[:2])
        assert not (n & l).any() and l.any()
        snapshot = label.ai_details
        sync_rgb_label(db, db.query(VASIAssessment).one())
        db.commit()
        assert (
            db.query(ImageLabel).count() == 1
            and db.query(ImageLabelAnnotation).count() == 1
        )
        assert label.ai_details == snapshot and label.ai_is_vitiligo is None


def test_user_revisions_reopen_review_without_replacing_ai_or_admin(isolated, photo):
    factory, _, _ = isolated
    job = create_and_run(factory, photo)
    result, skin, lesion = user_review(factory, job, photo)
    with factory() as db:
        label = db.query(ImageLabel).one()
        ai = db.query(ImageLabelAnnotation).filter_by(source="ai").one().mask_data
        label.label_status = "labeled"
        label.training_eligible = True
        db.add(
            ImageLabelAnnotation(
                image_label_id=label.id,
                source="admin",
                region_index=0,
                mask_data="retained-admin",
            )
        )
        db.commit()
        lesion[220:225, 330:335] = False
        latest = review_job(
            db,
            job["id"],
            1,
            result["result"]["mask_revision"],
            encode_layer(skin, (96, 165, 250)),
            encode_layer(lesion, (0, 170, 100)),
            True,
        )
        assert label.label_status == "pending" and not label.training_eligible
        assert (
            db.query(ImageLabelAnnotation).filter_by(source="ai").one().mask_data == ai
        )
        assert (
            db.query(ImageLabelAnnotation).filter_by(source="admin").one().mask_data
            == "retained-admin"
        )
        user = db.query(ImageLabelAnnotation).filter_by(source="user").one()
        n = decode_editor_mask(user.skin_mask_data, skin.shape)
        l = decode_editor_mask(user.mask_data, skin.shape)
        assert int(n.sum() + l.sum()) == int(skin.sum()) and np.array_equal(l, lesion)
        assert (
            db.query(ImageLabelLog).filter_by(action="rgb-user-reference").count() == 2
        )
        sync_rgb_label(db, db.query(VASIAssessment).one())
        db.commit()
        assert (
            db.query(ImageLabelLog).filter_by(action="rgb-user-reference").count() == 2
        )
        artifacts.read_manifest(job["id"], result["result"]["mask_revision"])


def test_admin_snapshots_keep_history_and_compute_union_denominator(isolated, photo):
    factory, _, _ = isolated
    job = create_and_run(factory, photo)
    result, skin, lesion = user_review(factory, job, photo)
    with factory() as db:
        a = db.query(VASIAssessment).one()
        original = a.user_lesion_layer
        label = db.query(ImageLabel).one()
        anns = [
            {
                "source": "admin",
                "skin_mask_data": encode_layer(skin & ~lesion, (147, 197, 253)),
                "mask_data": encode_layer(lesion, (249, 168, 212)),
            }
        ]
        area = save_admin_reference(db, label, 2, anns, True)
        db.commit()
        assert area == round(lesion.sum() / skin.sum() * 100, 2)
        save_admin_reference(db, label, 2, anns, False)
        db.commit()
        logs = (
            db.query(ImageLabelLog)
            .filter_by(action="rgb-admin-reference")
            .order_by(ImageLabelLog.id)
            .all()
        )
        assert len(logs) == 2
        first, last = [json.loads(row.new_value) for row in logs]
        assert (
            last["previous_revision"] == first["revision"]
            and last["user_revision"] == result["result"]["mask_revision"]
        )
        for entry in (first, last):
            assert (
                artifacts.ROOT
                / "admin_labels"
                / str(label.id)
                / entry["revision"]
                / "lesion.png"
            ).is_file()
        assert a.user_lesion_layer == original
        label.training_eligible = True
        label.label_status = "labeled"
        label.image_hash = "synthetic"
        assert VasiFeedbackCollector(db).upsert_from_admin_label(label) is None


def test_invalid_admin_mask_and_deleted_record_are_rejected(isolated, photo):
    factory, _, _ = isolated
    create_and_run(factory, photo)
    with factory() as db:
        label = db.query(ImageLabel).one()
        with pytest.raises(RGBSegmentationError):
            save_admin_reference(
                db, label, 2, [{"source": "admin", "mask_data": "invalid"}], False
            )
        assert (
            db.query(ImageLabelLog).filter_by(action="rgb-admin-reference").count() == 0
        )
        label.is_user_deleted = True
        with pytest.raises(RGBSegmentationError):
            save_admin_reference(db, label, 2, [], True)


def test_expired_deleted_observation_removes_new_private_mask_copies(
    isolated, photo, monkeypatch
):
    factory, _, _ = isolated
    job = create_and_run(factory, photo)
    _, skin, lesion = user_review(factory, job, photo)
    with factory() as db:
        label = db.query(ImageLabel).one()
        lid = label.id
        save_admin_reference(
            db,
            label,
            2,
            [
                {
                    "source": "admin",
                    "skin_mask_data": encode_layer(skin, (147, 197, 253)),
                    "mask_data": encode_layer(lesion, (249, 168, 212)),
                }
            ],
            False,
        )
        db.delete(db.query(VASIAssessment).one())
        db.query(RGBSegmentationJob).one().updated_at = datetime.utcnow() - timedelta(
            days=8
        )
        db.commit()
    monkeypatch.setattr(cleanup, "SessionLocal", factory)
    cleanup.cleanup_jobs()
    with factory() as db:
        label = db.query(ImageLabel).get(lid)
        assert label.is_user_deleted and not label.training_eligible
        assert db.query(ImageLabelAnnotation).count() == 0
        assert not (artifacts.ROOT / "admin_labels" / str(lid)).exists()


def test_backfill_upgrades_existing_rgb_label_without_overwriting_admin(
    isolated, photo
):
    factory, _, _ = isolated
    job = create_and_run(factory, photo)
    with factory() as db:
        label = db.query(ImageLabel).one()
        label.ai_details = "{}"
        label.ai_is_vitiligo = True
        db.add(
            ImageLabelAnnotation(
                image_label_id=label.id,
                source="admin",
                region_index=0,
                mask_data="admin-keep",
            )
        )
        db.commit()
        sync_rgb_label(db, db.query(VASIAssessment).one())
        db.commit()
        assert json.loads(label.ai_details)["rgb_sync"]["job_id"] == job["id"]
        assert label.ai_is_vitiligo is None
        assert db.query(ImageLabel).count() == 1
        assert (
            db.query(ImageLabelAnnotation).filter_by(source="admin").one().mask_data
            == "admin-keep"
        )
        assert db.query(ImageLabelAnnotation).filter_by(source="ai").count() == 1


def test_admin_api_requires_admin_and_legacy_export_excludes_rgb(isolated, photo):
    from web.backend.api import image_label as admin_api
    factory,http,app=isolated;create_and_run(factory,photo);app.include_router(admin_api.router)
    with factory() as db:
        label=db.query(ImageLabel).one();lid=label.id;label.label_status="labeled";label.training_eligible=True;label.admin_is_vitiligo=True;db.commit()
    response=http.post(f"/admin/image-labels/{lid}/label",json={"annotations":[]})
    assert response.status_code in (401,403)
    app.dependency_overrides[admin_api.get_current_admin_user]=lambda:SimpleNamespace(id=2)
    response=http.post(f"/admin/image-labels/{lid}/label",json={"annotations":[{"source":"admin","mask_data":"invalid"}]})
    assert response.status_code==400 and "标注与当前照片不一致" in response.text
    response=http.post("/admin/image-labels/training-export",json={})
    assert response.status_code==200 and response.json()["total_count"]==0

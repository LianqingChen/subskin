"""Synthetic, isolated RGB job/measurement/security regression tests."""

import base64
import io
import json
import os
import secrets
from datetime import datetime, timedelta
from types import SimpleNamespace

os.environ.setdefault("SECRET_KEY", secrets.token_hex(32))
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import numpy as np
import pytest
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi import FastAPI
from fastapi.testclient import TestClient
from web.backend.api.rgb_segmentation import router, get_current_user, get_db
from web.backend.api import rgb_segmentation as api
from web.backend.database.database import Base
from web.backend.database.models import User
from web.backend.models.vasi import VASIAssessment
from web.backend.models.rgb_segmentation import RGBSegmentationJob
from web.backend.exceptions import RGBSegmentationError
from web.backend.services.annotation_contract import encode_layer
from web.backend.services.rgb_segmentation import artifacts, pipeline
from web.backend.services.rgb_segmentation.images import (
    canonical_image,
    png_bytes,
    encode_mask,
    decode_binary,
)
from web.backend.services.rgb_segmentation.policy import measure_rgb
from web.backend.services.rgb_segmentation.jobs import (
    create_job,
    claim_job,
    cancel_job,
    serialize_job,
)
from web.backend.services.rgb_segmentation.review import review_job, decode_editor_mask
from web.backend.services.rgb_segmentation.refinement import select_candidate


@pytest.fixture
def photo():
    rng = np.random.default_rng(2)
    rgb = np.clip(
        np.array([178, 137, 112]) + rng.integers(-15, 16, (600, 800, 3)), 0, 255
    ).astype(np.uint8)
    rgb[200:300, 300:500] = np.clip(
        np.array([224, 214, 195]) + rng.integers(-8, 9, (100, 200, 3)), 0, 255
    )
    return rgb, png_bytes(rgb)


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        db.add_all(
            [
                User(id=1, username="synthetic-owner-a", is_active=True),
                User(id=2, username="synthetic-owner-b", is_active=True),
            ]
        )
        db.commit()
    monkeypatch.setattr(artifacts, "ROOT", tmp_path / "private")
    monkeypatch.setattr(artifacts, "PROJECT_ROOT", tmp_path / "project")
    monkeypatch.setattr(pipeline, "SessionLocal", factory)
    monkeypatch.setattr(api, "worker_ready", lambda: True)
    app = FastAPI()
    app.include_router(router)

    def session():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = session
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1)
    with TestClient(app) as http:
        yield factory, http, app
    engine.dispose()


def create_and_run(factory, photo):
    with factory() as db:
        job = create_job(
            db, 1, "synthetic-request", photo[1], "face", {"capture_date": "2026-09-01"}
        )
        jid = job.id
    with factory() as db:
        claimed = claim_job(db)
        lease = claimed.lease
    pipeline.process_job(jid, lease)
    with factory() as db:
        return serialize_job(db.query(RGBSegmentationJob).get(jid))


def test_canonical_exif_and_no_geometric_stretch():
    image = Image.new("RGB", (80, 40), (180, 130, 100))
    exif = image.getexif()
    exif[274] = 6
    out = io.BytesIO()
    image.save(out, format="JPEG", exif=exif)
    rgb, meta = canonical_image(out.getvalue())
    assert rgb.shape[:2] == (80, 40)
    assert meta["original_width"] == 40 and meta["exif_orientation_applied"] == 6
    assert len(meta["sha256"]) == 64


def test_transparent_image_is_not_silently_composited():
    image = Image.new("RGBA", (50, 50), (200, 150, 100, 0))
    out = io.BytesIO()
    image.save(out, format="PNG")
    with pytest.raises(RGBSegmentationError):
        canonical_image(out.getvalue())


def test_canonical_mask_is_binary_and_not_display_overlay():
    mask = np.zeros((40, 60), bool)
    mask[4:18, 7:20] = True
    assert np.array_equal(mask, decode_binary(encode_mask(mask), mask.shape))
    with pytest.raises(RGBSegmentationError):
        decode_binary(png_bytes(np.full(mask.shape, 128, np.uint8)), mask.shape)
    with pytest.raises(RGBSegmentationError):
        decode_editor_mask(encode_layer(mask, (0, 170, 100)), (41, 60))


def test_measurement_requires_review_and_never_invents_scale(photo):
    rgb, image = photo
    skin = np.ones(rgb.shape[:2], bool)
    lesion = np.zeros(skin.shape, bool)
    lesion[200:300, 300:500] = True
    masks = dict(
        skin=skin,
        lesion=lesion,
        uncertain=np.zeros_like(skin),
        excluded=np.zeros_like(skin),
    )
    pending = measure_rgb(rgb, masks, image, False)
    assert (
        pending["status"] == "review_required"
        and pending["measurement"]["area_percentage"] is None
    )
    reviewed = measure_rgb(rgb, masks, image, True)
    assert reviewed["status"] == "measurable"
    assert reviewed["measurement"]["lesion_pixels"] == 20000
    assert reviewed["measurement"]["area_percentage"] == round(20000 / 480000 * 100, 2)
    assert reviewed["measurement"]["area_cm2"] is None


def test_user_acknowledgement_cannot_recover_clipped_information(photo):
    rgb = np.full(photo[0].shape, 255, np.uint8)
    skin = np.ones(rgb.shape[:2], bool)
    masks = dict(
        skin=skin,
        lesion=skin.copy(),
        uncertain=np.zeros_like(skin),
        excluded=np.zeros_like(skin),
    )
    result = measure_rgb(rgb, masks, png_bytes(rgb), True)
    assert (
        result["status"] == "retake_required"
        and result["measurement"]["area_percentage"] is None
    )


def test_outside_lesion_is_rejected_before_clipping(photo):
    rgb, image = photo
    skin = np.zeros(rgb.shape[:2], bool)
    skin[100:500, 100:700] = True
    masks = dict(
        skin=skin,
        lesion=np.ones_like(skin),
        uncertain=np.zeros_like(skin),
        excluded=np.zeros_like(skin),
    )
    with pytest.raises(RGBSegmentationError, match="超出皮肤"):
        measure_rgb(rgb, masks, image, True)


def test_idempotency_and_queue_limits(isolated, photo):
    factory, _, _ = isolated
    with factory() as db:
        first = create_job(db, 1, "same-request", photo[1], "face", {})
        same = create_job(db, 1, "same-request", photo[1], "face", {})
        assert first.id == same.id
        with pytest.raises(RGBSegmentationError) as error:
            create_job(db, 1, "same-request", photo[1], "neck", {})
        assert error.value.http_status == 409
        create_job(db, 1, "next-request", png_bytes(photo[0] ^ 1), "face", {})
        with pytest.raises(RGBSegmentationError) as error:
            create_job(db, 1, "third-request", png_bytes(photo[0] ^ 2), "face", {})
        assert error.value.http_status == 429


def test_duplicate_photo_is_not_recorded_twice(isolated, photo):
    factory, _, _ = isolated
    data = create_and_run(factory, photo)
    with factory() as db:
        with pytest.raises(RGBSegmentationError) as error:
            create_job(db, 1, "duplicate-again", photo[1], "face", {})
        assert error.value.code == "DUPLICATE_IMAGE"
        assert error.value.http_status == 409
        # 同一张照片换到别的部位仍是新记录
        create_job(db, 1, "other-site", photo[1], "neck", {})
        # 已放弃的记录不阻止重新记录
        record = db.query(VASIAssessment).filter_by(id=data["assessment_id"]).one()
        record.status = "abandoned"
        db.commit()
        again = create_job(db, 1, "after-abandon", photo[1], "face", {})
        assert again.id != data["id"]


def test_in_flight_photo_blocks_resubmission(isolated, photo):
    factory, _, _ = isolated
    with factory() as db:
        first = create_job(db, 1, "in-flight", photo[1], "face", {})
        with pytest.raises(RGBSegmentationError) as error:
            create_job(db, 1, "in-flight-again", photo[1], "face", {})
        assert error.value.code == "DUPLICATE_IMAGE"
        other = create_job(
            db, 1, "in-flight-other", png_bytes(photo[0] ^ 3), "face", {}
        )
        assert other.id != first.id


def test_job_pipeline_keeps_untrained_results_pending(isolated, photo):
    factory, http, _ = isolated
    data = create_and_run(factory, photo)
    assert data["state"] == "completed" and data["assessment_id"]
    assert (
        data["result"]["status"] == "review_required"
        and data["result"]["measurement"] is None
    )
    assert data["result"]["confidence"]["score"] is None
    revision = data["result"]["mask_revision"]
    response = http.get(
        "/segmentation-jobs/%s/artifacts/%s/skin" % (data["id"], revision)
    )
    assert (
        response.status_code == 200
        and response.headers["cache-control"] == "private, no-store"
    )
    assert Image.open(io.BytesIO(response.content)).mode == "L"


def test_owner_boundaries_include_read_cancel_masks_and_review(isolated, photo):
    factory, http, app = isolated
    data = create_and_run(factory, photo)
    job_id = data["id"]
    revision = data["result"]["mask_revision"]
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=2)
    for path in [
        f"/segmentation-jobs/{job_id}",
        f"/segmentation-jobs/{job_id}/artifacts/{revision}/skin",
        f"/segmentation-jobs/{job_id}/overlays/{revision}/lesion",
    ]:
        assert http.get(path).status_code == 404
    assert http.post(f"/segmentation-jobs/{job_id}/cancel").status_code == 404


def test_cancel_and_expiry_prevent_late_assessment(isolated, photo):
    factory, _, _ = isolated
    with factory() as db:
        job = create_job(db, 1, "cancel-request", photo[1], "face", {})
        jid = job.id
        lease = claim_job(db).lease
        cancel_job(db, jid, 1)
    with pytest.raises(RGBSegmentationError):
        pipeline.process_job(jid, lease)
    with factory() as db:
        assert db.query(VASIAssessment).count() == 0
        job = create_job(db, 1, "expire-request", photo[1], "face", {})
        job.deadline_at = datetime.utcnow() - timedelta(seconds=1)
        db.commit()
        assert serialize_job(job)["error_code"] == "TIMEOUT"
        claim_job(db)
        assert db.query(VASIAssessment).count() == 0


def test_review_versions_audit_and_original_masks(isolated, photo):
    factory, http, _ = isolated
    data = create_and_run(factory, photo)
    shape = photo[0].shape[:2]
    skin = np.ones(shape, bool)
    lesion = np.zeros(shape, bool)
    lesion[200:300, 300:500] = True
    payload = {
        "base_revision": data["result"]["mask_revision"],
        "skin_mask": encode_layer(skin, (96, 165, 250)),
        "lesion_mask": encode_layer(lesion, (0, 170, 100)),
        "acknowledged": True,
    }
    response = http.patch("/segmentation-jobs/%s/review" % data["id"], json=payload)
    assert response.status_code == 200, response.text
    assert (
        response.json()["measurement"]["annotation"]["review_state"] == "user_reviewed"
    )
    assert response.json()["result"]["measurement"]["area_cm2"] is None
    assert (
        http.patch(
            "/segmentation-jobs/%s/review" % data["id"], json=payload
        ).status_code
        == 409
    )
    with factory() as db:
        assessment = db.query(VASIAssessment).get(data["assessment_id"])
        details = json.loads(assessment.details)
        assert details["raw_annotation"]["review_state"] == "pending"
        assert len(details["annotation_reviews"]) == 1
        assert assessment.auto_finalized is False and assessment.status == "draft"


def test_artifact_tampering_is_detected(isolated, photo):
    factory, _, _ = isolated
    data = create_and_run(factory, photo)
    rev = data["result"]["mask_revision"]
    (artifacts.job_directory(data["id"]) / rev / "skin.png").write_bytes(b"corrupt")
    with pytest.raises(RGBSegmentationError):
        artifacts.read_artifact(data["id"], rev, "skin")


def test_legacy_feedback_never_exports_rgb_reference():
    from web.backend.services.vasi_feedback import VasiFeedbackCollector

    result = VasiFeedbackCollector._upsert_training_sample(
        SimpleNamespace(), SimpleNamespace(assessment_source="rgb-tools-v1")
    )
    assert result is None


def test_manifest_hash_binds_metadata_and_masks(isolated, photo):
    factory, _, _ = isolated
    data = create_and_run(factory, photo)
    rev = data["result"]["mask_revision"]
    path = artifacts.job_directory(data["id"]) / rev / "metadata.json"
    value = json.loads(path.read_text())
    value["metadata"]["image"]["width"] += 1
    path.write_text(json.dumps(value))
    with pytest.raises(RGBSegmentationError):
        artifacts.read_artifact(data["id"], rev, "skin")


def test_disabled_owner_cannot_finish_job(isolated, photo):
    factory, _, _ = isolated
    with factory() as db:
        job = create_job(db, 1, "owner-disabled-request", photo[1], "face", {})
        jid = job.id
        lease = claim_job(db).lease
        db.query(User).filter_by(id=1).update({"is_active": False})
        db.commit()
    with pytest.raises(RGBSegmentationError):
        pipeline.process_job(jid, lease)
    with factory() as db:
        assert db.query(VASIAssessment).count() == 0


def test_refinement_uses_supported_candidate_not_highest_sam_score(
    isolated, photo, monkeypatch
):
    from web.backend.services.rgb_segmentation import refinement

    factory, _, _ = isolated
    parent = create_and_run(factory, photo)
    monkeypatch.setattr(refinement, "SessionLocal", factory)
    shape = photo[0].shape[:2]
    skin = np.ones(shape, bool)
    target = np.zeros(shape, bool)
    target[200:300, 300:500] = True
    with factory() as db:
        child = refinement.enqueue_refinement(
            db,
            parent["id"],
            1,
            "refinement-test",
            parent["result"]["mask_revision"],
            encode_layer(skin, (96, 165, 250)),
            [{"x": 400.5 / 800, "y": 250.5 / 600, "label": 1}],
            [0.25, 0.22, 0.75, 0.61],
        )
        cid = child.id
        leased = claim_job(db)
        lease = leased.lease
        context = json.loads(leased.context_json)
    monkeypatch.setattr(
        refinement.vasi_promptable, "prepare_image", lambda *a: {"cached": False}
    )
    monkeypatch.setattr(
        refinement.vasi_promptable,
        "predict_by_points",
        lambda *a, **kw: {
            "candidates": [
                {"mask_b64_png": encode_layer(skin, (0, 170, 100)), "score": 1.0},
                {"mask_b64_png": encode_layer(target, (0, 170, 100)), "score": 0.7},
            ]
        },
    )
    refinement.process_refinement(cid, lease, context)
    with factory() as db:
        data = serialize_job(db.query(RGBSegmentationJob).filter_by(id=cid).one())
        assert data["state"] == "completed"
        assert data["assessment_id"] is None
        assert data["result"]["measurement"] is None
        assert db.query(VASIAssessment).count() == 1
    mask = decode_binary(
        artifacts.read_artifact(cid, data["result"]["mask_revision"], "lesion"), shape
    )
    assert np.array_equal(mask, target)


def test_refinement_rejects_stale_revision_and_invalid_points(isolated, photo):
    from web.backend.services.rgb_segmentation.refinement import enqueue_refinement

    factory, _, _ = isolated
    parent = create_and_run(factory, photo)
    data = encode_layer(np.ones(photo[0].shape[:2], bool), (96, 165, 250))
    with factory() as db:
        with pytest.raises(RGBSegmentationError):
            enqueue_refinement(
                db,
                parent["id"],
                1,
                "bad-refinement",
                "0" * 64,
                data,
                [{"x": 0.5, "y": 0.5, "label": 1}],
                None,
            )
        with pytest.raises(RGBSegmentationError):
            enqueue_refinement(
                db,
                parent["id"],
                1,
                "bad-refinement",
                parent["result"]["mask_revision"],
                data,
                [{"x": 0.5, "y": 0.5, "label": 0}],
                None,
            )
        assert db.query(RGBSegmentationJob).count() == 1


def test_private_artifacts_expire_but_active_observations_remain(
    isolated, photo, monkeypatch
):
    from web.backend.services.rgb_segmentation import cleanup

    factory, _, _ = isolated
    active = create_and_run(factory, photo)
    monkeypatch.setattr(cleanup, "SessionLocal", factory)
    with factory() as db:
        record = db.query(VASIAssessment).filter_by(id=active["assessment_id"]).one()
        record.status = "active"
        job = db.query(RGBSegmentationJob).filter_by(id=active["id"]).one()
        job.updated_at = datetime.utcnow() - timedelta(days=8)
        db.commit()
        expired = create_job(
            db, 1, "expired-private", png_bytes(photo[0] ^ 2), "face", {}
        )
        expired.state = "failed"
        expired.updated_at = datetime.utcnow() - timedelta(days=8)
        eid = expired.id
        db.commit()
    cleanup.cleanup_jobs()
    assert artifacts.job_directory(active["id"]).exists()
    assert not artifacts.job_directory(eid).exists()
    with factory() as db:
        assert db.query(RGBSegmentationJob).filter_by(id=eid).first() is None
    # Account erasure removes the private revisions and any orphaned observation.
    with factory() as db:
        db.query(User).filter_by(id=1).delete(synchronize_session=False)
        db.commit()
    cleanup.cleanup_jobs()
    assert not artifacts.job_directory(active["id"]).exists()
    with factory() as db:
        assert db.query(VASIAssessment).count() == 0


def test_registry_rejects_unreviewed_weights_and_path_escape(tmp_path, monkeypatch):
    import hashlib
    from web.backend.services.rgb_segmentation import registry

    root = tmp_path / "project"
    weights = root / "models/rgb/model.pt"
    weights.parent.mkdir(parents=True)
    weights.write_bytes(b"synthetic-not-an-executable-model")
    manifest = tmp_path / "registry.json"
    monkeypatch.setattr(registry, "PROJECT_ROOT", root)
    monkeypatch.setenv("RGB_SEGMENTATION_REGISTRY", str(manifest))
    entry = {
        "enabled": True,
        "model_id": "synthetic-registry-test",
        "input_type": "rgb_photo",
        "format": "torchscript",
        "weights": "model.pt",
        "sha256": hashlib.sha256(weights.read_bytes()).hexdigest(),
        "labels": registry.LABELS,
        "dataset_review_id": "test-review",
        "training_source": "synthetic",
        "automatic_measurement": True,
    }
    manifest.write_text(json.dumps(entry))
    with pytest.raises(RGBSegmentationError):
        registry.registered_model()
    entry["training_source"] = "authorized_reviewed_manifest"
    manifest.write_text(json.dumps(entry))
    assert registry.registered_model()["automatic_measurement"] is False
    entry["weights"] = "../../outside.pt"
    manifest.write_text(json.dumps(entry))
    with pytest.raises(RGBSegmentationError):
        registry.registered_model()


def test_registered_rgb_adapter_keeps_measurement_manual(photo, tmp_path, monkeypatch):
    import torch
    from web.backend.services.rgb_segmentation import inference

    class ToyModel(torch.nn.Module):
        def forward(self, x):
            out = torch.zeros((x.shape[0], 5, x.shape[2], x.shape[3]))
            out[:, 1] = 10
            out[:, 2] = torch.where(x[:, 0] > 0.8, 20.0, 0.0)
            return out

    weights = tmp_path / "toy.pt"
    torch.jit.trace(ToyModel(), torch.zeros(1, 3, 64, 64)).save(str(weights))
    monkeypatch.setattr(
        inference,
        "registered_model",
        lambda: {
            "resolved_weights": str(weights),
            "weights_bytes": weights.read_bytes(),
            "model_id": "synthetic-adapter-test",
            "sha256": "f" * 64,
            "automatic_measurement": True,
        },
    )
    masks, metadata = inference.infer_rgb(photo[0])
    assert masks["lesion"].sum() == 20000
    assert not masks["uncertain"].any()
    assert metadata["automatic_measurement"] is False


def test_storage_quota_is_checked_before_upload_write(isolated, photo, monkeypatch):
    from web.backend.services.rgb_segmentation import jobs

    factory, _, _ = isolated
    monkeypatch.setattr(jobs, "MAX_ESTIMATED_USER_BYTES", 1)
    with factory() as db:
        with pytest.raises(RGBSegmentationError) as err:
            jobs.create_job(db, 1, "quota-test", photo[1], "face", {})
        assert err.value.http_status == 429
        assert db.query(RGBSegmentationJob).count() == 0
    assert not (artifacts.ROOT / "jobs").exists()


def test_opaque_binary_editor_png_is_supported_but_photo_is_not():
    rgb = np.full((40, 50, 3), (96, 165, 250), np.uint8)
    url = "data:image/png;base64," + base64.b64encode(png_bytes(rgb)).decode()
    assert decode_editor_mask(url, (40, 50)).all()
    rgb[0, 0] = [13, 87, 201]
    url = "data:image/png;base64," + base64.b64encode(png_bytes(rgb)).decode()
    with pytest.raises(RGBSegmentationError):
        decode_editor_mask(url, (40, 50))


def test_rgb_pipeline_does_not_call_configured_language_model(
    isolated, photo, monkeypatch
):
    from web.backend.services import annotation_provider
    from web.backend.utils import llm_config

    def forbidden(*args, **kwargs):
        raise AssertionError("RGB masks must not depend on language model calls")

    monkeypatch.setattr(annotation_provider, "propose_annotation", forbidden)
    monkeypatch.setattr(llm_config, "get_llm_config", forbidden)
    data = create_and_run(isolated[0], photo)
    assert data["state"] == "completed"
    assert data["result"]["confidence"]["score"] is None


def test_rgb_photo_uses_existing_private_file_ownership_contract(isolated, photo):
    from fastapi import HTTPException
    from web.backend.api.files import _assert_path_ownership

    factory, _, _ = isolated
    data = create_and_run(factory, photo)
    with factory() as db:
        user = db.query(User).filter_by(id=1).one()
        _assert_path_ownership("vasi/rgb_" + data["id"] + ".png", user, db)
        other = db.query(User).filter_by(id=2).one()
        with pytest.raises(HTTPException):
            _assert_path_ownership("vasi/rgb_" + data["id"] + ".png", other, db)

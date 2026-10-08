"""Isolated tests for the high-resolution vision outline job (no network)."""
import base64
import io
import json
import os
import secrets
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
from web.backend.services import vision_outline, vasi_promptable
from web.backend.services.annotation_contract import encode_layer
from web.backend.services.rgb_segmentation import artifacts, pipeline
from web.backend.services.rgb_segmentation import outline as outline_job
from web.backend.services.rgb_segmentation.images import canonical_image, png_bytes
from web.backend.services.rgb_segmentation.jobs import (
    create_job,
    claim_job,
    serialize_job,
)

SYNTHETIC_DOC = {
    "protocol": "skin-outline-v1",
    "status": "candidate",
    "skin_regions": [[[0.02, 0.02], [0.98, 0.02], [0.98, 0.98], [0.02, 0.98]]],
    "excluded_regions": [],
    "lesion_regions": [[[0.35, 0.3], [0.75, 0.3], [0.75, 0.72], [0.35, 0.72]]],
    "uncertain_regions": [],
}


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


def create_and_run(factory, photo_bytes):
    with factory() as db:
        job = create_job(db, 1, "synthetic-request", photo_bytes, "face",
                         {"capture_date": "2026-09-20"})
        jid = job.id
    with factory() as db:
        lease = claim_job(db).lease
    pipeline.process_job(jid, lease)
    with factory() as db:
        return serialize_job(db.query(RGBSegmentationJob).get(jid))


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
        db.add_all([
            User(id=1, username="synthetic-owner-a", is_active=True),
            User(id=2, username="synthetic-owner-b", is_active=True),
        ])
        db.commit()
    monkeypatch.setattr(artifacts, "ROOT", tmp_path / "private")
    monkeypatch.setattr(artifacts, "PROJECT_ROOT", tmp_path / "project")
    monkeypatch.setattr(pipeline, "SessionLocal", factory)
    monkeypatch.setattr(outline_job, "SessionLocal", factory)
    monkeypatch.setattr(api, "worker_ready", lambda: True)
    app = FastAPI()
    app.include_router(router)

    def session():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = session
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1)
    with TestClient(app) as http:
        yield factory, http
    engine.dispose()


@pytest.fixture
def stubs(monkeypatch):
    async def fake_call(client, model, image_b64, prompt, *, thinking, max_tokens, timeout_s):
        return dict(SYNTHETIC_DOC), {"latency_s": 0.01, "thinking": thinking, "tokens": None}

    monkeypatch.setattr(vision_outline, "_call_outline", fake_call)
    monkeypatch.setattr(
        "web.backend.utils.llm_config.get_llm_config",
        lambda key: {"vision_model": "stub-model", "api_key": "stub",  # pragma: allowlist secret
                     "base_url": "http://stub.invalid"},
    )
    monkeypatch.setattr(vasi_promptable, "prepare_image", lambda *a, **k: {"cached": True})

    def fake_predict(key, points, multimask=False, box=None, **kwargs):
        mask = np.zeros((600, 800), bool)
        mask[180:432, 280:600] = True
        return {"mask_b64_png": encode_layer(mask, (0, 170, 100)), "score": 0.9}

    monkeypatch.setattr(vasi_promptable, "predict_by_points", fake_predict)


def test_zoom_remap_and_thinking_primitives():
    box = [0.2, 0.4, 0.6, 0.8]
    remapped = vision_outline.remap_polygon(
        [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]], box
    )
    assert remapped == [[0.2, 0.4], [0.6, 0.4], [0.6, 0.8], [0.2, 0.8]]
    padded = vision_outline.crop_box_for_polygon([[0.5, 0.5], [0.55, 0.55]])
    assert padded[2] - padded[0] >= 0.18 - 1e-9 and padded[3] - padded[1] >= 0.18 - 1e-9
    assert vision_outline.thinking_extra_body("off") == {"enable_thinking": False}
    assert vision_outline.thinking_extra_body("default") is None
    assert vision_outline.thinking_extra_body("medium")["reasoning_effort"] == "medium"


def test_safe_raster_skips_malformed_regions():
    mask = vision_outline.safe_raster(
        [[[0.0, 0.0], [1.0, 1.0]], [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]]],
        64, 64,
    )
    assert mask.any()


def test_consensus_keeps_intersection_and_flags_disputes():
    doc_a = {**SYNTHETIC_DOC, "lesion_regions": [[[0.2, 0.2], [0.6, 0.2], [0.6, 0.6], [0.2, 0.6]]]}
    doc_b = {**SYNTHETIC_DOC, "lesion_regions": [[[0.4, 0.4], [0.8, 0.4], [0.8, 0.8], [0.4, 0.8]]]}
    merged, iou = vision_outline.consensus_documents(doc_a, doc_b, 100, 100)
    assert 0 < iou < 1
    assert merged["lesion_regions"]
    assert merged["uncertain_regions"]


def test_canonical_image_high_res_side():
    image = Image.new("RGB", (3000, 2000), (180, 130, 100))
    out = io.BytesIO()
    image.save(out, format="PNG")
    rgb, meta = canonical_image(out.getvalue(), max_side=2048)
    assert max(rgb.shape[:2]) == 2048
    assert meta["transform_id"] == "exif-srgb-fit2048-v1"
    default_rgb, default_meta = canonical_image(out.getvalue())
    assert max(default_rgb.shape[:2]) == 1024
    assert default_meta["transform_id"] == "exif-srgb-fit1024-v1"


def test_outline_rejects_stale_revision(isolated, photo):
    factory, _ = isolated
    data = create_and_run(factory, photo[1])
    with factory() as db:
        with pytest.raises(RGBSegmentationError):
            outline_job.enqueue_outline(db, data["id"], 1, "outline-stale", "0" * 64)


def test_outline_job_roundtrip(isolated, photo, stubs):
    factory, http = isolated
    data = create_and_run(factory, photo[1])
    revision = data["result"]["mask_revision"]
    response = http.post(
        "/segmentation-jobs/%s/outline" % data["id"],
        json={"idempotency_key": "outline-request-1", "base_revision": revision},
    )
    assert response.status_code == 202, response.text
    oid = response.json()["id"]
    with factory() as db:
        leased = claim_job(db)
        assert leased.id == oid
        lease = leased.lease
    pipeline.process_job(oid, lease)
    with factory() as db:
        done = serialize_job(db.query(RGBSegmentationJob).filter_by(id=oid).one())
        assert done["state"] == "completed"
        assert done["assessment_id"] is None
        assert db.query(VASIAssessment).count() == 1
        parent = db.query(RGBSegmentationJob).filter_by(id=data["id"]).one()
        assert json.loads(parent.result_json)["mask_revision"] == revision
    masked = http.get(f"/segmentation-jobs/{oid}/artifacts/{done['result']['mask_revision']}/lesion")
    assert masked.status_code == 200
    lesion = np.asarray(Image.open(io.BytesIO(masked.content))) > 0
    uncertain = http.get(f"/segmentation-jobs/{oid}/artifacts/{done['result']['mask_revision']}/uncertain")
    uncertain_mask = np.asarray(Image.open(io.BytesIO(uncertain.content))) > 0
    assert (lesion | uncertain_mask).any()
    overlay = http.get(f"/segmentation-jobs/{oid}/overlays/{done['result']['mask_revision']}/lesion")
    assert overlay.status_code == 200
    mask_url = overlay.json()["mask_data_url"]
    assert mask_url.startswith("data:image/png;base64,")
    decoded = Image.open(io.BytesIO(base64.b64decode(mask_url.split(",", 1)[1])))
    assert decoded.mode == "RGBA"

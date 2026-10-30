"""Five-class admin labeling: visibility, versions, review, benchmark, export, uploads."""

import base64
import io
import json
import re
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

from test_rgb_dataset_pipeline import grant, run_for
from test_rgb_segmentation import isolated, photo  # noqa: F401  (fixtures)
from web.backend.database.models import User
from web.backend.exceptions import RGBSegmentationError
from web.backend.models.image_label import ImageLabel
from web.backend.models.label_submission import LabelSubmission
from web.backend.services import data_consent as dc
from web.backend.services.labeling import class_map, sources, submissions, tasks, uploads, workflow
from web.backend.services.rgb_segmentation import artifacts
from web.backend.services.rgb_segmentation import dataset_pipeline as dp
from web.backend.services.rgb_segmentation.images import png_bytes
from web.backend.utils.assessment_body_sites import BODY_SITE_LABELS
from web.backend.utils.body_sites import group_of, normalize

ADMIN, OTHER = 90, 91


def canvas_url(labels: np.ndarray) -> str:
    """Encode like the browser editor: RGBA canvas, red channel = class, opaque."""
    rgba = np.zeros((*labels.shape, 4), np.uint8)
    rgba[..., 0] = rgba[..., 1] = rgba[..., 2] = labels
    rgba[..., 3] = 255
    out = io.BytesIO()
    Image.fromarray(rgba, "RGBA").save(out, format="PNG")
    return "data:image/png;base64," + base64.b64encode(out.getvalue()).decode()


def drawn(shape, unknown_band=True):
    labels = np.zeros(shape, np.uint8)
    labels[100:500, 100:700] = class_map.NORMAL
    labels[200:300, 300:500] = class_map.LESION
    labels[100:110, 100:700] = class_map.OCCLUSION
    if unknown_band:
        labels[0:20, :] = class_map.UNKNOWN
    return labels


def admins(factory):
    with factory() as db:
        for uid in (ADMIN, OTHER):
            if not db.get(User, uid):
                db.add(User(id=uid, username="admin-%d" % uid, is_active=True, is_admin=True))
        db.commit()


ATTRS = {"monk_skin_tone": 4, "lighting": "indoor", "shot_type": "close", "quality_issues": []}


def test_class_map_codec_and_metrics():
    labels = drawn((600, 800))
    assert (class_map.from_data_url(canvas_url(labels), (600, 800)) == labels).all()
    assert (class_map.from_png(class_map.to_png(labels), (600, 800)) == labels).all()
    bad = labels.copy()
    bad[0, 0] = 7
    with pytest.raises(RGBSegmentationError):
        class_map.from_data_url(canvas_url(bad), (600, 800))
    with pytest.raises(RGBSegmentationError):
        class_map.from_data_url(canvas_url(labels), (601, 800))
    other = labels.copy()
    other[0:20, :] = class_map.LESION  # inside the other map's unknown band → ignored
    assert class_map.dice(labels, other, class_map.LESION) == 1.0
    summary = class_map.stats(labels)
    assert summary["lesion_ratio"] == round(100 * 20000 / (400 * 600 - 10 * 600), 2)


def test_body_site_taxonomy_matches_diary_and_keeps_stored_labels():
    diary = Path(__file__).resolve().parents[2] / "web/app/src/constants/bodySites.ts"
    union = re.search(r"export type BodySite =(.+?)\n\n", diary.read_text(), re.S).group(1)
    codes = set(re.findall(r"'([a-z_]+)'", union))
    assert codes and codes <= set(BODY_SITE_LABELS)
    assert BODY_SITE_LABELS["head"] == "头部" and BODY_SITE_LABELS["neck"] == "颈部"
    assert normalize("躯干后面") == "back" and group_of("左臂") == "arm" and group_of("??") == "unknown"


def test_diary_tasks_are_hidden_until_training_consent(isolated, photo):
    factory, _, _ = isolated
    run_for(factory, 1, photo[0])
    with factory() as db:
        assert tasks.list_tasks(db, ADMIN, {}, 20, 0)["total"] == 0
        assert tasks.stats(db)["hidden_unconsented"] == 1
        label = db.query(ImageLabel).one()
        with pytest.raises(RGBSegmentationError):
            tasks.get_visible(db, label.id)
        grant(db, 1)
        listed = tasks.list_tasks(db, ADMIN, {"status": "open"}, 20, 0)
        assert listed["total"] == 1 and listed["items"][0]["origin"] == "diary"
        detail = tasks.detail(db, tasks.get_visible(db, label.id), ADMIN)
    assert detail["image"] == {"width": 800, "height": 600}
    ai = class_map.from_data_url(detail["layers"]["ai"], (600, 800))
    assert set(np.unique(ai)) <= {0, 1, 2, 255}


def test_submit_review_and_export_keep_unknown_pixels(isolated, photo, monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "synthetic-key")
    factory, _, _ = isolated
    admins(factory)
    for uid in (1, 2, 3):
        rgb = photo[0].copy()
        rgb[0, 0] = (uid, uid, uid)
        run_for(factory, uid, rgb)
    with factory() as db:
        for label in db.query(ImageLabel).all():
            grant(db, label.original_user_id)
            row = submissions.submit(db, label, ADMIN, canvas_url(drawn((600, 800))), ATTRS, "ai", 42000)
            assert label.label_status == "in_review" and row.stats
            assert json.loads(row.stats)["vs_ai"] is not None
            with pytest.raises(RGBSegmentationError):
                workflow.return_submission(db, row.id, OTHER, "")  # note required
            workflow.approve(db, row.id, ADMIN)
            assert row.review_mode == "single_review" and label.label_status == "gold"
        db.commit()
        report = dp.export_dataset(db, ADMIN)
    assert report["valid"], report["error"]
    folder = dp.datasets_dir() / report["dataset_id"]
    manifest = json.loads((folder / "manifest.json").read_text())
    item = manifest["items"][0]
    mask = np.asarray(Image.open(folder / item["mask"]))
    assert set(np.unique(mask)) == {0, 1, 2, 3, 255}
    assert item["groups"]["skin_tone"] == "mst_4" and item["groups"]["body_site"] == "head"
    assert item["provenance"]["review_mode"] == "single_review"
    assert item["provenance"]["annotator"].startswith("annotator_") and "90" not in item["provenance"]["annotator"]


def test_benchmark_requires_blind_label_and_second_reviewer(isolated, photo):
    factory, _, _ = isolated
    admins(factory)
    run_for(factory, 1, photo[0])
    with factory() as db:
        grant(db, 1)
        label = db.query(ImageLabel).one()
        prefilled = submissions.submit(db, label, ADMIN, canvas_url(drawn((600, 800))), ATTRS, "ai")
        workflow.approve(db, prefilled.id, ADMIN)
        workflow.set_benchmark(db, label, ADMIN, True)
        assert prefilled.status == "superseded" and sources.sync_of(label).get("gold") is None
        assert label.label_status == "pending"
        assert tasks.detail(db, label, ADMIN)["layers"]["ai"] is None  # blind
        with pytest.raises(RGBSegmentationError) as blind:
            submissions.submit(db, label, ADMIN, canvas_url(drawn((600, 800))), ATTRS, "ai")
        assert blind.value.code == "BLIND_REQUIRED"
        row = submissions.submit(db, label, ADMIN, canvas_url(drawn((600, 800))), ATTRS, "none")
        with pytest.raises(RGBSegmentationError) as dual:
            workflow.approve(db, row.id, ADMIN)
        assert dual.value.code == "DUAL_REVIEW_REQUIRED"
        workflow.approve(db, row.id, OTHER)
        assert row.review_mode == "dual" and sources.sync_of(label)["gold"]["submission_id"] == row.id


def test_rejecting_revokes_gold_and_reopen_restores_queue(isolated, photo):
    factory, _, _ = isolated
    admins(factory)
    run_for(factory, 1, photo[0])
    with factory() as db:
        grant(db, 1)
        label = db.query(ImageLabel).one()
        row = submissions.submit(db, label, ADMIN, canvas_url(drawn((600, 800))), ATTRS, "user")
        workflow.approve(db, row.id, ADMIN)
        with pytest.raises(RGBSegmentationError):
            workflow.set_status(db, label, ADMIN, "rejected", [])
        workflow.set_status(db, label, ADMIN, "rejected", ["glare", "identifiable"])
        assert label.label_status == "rejected" and not sources.sync_of(label).get("gold")
        assert dp._gold_rows(db) == []
        with pytest.raises(RGBSegmentationError):
            submissions.submit(db, label, ADMIN, canvas_url(drawn((600, 800))), ATTRS)
        workflow.set_status(db, label, ADMIN, "pending", [])
        assert label.label_status == "pending" and "rejection" not in sources.sync_of(label)


def test_uploads_are_canonical_visible_and_grouped_by_subject_ref(isolated, photo, monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "synthetic-key")
    factory, _, _ = isolated
    admins(factory)
    second = photo[0].copy()
    second[0, 0] = (1, 2, 3)
    with factory() as db:
        with pytest.raises(RGBSegmentationError):
            uploads.upload_photos(db, ADMIN, [("a.png", photo[1])], "合作医院A", None, False)
        result = uploads.upload_photos(
            db, ADMIN, [("a.png", photo[1]), ("dup.png", photo[1]), ("b.png", png_bytes(second))],
            "合作医院A 授权研究", "patient-007", True,
        )
        db.commit()
        assert len(result["created"]) == 2 and result["skipped"][0]["reason"] == "重复图片"
        labels = [db.get(ImageLabel, i) for i in result["created"]]
        assert all(l.original_user_id is None and sources.kind(l) == "upload" for l in labels)
        assert tasks.list_tasks(db, ADMIN, {}, 20, 0)["total"] == 2
        assert tasks.list_tasks(db, ADMIN, {"external": "any"}, 20, 0)["total"] == 0  # no attribution given
        assert len({dp._label_subject(l) for l in labels}) == 1
        image, shape = sources.canonical(labels[0])
        assert shape == (600, 800) and image.startswith(b"\x89PNG")


def test_legacy_rows_import_into_the_workflow(isolated, photo):
    factory, _, _ = isolated
    admins(factory)
    target = artifacts.PROJECT_ROOT / "data" / "uploads" / "vasi" / "old.png"
    target.parent.mkdir(parents=True)
    target.write_bytes(photo[1])
    with factory() as db:
        old = ImageLabel(original_user_id=ADMIN, image_url="/api/files/serve/vasi/old.png", label_status="labeled")
        escape = ImageLabel(original_user_id=ADMIN, image_url="/api/files/serve/../../etc/passwd")
        db.add_all([old, escape])
        db.commit()
        refused = uploads.import_all_legacy(db, ADMIN)  # admin-uploaded rows need a rights confirmation
        assert refused["imported"] == [] and old.original_user_id == ADMIN
        result = uploads.import_all_legacy(db, ADMIN, rights_confirmed=True)
        db.commit()
        assert result["imported"] == [old.id] and result["failed"][0]["id"] == escape.id
        assert sources.sync_of(old)["provenance"]["rights_confirmed_by"] == ADMIN
        assert old.original_user_id is None and old.label_status == "pending"
        assert sources.kind(old) == "upload" and sources.ai_draft(old) is not None


def test_withdrawal_purges_exported_datasets(isolated, photo, monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "synthetic-key")
    factory, _, _ = isolated
    admins(factory)
    run_for(factory, 1, photo[0])
    with factory() as db:
        grant(db, 1)
        label = db.query(ImageLabel).one()
        row = submissions.submit(db, label, ADMIN, canvas_url(drawn((600, 800))), ATTRS, "ai")
        workflow.approve(db, row.id, ADMIN)
        db.commit()
        report = dp.export_dataset(db, ADMIN)
        assert (dp.datasets_dir() / report["dataset_id"]).exists()
        dc.withdraw_grant(db, 1, dc.list_grants(db, 1)[0]["id"])
        assert dp.prune_datasets(db) == 1
        assert not (dp.datasets_dir() / report["dataset_id"]).exists()


def test_workbench_api_flow_and_legacy_manifest_guard(isolated, photo):
    from web.backend.api import image_label as legacy_api
    from web.backend.api import labeling_admin

    factory, http, app = isolated
    admins(factory)
    run_for(factory, 1, photo[0])
    app.include_router(labeling_admin.router)
    app.include_router(legacy_api.router)
    assert http.get("/admin/labeling/tasks").status_code in (401, 403)
    app.dependency_overrides[labeling_admin.get_current_admin_user] = lambda: SimpleNamespace(id=ADMIN)
    app.dependency_overrides[legacy_api.get_current_admin_user] = lambda: SimpleNamespace(id=ADMIN)
    with factory() as db:
        grant(db, 1)
        lid = db.query(ImageLabel).one().id
    assert http.get("/admin/labeling/tasks/%d/image" % lid).headers["content-type"] == "image/png"
    assert http.get("/admin/labeling/tasks/%d/image?size=thumb" % lid).headers["content-type"] == "image/jpeg"
    body = {"labels": canvas_url(drawn((600, 800))), "attributes": ATTRS, "prefill_source": "ai"}
    submitted = http.post("/admin/labeling/tasks/%d/submissions" % lid, json=body)
    assert submitted.status_code == 200, submitted.text
    sid = submitted.json()["submission_id"]
    assert http.post("/admin/labeling/submissions/%d/return" % sid, json={"note": "鼻翼漏标"}).status_code == 200
    assert http.get("/admin/labeling/tasks/%d" % lid).json()["task"]["status"] == "returned"
    snapped = http.post("/admin/labeling/tasks/%d/snap" % lid, json={"labels": body["labels"]})
    assert snapped.status_code == 200
    stats = http.get("/admin/labeling/stats").json()
    assert stats["counts"]["returned"] == 1
    with factory() as db:
        assert db.query(LabelSubmission).count() == 1
    guard = http.get("/admin/image-labels/training-manifest",
                     params={"path": "/root/subskin/data/training_manifests/../../../etc/passwd"})
    assert guard.status_code == 400

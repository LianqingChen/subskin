"""Offline benchmark fixture, split safety, and admin-snapshot intake."""

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image


def load_benchmark():
    spec = importlib.util.spec_from_file_location(
        "assessment_benchmark", "scripts/assessment_benchmark.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_synthetic_fixture_emits_offline_metrics(tmp_path):
    module = load_benchmark()
    manifest = module.write_synthetic_fixture(tmp_path / "bench")
    output = tmp_path / "metrics.json"
    report = module.run(manifest, output)
    saved = json.loads(output.read_text())
    assert saved["status"] == "offline_benchmark_not_clinical_certification"
    assert report["status"] == saved["status"]
    for key in ("dice", "iou", "boundary_f1_2px", "area_error_percent", "area_abs_error_percent"):
        assert key in saved["overall"]
    assert saved["overall"]["positive_dice"] is not None
    assert saved["overall"]["positive_sample_count"] == saved["test_sample_count"] - 1
    assert "body_site:face" in saved["strata"]
    assert "skin_tone:V" in saved["strata"]
    assert "body_site:hand" in saved["strata"]
    assert saved["patients_by_split"]["test"]
    assert saved["repeat_area_cv_percent"] == [0.0]
    assert "synthetic-a" not in saved["patients_by_split"]["test"]


def test_patient_leakage_and_unauthorized_labels_are_rejected(tmp_path):
    module = load_benchmark()
    manifest = module.write_synthetic_fixture(tmp_path / "bench")
    data = json.loads(Path(manifest).read_text())
    leaked = json.loads(json.dumps(data))
    leaked["samples"][0]["split"] = "test"
    Path(manifest).write_text(json.dumps(leaked))
    with pytest.raises(ValueError, match="leakage"):
        module.run(manifest, tmp_path / "metrics.json")
    unauthorized = json.loads(json.dumps(data))
    unauthorized["samples"][2]["label_source"] = "admin"
    unauthorized["samples"][2]["consent"] = False
    Path(manifest).write_text(json.dumps(unauthorized))
    with pytest.raises(ValueError, match="clinician"):
        module.run(manifest, tmp_path / "metrics.json")


def test_admin_snapshot_is_not_gold_until_clinician_consent(tmp_path):
    module = load_benchmark()
    snapshot = tmp_path / "admin_labels" / "9" / "abc"
    snapshot.mkdir(parents=True)
    image = np.zeros((32, 32), np.uint8)
    image[4:20, 4:20] = 255
    Image.fromarray(image).save(snapshot / "lesion.png")
    (snapshot / "metadata.json").write_text(json.dumps({"draft": True, "area_percentage": 12}))
    with pytest.raises(ValueError, match="Draft"):
        module.manifest_row_from_admin_snapshot(
            snapshot, "pseudo-1", "test", "pred.png", True, "clinician"
        )
    (snapshot / "metadata.json").write_text(
        json.dumps({"draft": False, "area_percentage": 25.0, "training_state": "awaiting_authorized_dataset"})
    )
    Image.fromarray(image).save(tmp_path / "pred.png")
    row = module.manifest_row_from_admin_snapshot(
        snapshot,
        "pseudo-1",
        "test",
        "pred.png",
        False,
        "admin",
        body_site="face",
        skin_tone="IV",
    )
    assert row["source"] == "admin_reviewed_mask"
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"samples": [row], "model_version": "admin-snapshot-test"}))
    with pytest.raises(ValueError, match="clinician"):
        module.run(manifest, tmp_path / "blocked.json")
    row["consent"] = True
    row["label_source"] = "clinician"
    manifest.write_text(json.dumps({"samples": [row]}))
    report = module.run(manifest, tmp_path / "metrics.json")
    assert report["status"] == "offline_benchmark_not_clinical_certification"
    assert report["overall"]["dice"] == 1
    assert report["strata"]["body_site:face"]["dice"] == 1
    assert report["strata"]["skin_tone:IV"]["iou"] == 1

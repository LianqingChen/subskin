import hashlib
import json
from contextlib import nullcontext

import numpy as np
import pytest

from ml.vlm_labeling import regression


def test_pixel_changes_track_corrected_introduced_and_unresolved_classes():
    baseline = np.array([[2, 2, 2, 1, 1, 0, 2, 255]], dtype=np.uint8)
    candidate = np.array([[1, 1, 1, 2, 1, 2, 0, 2]], dtype=np.uint8)
    approved = np.array([[0, 1, 2, 1, 1, 255, 0, 2]], dtype=np.uint8)

    changes = regression._pixel_changes(baseline, candidate, approved)
    assert changes["changed_pixels"] == 7
    assert changes["corrected"] == 3
    assert changes["introduced_errors"] == 2
    assert changes["still_incorrect"] == 1
    assert changes["unknown_reference"] == 1
    assert changes["net_known_error_change"] == -1
    assert {
        "approved_class": "background",
        "baseline_class": "depigmented_skin",
        "candidate_class": "normal_skin",
        "outcome": "still_incorrect",
        "pixels": 1,
    } in changes["transitions"]

    unchanged = regression._pixel_changes(baseline, baseline, approved)
    assert unchanged["changed_pixels"] == 0
    assert unchanged["transitions"] == []


def test_regression_rejects_white_dice_gain_with_new_pixel_errors(tmp_path, monkeypatch):
    approved = np.array([[2] * 4 + [0] * 10 + [1] * 2], dtype=np.uint8)
    baseline = np.array([[2] * 14 + [1] * 2], dtype=np.uint8)
    candidate = np.array([[2] * 3 + [1] * 13], dtype=np.uint8)
    rgb, revision, submission = "a" * 64, "b" * 64, 17
    monkeypatch.setattr(regression, "SessionLocal", lambda: nullcontext(None))
    monkeypatch.setattr(regression, "_reference", lambda db, task: (rgb, approved.shape, submission, revision))
    monkeypatch.setattr(regression, "read_snapshot", lambda task, rev: approved)

    manifests = []
    for name, labels, workflow in (("baseline", baseline, "c" * 64), ("candidate", candidate, "d" * 64)):
        mask = tmp_path / (name + ".npy")
        np.save(mask, labels, allow_pickle=False)
        path = tmp_path / (name + ".json")
        path.write_text(json.dumps({
            "model": "qwen3.8-max",
            "workflow_sha256": workflow,
            "cases": [{
                "task_id": 1, "source_rgb_sha256": rgb, "gold_revision": revision,
                "gold_submission": submission, "labels": mask.name,
                "labels_sha256": hashlib.sha256(mask.read_bytes()).hexdigest(),
            }],
        }))
        manifests.append(path)

    report = regression.compare(*manifests)
    assert report["any_metric_improved"]
    assert not report["improved_without_regression"]
    assert not report["non_regression"]
    case, = report["cases"]
    assert "white_dice" in case["improved_metrics"]
    assert "normal_skin_dice" in case["regressed_metrics"]
    assert case["pixel_changes"]["introduced_errors"] == 1
    assert case["pixel_changes"]["still_incorrect"] == 10


def test_suite_rejects_model_regression_and_missing_model(tmp_path, monkeypatch):
    gold = np.array([[1, 1, 2]], dtype=np.uint8)
    weaker = np.array([[1, 2, 2]], dtype=np.uint8)
    rgb, revision = "a" * 64, "b" * 64
    monkeypatch.setattr(regression, "SessionLocal", lambda: nullcontext(None))
    monkeypatch.setattr(regression, "_reference", lambda db, task: (rgb, gold.shape, 17, revision))
    monkeypatch.setattr(regression, "read_snapshot", lambda task, rev: gold)

    def suite(name, workflows):
        models = {}
        for model, labels in workflows.items():
            artifact = tmp_path / f"{name}-{model}.npy"
            np.save(artifact, labels, allow_pickle=False)
            manifest = tmp_path / f"{name}-{model}.json"
            manifest.write_text(json.dumps({
                "model": model,
                "workflow_sha256": "c" * 64,
                "cases": [{
                    "task_id": 1,
                    "source_rgb_sha256": rgb,
                    "gold_submission": 17,
                    "gold_revision": revision,
                    "labels": artifact.name,
                    "labels_sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
                }],
            }))
            models[model] = manifest.name
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps({"models": models}))
        return path

    baseline = suite("baseline", {"qwen": weaker, "deepseek": gold})
    candidate = suite("candidate", {"qwen": gold, "deepseek": weaker})
    report = regression.compare_suite(baseline, candidate)
    assert report["models"]["qwen"]["improved_without_regression"]
    assert not report["models"]["deepseek"]["non_regression"]
    assert report["any_metric_improved"]
    assert not report["improved_without_regression"]
    assert not regression.compare_suite(baseline, baseline)["improved_without_regression"]

    improved = suite("improved", {"qwen": gold, "deepseek": gold})
    assert regression.compare_suite(baseline, improved)["improved_without_regression"]

    missing = suite("missing", {"qwen": gold})
    with pytest.raises(ValueError, match="different model list"):
        regression.compare_suite(baseline, missing)

    mislabeled = tmp_path / "mislabeled.json"
    mislabeled.write_text(json.dumps({"models": {"qwen": "candidate-deepseek.json",
                                                 "deepseek": "candidate-qwen.json"}}))
    with pytest.raises(ValueError, match="different model"):
        regression.compare_suite(baseline, mislabeled)

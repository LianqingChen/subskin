"""Synthetic dataset/metric contract tests; no patient files or clinical claims."""

import hashlib
import json
from pathlib import Path
import numpy as np
import pytest
from PIL import Image
from ml.rgb_segmentation.dataset import validate_manifest, LABELS
from ml.rgb_segmentation.metrics import score_labels, aggregate


def write_dataset(root: Path):
    root.mkdir(parents=True, exist_ok=True)
    items = []
    for index, split in enumerate(
        ["train", "train", "validation", "validation", "test", "test"]
    ):
        rng = np.random.default_rng(index)
        labels = np.zeros((64, 64), np.uint8)
        labels[8:56, 8:56] = 1
        labels[20:35, 24 + index : 42 + index] = 2
        labels[10:13, 10:42] = 3
        labels[45:49, 44:48] = 4
        palette = np.array(
            [
                [55, 65, 75],
                [180, 137, 115],
                [226, 214, 195],
                [40, 30, 20],
                [250, 250, 250],
            ]
        )
        rgb = np.clip(
            palette[labels] + rng.integers(-5, 6, (64, 64, 3)), 0, 255
        ).astype(np.uint8)
        ip = root / f"image-{index}.png"
        mp = root / f"mask-{index}.png"
        Image.fromarray(rgb).save(ip)
        Image.fromarray(labels).save(mp)
        items.append(
            {
                "id": f"image_{index}",
                "subject_id": "subject_" + f"{index:08x}",
                "split": split,
                "image": ip.name,
                "mask": mp.name,
                "image_sha256": hashlib.sha256(ip.read_bytes()).hexdigest(),
                "mask_sha256": hashlib.sha256(mp.read_bytes()).hexdigest(),
                "review_reference": "synthetic-review",
                "groups": {
                    "body_site": "synthetic",
                    "skin_tone": "unknown",
                    "lighting": "synthetic",
                    "quality": "synthetic",
                    "device": "synthetic",
                },
            }
        )
    doc = {
        "labels": LABELS,
        "coordinate_frame": "normalized_rgb",
        "synthetic": True,
        "authorization": {"training": True, "reference": "synthetic-test-only"},
        "dataset_review_id": "synthetic-review",
        "items": items,
    }
    path = root / "manifest.json"
    path.write_text(json.dumps(doc))
    return path


def test_training_requires_explicit_scope_and_rejects_split_leakage(tmp_path):
    path = write_dataset(tmp_path / "dataset")
    with pytest.raises(ValueError, match="Synthetic"):
        validate_manifest(path)
    assert validate_manifest(path, True)["subject_count"] == 6
    doc = json.loads(path.read_text())
    doc["items"][-1]["subject_id"] = doc["items"][0]["subject_id"]
    path.write_text(json.dumps(doc))
    with pytest.raises(ValueError, match="leakage"):
        validate_manifest(path, True)


def test_training_rejects_missing_authorization_and_wrong_grid(tmp_path):
    path = write_dataset(tmp_path / "dataset")
    doc = json.loads(path.read_text())
    doc["authorization"]["training"] = False
    path.write_text(json.dumps(doc))
    with pytest.raises(ValueError, match="authorization"):
        validate_manifest(path, True)
    doc["authorization"]["training"] = True
    doc["coordinate_frame"] = "unknown"
    path.write_text(json.dumps(doc))
    with pytest.raises(ValueError, match="coordinate"):
        validate_manifest(path, True)


def test_perfect_metrics_and_negative_cases_do_not_inflate_dice():
    truth = np.ones((64, 64), np.uint8)
    truth[10:30, 20:40] = 2
    rgb = np.full((64, 64, 3), 170, np.uint8)
    positive = score_labels(truth, truth, rgb)
    assert positive["dice"] == positive["iou"] == positive["boundary_f1"] == 1
    assert (
        positive["area_percentage_point_error"] == 0 and positive["missed_regions"] == 0
    )
    negative = np.ones_like(truth)
    empty = score_labels(negative, negative, rgb)
    assert empty["dice"] is None and empty["false_positive_image"] is False
    error = score_labels(truth, negative, rgb)
    assert error["false_positive_image"] is True and error["false_regions"] == 1
    report = aggregate(
        [
            {"subject_id": "a", "metrics": positive},
            {"subject_id": "b", "metrics": empty},
        ]
    )
    assert report["dice"]["n"] == 1


def test_missing_lesion_is_measured_as_miss_not_silently_dropped():
    truth = np.ones((64, 64), np.uint8)
    truth[8:20, 8:20] = 2
    pred = np.ones_like(truth)
    result = score_labels(pred, truth, np.full((64, 64, 3), 170, np.uint8))
    assert (
        result["dice"] == 0 and result["recall"] == 0 and result["missed_regions"] == 1
    )
    assert result["area_relative_error"] == 1


def test_area_ratio_detects_wrong_skin_denominator_with_correct_lesion():
    truth = np.zeros((64, 64), np.uint8)
    truth[:32] = 1
    truth[8:16, 8:16] = 2
    prediction = np.ones_like(truth)
    prediction[truth == 2] = 2
    metrics = score_labels(prediction, truth, np.full((64, 64, 3), 170, np.uint8))
    assert metrics["area_relative_error"] == 0
    assert metrics["area_ratio_relative_error"] == pytest.approx(0.5)
    assert metrics["reference_area_percentage"] == pytest.approx(3.125)
    assert metrics["predicted_area_percentage"] == pytest.approx(1.5625)


def test_correct_ratio_does_not_hide_wrong_masks():
    truth = np.zeros((64, 64), np.uint8)
    truth[:32] = 1
    truth[:8] = 2
    prediction = np.ones_like(truth)
    prediction[:16] = 2
    metrics = score_labels(prediction, truth, np.full((64, 64, 3), 170, np.uint8))
    assert metrics["area_ratio_relative_error"] == 0
    assert metrics["dice"] < 0.95 and metrics["skin_dice"] < 0.95
    assert metrics["area_relative_error"] == 1


def test_ratio_missing_skin_and_zero_truth_are_not_perfect_scores():
    rgb = np.full((64, 64, 3), 170, np.uint8)
    truth = np.ones((64, 64), np.uint8)
    truth[:8] = 2
    missing = score_labels(np.zeros_like(truth), truth, rgb)
    negative = score_labels(np.ones_like(truth), np.ones_like(truth), rgb)
    assert missing["area_ratio_relative_error"] is None
    assert missing["measurement_denominator_missing"]
    assert negative["area_ratio_relative_error"] is None
    assert aggregate([{"subject_id": "synthetic_a", "metrics": missing}])["area_ratio_relative_error"] is None


def test_ratio_aggregation_keeps_legacy_rows_readable():
    truth = np.ones((64, 64), np.uint8)
    truth[:8] = 2
    metrics = score_labels(truth, truth, np.full((64, 64, 3), 170, np.uint8))
    legacy = dict(metrics)
    legacy.pop("area_ratio_relative_error")
    report = aggregate([{"subject_id": "synthetic_a", "metrics": metrics},
                        {"subject_id": "synthetic_b", "metrics": legacy},
                        {"subject_id": "synthetic_c", "metrics": None}])
    assert report["area_ratio_relative_error"]["n"] == 1
    assert report["area_ratio_relative_error"]["mean"] == 0
    assert report["inference_failures"] == 1


def test_evaluation_only_permission_never_authorizes_training(tmp_path):
    path = write_dataset(tmp_path / "cohort")
    doc = json.loads(path.read_text())
    doc["items"] = [i for i in doc["items"] if i["split"] == "test"]
    doc["authorization"] = {"training": False, "evaluation": True, "reference": "synthetic-eval-only"}
    path.write_text(json.dumps(doc))
    accepted = validate_manifest(path, True, purpose="evaluation")
    assert accepted["counts"] == {"train": 0, "validation": 0, "test": 2}
    assert accepted["authorization_purpose"] == "evaluation"
    with pytest.raises(ValueError, match="training authorization"):
        validate_manifest(path, True)
    with pytest.raises(ValueError, match="Unsupported"):
        validate_manifest(path, True, purpose="anything")


def test_evaluation_only_retains_integrity_split_and_permission_gates(tmp_path):
    path = write_dataset(tmp_path / "cohort")
    doc = json.loads(path.read_text())
    with pytest.raises(ValueError, match="evaluation authorization"):
        validate_manifest(path, True, purpose="evaluation")
    doc["authorization"]["evaluation"] = True
    doc["items"][-1]["subject_id"] = doc["items"][0]["subject_id"]
    path.write_text(json.dumps(doc))
    with pytest.raises(ValueError, match="leakage"):
        validate_manifest(path, True, purpose="evaluation")
    doc["items"] = [i for i in doc["items"] if i["split"] != "test"]
    path.write_text(json.dumps(doc))
    with pytest.raises(ValueError, match="locked test"):
        validate_manifest(path, True, purpose="evaluation")

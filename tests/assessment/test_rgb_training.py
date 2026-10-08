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

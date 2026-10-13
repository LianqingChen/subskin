"""Offline segmentation benchmark. Inputs stay local; no model/API calls.

Usage:
  python scripts/assessment_benchmark.py --write-fixture /tmp/bench
  python scripts/assessment_benchmark.py --manifest dataset.json --output metrics.json

Each sample needs a pseudonymous patient_id, split, ground_truth, prediction,
label_source='clinician', and consent=true. Optional: skin_tone, body_site,
repeat_group, unchanged=true. All masks must share one coordinate system.

label_sync stores AI or user candidates. Those files are not ground truth.
Admin review writes lesion.png under
data/rgb_segmentation/admin_labels/{label_id}/{revision}/.
manifest_row_from_admin_snapshot() turns that folder into a manifest row.
The row is still rejected unless consent is true and label_source is clinician.
Output status is always offline_benchmark_not_clinical_certification.
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Optional

import cv2
import numpy as np
from PIL import Image


def mask(path):
    img = Image.open(path)
    return np.asarray(img.getchannel("A") if "A" in img.getbands() else img.convert("L")) > 127


def evaluate(gt, pred):
    if gt.shape != pred.shape:
        raise ValueError("Prediction/ground-truth shape mismatch")
    intersection = int((gt & pred).sum())
    total = int(gt.sum() + pred.sum())
    union = int((gt | pred).sum())
    kernel = np.ones((3, 3), np.uint8)
    edge = lambda layer: layer & ~cv2.erode(layer.astype(np.uint8), kernel).astype(bool)
    gt_edge, pred_edge = edge(gt), edge(pred)
    distance_gt = cv2.distanceTransform((~gt_edge).astype(np.uint8), cv2.DIST_L2, 5)
    distance_pred = cv2.distanceTransform((~pred_edge).astype(np.uint8), cv2.DIST_L2, 5)
    distances = (
        np.concatenate([distance_gt[pred_edge], distance_pred[gt_edge]])
        if gt_edge.any() and pred_edge.any()
        else None
    )
    recall = float((distance_pred[gt_edge] <= 2).mean()) if gt_edge.any() else float(not pred_edge.any())
    precision = float((distance_gt[pred_edge] <= 2).mean()) if pred_edge.any() else float(not gt_edge.any())
    signed = float((pred.sum() - gt.sum()) / gt.sum() * 100) if gt.any() else None
    return {
        "dice": 2 * intersection / total if total else 1.0,
        "iou": intersection / union if union else 1.0,
        "boundary_f1_2px": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
        "hd95_px": float(np.percentile(distances, 95)) if distances is not None else None,
        "area_error_px": int(pred.sum()) - int(gt.sum()),
        "area_error_percent": signed,
        "area_abs_error_percent": abs(signed) if signed is not None else None,
        "false_positive_pixels": int((pred & ~gt).sum()),
        "predicted_area_px": int(pred.sum()),
        "empty_agreement": (not gt.any()) and (not pred.any()),
    }


def _mean(rows, key):
    values = [row[key] for row in rows if row.get(key) is not None]
    return float(np.mean(values)) if values else None


def summary(rows):
    keys = ("dice", "iou", "boundary_f1_2px", "hd95_px", "area_error_percent", "area_abs_error_percent")
    result = {key: _mean(rows, key) for key in keys}
    positive = [row for row in rows if not row.get("empty_agreement")]
    result["positive_dice"] = _mean(positive, "dice")
    result["positive_sample_count"] = len(positive)
    return result


def run(manifest, output):
    path = Path(manifest)
    data = json.loads(path.read_text())
    samples = data["samples"]
    patients = {}
    results = []
    groups = defaultdict(list)
    repeats = defaultdict(list)
    split_patients = defaultdict(set)
    for sample in samples:
        patient = sample["patient_id"]
        split = sample["split"]
        if patient in patients and patients[patient] != split:
            raise ValueError("Patient leakage across splits")
        patients[patient] = split
        split_patients[split].add(patient)
        if not sample.get("consent") or sample.get("label_source") != "clinician":
            raise ValueError("Authorized clinician labels required")
    for index, sample in enumerate(samples):
        if sample["split"] != "test":
            continue
        metric = evaluate(mask(path.parent / sample["ground_truth"]), mask(path.parent / sample["prediction"]))
        metric["sample_index"] = index
        results.append(metric)
        for dimension in ("skin_tone", "body_site"):
            groups["%s:%s" % (dimension, sample.get(dimension) or "unknown")].append(metric)
        if sample.get("repeat_group") and sample.get("unchanged"):
            repeats[(sample["patient_id"], sample["repeat_group"])].append(metric["predicted_area_px"])
    if not results:
        raise ValueError("No held-out test samples")
    repeat = [
        float(np.std(values, ddof=1) / np.mean(values) * 100)
        for values in repeats.values()
        if len(values) > 1 and np.mean(values) > 0
    ]
    report = {
        "status": "offline_benchmark_not_clinical_certification",
        "test_sample_count": len(results),
        "patients_by_split": {split: sorted(ids) for split, ids in split_patients.items()},
        "overall": summary(results),
        "strata": {key: summary(value) for key, value in groups.items()},
        "repeat_area_cv_percent": repeat,
        "samples": results,
        "model_version": data.get("model_version"),
        "limitations": [
            "offline_benchmark_not_clinical_certification",
            "No diagnosis sensitivity/specificity evaluation",
            "2px boundary tolerance depends on image resolution",
            "Empty agreement is excluded from positive_dice",
            "Expert sample-size planning still required",
        ],
    }
    Path(output).write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    return report


def _write_mask(path: Path, active: np.ndarray) -> None:
    image = np.zeros(active.shape, np.uint8)
    image[active] = 255
    Image.fromarray(image).save(path)


def write_synthetic_fixture(directory) -> Path:
    """Small synthetic masks so the benchmark can run without a gold dataset."""
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    face = np.zeros((64, 64), bool)
    face[12:44, 12:44] = True
    face_pred = np.zeros_like(face)
    face_pred[16:48, 16:48] = True
    hand = np.zeros((64, 64), bool)
    hand[8:28, 30:58] = True
    hand_pred = hand.copy()
    hand_pred[8:28, 34:62] = True
    empty = np.zeros((64, 64), bool)
    names = {
        "face_gt.png": face,
        "face_pred.png": face_pred,
        "face_repeat.png": face_pred,
        "hand_gt.png": hand,
        "hand_pred.png": hand_pred,
        "empty_gt.png": empty,
        "empty_pred.png": empty,
    }
    for name, layer in names.items():
        _write_mask(root / name, layer)
    manifest = {
        "model_version": "synthetic-fixture",
        "note": "Synthetic masks only. Not a clinical dataset.",
        "samples": [
            {
                "patient_id": "synthetic-a",
                "split": "train",
                "ground_truth": "face_gt.png",
                "prediction": "face_pred.png",
                "label_source": "clinician",
                "consent": True,
                "body_site": "face",
                "skin_tone": "III",
            },
            {
                "patient_id": "synthetic-a",
                "split": "train",
                "ground_truth": "face_gt.png",
                "prediction": "face_repeat.png",
                "label_source": "clinician",
                "consent": True,
                "body_site": "face",
                "skin_tone": "III",
            },
            {
                "patient_id": "synthetic-b",
                "split": "test",
                "ground_truth": "face_gt.png",
                "prediction": "face_pred.png",
                "label_source": "clinician",
                "consent": True,
                "body_site": "face",
                "skin_tone": "III",
                "repeat_group": "same-day",
                "unchanged": True,
            },
            {
                "patient_id": "synthetic-b",
                "split": "test",
                "ground_truth": "face_gt.png",
                "prediction": "face_repeat.png",
                "label_source": "clinician",
                "consent": True,
                "body_site": "face",
                "skin_tone": "III",
                "repeat_group": "same-day",
                "unchanged": True,
            },
            {
                "patient_id": "synthetic-c",
                "split": "test",
                "ground_truth": "hand_gt.png",
                "prediction": "hand_pred.png",
                "label_source": "clinician",
                "consent": True,
                "body_site": "hand",
                "skin_tone": "V",
            },
            {
                "patient_id": "synthetic-d",
                "split": "test",
                "ground_truth": "empty_gt.png",
                "prediction": "empty_pred.png",
                "label_source": "clinician",
                "consent": True,
                "body_site": "trunk",
                "skin_tone": "II",
            },
        ],
    }
    destination = root / "manifest.json"
    destination.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    return destination


def manifest_row_from_admin_snapshot(
    snapshot_dir,
    patient_id: str,
    split: str,
    prediction: str,
    consent: bool,
    label_source: str,
    body_site: Optional[str] = None,
    skin_tone: Optional[str] = None,
    repeat_group: Optional[str] = None,
    unchanged: Optional[bool] = None,
) -> Dict[str, Any]:
    """Map one admin-reviewed mask folder into a benchmark sample.

    ``save_admin_reference`` writes ``lesion.png`` plus ``metadata.json``.
    ``label_sync`` AI masks must not be passed as ground truth. This helper
    does not grant clinician status; ``run`` still requires consent and
    label_source='clinician'.
    """
    folder = Path(snapshot_dir)
    lesion = folder / "lesion.png"
    if not lesion.is_file():
        raise ValueError("Admin snapshot is missing lesion.png")
    metadata_path = folder / "metadata.json"
    metadata: Dict[str, Any] = {}
    if metadata_path.is_file():
        metadata = json.loads(metadata_path.read_text())
        if metadata.get("draft") is True:
            raise ValueError("Draft admin masks cannot enter the benchmark manifest")
    row: Dict[str, Any] = {
        "patient_id": patient_id,
        "split": split,
        "ground_truth": str(lesion),
        "prediction": prediction,
        "consent": bool(consent),
        "label_source": label_source,
        "body_site": body_site,
        "skin_tone": skin_tone,
        "source": "admin_reviewed_mask",
        "admin_area_percentage": metadata.get("area_percentage"),
    }
    if repeat_group:
        row["repeat_group"] = repeat_group
    if unchanged is not None:
        row["unchanged"] = bool(unchanged)
    return row


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest")
    parser.add_argument("--output")
    parser.add_argument("--write-fixture", help="Write a synthetic manifest and masks")
    args = parser.parse_args()
    if args.write_fixture:
        print(write_synthetic_fixture(args.write_fixture))
    if args.manifest or args.output:
        if not args.manifest or not args.output:
            parser.error("--manifest and --output are required together")
        run(args.manifest, args.output)
    elif not args.write_fixture:
        parser.error("provide --write-fixture and/or --manifest with --output")

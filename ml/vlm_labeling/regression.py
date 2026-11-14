"""Compare two frozen model workflows against the same approved SubSkin references."""

import hashlib
import io
import json
from pathlib import Path
import re
from typing import Any, Dict, Tuple

import numpy as np

from ml.vlm_labeling.learn import coating_scores
from web.backend.database.database import SessionLocal
from web.backend.models.label_submission import LabelSubmission
from web.backend.services.labeling import class_map, sources, tasks
from web.backend.services.labeling.submissions import read_snapshot


DIGEST = re.compile(r"[a-f0-9]{64}")


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _manifest(path: Path) -> Tuple[Dict[str, Any], Dict[int, Dict[str, Any]]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a workflow and its case list")
    model, workflow = value.get("model"), value.get("workflow_sha256")
    if not isinstance(model, str) or not model.strip() or model.startswith("sim:"):
        raise ValueError(f"{path.name} requires the actual model used for the predictions")
    if not isinstance(workflow, str) or not DIGEST.fullmatch(workflow):
        raise ValueError(f"{path.name} requires the frozen workflow SHA-256")
    cases = value.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError(f"{path.name} must list the completed cases")
    by_task = {}
    for row in cases:
        task = row.get("task_id") if isinstance(row, dict) else None
        if type(task) is not int or task <= 0 or task in by_task:
            raise ValueError(f"{path.name} contains an invalid or duplicate task ID")
        for field in ("source_rgb_sha256", "gold_revision", "labels_sha256"):
            digest = row.get(field)
            if not isinstance(digest, str) or not DIGEST.fullmatch(digest):
                raise ValueError(f"Task {task} requires a valid {field}")
        if type(row.get("gold_submission")) is not int or row["gold_submission"] <= 0:
            raise ValueError(f"Task {task} requires an approved submission ID")
        if not isinstance(row.get("labels"), str) or not row["labels"]:
            raise ValueError(f"Task {task} requires a frozen class map")
        by_task[task] = row
    return value, by_task


def _load_labels(manifest: Path, row: Dict[str, Any], shape: Tuple[int, int]) -> np.ndarray:
    task = row["task_id"]
    path = manifest.parent / row["labels"]
    if path.suffix != ".npy":
        raise ValueError(f"Task {task} class map must be an NPY file")
    raw = path.read_bytes()
    if _sha256(raw) != row["labels_sha256"]:
        raise ValueError(f"Task {task} class map differs from its frozen SHA-256")
    labels = np.load(io.BytesIO(raw), allow_pickle=False)
    if (not isinstance(labels, np.ndarray) or labels.shape != shape or labels.dtype != np.uint8
            or not np.isin(labels, class_map.VALUES).all()):
        raise ValueError(f"Task {task} class map does not fit the canonical image or classes")
    return labels


def _reference(db, task: int) -> Tuple[str, Tuple[int, int], int, str]:
    label = tasks.get_visible(db, task)
    image, shape = sources.canonical(label)
    submission = (db.query(LabelSubmission)
                  .filter_by(image_label_id=task, status="approved")
                  .order_by(LabelSubmission.id.desc()).first())
    if submission is None:
        raise ValueError(f"Task {task} has no approved submission")
    return _sha256(image), shape, submission.id, submission.revision


def _higher_is_better(score: Dict[str, Any]) -> Dict[str, float]:
    result = {key: -score[key] for key in ("known_pixel_errors", "unknown_on_known_pixels")}
    for name, values in score["coatings"].items():
        # Dice is undefined when both masks are empty. This is exact class agreement.
        result[f"{name}_dice"] = 1.0 if values["dice"] is None else values["dice"]
    return result


def _pixel_changes(baseline: np.ndarray, candidate: np.ndarray, approved: np.ndarray) -> Dict[str, Any]:
    changed = baseline != candidate
    classes = np.asarray(class_map.VALUES, dtype=np.uint8)
    width = len(classes)
    reference, before, after = (
        np.searchsorted(classes, labels[changed]) for labels in (approved, baseline, candidate)
    )
    keys = (reference * width + before) * width + after
    counts = np.bincount(keys, minlength=width ** 3).reshape((width,) * 3)

    outcomes = {"corrected": 0, "introduced_errors": 0, "still_incorrect": 0, "unknown_reference": 0}
    transitions = []
    for target_index, before_index, after_index in np.argwhere(counts):
        target = int(classes[target_index])
        old = int(classes[before_index])
        new = int(classes[after_index])
        pixels = int(counts[target_index, before_index, after_index])
        if target == class_map.UNKNOWN:
            outcome = "unknown_reference"
        elif new == target:
            outcome = "corrected"
        elif old == target:
            outcome = "introduced_errors"
        else:
            outcome = "still_incorrect"
        outcomes[outcome] += pixels
        transitions.append({
            "approved_class": class_map.NAMES[target],
            "baseline_class": class_map.NAMES[old],
            "candidate_class": class_map.NAMES[new],
            "outcome": outcome,
            "pixels": pixels,
        })
    return {
        "changed_pixels": sum(outcomes.values()),
        **outcomes,
        "net_known_error_change": outcomes["introduced_errors"] - outcomes["corrected"],
        "transitions": transitions,
    }


def compare(baseline: Path, candidate: Path) -> Dict[str, Any]:
    return _compare(baseline, candidate, _manifest(baseline), _manifest(candidate))


def _compare(
    baseline: Path,
    candidate: Path,
    previous_manifest: Tuple[Dict[str, Any], Dict[int, Dict[str, Any]]],
    proposed_manifest: Tuple[Dict[str, Any], Dict[int, Dict[str, Any]]],
) -> Dict[str, Any]:
    previous, previous_cases = previous_manifest
    proposed, proposed_cases = proposed_manifest
    if previous["model"] != proposed["model"]:
        raise ValueError("Compare the same model on both sides")
    if previous_cases.keys() != proposed_cases.keys():
        missing = sorted(previous_cases.keys() - proposed_cases.keys())
        extra = sorted(proposed_cases.keys() - previous_cases.keys())
        raise ValueError(f"Candidate has a different case list (missing {missing}, extra {extra})")

    rows = []
    with SessionLocal() as db:
        for task, left in sorted(previous_cases.items()):
            right = proposed_cases[task]
            source_sha, shape, submission, revision = _reference(db, task)
            for row in (left, right):
                if row["source_rgb_sha256"] != source_sha:
                    raise ValueError(f"Task {task} source image fingerprint changed")
                if row["gold_submission"] != submission or row["gold_revision"] != revision:
                    raise ValueError(f"Task {task} requires the same current approved submission and revision")
            old_labels = _load_labels(baseline, left, shape)
            new_labels = _load_labels(candidate, right, shape)
            approved = read_snapshot(task, revision)
            if approved.shape != shape:
                raise ValueError(f"Task {task} approved snapshot has a different grid")
            baseline_scores = coating_scores(old_labels, approved)
            candidate_scores = coating_scores(new_labels, approved)
            before = _higher_is_better(baseline_scores)
            after = _higher_is_better(candidate_scores)
            rows.append({
                "task_id": task, "source_rgb_sha256": source_sha,
                "gold_submission": submission, "gold_revision": revision,
                "baseline": baseline_scores, "candidate": candidate_scores,
                "pixel_changes": _pixel_changes(old_labels, new_labels, approved),
                "regressed_metrics": [name for name in before if after[name] < before[name]],
                "improved_metrics": [name for name in before if after[name] > before[name]],
            })
    non_regression = all(not row["regressed_metrics"] for row in rows)
    any_improved = any(row["improved_metrics"] for row in rows)
    return {
        "model": previous["model"],
        "baseline_workflow_sha256": previous["workflow_sha256"],
        "candidate_workflow_sha256": proposed["workflow_sha256"],
        "non_regression": non_regression,
        "any_metric_improved": any_improved,
        "improved_without_regression": non_regression and any_improved,
        "cases": rows,
    }


def _suite(path: Path) -> Dict[str, Path]:
    data = json.loads(path.read_text(encoding="utf-8"))
    models = data.get("models") if isinstance(data, dict) else None
    if not isinstance(models, dict) or not models:
        raise ValueError(f"{path.name} requires a nonempty model-to-manifest mapping")
    manifests = {}
    for model, filename in models.items():
        if not model.strip() or not isinstance(filename, str) or not filename:
            raise ValueError(f"{path.name} contains an invalid model or manifest path")
        manifests[model] = path.parent / filename
    return manifests


def compare_suite(baseline: Path, candidate: Path) -> Dict[str, Any]:
    """Evaluate every baseline model, keeping each model's frozen cohort intact."""
    previous = _suite(baseline)
    proposed = _suite(candidate)
    missing = sorted(previous.keys() - proposed.keys())
    extra = sorted(proposed.keys() - previous.keys())
    if missing or extra:
        raise ValueError(f"Candidate has a different model list (missing {missing}, extra {extra})")

    results = {}
    for model in sorted(previous):
        before, after = previous[model], proposed[model]
        old_manifest, new_manifest = _manifest(before), _manifest(after)
        if old_manifest[0]["model"] != model or new_manifest[0]["model"] != model:
            raise ValueError(f"Suite entry {model} points to a manifest for a different model")
        results[model] = _compare(before, after, old_manifest, new_manifest)

    non_regression = all(report["non_regression"] for report in results.values())
    any_improved = any(report["any_metric_improved"] for report in results.values())
    return {
        "models": results,
        "candidate_tasks_with_pixel_differences": {
            model: [row["task_id"] for row in report["cases"] if not row["candidate"]["pixel_exact"]]
            for model, report in results.items()
        },
        "non_regression": non_regression,
        "any_metric_improved": any_improved,
        "improved_without_regression": non_regression and any_improved,
    }

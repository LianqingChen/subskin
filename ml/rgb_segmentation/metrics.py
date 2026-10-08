"""Reproducible pixel, boundary, lesion-wise and measurement-error metrics."""

from typing import Any, Dict, Optional
import cv2
import numpy as np


def dice(a: np.ndarray, b: np.ndarray) -> float:
    denom = int(a.sum() + b.sum())
    return 2 * int((a & b).sum()) / denom if denom else 1.0


def lesion_counts(pred: np.ndarray, truth: np.ndarray, threshold: float = 0.25):
    pn, pl = cv2.connectedComponents(pred.astype(np.uint8), connectivity=8)
    tn, tl = cv2.connectedComponents(truth.astype(np.uint8), connectivity=8)
    ps = np.bincount(pl.ravel())
    ts = np.bincount(tl.ravel())
    overlap = (pl > 0) & (tl > 0)
    pairs, intersections = (
        np.unique(
            np.stack([pl[overlap], tl[overlap]], axis=1), axis=0, return_counts=True
        )
        if overlap.any()
        else ([], [])
    )
    candidates = []
    for (p, t), common in zip(pairs, intersections):
        iou = common / (ps[p] + ts[t] - common)
        if iou >= threshold:
            candidates.append((iou, int(p), int(t)))
    used_p, used_t = set(), set()
    for _, p, t in sorted(candidates, reverse=True):
        if p not in used_p and t not in used_t:
            used_p.add(p)
            used_t.add(t)
    return {
        "matched": len(used_t),
        "truth_regions": tn - 1,
        "predicted_regions": pn - 1,
        "missed_regions": tn - 1 - len(used_t),
        "false_regions": pn - 1 - len(used_p),
    }


def boundary_f1(
    pred: np.ndarray,
    truth: np.ndarray,
    tolerance: int = 2,
    valid: Optional[np.ndarray] = None,
) -> Optional[float]:
    edge = lambda mask: mask & ~cv2.erode(
        mask.astype(np.uint8), np.ones((3, 3), np.uint8)
    ).astype(bool)
    pe, te = edge(pred), edge(truth)
    if valid is not None:
        interior = cv2.erode(
            valid.astype(np.uint8),
            np.ones((2 * tolerance + 3, 2 * tolerance + 3), np.uint8),
        ).astype(bool)
        pe &= interior
        te &= interior
    if not pe.any() or not te.any():
        return None if not pe.any() and not te.any() else 0.0
    kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (2 * tolerance + 1, 2 * tolerance + 1)
    )
    precision = float(
        (pe & cv2.dilate(te.astype(np.uint8), kernel).astype(bool)).sum()
    ) / int(pe.sum())
    recall = float(
        (te & cv2.dilate(pe.astype(np.uint8), kernel).astype(bool)).sum()
    ) / int(te.sum())
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def score_labels(
    prediction: np.ndarray, truth: np.ndarray, rgb: np.ndarray
) -> Dict[str, Any]:
    if prediction.shape != truth.shape or rgb.shape[:2] != truth.shape:
        raise ValueError("Prediction, annotation and image dimensions differ")
    valid = truth != 255
    pred, actual = (prediction == 2) & valid, (truth == 2) & valid
    skin_p, skin_t = np.isin(prediction, [1, 2]) & valid, np.isin(truth, [1, 2]) & valid
    tp, fp, fn = (
        int((pred & actual).sum()),
        int((pred & ~actual).sum()),
        int((~pred & actual).sum()),
    )
    pcount, tcount = int(pred.sum()), int(actual.sum())
    truth_pct = 100 * tcount / int(skin_t.sum()) if skin_t.any() else None
    pred_pct = 100 * pcount / int(skin_p.sum()) if skin_p.any() else None
    h, w = truth.shape
    scale = 1024 / max(h, w)
    size = (max(1, round(w * scale)), max(1, round(h * scale)))
    normalized = lambda mask: cv2.resize(
        mask.astype(np.uint8), size, interpolation=cv2.INTER_NEAREST
    ).astype(bool)
    result = {
        "skin_dice": dice(skin_p, skin_t),
        "dice": dice(pred, actual) if tcount else None,
        "iou": tp / (tp + fp + fn) if tcount else None,
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
        "boundary_f1": (
            boundary_f1(normalized(pred), normalized(actual), valid=normalized(valid))
            if tcount
            else None
        ),
        "area_absolute_pixels": abs(pcount - tcount),
        "area_relative_error": abs(pcount - tcount) / tcount if tcount else None,
        "area_percentage_point_error": (
            abs(pred_pct - truth_pct)
            if pred_pct is not None and truth_pct is not None
            else None
        ),
        "negative_image": not bool(tcount),
        "false_positive_image": not bool(tcount) and bool(pcount),
        "measurement_denominator_missing": not skin_p.any(),
        "color_delta_e76": None,
        **lesion_counts(pred, actual),
    }
    if pred.any() and actual.any():
        lab = cv2.cvtColor(rgb.astype(np.float32) / 255.0, cv2.COLOR_RGB2LAB)
        result["color_delta_e76"] = float(
            np.linalg.norm(
                np.median(lab[pred], axis=0) - np.median(lab[actual], axis=0)
            )
        )
    return result


def aggregate(rows: list) -> Dict[str, Any]:
    keys = [
        "skin_dice",
        "dice",
        "iou",
        "precision",
        "recall",
        "boundary_f1",
        "area_relative_error",
        "area_percentage_point_error",
        "color_delta_e76",
    ]
    successful = [r for r in rows if r.get("metrics") is not None]
    result: Dict[str, Any] = {
        "images": len(rows),
        "inference_failures": len(rows) - len(successful),
    }
    for key in keys:
        values = [
            r["metrics"][key] for r in successful if r["metrics"][key] is not None
        ]
        result[key] = (
            {
                "n": len(values),
                "mean": float(np.mean(values)),
                "median": float(np.median(values)),
                "p90": float(np.percentile(values, 90)),
            }
            if values
            else None
        )
    negatives = [r for r in successful if r["metrics"]["negative_image"]]
    result["false_positive_image_rate"] = (
        sum(r["metrics"]["false_positive_image"] for r in negatives) / len(negatives)
        if negatives
        else None
    )
    truth = sum(r["metrics"]["truth_regions"] for r in successful)
    missed = sum(r["metrics"]["missed_regions"] for r in successful)
    result["missed_region_rate"] = missed / truth if truth else None
    result["false_regions_per_image"] = (
        sum(r["metrics"]["false_regions"] for r in successful) / len(successful)
        if successful
        else None
    )
    subjects = {}
    for row in successful:
        value = row["metrics"]["dice"]
        if value is not None:
            subjects.setdefault(row["subject_id"], []).append(value)
    means = np.asarray([np.mean(v) for v in subjects.values()])
    result["positive_subjects"] = len(means)
    if len(means) >= 2:
        rng = np.random.default_rng(17)
        bootstrap = np.mean(rng.choice(means, (1000, len(means)), replace=True), axis=1)
        result["patient_bootstrap_dice_95_interval"] = [
            float(np.percentile(bootstrap, 2.5)),
            float(np.percentile(bootstrap, 97.5)),
        ]
    else:
        result["patient_bootstrap_dice_95_interval"] = None
    return result

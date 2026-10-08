"""Locked-test evaluation with grouped error reporting, not deployment approval."""

import hashlib
import io
import json
from pathlib import Path
from typing import Any, Dict, Optional
import cv2
import numpy as np
import torch
from ml.rgb_segmentation.dataset import validate_manifest, load_item
from ml.rgb_segmentation.metrics import score_labels, aggregate


def predict(model, rgb: np.ndarray) -> np.ndarray:
    h, w = rgb.shape[:2]
    factor = min(1.0, 1024 / max(h, w))
    shape = (max(1, round(w * factor)), max(1, round(h * factor)))
    resized = cv2.resize(rgb, shape, interpolation=cv2.INTER_AREA)
    tensor = (
        torch.from_numpy(resized.copy()).permute(2, 0, 1).float().unsqueeze(0) / 255
    )
    tensor = torch.nn.functional.pad(tensor, (0, (-shape[0]) % 16, 0, (-shape[1]) % 16))
    with torch.inference_mode():
        probability = torch.softmax(model(tensor), 1)[:, :, : shape[1], : shape[0]]
    if probability.shape[1] != 5 or not torch.isfinite(probability).all():
        raise ValueError("Invalid model output")
    probability = torch.nn.functional.interpolate(
        probability, size=(h, w), mode="bilinear", align_corners=False
    )
    return probability[0].argmax(0).cpu().numpy().astype(np.uint8)


def evaluate(
    manifest: Path, weights: Optional[Path], output: Path, allow_synthetic: bool = False
) -> Dict[str, Any]:
    document = validate_manifest(manifest, allow_synthetic)
    torch.set_num_threads(2)
    weights_bytes = weights.read_bytes() if weights else None
    model = (
        torch.jit.load(io.BytesIO(weights_bytes), map_location="cpu").eval()
        if weights_bytes
        else None
    )
    rows = []
    for item in document["items"]:
        if item["split"] != "test":
            continue
        rgb, truth = load_item(Path(document["root"]), item)
        row = {
            "id": item["id"],
            "subject_id": item["subject_id"],
            "groups": dict(item["groups"]),
        }
        fraction = float((truth == 2).sum()) / max(1, int(np.isin(truth, [1, 2]).sum()))
        row["groups"]["lesion_size"] = (
            "none"
            if fraction == 0
            else "small" if fraction < 0.05 else "medium" if fraction < 0.3 else "large"
        )
        try:
            if model is not None:
                prediction = predict(model, rgb)
            else:
                from web.backend.services.vasi_skin_mask import build_skin_mask
                from web.backend.services.vasi_edge_segmentation import (
                    segment_lesions_edge_aware,
                )

                skin = build_skin_mask(rgb)
                prediction = np.zeros(truth.shape, np.uint8)
                if skin is not None:
                    prediction[skin] = 1
                    candidate = (
                        segment_lesions_edge_aware(rgb, region=skin) or {}
                    ).get("lesion_mask")
                    if candidate is not None:
                        prediction[candidate & skin] = 2
            row["metrics"] = score_labels(prediction, truth, rgb)
        except Exception:
            row["metrics"] = None
            row["error"] = "inference_failed"
        rows.append(row)
    grouped = {}
    for key in [
        "body_site",
        "skin_tone",
        "lighting",
        "quality",
        "device",
        "lesion_size",
    ]:
        grouped[key] = {
            value: aggregate([r for r in rows if r["groups"][key] == value])
            for value in sorted({r["groups"][key] for r in rows})
        }
    report = {
        "kind": "offline_model_benchmark",
        "baseline": (
            "torchscript" if model is not None else "raw_cv_candidate_not_v2_pipeline"
        ),
        "manifest_sha256": document["manifest_sha256"],
        "weights_sha256": (
            hashlib.sha256(weights_bytes).hexdigest() if weights_bytes else None
        ),
        "synthetic": document.get("synthetic", False),
        "configuration": {
            "boundary_grid_long_side": 1024,
            "boundary_tolerance_px": 2,
            "region_match_iou": 0.25,
            "minimum_component_pixels": 1,
            "empty_lesion_dice": "excluded_from_positive_macro",
            "color_metric": "same_photo_mask_bias_uncalibrated_delta_e76",
        },
        "summary": aggregate(rows),
        "groups": grouped,
        "rows": rows,
        "automatic_measurement_coverage": 0.0,
        "deployment_approved": False,
        "note": "Raw model metrics are not medical validation; current runtime always requires user review.",
    }
    if output.exists():
        raise ValueError("Use a new report path")
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    output.write_text(json.dumps(report, indent=2))
    output.chmod(0o600)
    return report

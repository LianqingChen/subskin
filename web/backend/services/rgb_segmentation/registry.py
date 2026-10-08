"""Explicit local weight registration. Never download or select an LLM as fallback."""

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional
from web.backend.exceptions import RGBSegmentationError
from web.backend.services.rgb_segmentation.artifacts import PROJECT_ROOT

LABELS = ["background", "normal_skin", "depigmented_skin", "occlusion", "unreadable"]


def registered_model() -> Optional[Dict[str, Any]]:
    registry_path = Path(
        os.getenv(
            "RGB_SEGMENTATION_REGISTRY",
            str(PROJECT_ROOT / "configs" / "rgb_segmentation_registry.json"),
        )
    )
    if not registry_path.exists():
        return None
    try:
        entry = json.loads(registry_path.read_text())
        if entry.get("enabled") is not True:
            return None
        if (
            entry.get("labels") != LABELS
            or entry.get("format") != "torchscript"
            or entry.get("input_type") != "rgb_photo"
        ):
            raise ValueError()
        root = (PROJECT_ROOT / "models" / "rgb").resolve()
        weights = (root / entry["weights"]).resolve()
        weights.relative_to(root)
        if not weights.is_file():
            raise ValueError()
        verified_bytes = weights.read_bytes()
        if hashlib.sha256(verified_bytes).hexdigest() != entry["sha256"]:
            raise ValueError()
        if (
            not entry.get("model_id")
            or not entry.get("dataset_review_id")
            or entry.get("training_source") != "authorized_reviewed_manifest"
        ):
            raise ValueError()
        return {
            **entry,
            "resolved_weights": str(weights),
            "weights_bytes": verified_bytes,
            "automatic_measurement": False,
        }
    except (OSError, ValueError, KeyError, TypeError):
        raise RGBSegmentationError(
            "MODEL_UNAVAILABLE", "分割模型暂不可用，请稍后重试", 503
        )

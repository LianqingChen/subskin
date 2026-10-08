"""Deterministic RGB proposal inference with an explicit untrained fallback."""

import io
from typing import Any, Dict, Tuple
import numpy as np
from web.backend.services.rgb_segmentation.registry import registered_model
from web.backend.services.vasi_skin_mask import build_skin_mask
from web.backend.services.vasi_edge_segmentation import segment_lesions_edge_aware
from web.backend.exceptions import RGBSegmentationError


def infer_rgb(rgb: np.ndarray) -> Tuple[Dict[str, np.ndarray], Dict[str, Any]]:
    entry = registered_model()
    empty = np.zeros(rgb.shape[:2], dtype=bool)
    if entry:
        import torch

        torch.set_num_threads(2)
        model = torch.jit.load(
            io.BytesIO(entry["weights_bytes"]), map_location="cpu"
        ).eval()
        h, w = rgb.shape[:2]
        tensor = (
            torch.from_numpy(rgb.copy()).permute(2, 0, 1).float().unsqueeze(0) / 255.0
        )
        tensor = torch.nn.functional.pad(tensor, (0, (-w) % 16, 0, (-h) % 16))
        with torch.inference_mode():
            logits = model(tensor)
        if logits.ndim != 4 or logits.shape[1] != 5 or not torch.isfinite(logits).all():
            raise RGBSegmentationError("MODEL_UNAVAILABLE", "分割结果暂不可用", 503)
        logits = torch.nn.functional.interpolate(
            logits, size=tensor.shape[-2:], mode="bilinear", align_corners=False
        )[:, :, :h, :w]
        probability = torch.softmax(logits, dim=1)[0].cpu().numpy()
        labels = probability.argmax(axis=0)
        skin = np.isin(labels, [1, 2])
        lesion = labels == 2
        uncertain = (
            probability.max(axis=0) < 0.7
        ) & skin  # heuristic, never a confidence percentage
        return {
            "skin": skin,
            "lesion": lesion & ~uncertain,
            "uncertain": uncertain,
            "excluded": np.isin(labels, [3, 4]),
        }, {
            "model_id": entry["model_id"],
            "weights_sha256": entry["sha256"],
            "source": "registered_rgb_model",
            "automatic_measurement": False,
            "note": "专用模型候选，仍需人工核对",
            "confidence_calibrated": False,
        }
    skin = build_skin_mask(rgb)
    skin = skin.astype(bool) if skin is not None else empty.copy()
    raw = segment_lesions_edge_aware(rgb, region=skin) if skin.any() else None
    candidate = (raw or {}).get("lesion_mask")
    candidate = candidate.astype(bool) if candidate is not None else empty.copy()
    # Do not convert CV proposals into successful automatic lesion measurements.
    return {
        "skin": skin,
        "lesion": empty.copy(),
        "uncertain": candidate & skin,
        "excluded": empty.copy(),
    }, {
        "model_id": None,
        "source": "interactive_rgb_reference",
        "automatic_measurement": False,
        "note": "当前为图像候选，请核对皮肤并补充浅色区域",
        "confidence_calibrated": False,
    }

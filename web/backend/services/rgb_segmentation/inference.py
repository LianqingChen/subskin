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
    return _interactive_reference(rgb, empty)


def _interactive_reference(
    rgb: np.ndarray, empty: np.ndarray
) -> Tuple[Dict[str, np.ndarray], Dict[str, Any]]:
    """CV fallback. Candidates stay uncertain and are not a measurement.

    The skin denominator is the visible body region, including depigmented
    pixels that colour thresholds miss. Edge snap is optional and only moves
    the candidate boundary.
    """
    from web.backend.services.vasi_edge_segmentation import (
        EdgeSegConfig,
        refine_skin_region,
    )

    color = build_skin_mask(rgb)
    color = color.astype(bool) if color is not None else empty.copy()
    meta: Dict[str, Any] = {
        "model_id": None,
        "source": "interactive_rgb_reference",
        "automatic_measurement": False,
        "note": "当前为图像候选，请核对皮肤并补充浅色区域",
        "confidence_calibrated": False,
        "edge_snap": False,
    }
    if not color.any():
        return {
            "skin": empty,
            "lesion": empty.copy(),
            "uncertain": empty.copy(),
            "excluded": empty.copy(),
        }, meta
    search = refine_skin_region(rgb, color, None)
    if not np.any(search):
        search = color
    cfg = EdgeSegConfig(snap_edges=True)
    raw = segment_lesions_edge_aware(
        rgb, region=search, skin_candidate=color, cfg=cfg
    )
    candidate = _bool_mask(raw.get("lesion_mask"), empty.shape)
    band = _bool_mask(raw.get("uncertain_mask"), empty.shape)
    visible = color | candidate
    skin = refine_skin_region(rgb, visible, candidate)
    if not np.any(skin):
        skin = visible
    meta["edge_snap"] = True
    return {
        "skin": skin,
        "lesion": empty.copy(),
        "uncertain": (candidate | band) & skin,
        "excluded": empty.copy(),
    }, meta


def _bool_mask(value: Any, shape: Tuple[int, ...]) -> np.ndarray:
    if value is None:
        return np.zeros(shape, dtype=bool)
    arr = np.asarray(value)
    if arr.shape != shape:
        return np.zeros(shape, dtype=bool)
    return arr.astype(bool)


def snap_visible_mask(
    rgb: np.ndarray, skin: np.ndarray, target: np.ndarray
) -> np.ndarray:
    """Snap a candidate onto colour edges. The result is still not a measurement."""
    from web.backend.services.vasi_edge_segmentation import (
        EdgeSegConfig,
        refine_mask_by_edges,
    )

    bounded = target.astype(bool) & skin.astype(bool)
    if not bounded.any():
        return bounded
    snapped = refine_mask_by_edges(
        rgb, bounded, region=skin, cfg=EdgeSegConfig(snap_edges=True)
    )
    snapped = np.asarray(snapped).astype(bool) & skin.astype(bool)
    return snapped if snapped.any() else bounded

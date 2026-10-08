"""Measurement eligibility and arithmetic are server policy, never LLM output."""

import hashlib
import json
from typing import Any, Dict, Optional
import cv2
import numpy as np
from web.backend.exceptions import RGBSegmentationError
from web.backend.services.rgb_segmentation.images import local_quality
from web.backend.services.annotation_contract import encode_layer
from web.backend.services.assessment_measurement import measure_layers

PROTOCOL = "skin-seg-v2"
POLICY_VERSION = "rgb-measurement-policy-v1"
MEASUREMENT_VERSION = "rgb-mask-v1"
REASONS = {
    "USER_REVIEW_REQUIRED": "请核对皮肤与浅色范围后再测量",
    "SKIN_UNVERIFIED": "尚未得到可靠皮肤范围，请先调整皮肤标注",
    "REGIONS_UNRESOLVED": "部分区域仍需核对，请补充遗漏或删除误圈范围",
    "QUALITY_INFORMATION_LOST": "照片局部严重过曝或过暗，请在均匀光照下重拍",
    "NO_TARGET": "本次未获得可测浅色区域，可手动补充",
}


def validate_masks(masks: Dict[str, np.ndarray], shape: tuple) -> None:
    if set(masks) != {"skin", "lesion", "uncertain", "excluded"}:
        raise RGBSegmentationError("ARTIFACT_INVALID", "缺少完整标注")
    for mask in masks.values():
        if mask.dtype != np.bool_ or mask.shape != shape:
            raise RGBSegmentationError("ARTIFACT_INVALID", "标注尺寸与照片不一致")
    skin, lesion = masks["skin"], masks["lesion"]
    outside = int((lesion & ~skin).sum())
    if outside > max(4, int(lesion.sum() * 0.02)):
        raise RGBSegmentationError(
            "ARTIFACT_INVALID", "浅色区域超出皮肤范围，请先核对两层标注"
        )
    if int((skin & masks["excluded"]).sum()) > max(4, int(skin.sum() * 0.02)):
        raise RGBSegmentationError("ARTIFACT_INVALID", "皮肤与排除范围冲突，请重新核对")


def measure_rgb(
    rgb: np.ndarray,
    masks: Dict[str, np.ndarray],
    image_bytes: bytes,
    reviewed: bool,
    calibration: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    validate_masks(masks, rgb.shape[:2])
    skin = masks["skin"] & ~masks["excluded"]
    lesion = masks["lesion"] & skin
    quality = local_quality(rgb, skin)
    blockers = []
    if quality["status"] == "retake_required":
        blockers.append("QUALITY_INFORMATION_LOST")
    if int(skin.sum()) < 64:
        blockers.append("SKIN_UNVERIFIED")
    if not reviewed:
        blockers.append("USER_REVIEW_REQUIRED")
    if masks["uncertain"].any():
        blockers.append("REGIONS_UNRESOLVED")
    measurement = measure_layers(
        encode_layer(skin, (96, 165, 250)),
        encode_layer(lesion, (0, 170, 100)),
        image_bytes,
        calibration,
    )
    measurement["version"] = MEASUREMENT_VERSION
    measurement["mask_revision"] = hashlib.sha256(
        image_bytes + skin.tobytes() + lesion.tobytes()
    ).hexdigest()
    count, _, stats, centers = cv2.connectedComponentsWithStats(
        lesion.astype(np.uint8), connectivity=8
    )
    order = sorted(range(1, count), key=lambda i: -int(stats[i, cv2.CC_STAT_AREA]))
    h, w = skin.shape
    locations = [
        ["图像左上", "图像上方", "图像右上"],
        ["图像左侧", "图像中心", "图像右侧"],
        ["图像左下", "图像下方", "图像右下"],
    ]
    measurement["region_count"] = count - 1
    measurement["regions"] = [
        {
            "id": int(i),
            "pixels": int(stats[i, cv2.CC_STAT_AREA]),
            "centroid": [
                round(float((centers[i, 0] + 0.5) / w), 6),
                round(float((centers[i, 1] + 0.5) / h), 6),
            ],
            "bbox_pixels": [int(v) for v in stats[i, :4]],
            "location": locations[min(2, int(centers[i, 1] * 3 / h))][
                min(2, int(centers[i, 0] * 3 / w))
            ],
        }
        for i in order[:128]
    ]
    measurement["region_details_truncated"] = count - 1 > 128
    measurement["quality"] = quality
    measurement["calibration_id"] = None
    if measurement.get("area_cm2") is not None:
        measurement["calibration_id"] = (
            "calibration_"
            + hashlib.sha256(
                json.dumps(calibration, sort_keys=True).encode()
            ).hexdigest()
        )
    else:
        measurement["scale"] = {"source": "unavailable", "scope": "pixel_grid"}
    if blockers:
        measurement.update(
            status="unavailable",
            availability="review_required",
            reasons=[REASONS[code] for code in blockers],
        )
        for key in [
            "area_percentage",
            "area_cm2",
            "color",
            "border",
            "extent",
            "lesion_pixels",
            "skin_pixels",
            "region_count",
            "regions",
        ]:
            measurement[key] = None
    state = (
        "retake_required"
        if "QUALITY_INFORMATION_LOST" in blockers
        else "review_required" if blockers else "measurable"
    )
    return {
        "status": state,
        "measurement": measurement,
        "blocking_reasons": blockers,
        "quality": quality,
    }


def result_contract(
    job_id: str,
    metadata: Dict[str, Any],
    revision: str,
    masks: Dict[str, np.ndarray],
    decision: Dict[str, Any],
    model: Dict[str, Any],
    reviewed: bool,
) -> Dict[str, Any]:
    raw = decision["measurement"]
    measurable = decision["status"] == "measurable"
    result = {
        "protocol": PROTOCOL,
        "input_type": "rgb_photo",
        "job_id": job_id,
        "image": {
            "id": "rgb-" + job_id,
            "sha256": metadata["sha256"],
            "width": metadata["width"],
            "height": metadata["height"],
            "transform_id": metadata["transform_id"],
            "roi_revision": revision,
            "coordinate_frame": "normalized_original",
        },
        "status": decision["status"],
        "review_state": "user_reviewed" if reviewed else "pending",
        "mask_revision": revision,
        "masks": {
            public: "mask_" + job_id + "_" + revision + "_" + kind
            for public, kind in [
                ("valid_skin", "skin"),
                ("lesion", "lesion"),
                ("uncertain", "uncertain"),
                ("excluded", "excluded"),
            ]
        },
        "measurement": (
            {
                "scope": "visible_skin_in_selected_roi",
                "skin_pixels": raw["skin_pixels"],
                "lesion_pixels": raw["lesion_pixels"],
                "area_percentage": raw["area_percentage"],
                "area_cm2": raw.get("area_cm2"),
                "calibration_id": raw.get("calibration_id"),
                "scale_status": (
                    "calibrated" if raw.get("area_cm2") is not None else "unavailable"
                ),
                "perimeter_pixels": (raw.get("border") or {}).get("perimeter_pixels"),
                "region_count": raw.get("region_count"),
            }
            if measurable
            else None
        ),
        "confidence": {
            "event": "segmentation_meets_acceptance",
            "calibrated": False,
            "score": None,
            "calibration_id": None,
        },
        "blocking_reasons": decision["blocking_reasons"],
        "provenance": {
            "skin_model": model.get("model_id"),
            "lesion_model": model.get("model_id"),
            "refiner": model.get("refiner"),
            "policy_version": POLICY_VERSION,
            "decision_by": "server_measurement_policy",
        },
    }
    return result


def annotation_metadata(
    job_id: str,
    revision: str,
    masks: Dict[str, np.ndarray],
    metadata: Dict[str, Any],
    model: Dict[str, Any],
    reviewed: bool = False,
) -> Dict[str, Any]:
    count, _ = cv2.connectedComponents(
        masks["uncertain"].astype(np.uint8), connectivity=8
    )
    return {
        "protocol": PROTOCOL,
        "job_id": job_id,
        "mask_revision": revision,
        "review_state": "user_reviewed" if reviewed else "pending",
        "width": metadata["width"],
        "height": metadata["height"],
        "uncertain_layer_data_url": encode_layer(masks["uncertain"], (240, 143, 0)),
        "excluded_layer_data_url": encode_layer(masks["excluded"], (100, 116, 139)),
        "uncertain_pixels": int(masks["uncertain"].sum()),
        "source": model["source"],
        "refine": {
            "version": "rgb-tools-v1",
            "measurement_eligible": False,
            "unresolved_region_count": max(0, count - 1),
            "status": "candidate-only" if not reviewed else "user-reviewed",
        },
        "image_metadata": metadata,
        "automatic_model_validated": False,
    }

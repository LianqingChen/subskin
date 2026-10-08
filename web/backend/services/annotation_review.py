"""Persist an explicit user review without changing original AI geometry or training."""
import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from web.backend.services.annotation_contract import AnnotationContractError
from web.backend.services.assessment_measurement import decode_mask, measure_layers, normalize_capture, read_details


def apply_review(assessment: Any, skin: Optional[str], lesion: Optional[str],
                 uncertainty_reviewed: bool, image_bytes: Optional[bytes]) -> Dict[str, Any]:
    if not uncertainty_reviewed:
        raise AnnotationContractError("请先核对皮肤、浅色范围及橙色不确定区域")
    if not skin or not lesion or len(skin) > 16000000 or len(lesion) > 16000000:
        raise AnnotationContractError("请提供完整、有效的双层标注")
    skin_mask, lesion_mask = decode_mask(skin), decode_mask(lesion)
    if skin_mask is None or lesion_mask is None or skin_mask.shape != lesion_mask.shape:
        raise AnnotationContractError("皮肤与浅色蒙层尺寸不一致，请重新标注")
    details = read_details(assessment.details)
    original = details.get("annotation") or {}
    if original.get("protocol") != "skin-outline-v1" and (original.get("refine") or {}).get("status") != "cv-fallback":
        raise AnnotationContractError("此记录未采用分层参考标注协议")
    if not image_bytes:
        raise AnnotationContractError("原始照片暂不可读取，无法核对标注坐标")
    normalized = normalize_capture(image_bytes)
    from PIL import Image
    import io
    width, height = Image.open(io.BytesIO(normalized)).size
    mh, mw = skin_mask.shape
    if abs(mw / mh - width / height) > .005:
        raise AnnotationContractError("蒙层与原图比例不一致，请重新标注")
    measurement = measure_layers(skin, lesion, normalized, details.get("scale_reference"))
    if measurement["status"] == "unavailable":
        raise AnnotationContractError("；".join(measurement["reasons"]))
    import cv2
    region_count, _ = cv2.connectedComponents(lesion_mask.astype("uint8"), connectivity=8)
    annotation = dict(original)
    annotation.update({"protocol": "skin-outline-v1", "review_state": "user_reviewed", "reviewed_at": datetime.now(timezone.utc).isoformat(),
                       "uncertainty_reviewed": True, "proposal_layer_data_url": None, "region_count": max(0, region_count - 1), "uncertain_layer_data_url": None,
                       "uncertain_pixels": 0, "uncertain_percentage": 0,
                       "candidate_pixels": measurement.get("lesion_pixels"), "skin_pixels": measurement.get("skin_pixels")})
    # Original AI layers, including uncertainty, remain under raw_annotation.
    details.setdefault("raw_annotation", original)
    previous = details.get("measurement") or {}
    revisions = details.setdefault("annotation_reviews", [])
    if len(revisions) >= 100:
        raise AnnotationContractError("此记录修订次数已达上限，请创建新的照片记录")
    revisions.append({"actor_id": assessment.user_id, "at": annotation["reviewed_at"],
                      "previous_revision": previous.get("mask_revision"), "revision": measurement.get("mask_revision"),
                      "previous_event_hash": revisions[-1]["event_hash"] if revisions else None})
    revisions[-1]["event_hash"] = hashlib.sha256(json.dumps(revisions[-1], sort_keys=True).encode()).hexdigest()
    details.update(annotation=annotation, measurement=measurement)
    assessment.details = json.dumps(details, ensure_ascii=False)
    assessment.user_skin_layer = skin
    assessment.user_lesion_layer = lesion
    assessment.user_mask_image = lesion
    assessment.is_user_corrected = True
    assessment.final_area_percentage = measurement["area_percentage"]
    assessment.final_vasi_score = 0.0
    assessment.visual_features_json = None
    return measurement

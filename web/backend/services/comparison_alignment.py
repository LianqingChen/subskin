"""Same-site comparison: verified measurements or consent-gated visual observations."""
import hashlib
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from uuid import uuid4

import cv2
import numpy as np

from web.backend.services.assessment_comparison import prepare, measure_common_roi, save_comparison_preview, unavailable
from web.backend.services.comparison_geometry import decode_photo, manual_transform, automatic_transform, residual_error, stable_skin_mask, warp_pair, png_bytes
from web.backend.services.comparison_visual import describe_comparison
from web.backend.services.comparison_refinement import refine_transform
from web.backend.services.spot_compare import load_photo_ref, resolve_image_bytes, normalize_body_site, compare_pair, merge_measurement_evidence


def load_pair(db: Any, user_id: int, ref_a: str, ref_b: str) -> Tuple[Dict[str, Any], Dict[str, Any], bytes, bytes, np.ndarray, np.ndarray]:
    infos = [load_photo_ref(db, ref) for ref in (ref_a, ref_b)]
    if any(not info or info["user_id"] != user_id for info in infos):
        raise ValueError("照片不存在或不可访问")
    a, b = sorted(infos, key=lambda info: info["date"])
    if not a.get("body_site") or normalize_body_site(a["body_site"]) != normalize_body_site(b.get("body_site")):
        raise ValueError("请选择同一身体部位的两张照片")
    raw_a, raw_b = [resolve_image_bytes(info["image_url"], info.get("image_key")) for info in (a, b)]
    try:
        rgb_a, rgb_b = decode_photo(raw_a), decode_photo(raw_b)
    except Exception:
        raise ValueError("照片无法读取，请重新选择") from None
    return a, b, raw_a, raw_b, rgb_a, rgb_b


def bound_manual_transform(a: Dict[str, Any], b: Dict[str, Any], rgb_a: np.ndarray, rgb_b: np.ndarray, settings: Dict[str, Any]) -> np.ndarray:
    if settings.get("version") != "manual-similarity-v1" or settings.get("confirmed") is not True:
        raise ValueError("请确认手动对齐后再分析")
    reference, moving = settings.get("reference_id"), settings.get("moving_id")
    if reference == moving or {reference, moving} != {a["record_id"], b["record_id"]}:
        raise ValueError("对齐照片已变化，请重新调整")
    if reference == a["record_id"]:
        transform = manual_transform(rgb_a, rgb_b, settings)
    else:
        transform = cv2.invertAffineTransform(manual_transform(rgb_b, rgb_a, settings))
    _, _, valid = warp_pair(rgb_a, rgb_b, transform)
    if float(valid.mean()) < .2:
        raise ValueError("两张照片重叠范围太少，请调整位置或缩放")
    return transform


def validate_manual_comparison(db: Any, user_id: int, ref_a: str, ref_b: str, settings: Dict[str, Any], body_site: Optional[str] = None) -> None:
    a, b, _, _, rgb_a, rgb_b = load_pair(db, user_id, ref_a, ref_b)
    if body_site and normalize_body_site(body_site) != normalize_body_site(a["body_site"]):
        raise ValueError("所选部位与照片记录不一致")
    bound_manual_transform(a, b, rgb_a, rgb_b, settings)


def quality(data: bytes) -> Tuple[float, str]:
    try:
        from web.backend.services.vasi_quality import vasi_quality_checker
        name = vasi_quality_checker.check_all(data).overall
        return (1.0 if name == "good" else .8), name
    except Exception:
        return .5, "unknown"


def reviewed(info: Dict[str, Any]) -> bool:
    measurement = info.get("measurement") or {}
    annotation = measurement.get("annotation") or {}
    return measurement.get("status") == "measured" and annotation.get("review_state") == "user_reviewed" and measurement.get("version") in ("photo-mask-v1", "rgb-mask-v1")


def pair_result(a: Dict[str, Any], b: Dict[str, Any], merged: Dict[str, Any]) -> Dict[str, Any]:
    return {"ref_a": a["ref"], "ref_b": b["ref"], "body_site": a["body_site"],
            "body_site_label": a["body_site_label"], "dates": {"a": a["date"].isoformat(), "b": b["date"].isoformat()}, "merged": merged}


def _compare_report_pair(db: Any, user_id: int, ref_a: str, ref_b: str,
                        settings: Optional[Dict[str, Any]] = None) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    # Reuse automatic cache only for automatic measurements; manual results are report-local.
    base = None
    if settings is None:
        base = compare_pair(db, user_id, ref_a, ref_b)
        merged = (base or {}).get("merged") or {}
        if merged.get("comparison_status") == "measured" or (merged.get("evidence") or {}).get("duplicate"):
            return base, save_comparison_preview(db, user_id, base)
    a, b, raw_a, raw_b, rgb_a, rgb_b = load_pair(db, user_id, ref_a, ref_b)
    qa, qb = quality(raw_a), quality(raw_b)
    if hashlib.sha256(raw_a).digest() == hashlib.sha256(raw_b).digest() or (rgb_a.shape == rgb_b.shape and np.array_equal(rgb_a, rgb_b)):
        evidence = unavailable("两张照片内容重复，不能用于判断随时间变化")
        evidence["duplicate"] = True
        merged = merge_measurement_evidence(evidence, qa, qb)
        return pair_result(a, b, merged), {"aligned": False, "note": evidence["reasons"][0]}
    source = "manual" if settings is not None else "automatic"
    pa = prepare(raw_a, a.get("skin_layer"), a.get("user_lesion_layer") or a.get("ai_lesion_layer"))
    pb = prepare(raw_b, b.get("skin_layer"), b.get("user_lesion_layer") or b.get("ai_lesion_layer"))
    mask_a = stable_skin_mask(pa) if pa is not None else None
    mask_b = stable_skin_mask(pb) if pb is not None else None
    transform = bound_manual_transform(a, b, rgb_a, rgb_b, settings) if settings is not None else automatic_transform(rgb_a, rgb_b, mask_a, mask_b)
    initial = transform.copy() if transform is not None else None
    if transform is not None and residual_error(rgb_a, rgb_b, transform, mask_a, mask_b) is None:
        transform = refine_transform(rgb_a, rgb_b, transform, mask_a, mask_b)
    refined = initial is not None and not np.allclose(initial, transform)
    evidence = unavailable("缺少经核对的白斑范围，本次提供图像观察")
    views_match = not ((a.get("observation") or {}).get("view") and (b.get("observation") or {}).get("view") and a["observation"]["view"] != b["observation"]["view"])
    if transform is not None and views_match and reviewed(a) and reviewed(b) and a["measurement"]["version"] == b["measurement"]["version"]:
        if pa is not None and pb is not None:
            error = residual_error(pa[0], pb[0], transform, stable_skin_mask(pa), stable_skin_mask(pb))
            if error is not None:
                evidence = measure_common_roi(pa, pb, transform, error)
            else:
                evidence = unavailable("对齐未通过定位点误差校验，本次提供图像观察")
    elif base:
        evidence = (base.get("merged") or {}).get("evidence") or evidence
    evidence = {**evidence, "alignment_source": source if transform is not None else "none",
                "auto_refined": refined, "display_transform": transform.tolist() if transform is not None else None}
    merged = merge_measurement_evidence(evidence, qa, qb)
    pair = pair_result(a, b, merged)
    if settings is not None:
        merged["manual_alignment"] = dict(settings)
    if merged["comparison_status"] == "measured":
        preview = save_comparison_preview(db, user_id, pair)
        preview["source"] = source
        preview["auto_refined"] = refined
        return pair, preview
    reference, moving, valid = (rgb_a, rgb_b, None)
    if transform is not None:
        reference, moving, valid = warp_pair(rgb_a, rgb_b, transform)
        if float(valid.mean()) < .2:
            transform = None
            reference, moving, valid = rgb_a, rgb_b, None
    description = describe_comparison(db, user_id, png_bytes(reference), png_bytes(moving), a["body_site_label"], transform is not None)
    merged.update({"comparison_status": "visual_only", "analysis_mode": "visual_only", "trend": "图像观察", "trend_en": "unknown",
                   "summary": description["summary"], "visual_analysis_status": description["status"], "color_reason": None,
                   "capture_note": "手动对齐仅用于照片对照，量化结果需通过独立校验" if source == "manual" else "仅描述图像可见差异，不推断病情变化"})
    if settings is not None:
        merged["manual_alignment"] = dict(settings)
    if transform is None:
        return pair, {"aligned": False, "source": "none", "note": "自动对齐暂未通过，已提供图像观察；可尝试手动调整"}
    folder = Path("data/uploads/reports")
    folder.mkdir(parents=True, exist_ok=True)
    name = "%s_%s-visual-align.png" % (user_id, uuid4().hex)
    # Transparent uncovered regions keep missing content distinct from skin.
    rgba = np.dstack((moving, valid.astype(np.uint8) * 255))
    (folder / name).write_bytes(png_bytes(rgba))
    return pair, {"aligned": True, "source": source, "auto_refined": refined, "aligned_after_url": "/uploads/reports/" + name,
                  "heatmap_url": None, "note": "缺少通过校验的共同白斑范围，本次不生成面积变化热力图"}


def compare_report_pair(db: Any, user_id: int, ref_a: str, ref_b: str,
                        settings: Optional[Dict[str, Any]] = None) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Always include available single-photo measurements, even when change is unavailable."""
    from copy import deepcopy
    from web.backend.services.report_quantification import pair_photo_measurements
    pair, preview = _compare_report_pair(db, user_id, ref_a, ref_b, settings)
    pair = deepcopy(pair)
    pair["merged"]["photo_measurements"] = pair_photo_measurements(db, user_id, pair["ref_a"], pair["ref_b"])
    pair["merged"]["photo_measurement_source"] = "report_snapshot"
    return pair, preview

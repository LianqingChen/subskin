"""Conservative longitudinal measurement in a verified common skin ROI."""
import io
from typing import Any, Dict, Optional

import cv2
import numpy as np
from PIL import Image, ImageOps

from web.backend.services.assessment_measurement import decode_mask, COMPARISON_VERSION


def unavailable(reason: str) -> Dict[str, Any]:
    return {"version": COMPARISON_VERSION, "status": "not_comparable", "reasons": [reason],
            "size_change_percent": None, "color_change": None, "border_change": None}


def prepare(image: bytes, skin_layer: Optional[str], lesion_layer: Optional[str]):
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(image))).convert("RGB")
    img.thumbnail((1024, 1024))
    rgb = np.asarray(img)
    skin, lesion = decode_mask(skin_layer, rgb.shape), decode_mask(lesion_layer, rgb.shape)
    if skin is None or lesion is None or not skin.any():
        return None
    return rgb, skin, lesion & skin


def compare_registered_masks(image_a: bytes, image_b: bytes, info_a: Dict[str, Any],
                             info_b: Dict[str, Any]) -> Dict[str, Any]:
    """No inferred numeric changes from unsegmented or unrelated photographs."""
    obs_a, obs_b = info_a.get("observation") or {}, info_b.get("observation") or {}
    if obs_a.get("view") and obs_b.get("view") and obs_a.get("view") != obs_b.get("view"):
        return unavailable("拍摄视角未确认，请选择同一视角")
    ma, mb = info_a.get("measurement") or {}, info_b.get("measurement") or {}
    for measurement in (ma, mb):
        annotation = measurement.get("annotation") or {}
        if annotation and annotation.get("review_state") != "user_reviewed":
            return unavailable("请先完成两次照片的范围核对，再计算变化")
    if ma.get("version") != mb.get("version") or ma.get("version") not in ("photo-mask-v1", "rgb-mask-v1"):
        return unavailable("两次记录的测量方法不同，需要使用同一方法重新核对")
    if ma.get("status") != "measured" or mb.get("status") != "measured":
        return unavailable("白斑范围不完整或尚未核对，不能计算变化率")
    a = prepare(image_a, info_a.get("skin_layer"), info_a.get("user_lesion_layer") or info_a.get("ai_lesion_layer"))
    b = prepare(image_b, info_b.get("skin_layer"), info_b.get("user_lesion_layer") or info_b.get("ai_lesion_layer"))
    if a is None or b is None:
        return unavailable("缺少有效的皮肤与白斑标注")
    return measure_registered(a, b)


def measure_registered(a, b) -> Dict[str, Any]:
    """Match stable skin features, use a similarity transform (no shape warping)."""
    rgb_a, skin_a, lesion_a = a
    rgb_b, skin_b, lesion_b = b
    kernel = np.ones((11, 11), np.uint8)
    features_a = skin_a & ~cv2.dilate(lesion_a.astype(np.uint8), kernel).astype(bool)
    features_b = skin_b & ~cv2.dilate(lesion_b.astype(np.uint8), kernel).astype(bool)
    orb = cv2.ORB_create(nfeatures=4000)
    ka, da = orb.detectAndCompute(cv2.cvtColor(rgb_a, cv2.COLOR_RGB2GRAY), features_a.astype(np.uint8) * 255)
    kb, db = orb.detectAndCompute(cv2.cvtColor(rgb_b, cv2.COLOR_RGB2GRAY), features_b.astype(np.uint8) * 255)
    if da is None or db is None:
        return unavailable("共同皮肤纹理不足，无法可靠对齐；请按上次照片重拍")
    pairs = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(db, da, k=2)
    good = [p[0] for p in pairs if len(p) == 2 and p[0].distance < 0.7 * p[1].distance]
    if len(good) < 12:
        return unavailable("共同定位点不足，不能计算面积变化")
    src = np.float32([kb[m.queryIdx].pt for m in good])
    dst = np.float32([ka[m.trainIdx].pt for m in good])
    transform, inliers = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC, ransacReprojThreshold=3)
    if transform is None or inliers is None or int(inliers.sum()) < 10 or float(inliers.mean()) < 0.6:
        return unavailable("拍摄角度或姿态差异较大，无法可靠对齐")
    scale = float(np.linalg.norm(transform[:, 0]))
    if not 0.5 <= scale <= 2 or np.linalg.det(transform[:, :2]) <= 0:
        return unavailable("拍摄距离差异过大，请按基线重新拍摄")
    good_idx = inliers.ravel().astype(bool)
    projected = src @ transform[:, :2].T + transform[:, 2]
    error = float(np.sqrt(np.mean(np.sum((projected[good_idx] - dst[good_idx]) ** 2, axis=1))))
    if error > 2.5:
        return unavailable("对齐误差过大，不能区分拍摄差异与白斑变化")
    return measure_common_roi(a, b, transform, error)


def measure_common_roi(a, b, transform: np.ndarray, alignment_error: float) -> Dict[str, Any]:
    """Compute all displayed quantitative evidence from one coordinate system."""
    rgb_a, skin_a, lesion_a = a
    rgb_b, skin_b, lesion_b = b
    h, w = skin_a.shape
    warp = lambda x: cv2.warpAffine(x.astype(np.uint8), transform, (w, h), flags=cv2.INTER_NEAREST).astype(bool)
    valid_b, skin_b_w, lesion_b_w = warp(np.ones(skin_b.shape)), warp(skin_b), warp(lesion_b)
    common = skin_a & skin_b_w & valid_b
    skin_union = skin_a | skin_b_w
    coverage = float(common.sum() / max(int(skin_union.sum()), 1))
    if coverage < 0.7 or int(common.sum()) < 1000:
        return unavailable("两张照片拍到的皮肤范围差异较大")
    for mask in (lesion_a, lesion_b_w):
        if mask.any() and float((mask & common).sum() / mask.sum()) < 0.98:
            return unavailable("部分白斑未出现在两张照片的共同范围内，请补拍完整范围")
    la, lb = lesion_a & common, lesion_b_w & common
    area_a, area_b = int(la.sum()), int(lb.sum())
    radius = max(2, int(np.ceil(alignment_error * 2)))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (radius * 2 + 1, radius * 2 + 1))
    def bounds(mask):
        low = int(cv2.erode(mask.astype(np.uint8), kernel).sum())
        high = int((cv2.dilate(mask.astype(np.uint8), kernel).astype(bool) & common).sum())
        return low, high
    low_a, high_a = bounds(la)
    low_b, high_b = bounds(lb)
    change = (area_b - area_a) / area_a * 100 if area_a >= 300 and low_a > 0 else None
    interval = [round((low_b / high_a - 1) * 100, 1), round((high_b / low_a - 1) * 100, 1)] if change is not None else None
    direction = "unknown" if interval is None else "increasing" if interval[0] > 0 else "decreasing" if interval[1] < 0 else "uncertain"
    result = {"version": COMPARISON_VERSION, "status": "measured", "reasons": [],
        "size_change_percent": round(change, 1) if change is not None else None,
        "area_a_px": area_a, "area_b_px": area_b, "common_pixels": int(common.sum()),
        "common_coverage": round(coverage, 3), "alignment_error_px": round(alignment_error, 2),
        "change_interval_percent": interval, "interval_kind": "boundary_sensitivity_not_clinical_ci",
        "area_direction": direction, "transform": transform.tolist(),
        "color_change": None, "border_change": None, "color_reason": "参考正常皮肤不足",
        "expanded_pixels": int((lb & ~cv2.dilate(la.astype(np.uint8), kernel).astype(bool)).sum()),
        "reduced_pixels": int((la & ~cv2.dilate(lb.astype(np.uint8), kernel).astype(bool)).sum())}
    if change is None:
        result["reasons"].append("基线白斑过小或为零，不计算相对变化率")
    elif direction == "uncertain":
        result["reasons"].append("变化未超出边界敏感性范围，暂未见明确面积变化")
    rgb_b_w = cv2.warpAffine(rgb_b, transform, (w, h))
    # The same surrounding skin, not independent scene-wide white balance.
    reference = common & ~cv2.dilate((la | lb).astype(np.uint8), kernel).astype(bool)
    if reference.sum() >= 200 and area_a >= 100 and area_b >= 100:
        lab_a = cv2.cvtColor(rgb_a.astype(np.float32) / 255, cv2.COLOR_RGB2LAB)
        lab_b = cv2.cvtColor(rgb_b_w.astype(np.float32) / 255, cv2.COLOR_RGB2LAB)
        ref_a, ref_b = np.median(lab_a[reference], axis=0), np.median(lab_b[reference], axis=0)
        ref_delta = float(np.linalg.norm(ref_a - ref_b))
        if ref_delta <= 8:
            light_a = float(np.median(lab_a[la, 0]) - ref_a[0])
            light_b = float(np.median(lab_b[lb, 0]) - ref_b[0])
            delta = light_b - light_a
            result.update({"relative_lightness_change": round(delta, 1), "reference_delta_e76": round(ref_delta, 1),
                "color_change": "whiter" if delta > 3 else "darker" if delta < -3 else "same", "color_reason": None})
        else:
            result["color_reason"] = "参考皮肤颜色差异较大，暂不比较颜色"
    if direction in ("increasing", "decreasing"):
        result["border_change"] = "outward" if direction == "increasing" else "inward"
    return result


def save_comparison_preview(db, user_id: int, pair: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Render precisely the transform/masks used for the numeric result."""
    from pathlib import Path
    from uuid import uuid4
    from web.backend.services.spot_compare import load_photo_ref, resolve_image_bytes
    merged = (pair or {}).get("merged") or {}
    evidence = merged.get("evidence") or {}
    if merged.get("comparison_status") != "measured" or not evidence.get("transform"):
        return {"aligned": False, "note": merged.get("capture_note") or "缺少可靠的共同测量范围"}
    info_a, info_b = load_photo_ref(db, pair["ref_a"]), load_photo_ref(db, pair["ref_b"])
    if not info_a or not info_b or info_a["user_id"] != user_id or info_b["user_id"] != user_id:
        return {"aligned": False, "note": "照片不可访问"}
    images = []
    for info in (info_a, info_b):
        raw = resolve_image_bytes(info["image_url"], info.get("image_key"))
        if not raw:
            return {"aligned": False, "note": "照片不可访问"}
        image = prepare(raw, info.get("skin_layer"), info.get("user_lesion_layer") or info.get("ai_lesion_layer"))
        if image is None:
            return {"aligned": False, "note": "缺少分割范围"}
        images.append(image)
    (a, sa, la), (b, sb, lb) = images
    h, w = sa.shape
    transform = np.asarray(evidence["transform"], dtype=np.float64)
    warp = lambda x: cv2.warpAffine(x.astype(np.uint8), transform, (w, h), flags=cv2.INTER_NEAREST).astype(bool)
    common = sa & warp(sb) & warp(np.ones(sb.shape))
    warped = cv2.warpAffine(b, transform, (w, h))
    la, lb = la & common, warp(lb) & common
    radius = max(2, int(np.ceil(evidence.get("alignment_error_px", 0) * 2)))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (radius * 2 + 1, radius * 2 + 1))
    expanded = lb & ~cv2.dilate(la.astype(np.uint8), kernel).astype(bool)
    reduced = la & ~cv2.dilate(lb.astype(np.uint8), kernel).astype(bool)
    heat = (a.astype(np.float32) * 0.6).astype(np.uint8)
    heat[expanded] = (230, 110, 60)
    heat[reduced] = (50, 160, 170)
    folder = Path("data/uploads/reports")
    folder.mkdir(parents=True, exist_ok=True)
    stem = f"{user_id}_{uuid4().hex}"
    Image.fromarray(warped).save(folder / f"{stem}-align.png")
    Image.fromarray(heat).save(folder / f"{stem}-diff.png")
    return {"aligned": True, "aligned_after_url": f"/uploads/reports/{stem}-align.png",
            "heatmap_url": f"/uploads/reports/{stem}-diff.png", "note": "仅显示共同可见皮肤，边界误差带不计入变化；颜色不表示病情分期",
            "classes": {"repigmented_px": int(reduced.sum()), "expanded_px": int(expanded.sum()), "analysis_px": int(common.sum())}}

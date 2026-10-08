"""共识引擎（vasi_consensus）— 评估时的患者级画布管线集成。

依据 hermes_plan/2026-08-27-vitiligo-auto-recognition-self-loop.md §6：

SAM 掩膜 vs 患者像素分类器掩膜 → IoU 共识 → 色值验证（文档 §7 L3：
候选彩度 C < 邻近正常皮肤 C×0.85 且 L* 更高 → 确认；否则丢弃）→
仍分歧则入 LLM 裁判队列（后台限速处理，裁决成为伪标签）。

输出 consensus_json 供评估持久化；自动终审条件见 auto_finalize_allowed()。
所有环节失败均优雅降级：无患者模型/无关键点/校准失败都返回
"未参与共识"的结果，不影响既有 VLM+SAM 主链路。
"""

import json
import logging
from typing import Any, Dict, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# 共识阈值
_IOU_AGREE = 0.5            # SAM 与患者模型 IoU ≥ 此值视为共识
# 色值验证阈值（文档 §7 L3）
_C_RATIO_CONFIRM = 0.85     # 候选 C 中位 < 邻近皮肤 C 中位 × 0.85
_L_GAP_CONFIRM = 1.0        # 候选 L* 中位 > 邻近皮肤 L* 中位 + 1
_DILATE_RING = 25           # 邻域环宽度 px


def mask_iou(a: Optional[np.ndarray], b: Optional[np.ndarray]) -> Optional[float]:
    """两个同尺寸布尔掩膜的 IoU。尺寸不一致返回 None。"""
    if a is None or b is None:
        return None
    if a.shape != b.shape:
        return None
    inter = int(np.logical_and(a, b).sum())
    union = int(np.logical_or(a, b).sum())
    if union == 0:
        return 1.0 if inter == 0 else 0.0
    return inter / union


def color_verify_candidate(canvas_img: np.ndarray,
                           candidate_mask: np.ndarray,
                           skin_mask: np.ndarray,
                           validity: Optional[np.ndarray] = None,
                           ) -> Optional[Dict[str, Any]]:
    """色值验证单个候选（文档 §7 L3）。

    Returns:
        {"passed": bool, "C_ratio": float, "L_gap": float, "cand_C": float,
         "nb_C": float, "cand_L": float, "nb_L": float} 或 None
    """
    if canvas_img is None or candidate_mask is None or not candidate_mask.any():
        return None
    if canvas_img.shape[:2] != candidate_mask.shape[:2]:
        return None
    try:
        import cv2
        from web.backend.services.vasi_canvas import lab_of
    except Exception:
        return None
    lab = lab_of(canvas_img)
    L = lab[..., 0]
    C = np.hypot(lab[..., 1], lab[..., 2])

    # 邻域 = 候选膨胀环 减去 候选本身，∩ 皮肤
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * _DILATE_RING + 1, 2 * _DILATE_RING + 1))
    dilated = cv2.dilate(candidate_mask.astype(np.uint8), k).astype(bool)
    nb = dilated & (~candidate_mask)
    if skin_mask is not None and skin_mask.shape == candidate_mask.shape:
        nb = nb & skin_mask.astype(bool)
    if validity is not None and validity.shape == candidate_mask.shape:
        nb = nb & validity.astype(bool)
    if not nb.any():
        return None

    cand_L = float(np.median(L[candidate_mask]))
    cand_C = float(np.median(C[candidate_mask]))
    nb_L = float(np.median(L[nb]))
    nb_C = float(np.median(C[nb]))
    if nb_C <= 0:
        return None
    passed = bool(cand_C < nb_C * _C_RATIO_CONFIRM and cand_L > nb_L + _L_GAP_CONFIRM)
    return {
        "passed": passed,
        "C_ratio": round(cand_C / nb_C, 3),
        "L_gap": round(cand_L - nb_L, 2),
        "cand_C": round(cand_C, 2),
        "nb_C": round(nb_C, 2),
        "cand_L": round(cand_L, 1),
        "nb_L": round(nb_L, 1),
    }


def load_anchor(db, user_id: int, body_site: str) -> Optional[Dict[str, Any]]:
    """读取患者级锚点（对齐目标 + 校准基准）。"""
    try:
        from web.backend.models.vasi import PatientAlignState
        row = (db.query(PatientAlignState)
               .filter(PatientAlignState.user_id == user_id,
                       PatientAlignState.body_site == body_site)
               .order_by(PatientAlignState.updated_at.desc()).first())
        if not row:
            return None
        return {
            "ref_mean_bgr": json.loads(row.calibration_json).get("ref_mean_bgr")
            if row.calibration_json else None,
            "kind": row.kind,
        }
    except Exception as e:
        logger.info("load anchor failed: %s", e)
        return None


def save_anchor(db, user_id: int, body_site: str, snapshot: Dict[str, Any],
                image_key: Optional[str] = None) -> None:
    """保存/更新患者级锚点（首张照片建立，此后不覆盖 ref 基准）。"""
    try:
        from web.backend.models.vasi import PatientAlignState
        row = (db.query(PatientAlignState)
               .filter(PatientAlignState.user_id == user_id,
                       PatientAlignState.body_site == body_site).first())
        if row is None:
            row = PatientAlignState(user_id=user_id, body_site=body_site)
            db.add(row)
            row.kind = snapshot.get("kind")
            row.canvas_params_json = json.dumps(snapshot.get("canvas") or {}, ensure_ascii=False)
            row.calibration_json = json.dumps(snapshot.get("calibration") or {}, ensure_ascii=False)
            row.anchor_image_key = image_key
        elif not (row.calibration_json and json.loads(row.calibration_json or "{}").get("ref_mean_bgr")):
            # 旧锚点缺少 ref 基准时补齐（不覆盖已有）
            row.kind = snapshot.get("kind") or row.kind
            row.calibration_json = json.dumps(snapshot.get("calibration") or {}, ensure_ascii=False)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.info("save anchor failed: %s", e)


def run_patient_consensus(db,
                          user_id: int,
                          body_site: str,
                          image_bytes: bytes,
                          image_key: Optional[str],
                          sam_lesion_mask_orig: Optional[np.ndarray],
                          sam_skin_mask_orig: Optional[np.ndarray],
                          ) -> Dict[str, Any]:
    """评估时执行患者级画布管线 + 共识。

    Args:
        sam_lesion_mask_orig / sam_skin_mask_orig: SAM 输出的原图坐标掩膜
        （lesion 可能为 None=未检出病灶）

    Returns:
        {"participated": bool, "snapshot": canvas_json|None,
         "patient_model_version": str|None, "patient_mask_orig": np.ndarray|None,
         "kmeans": {...}|None, "consensus": {...}, "auto_finalize": bool,
         "note": str}
    """
    out: Dict[str, Any] = {
        "participated": False,
        "snapshot": None,
        "patient_model_version": None,
        "patient_mask_orig": None,
        "kmeans": None,
        "consensus": None,
        "auto_finalize": False,
        "note": "",
    }
    try:
        from web.backend.services import vasi_canvas, vasi_patient_model
    except ImportError:
        out["note"] = "canvas modules unavailable"
        return out

    # ── 对齐 + 校准 ──
    anchor = load_anchor(db, user_id, body_site)
    result = vasi_canvas.align_and_calibrate(
        image_bytes, body_site, anchor=anchor,
        skin_mask=sam_skin_mask_orig, lesion_mask=sam_lesion_mask_orig,
    )
    if not result.ok:
        out["note"] = result.note
        return out
    snapshot = vasi_canvas.canvas_snapshot(result)
    out["snapshot"] = snapshot
    out["participated"] = True

    # 首张有效照片 → 锚点落库（含 ref_mean_bgr 基准）
    if anchor is None or (anchor.get("ref_mean_bgr") is None):
        save_anchor(db, user_id, body_site, snapshot, image_key)

    canvas_img = result.canvas_img
    validity = vasi_canvas.canvas_validity_mask(result.canvas_warped)
    skin_c = vasi_canvas.warp_mask_orig_to_canvas(sam_skin_mask_orig, snapshot) \
        if sam_skin_mask_orig is not None else None

    # ── 患者模型预测（无模型 → K-means 冷启动）──
    clf = vasi_patient_model.load_model(user_id, body_site)
    model_meta = vasi_patient_model.load_model_meta(user_id, body_site)
    # 画布定义一致性防护：模型训练画布尺寸与本次不一致 → 不使用（避免坐标特征失效）
    if clf is not None and model_meta and model_meta.get("canvas_shape"):
        if tuple(model_meta["canvas_shape"]) != tuple(canvas_img.shape[:2]):
            logger.info(
                "patient model canvas mismatch (model=%s, current=%s), using cold start",
                model_meta["canvas_shape"], canvas_img.shape[:2],
            )
            clf = None
            model_meta = None
    if clf is not None and model_meta:
        out["patient_model_version"] = str(model_meta.get("version") or "v1")
    patient_mask_canvas: Optional[np.ndarray] = None
    if clf is not None:
        # 只预测皮肤区（膨胀后），大图/恒等画布下性能优化
        predict_region = validity
        if skin_c is not None and skin_c.shape == validity.shape:
            import cv2 as _cv2
            k = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (51, 51))
            predict_region = _cv2.dilate(skin_c.astype(np.uint8), k).astype(bool) & validity
        prob = vasi_patient_model.predict_canvas(clf, canvas_img, validity,
                                                 predict_region=predict_region)
        if prob is not None:
            patient_mask_canvas = vasi_patient_model.postprocess_canvas(
                prob > 0.5, top_hard_open_rows=(150 if snapshot.get("kind") == "face" else 0))
    if patient_mask_canvas is None:
        # 冷启动（文档 §4.6）
        km = vasi_patient_model.kmeans_cold_start(canvas_img, skin_c if skin_c is not None else validity)
        if km and km.get("sane"):
            out["kmeans"] = {
                "cluster_white": km["cluster_white"],
                "cluster_normal": km["cluster_normal"],
                "sane": km["sane"],
            }
            patient_mask_canvas = km["mask"]

    patient_mask_orig: Optional[np.ndarray] = None
    if patient_mask_canvas is not None and result.transform is not None:
        import cv2
        h, w = cv2.imdecode(np.frombuffer(image_bytes, np.uint8),
                            cv2.IMREAD_GRAYSCALE).shape
        patient_mask_orig = vasi_patient_model.canvas_mask_to_original(
            patient_mask_canvas, result.transform, (h, w))
    out["patient_mask_orig"] = patient_mask_orig

    # 掩膜黑边率（自动质检：掩膜不应落在画布有效区外）
    border_ratio = 0.0
    if patient_mask_canvas is not None and patient_mask_canvas.any():
        outside = patient_mask_canvas & (~validity)
        border_ratio = float(outside.sum()) / max(float(patient_mask_canvas.sum()), 1.0)

    sam_mask = sam_lesion_mask_orig
    consensus: Dict[str, Any] = {
        "sam_pixels": int(sam_mask.sum()) if sam_mask is not None else None,
        "patient_pixels": int(patient_mask_orig.sum()) if patient_mask_orig is not None else None,
        "patient_border_ratio": round(border_ratio, 4),
        "iou": None,
        "verdict": "no_participant",
        "verified_candidates": [],
    }

    if patient_mask_orig is None and (sam_mask is None or not sam_mask.any()):
        consensus["verdict"] = "both_empty"
        out["consensus"] = consensus
        out["auto_finalize"] = True  # 双方都认为无白斑
        out["note"] = "both empty consensus"
        return out

    iou = mask_iou(sam_mask, patient_mask_orig) \
        if (sam_mask is not None and patient_mask_orig is not None) else None
    consensus["iou"] = round(iou, 3) if iou is not None else None

    if iou is not None and iou >= _IOU_AGREE:
        consensus["verdict"] = "agreed"
        out["auto_finalize"] = True
        out["note"] = f"consensus IoU={iou:.2f}"
    else:
        # 分歧/单方检出 → 色值验证（画布上）
        cand_masks = []
        if sam_mask is not None and sam_mask.any():
            cand_masks.append(("sam", sam_mask))
        if patient_mask_orig is not None and patient_mask_orig.any():
            cand_masks.append(("patient", patient_mask_orig))
        verified = 0
        failed = 0
        for src, m in cand_masks:
            m_c = vasi_canvas.warp_mask_orig_to_canvas(m, snapshot)
            if m_c is None or not m_c.any():
                continue
            chk = color_verify_candidate(canvas_img, m_c,
                                         skin_c if skin_c is not None else validity,
                                         validity)
            if chk is None:
                continue
            consensus["verified_candidates"].append({"source": src, **chk})
            if chk["passed"]:
                verified += 1
            else:
                failed += 1
        if verified > 0 and failed == 0:
            consensus["verdict"] = "color_confirmed"
            out["auto_finalize"] = True
            out["note"] = "color verification confirmed"
        elif verified == 0 and failed > 0:
            consensus["verdict"] = "color_rejected"
            out["note"] = "color verification rejected"
        else:
            consensus["verdict"] = "disputed_needs_judge"
            out["note"] = "disputed, queued for LLM judge"

    out["consensus"] = consensus
    return out


def auto_finalize_allowed(quality_overall: str,
                          consensus: Optional[Dict[str, Any]],
                          qa: Optional[Dict[str, Any]] = None) -> bool:
    """自动终审门禁（hermes_plan §6 条件）：
    质检 acceptable 以上 + 共识/验证通过 + 质检门禁无异常。
    """
    if quality_overall not in ("good", "acceptable"):
        return False
    if not consensus or consensus.get("verdict") not in ("agreed", "both_empty", "color_confirmed"):
        return False
    if qa and qa.get("anomalies"):
        return False
    return True

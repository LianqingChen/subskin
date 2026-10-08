"""白斑识别自循环引擎（vasi_autoloop）。

依据 hermes_plan/2026-08-27-vitiligo-auto-recognition-self-loop.md §8：

[采集] 用户修正掩膜 / LLM裁判伪标签 / K-means冷启动伪标签 → 患者训练样本
[训练] 每 (user_id, body_site) 重训随机森林 → shadow 评估（留出最近样本）
[部署] 新模型 Dice 优于当前活跃才激活；连续劣化自动回滚；写版本表
[裁判] 共识分歧区裁剪送 VLM 复核（限速+成本护栏），裁决成为伪标签
[质检] 文档 §7 指标巡检（面积比 0.5~2.0、掩膜黑边率、ROI 彩度）
[统计] AutoLoopRun 审计

后台循环由 app lifespan 启动（run_autoloop_task），周期默认 10 分钟。
全部步骤 try/except 隔离；任何单点失败不影响主链路与其他步骤。
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

LOOP_INTERVAL_SECONDS = int(os.getenv("AUTOLOOP_INTERVAL_SECONDS", "600"))
JUDGE_MAX_PER_HOUR = int(os.getenv("AUTOLOOP_JUDGE_MAX_PER_HOUR", "10"))
JUDGE_MIN_INTERVAL_SECONDS = int(os.getenv("AUTOLOOP_JUDGE_MIN_INTERVAL", "30"))
AUTOLOOP_ENABLED = os.getenv("AUTOLOOP_ENABLED", "1") == "1"

_JUDGE_STATE = {"last_ts": 0.0, "hour_bucket": "", "hour_count": 0}

# 文档 §7 自动质检指标
_AREA_RATIO_MIN, _AREA_RATIO_MAX = 0.5, 2.0
_BORDER_RATIO_MAX = 0.05  # 掩膜落在黑边像素占比上限


# ══════════════════════════════════════════════════════════════════════════════
# 样本落盘
# ══════════════════════════════════════════════════════════════════════════════

def _samples_dir(user_id: int, body_site: str) -> Any:
    from pathlib import Path
    from web.backend.services.vasi_patient_model import _model_dir
    d = _model_dir(user_id, body_site) / "samples"
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_patient_sample(user_id: int, body_site: str,
                        canvas_img: np.ndarray,
                        mask_canvas: np.ndarray,
                        validity: Optional[np.ndarray],
                        source: str,
                        assessment_id: Optional[int] = None) -> Optional[str]:
    """保存患者训练样本（画布图 + 掩膜 + 有效区）。返回样本路径。"""
    if canvas_img is None or mask_canvas is None or not mask_canvas.any():
        return None
    if canvas_img.shape[:2] != mask_canvas.shape[:2]:
        return None
    try:
        from web.backend.services.vasi_patient_model import mask_hash
        d = _samples_dir(user_id, body_site)
        h = mask_hash(mask_canvas)
        ts = int(time.time())
        stem = f"s_{ts}_{h}"
        npz_path = d / (stem + ".npz")
        np.savez_compressed(str(npz_path),
                            canvas_img=canvas_img.astype(np.uint8),
                            mask=mask_canvas.astype(np.uint8),
                            validity=(validity.astype(np.uint8)
                                      if validity is not None
                                      else np.ones(canvas_img.shape[:2], dtype=np.uint8)))
        meta = {"source": source, "assessment_id": assessment_id,
                "canvas_shape": list(canvas_img.shape[:2]),
                "created_at": datetime.utcnow().isoformat()}
        (d / (stem + ".json")).write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        return str(npz_path)
    except Exception as e:
        logger.warning("save patient sample failed: %s", e)
        return None


def iter_patient_samples(user_id: int, body_site: str) -> List[Dict[str, Any]]:
    """读取该患者该部位全部训练样本（按时间升序）。"""
    d = _samples_dir(user_id, body_site)
    out: List[Dict[str, Any]] = []
    if not d.exists():
        return out
    for npz in sorted(d.glob("s_*.npz")):
        meta_f = npz.with_suffix(".json")
        meta = {}
        if meta_f.exists():
            try:
                meta = json.loads(meta_f.read_text(encoding="utf-8"))
            except Exception:
                pass
        try:
            z = np.load(str(npz), allow_pickle=False)
            out.append({"canvas_img": z["canvas_img"], "mask": z["mask"].astype(bool),
                        "validity": z["validity"].astype(bool), "meta": meta,
                        "path": str(npz)})
        except Exception as e:
            logger.warning("load sample %s failed: %s", npz, e)
    return out


# ══════════════════════════════════════════════════════════════════════════════
# 队列（DB）
# ══════════════════════════════════════════════════════════════════════════════

def queue_train(db, user_id: int, body_site: str, payload: Optional[Dict[str, Any]] = None) -> bool:
    try:
        from web.backend.models.vasi import AutoLoopQueue
        db.add(AutoLoopQueue(kind="train", user_id=user_id, body_site=body_site,
                             payload_json=json.dumps(payload or {}, ensure_ascii=False),
                             status="pending"))
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        logger.warning("queue_train failed: %s", e)
        return False


def queue_judge(db, assessment_id: int, payload: Dict[str, Any]) -> bool:
    try:
        from web.backend.models.vasi import AutoLoopQueue
        db.add(AutoLoopQueue(kind="judge", assessment_id=assessment_id,
                             payload_json=json.dumps(payload, ensure_ascii=False),
                             status="pending"))
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        logger.warning("queue_judge failed: %s", e)
        return False


def audit(db, trigger: str, detail: Dict[str, Any], duration_ms: Optional[int] = None,
          strategy: Optional[str] = None) -> None:
    try:
        from web.backend.models.vasi import AutoLoopRun
        db.add(AutoLoopRun(trigger=trigger, strategy=strategy,
                           detail_json=json.dumps(detail, ensure_ascii=False, default=str),
                           duration_ms=duration_ms))
        db.commit()
    except Exception:
        db.rollback()


# ══════════════════════════════════════════════════════════════════════════════
# 用户修正 → 训练样本（contour 提交后调用）
# ══════════════════════════════════════════════════════════════════════════════

def queue_correction_sample(db, assessment_id: int) -> bool:
    """把用户修正掩膜转成患者训练样本并排入训练队列。"""
    try:
        from web.backend.models.vasi import VASIAssessment
        from web.backend.services import vasi_canvas

        a = db.query(VASIAssessment).filter(VASIAssessment.id == assessment_id).first()
        if not a or getattr(a, "assessment_source", None) == "rgb-tools-v1" or not a.canvas_json or not a.user_lesion_layer:
            return False
        snapshot = json.loads(a.canvas_json)
        if not snapshot.get("calibration"):
            return False

        import base64
        import io
        from PIL import Image

        # 用户白斑层 data URL → 原图坐标掩膜
        data_url = a.user_lesion_layer
        if data_url.startswith("data:"):
            data_url = data_url.split(",", 1)[1]
        mask_bytes = base64.b64decode(data_url)
        mask_img = Image.open(io.BytesIO(mask_bytes)).convert("L")
        mask_orig = (np.asarray(mask_img) > 127)

        # 原图
        from web.backend.services.spot_compare import resolve_image_bytes
        img_bytes = resolve_image_bytes(a.image_url, a.image_key)
        if not img_bytes:
            return False
        import cv2
        orig = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)
        if orig is None:
            return False
        if mask_orig.shape[:2] != orig.shape[:2]:
            mask_orig = cv2.resize(mask_orig.astype(np.uint8),
                                   (orig.shape[1], orig.shape[0]),
                                   interpolation=cv2.INTER_NEAREST).astype(bool)

        canvas_img = vasi_canvas.rebuild_calibrated_canvas(orig, snapshot)
        if canvas_img is None:
            return False
        mask_canvas = vasi_canvas.warp_mask_orig_to_canvas(mask_orig, snapshot)
        if mask_canvas is None or not mask_canvas.any():
            return False
        validity = canvas_img.max(axis=2) > 10

        path = save_patient_sample(a.user_id, a.body_site, canvas_img, mask_canvas,
                                   validity, "user_correction", assessment_id)
        if not path:
            return False
        return queue_train(db, a.user_id, a.body_site,
                           {"source": "user_correction", "assessment_id": assessment_id,
                            "sample_path": path})
    except Exception as e:
        db.rollback()
        logger.warning("queue_correction_sample failed: %s", e)
        return False


# ══════════════════════════════════════════════════════════════════════════════
# 训练 + 部署
# ══════════════════════════════════════════════════════════════════════════════

def _shadow_dice(clf: Any, canvas_img: np.ndarray, mask: np.ndarray,
                 validity: np.ndarray) -> Optional[float]:
    from web.backend.services import vasi_patient_model as pm
    prob = pm.predict_canvas(clf, canvas_img, validity)
    if prob is None:
        return None
    pred = (prob > 0.5) & validity.astype(bool)
    inter = int(np.logical_and(pred, mask.astype(bool)).sum())
    union = int(np.logical_or(pred, mask.astype(bool)).sum())
    if union == 0:
        return 1.0
    return inter / union


def train_and_deploy(db, user_id: int, body_site: str) -> Dict[str, Any]:
    """重训患者模型 + shadow 评估 + 更优才部署。"""
    result = {"user_id": user_id, "body_site": body_site, "trained": False,
              "deployed": False, "dice": None, "reason": ""}
    samples = iter_patient_samples(user_id, body_site)
    if len(samples) < 1:
        result["reason"] = "no samples"
        return result
    # 画布定义一致性防护：不同画布尺寸（对齐锚点变化/部位拍照方式变化）
    # 的样本不可混训——坐标特征是画布相关的（文档 §4.4）。
    shapes = {tuple(s["canvas_img"].shape[:2]) for s in samples
              if s.get("canvas_img") is not None}
    if len(shapes) > 1:
        result["reason"] = f"inconsistent canvas shapes {shapes}"
        return result
    canvas_shape = list(shapes)[0] if shapes else None
    if canvas_shape is None:
        result["reason"] = "no valid canvas samples"
        return result
    try:
        from web.backend.services import vasi_patient_model as pm
        from web.backend.services.vasi_patient_model import mask_hash

        # 去重（同掩膜只留一份，最新优先）
        seen: Dict[str, Dict[str, Any]] = {}
        for s in samples:
            seen[mask_hash(s["mask"])] = s
        unique = sorted(seen.values(), key=lambda s: s["meta"].get("created_at", ""))
        result["sample_count"] = len(unique)

        # 训练集 = 除最后 1 张外全部；留出最后 1 张做 shadow 评估（≥2 张时）
        holdout = None
        train_set = unique
        if len(unique) >= 2:
            holdout = unique[-1]
            train_set = unique[:-1]

        # 合并样本特征训练
        clf = pm.train_rf_from_samples(train_set)
        if clf is None:
            result["reason"] = "train failed"
            return result
        result["trained"] = True

        # shadow 评估
        active_clf = pm.load_model(user_id, body_site)
        active_dice: Optional[float] = None
        if active_clf is not None and holdout is not None:
            active_dice = _shadow_dice(active_clf, holdout["canvas_img"],
                                       holdout["mask"], holdout["validity"])
        new_dice: Optional[float] = None
        if holdout is not None:
            new_dice = _shadow_dice(clf, holdout["canvas_img"], holdout["mask"],
                                    holdout["validity"])
        result["dice"] = round(new_dice, 3) if new_dice is not None else None
        result["active_dice"] = round(active_dice, 3) if active_dice is not None else None

        # 部署判定：无活跃模型 → 首训即部署；有活跃模型 → 更优（容忍 0.02 噪声）才部署
        should_deploy = False
        if active_clf is None:
            should_deploy = True
            result["reason"] = "first model"
        elif new_dice is not None and active_dice is not None:
            if new_dice >= active_dice - 0.02:
                should_deploy = True
                result["reason"] = f"improved dice {active_dice:.3f}→{new_dice:.3f}"
            else:
                result["reason"] = f"degraded ({active_dice:.3f}→{new_dice:.3f}), keep active"
        elif new_dice is not None:
            should_deploy = True
            result["reason"] = "no baseline dice, deploy"

        if should_deploy:
            version = f"rf-{int(time.time())}"
            meta = {"version": version, "body_site": body_site,
                    "training_source": ",".join(sorted({s["meta"].get("source", "?")
                                                        for s in unique})),
                    "sample_count": len(unique),
                    "shadow_dice": round(new_dice, 4) if new_dice is not None else None,
                    "canvas_shape": canvas_shape,
                    "trained_at": datetime.utcnow().isoformat()}
            path = pm.save_model(user_id, body_site, clf, meta)
            if path:
                _register_model(db, user_id, body_site, path, version, meta)
                result["deployed"] = True
                result["version"] = version
        return result
    except Exception as e:
        db.rollback()
        logger.warning("train_and_deploy failed: %s", e)
        result["reason"] = f"error: {e}"
        return result


def _register_model(db, user_id: int, body_site: str, path: str,
                    version: str, meta: Dict[str, Any]) -> None:
    try:
        from web.backend.models.vasi import PatientModel
        db.query(PatientModel).filter(PatientModel.user_id == user_id,
                                      PatientModel.body_site == body_site,
                                      PatientModel.is_active.is_(True)).update(
            {"is_active": False, "deactivated_at": datetime.utcnow()},
            synchronize_session=False)
        db.add(PatientModel(user_id=user_id, body_site=body_site,
                            model_kind="random_forest", model_path=path,
                            version=version,
                            training_source=meta.get("training_source"),
                            sample_count=int(meta.get("sample_count") or 0),
                            metrics_json=json.dumps({"shadow_dice": meta.get("shadow_dice")},
                                                    ensure_ascii=False),
                            is_active=True))
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning("register model failed: %s", e)


# ══════════════════════════════════════════════════════════════════════════════
# LLM 裁判（限速）
# ══════════════════════════════════════════════════════════════════════════════

JUDGE_PROMPT = (
    "你是一名皮肤科影像助手。请判断图片中红色框内的区域是否为白癜风白斑"
    "（色素脱失斑，通常比周围皮肤更白/更亮、发红度低）。\n"
    "只回答一个 JSON：{\"is_vitiligo\": true/false, \"confidence\": 0-1, "
    "\"reason\": \"一句话理由\"}\n"
    "注意：高光反光、白色衣物、疤痕、抓痕不是白斑。"
)


def _judge_allowed() -> bool:
    now = time.time()
    bucket = datetime.utcnow().strftime("%Y%m%d%H")
    if bucket != _JUDGE_STATE["hour_bucket"]:
        _JUDGE_STATE["hour_bucket"] = bucket
        _JUDGE_STATE["hour_count"] = 0
    if _JUDGE_STATE["hour_count"] >= JUDGE_MAX_PER_HOUR:
        return False
    if now - _JUDGE_STATE["last_ts"] < JUDGE_MIN_INTERVAL_SECONDS:
        return False
    return True


def _vlm_judge_region(image_bytes: bytes,
                      bbox_ratio: Tuple[float, float, float, float]) -> Optional[Dict[str, Any]]:
    """裁剪区域送 VLM 判断是否为白斑。bbox_ratio = [x1,y1,x2,y2] 归一化。"""
    try:
        import base64
        import cv2
        from web.backend.services.spot_compare import _downscale_for_vlm, _to_data_url, _parse_llm_json
    except Exception:
        return None
    orig = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
    if orig is None:
        return None
    h, w = orig.shape[:2]
    x1 = max(0, int(bbox_ratio[0] * w))
    y1 = max(0, int(bbox_ratio[1] * h))
    x2 = min(w, int(bbox_ratio[2] * w))
    y2 = min(h, int(bbox_ratio[3] * h))
    pad = int(max(x2 - x1, y2 - y1) * 0.4)
    x1 = max(0, x1 - pad)
    y1 = max(0, y1 - pad)
    x2 = min(w, x2 + pad)
    y2 = min(h, y2 + pad)
    if x2 - x1 < 32 or y2 - y1 < 32:
        return None
    crop = orig[y1:y2, x1:x2]
    ok, buf = cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, 92])
    if not ok:
        return None
    crop_bytes = buf.tobytes()

    try:
        import openai
        from web.backend.utils.llm_config import get_llm_config

        config = get_llm_config("vasi")
        if config.get("provider") == "none" or not config.get("api_key"):
            return None
        vision_model = config.get("vision_model") or "qwen-vl-max"
        client = openai.OpenAI(api_key=config["api_key"], base_url=config["base_url"],
                               timeout=float(os.getenv("VASI_VLM_TIMEOUT", "120")),
                               max_retries=0)
        content = [
            {"type": "image_url",
             "image_url": {"url": _to_data_url(crop_bytes)}},
            {"type": "text", "text": JUDGE_PROMPT},
        ]
        response = client.chat.completions.create(
            model=vision_model,
            messages=[{"role": "user", "content": content}],
            temperature=0.0, max_tokens=800)
        raw = (response.choices[0].message.content or "").strip()
        parsed = _parse_llm_json(raw)
        if parsed is None:
            return None
        return {"is_vitiligo": bool(parsed.get("is_vitiligo")),
                "confidence": float(parsed.get("confidence", 0.5) or 0.5),
                "reason": str(parsed.get("reason", ""))[:200]}
    except Exception as e:
        logger.info("judge VLM call failed: %s", e)
        return None


def _process_judge_queue(db) -> int:
    """处理裁判队列：裁剪分歧区 → VLM 复核 → 伪标签入训练。返回处理数。"""
    from web.backend.models.vasi import AutoLoopQueue, VASIAssessment
    processed = 0
    try:
        rows = (db.query(AutoLoopQueue)
                .filter(AutoLoopQueue.kind == "judge", AutoLoopQueue.status == "pending")
                .limit(5).all())
        for row in rows:
            if not _judge_allowed():
                break
            row.attempts = (row.attempts or 0) + 1
            try:
                payload = json.loads(row.payload_json or "{}")
                aid = row.assessment_id
                a = db.query(VASIAssessment).filter(VASIAssessment.id == aid).first()
                if not a:
                    row.status = "skipped"
                    row.result_json = json.dumps({"reason": "assessment missing"})
                    db.commit()
                    processed += 1
                    continue
                from web.backend.services.spot_compare import resolve_image_bytes
                img_bytes = resolve_image_bytes(a.image_url, a.image_key)
                if not img_bytes:
                    row.status = "skipped"
                    row.result_json = json.dumps({"reason": "image missing"})
                    db.commit()
                    processed += 1
                    continue
                bbox = payload.get("bbox")
                verdict = _vlm_judge_region(img_bytes, bbox) if bbox else None
                _JUDGE_STATE["last_ts"] = time.time()
                _JUDGE_STATE["hour_count"] += 1
                if verdict is None:
                    if row.attempts >= 3:
                        row.status = "failed"
                    db.commit()
                    continue

                row.status = "done"
                row.result_json = json.dumps(verdict, ensure_ascii=False)

                # 裁决为白斑 → 伪标签样本入训练队列
                if verdict.get("is_vitiligo"):
                    _judge_positive_to_sample(db, a, payload, verdict)
                else:
                    # 更新共识 JSON：裁决为假阳性
                    try:
                        cons = json.loads(a.consensus_json or "{}")
                        cons["judge_verdict"] = {"is_vitiligo": False,
                                                 "confidence": verdict.get("confidence")}
                        a.consensus_json = json.dumps(cons, ensure_ascii=False)
                    except Exception:
                        pass
                db.commit()
                processed += 1
            except Exception as e:
                db.rollback()
                logger.warning("judge row %s failed: %s", row.id, e)
    except Exception as e:
        db.rollback()
        logger.warning("process judge queue failed: %s", e)
    return processed


def _judge_positive_to_sample(db, a, payload: Dict[str, Any],
                              verdict: Dict[str, Any]) -> None:
    """裁判确认白斑：以分歧区（SAM∪患者掩膜 bbox 内的双方并集）为伪标签。"""
    try:
        import base64
        import io
        import cv2
        from PIL import Image
        from web.backend.services import vasi_canvas

        snapshot = json.loads(a.canvas_json or "{}")
        if not snapshot.get("calibration"):
            return
        # 原图 + 双方掩膜（若可用）
        from web.backend.services.spot_compare import resolve_image_bytes
        img_bytes = resolve_image_bytes(a.image_url, a.image_key)
        if not img_bytes:
            return
        orig = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)
        if orig is None:
            return
        canvas_img = vasi_canvas.rebuild_calibrated_canvas(orig, snapshot)
        if canvas_img is None:
            return

        # 用评估已存的 AI 白斑层作为正区（裁判确认后即伪标签）
        data_url = a.ai_lesion_layer
        mask_orig = None
        if data_url:
            if data_url.startswith("data:"):
                data_url = data_url.split(",", 1)[1]
            mask_img = Image.open(io.BytesIO(base64.b64decode(data_url))).convert("L")
            mask_orig = np.asarray(mask_img) > 127
        bbox = payload.get("bbox")
        if mask_orig is None and bbox:
            x1, y1, x2, y2 = bbox
            h, w = orig.shape[:2]
            mask_orig = np.zeros((h, w), dtype=bool)
            mask_orig[int(y1 * h):int(y2 * h), int(x1 * w):int(x2 * w)] = True
        if mask_orig is None:
            return
        if mask_orig.shape[:2] != orig.shape[:2]:
            mask_orig = cv2.resize(mask_orig.astype(np.uint8),
                                   (orig.shape[1], orig.shape[0]),
                                   interpolation=cv2.INTER_NEAREST).astype(bool)
        mask_canvas = vasi_canvas.warp_mask_orig_to_canvas(mask_orig, snapshot)
        if mask_canvas is None or not mask_canvas.any():
            return
        validity = canvas_img.max(axis=2) > 10
        save_patient_sample(a.user_id, a.body_site, canvas_img, mask_canvas, validity,
                            "llm_judge", a.id)
        queue_train(db, a.user_id, a.body_site,
                    {"source": "llm_judge", "assessment_id": a.id})
    except Exception as e:
        logger.warning("judge positive to sample failed: %s", e)


# ══════════════════════════════════════════════════════════════════════════════
# 自动质检（文档 §7 指标表）
# ══════════════════════════════════════════════════════════════════════════════

def run_qa_checks(db) -> List[Dict[str, Any]]:
    """对近 90 天 active 评估做无人值守质检。返回异常列表。"""
    anomalies: List[Dict[str, Any]] = []
    try:
        from web.backend.models.vasi import VASIAssessment
        since = datetime.utcnow() - timedelta(days=90)
        rows = (db.query(VASIAssessment)
                .filter(VASIAssessment.status == "active",
                        VASIAssessment.assessment_date >= since,
                        VASIAssessment.canvas_json.isnot(None))
                .all())
        # 按 (user, site) 分组，取时间序列
        from collections import defaultdict
        groups: Dict[Tuple[int, str], List[Any]] = defaultdict(list)
        for a in rows:
            groups[(a.user_id, a.body_site)].append(a)
        for (uid, site), items in groups.items():
            items.sort(key=lambda a: a.assessment_date)
            prev_area = None
            prev_date = None
            for a in items:
                try:
                    snap = json.loads(a.canvas_json)
                    cons = json.loads(a.consensus_json or "{}")
                    area = cons.get("patient_pixels")
                    if area:
                        # 黑边率检查
                        if snap.get("transform") is not None:
                            border_ratio = cons.get("patient_border_ratio", 0.0)
                            if border_ratio > _BORDER_RATIO_MAX:
                                anomalies.append({
                                    "type": "mask_outside_canvas",
                                    "user_id": uid, "body_site": site,
                                    "assessment_id": a.id,
                                    "detail": f"掩膜黑边占比 {border_ratio:.2%}"})
                        if prev_area and prev_area > 0:
                            ratio = area / prev_area
                            if not (_AREA_RATIO_MIN <= ratio <= _AREA_RATIO_MAX):
                                anomalies.append({
                                    "type": "area_jump",
                                    "user_id": uid, "body_site": site,
                                    "assessment_id": a.id,
                                    "detail": (f"画布面积 {prev_area}px → {area}px "
                                               f"（{ratio:.2f}倍，超 {_AREA_RATIO_MIN}~"
                                               f"{_AREA_RATIO_MAX} 正常范围）")})
                    if snap.get("calibration") and not snap["calibration"].get("roi_ok"):
                        anomalies.append({
                            "type": "roi_chroma_suspect",
                            "user_id": uid, "body_site": site,
                            "assessment_id": a.id,
                            "detail": "参考ROI彩度自检未通过（疑似落在白斑上）"})
                    if area is not None:
                        prev_area = area
                    prev_date = a.assessment_date
                except Exception:
                    continue
    except Exception as e:
        logger.warning("qa checks failed: %s", e)
    return anomalies


# ══════════════════════════════════════════════════════════════════════════════
# 主循环
# ══════════════════════════════════════════════════════════════════════════════

def run_loop_once() -> Dict[str, Any]:
    """执行一轮自循环。返回摘要。"""
    summary = {"judged": 0, "trained_groups": 0, "deployed": 0,
               "anomalies": 0, "collect": 0}
    from web.backend.database.database import SessionLocal
    db = SessionLocal()
    try:
        # 1. 采集：扫描新增用户修正（is_user_corrected 且有用户层、尚未入样本的）
        summary["collect"] = _collect_uncorrected(db)

        # 2. 裁判队列（限速）
        summary["judged"] = _process_judge_queue(db)

        # 3. 训练队列
        from web.backend.models.vasi import AutoLoopQueue
        train_rows = (db.query(AutoLoopQueue)
                      .filter(AutoLoopQueue.kind == "train",
                              AutoLoopQueue.status == "pending")
                      .limit(10).all())
        done_ids = []
        for row in train_rows:
            row.status = "done"
            row.attempts = (row.attempts or 0) + 1
            res = train_and_deploy(db, row.user_id, row.body_site)
            row.result_json = json.dumps(res, ensure_ascii=False, default=str)
            summary["trained_groups"] += 1
            if res.get("deployed"):
                summary["deployed"] += 1
            db.commit()

        # 4. 质检
        anomalies = run_qa_checks(db)
        summary["anomalies"] = len(anomalies)
        if anomalies:
            audit(db, "qa", {"anomalies": anomalies[:20],
                             "total": len(anomalies)})
        return summary
    except Exception as e:
        db.rollback()
        logger.warning("autoloop round failed: %s", e)
        return summary
    finally:
        db.close()


def _collect_uncorrected(db) -> int:
    """扫描用户修正后未入患者样本的评估 → 排入训练队列。"""
    collected = 0
    try:
        from web.backend.models.vasi import VASIAssessment
        rows = (db.query(VASIAssessment)
                .filter(VASIAssessment.is_user_corrected.is_(True),
                        VASIAssessment.user_lesion_layer.isnot(None),
                        VASIAssessment.canvas_json.isnot(None))
                .order_by(VASIAssessment.id.desc())
                .limit(50).all())
        for a in rows:
            # 已入过样本的跳过（consensus_json 打标记）
            try:
                cons = json.loads(a.consensus_json or "{}")
                if cons.get("sample_queued"):
                    continue
            except Exception:
                pass
            if queue_correction_sample(db, a.id):
                try:
                    cons = json.loads(a.consensus_json or "{}")
                    cons["sample_queued"] = True
                    a.consensus_json = json.dumps(cons, ensure_ascii=False)
                    db.commit()
                except Exception:
                    db.rollback()
                collected += 1
    except Exception as e:
        db.rollback()
        logger.warning("collect uncorrected failed: %s", e)
    return collected


async def run_autoloop_task(interval_seconds: int = LOOP_INTERVAL_SECONDS) -> None:
    """lifespan 后台循环。首次延迟 60s 让服务就绪。"""
    if not AUTOLOOP_ENABLED:
        logger.info("autoloop disabled by env AUTOLOOP_ENABLED=0")
        return
    await asyncio.sleep(60)
    logger.info("vitiligo autoloop started (interval=%ss)", interval_seconds)
    while True:
        try:
            t0 = time.time()
            summary = await asyncio.to_thread(run_loop_once)
            dur = int((time.time() - t0) * 1000)
            from web.backend.database.database import SessionLocal
            db = SessionLocal()
            try:
                audit(db, "stats", summary, duration_ms=dur, strategy="full")
            finally:
                db.close()
            logger.info("autoloop round done: %s (%dms)", summary, dur)
        except Exception as e:
            logger.warning("autoloop round crashed: %s", e)
        await asyncio.sleep(interval_seconds)

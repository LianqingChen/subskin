"""
白斑变化分析报告生成服务

聚合用户的图文日记、日记图片（轻量视觉分析）与 VASI 评估（深度数值），
由 AI 生成结构化指标 + 叙事文本，产出可分享的「白斑变化报告」。

第一期：对比报告（generate_comparison_report）
- 数据源优先级：VASI 深度数值 > 日记图轻量分析
- 视觉理解已在轻量分析阶段（diary_image.py）完成，此处用文本模型综合叙事
- 输出 metrics_json / narrative / insights / recommendations / trend_chart_data

第二期：周报/月报（generate_periodic_report）
- 周期窗口内多部位聚合：每部位取「周期前基线照片 → 周期末照片」
- 配对识别由 services/spot_compare.py 负责（VLM 双图对比 + CV 像素交叉验证，带缓存）
- 生成封面拼图（各部位前后对比）写入 cover_composite_url
- 数据源合并 post_images 与 vasi_assessments（按本地文件名去重）
"""

import json
import logging
import secrets
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from web.backend.database.models import SkinReport

logger = logging.getLogger(__name__)


# 部位英文 key → 中文（与 vasi.py BODY_SITE_LABELS 对齐，独立定义避免重依赖）
BODY_SITE_LABELS: Dict[str, str] = {
    "face": "面部",
    "neck": "颈部",
    "chest": "胸部",
    "abdomen": "腹部",
    "upper_back": "上背部",
    "lower_back": "下背部",
    "left_arm": "左臂",
    "right_arm": "右臂",
    "left_hand": "左手",
    "right_hand": "右手",
    "left_leg": "左腿",
    "right_leg": "右腿",
    "left_foot": "左脚",
    "right_foot": "右脚",
    "hands": "手部",
    "arms": "上肢",
    "legs": "下肢",
    "feet": "足部",
    "back": "背部",
    "other": "其他",
}


def _get_prompt_template(module_key: str, prompt_key: str, fallback: str) -> str:
    """从 DB 读取管理后台可编辑的提示词模板，失败时回退内置常量。"""
    try:
        from web.backend.database.database import SessionLocal
        from web.backend.services.llm_prompt_service import LLMPromptService

        db = SessionLocal()
        try:
            template = LLMPromptService.get_prompt(db, module_key, prompt_key)
            if template:
                return template
        finally:
            db.close()
    except Exception as e:
        logger.warning("Failed to load prompt %s/%s: %s", module_key, prompt_key, e)
    return fallback


def _site_label(body_site: Optional[str]) -> str:
    if not body_site:
        return "全身概览"
    return BODY_SITE_LABELS.get(body_site, body_site)


def _score_of(a) -> Optional[float]:
    """VASI 评分：优先 final_vasi_score（用户修正后），否则 vasi_score。"""
    if a is None:
        return None
    return a.final_vasi_score if getattr(a, "final_vasi_score", None) is not None else a.vasi_score


def _area_of(a) -> Optional[float]:
    if a is None:
        return None
    return (
        a.final_area_percentage
        if getattr(a, "final_area_percentage", None) is not None
        else a.area_percentage
    )


def _img_date(img) -> date:
    """图片的有效日期：capture_date 优先，否则 created_at。"""
    if img.capture_date:
        return img.capture_date
    if getattr(img, "created_at", None):
        return img.created_at.date() if isinstance(img.created_at, datetime) else img.created_at
    return date.today()


def _light_summary(img) -> Optional[str]:
    """从轻量分析 JSON 提取一句话摘要。"""
    if not img.visual_analysis_json:
        return None
    try:
        d = json.loads(img.visual_analysis_json)
        return d.get("summary") or d.get("change_note")
    except Exception:
        return None


def _photo_quality(image_url: Optional[str]) -> Optional[str]:
    """照片质量快速评级（good/acceptable/poor），供前端低质量角标与热力图门禁。"""
    if not image_url:
        return None
    try:
        from web.backend.services.spot_compare import resolve_image_bytes
        from web.backend.services.vasi_quality import vasi_quality_checker

        raw = resolve_image_bytes(image_url)
        if not raw:
            return None
        return vasi_quality_checker.check_all(raw).overall
    except Exception:
        return None


def _build_points(db, images) -> List[Dict[str, Any]]:
    """为每张图片构建一个数据点（合并关联的 VASI 评估）。"""
    from web.backend.models.vasi import VASIAssessment

    # 批量加载关联的 VASI 评估
    vasi_ids = {img.vasi_assessment_id for img in images if img.vasi_assessment_id}
    vasi_map: Dict[int, Any] = {}
    if vasi_ids:
        vasis = db.query(VASIAssessment).filter(VASIAssessment.id.in_(vasi_ids)).all()
        vasi_map = {v.id: v for v in vasis}

    points = []
    for img in images:
        va = vasi_map.get(img.vasi_assessment_id) if img.vasi_assessment_id else None
        points.append(
            {
                "image_id": img.id,
                "date": _img_date(img).isoformat(),
                "image_url": img.image_url,
                "body_site": img.body_site,
                "has_vasi": va is not None,
                "vasi_score": _score_of(va),
                "area_percentage": _area_of(va),
                "stage": getattr(va, "stage", None) if va else None,
                "classification": getattr(va, "classification", None) if va else None,
                "light_summary": _light_summary(img),
                "depigmentation_level": getattr(va, "depigmentation_level", None) if va else None,
                "quality": _photo_quality(img.image_url),
            }
        )
    return points


def _decide_body_site(images) -> Optional[str]:
    sites = [img.body_site for img in images if img.body_site]
    if not sites:
        return None
    # 取众数
    from collections import Counter

    return Counter(sites).most_common(1)[0][0]


def _compute_metrics(points: List[Dict[str, Any]]) -> Dict[str, Any]:
    """根据数据点计算首末对比指标与趋势。"""
    has_vasi = any(p["has_vasi"] and p["vasi_score"] is not None for p in points)
    first, last = points[0], points[-1]

    metrics: Dict[str, Any] = {
        "point_count": len(points),
        "first": first,
        "last": last,
        "has_vasi": has_vasi,
        "data_source": "vasi" if has_vasi else "light",
    }

    # 日期跨度
    try:
        d0 = date.fromisoformat(first["date"])
        d1 = date.fromisoformat(last["date"])
        metrics["date_span_days"] = max((d1 - d0).days, 0)
    except Exception:
        metrics["date_span_days"] = 0

    metrics.update({"trend": "无法可靠比较", "has_vasi": False,
                    "measurement_version": "common-roi-v1", "comparison_status": "not_comparable",
                    "vasi_change": None, "vasi_change_percent": None, "area_change": None})

    return metrics


def _trend_from_percent(change_percent: float) -> str:
    """VASI 变化百分比 → 趋势（复用 vasi.py 的 ±5% 阈值）。"""
    if abs(change_percent) < 5:
        return "稳定"
    return "好转" if change_percent < 0 else "加重"


def _infer_trend_from_light(points: List[Dict[str, Any]]) -> str:
    """无 VASI 数值时，从轻量分析摘要推断趋势。"""
    return "无法可靠比较"


def _build_trend_chart_data(points: List[Dict[str, Any]]) -> Dict[str, Any]:
    """构建前端 ECharts 趋势曲线数据。"""
    return {
        "dates": [p["date"] for p in points],
        "vasi_scores": [None for p in points],
        "area_percentages": [None for p in points],
    }


def _build_source_data(images, points, diary_ctx, treatment_ctx) -> Dict[str, Any]:
    return {
        "images": [
            {
                "id": p["image_id"],
                "date": p["date"],
                "body_site": p["body_site"],
                "has_vasi": p["has_vasi"],
                "light_summary": p.get("light_summary"),
            }
            for p in points
        ],
        "diary_context": diary_ctx,
        "treatment_events": treatment_ctx,
    }


def _collect_diary_context(db, user_id: int, d_start: date, d_end: date) -> List[Dict[str, Any]]:
    """采集周期内的帖子摘要（心情/用药/患处），作为报告上下文。

    日记合并到分享后，数据源从 DiaryEntry 切换为 Post（含 ai_extracted_json）。
    """
    from web.backend.database.models import Post

    posts = (
        db.query(Post)
        .filter(
            Post.user_id == user_id,
            Post.diary_date >= d_start,
            Post.diary_date <= d_end,
        )
        .order_by(Post.diary_date.asc())
        .limit(30)
        .all()
    )
    result = []
    for p in posts:
        extracted: Dict[str, Any] = {}
        if p.ai_extracted_json:
            try:
                extracted = json.loads(p.ai_extracted_json)
            except Exception:
                extracted = {}
        result.append(
            {
                "date": p.diary_date.isoformat() if p.diary_date else None,
                "mood": extracted.get("mood") or p.mood,
                "skin_condition": extracted.get("skin_condition"),
                "medication_taken": extracted.get("medication_taken"),
                "summary": (p.ai_summary or p.content_text or p.content or "")[:80],
            }
        )
    return result


def _collect_treatment_context(
    db, user_id: int, d_start: date, d_end: date
) -> List[Dict[str, Any]]:
    from web.backend.database.models import TreatmentEvent

    events = (
        db.query(TreatmentEvent)
        .filter(
            TreatmentEvent.user_id == user_id,
            TreatmentEvent.event_date >= d_start,
            TreatmentEvent.event_date <= d_end,
        )
        .order_by(TreatmentEvent.event_date.asc())
        .limit(30)
        .all()
    )
    return [
        {
            "date": ev.event_date.isoformat() if ev.event_date else None,
            "type": ev.event_type,
            "title": ev.title,
        }
        for ev in events
    ]


# ════════════════════════════════════════════════════════════════════════════
# 综合健康报告：心情/互动、体检、问答 数据采集（周报/月报/年报扩展）
# ════════════════════════════════════════════════════════════════════════════

_VITILIGO_RELEVANT_KEYWORDS = (
    "甲状腺", "免疫", "抗体", "肝功能", "转氨酶", "ALT", "AST",
    "谷丙", "谷草", "铜", "锌", "维生素", "25-羟", "微量元素",
)


def _period_datetime_range(d_start: date, d_end: date) -> Tuple[datetime, datetime]:
    """date 周期 → 朴素 datetime 范围（右开区间），供 DateTime 列过滤。"""
    start = datetime(d_start.year, d_start.month, d_start.day)
    end = start + timedelta(days=(d_end - d_start).days + 1)
    return start, end


def _bucket_mood(raw: Optional[str]) -> str:
    """把心情标签归一为 positive/neutral/negative。"""
    text = raw or ""
    low = text.strip().lower()
    if low in ("good", "hopeful", "positive"):
        return "positive"
    if low in ("bad", "anxious", "negative"):
        return "negative"
    if any(w in text for w in ("低落", "难过", "焦虑", "沮丧", "烦", "崩溃", "失望", "不好", "差")):
        return "negative"
    if any(w in text for w in ("坚持", "好转", "开心", "高兴", "期待", "有希望", "好")):
        return "positive"
    if any(w in text for w in ("疑问", "困惑")):
        return "neutral"
    return "neutral"


def _dominant_mood(moods: List[str]) -> str:
    if not moods:
        return "暂无"
    pos = moods.count("positive")
    neg = moods.count("negative")
    if pos > neg:
        return "积极"
    if neg > pos:
        return "低落"
    return "平稳"


def _collect_mood_social(db, user_id: int, d_start: date, d_end: date) -> Dict[str, Any]:
    """周期内分享/日记：心情分布、发帖与互动统计。"""
    from web.backend.database.models import Post, PostComment, PostLike

    start_dt, end_dt = _period_datetime_range(d_start, d_end)
    posts = (
        db.query(Post)
        .filter(
            Post.user_id == user_id,
            Post.created_at >= start_dt - timedelta(days=1),
            Post.created_at < end_dt,
        )
        .order_by(Post.created_at.desc())
        .limit(200)
        .all()
    )

    in_period = []
    for p in posts:
        d = p.diary_date if p.diary_date else (p.created_at.date() if p.created_at else None)
        if d and d_start <= d <= d_end:
            in_period.append(p)

    moods: List[str] = []
    top_content: List[str] = []
    for p in in_period:
        extracted: Dict[str, Any] = {}
        if p.ai_extracted_json:
            try:
                extracted = json.loads(p.ai_extracted_json)
            except Exception:
                extracted = {}
        raw_mood = extracted.get("mood") or p.mood
        if raw_mood:
            moods.append(_bucket_mood(raw_mood))
        snippet = (p.ai_summary or p.content_text or p.content or "").strip()
        if snippet:
            top_content.append(snippet[:60])

    post_ids = [p.id for p in in_period]
    like_received = 0
    comment_received = 0
    if post_ids:
        like_received = db.query(PostLike).filter(PostLike.post_id.in_(post_ids)).count()
        comment_received = db.query(PostComment).filter(PostComment.post_id.in_(post_ids)).count()

    return {
        "post_count": len(in_period),
        "like_received": like_received,
        "comment_received": comment_received,
        "mood_positive": moods.count("positive"),
        "mood_neutral": moods.count("neutral"),
        "mood_negative": moods.count("negative"),
        "mood_label": _dominant_mood(moods),
        "top_content": top_content[:5],
    }


def _is_vitiligo_relevant(name: str, canonical: Optional[str] = None) -> bool:
    hay = f"{name or ''} {canonical or ''}"
    return any(k in hay for k in _VITILIGO_RELEVANT_KEYWORDS)


def _overall_exam_risk(risk_counts: Dict[str, int], total: int) -> str:
    if not total:
        return "暂无"
    if risk_counts.get("critical") or risk_counts.get("high"):
        return "需关注"
    if risk_counts.get("medium"):
        return "部分异常"
    return "良好"


def _collect_exam(db, user_id: int, d_start: date, d_end: date) -> Dict[str, Any]:
    """周期内体检报告：风险分布、异常指标、白癜风相关指标。"""
    from web.backend.database.models import MedicalReport

    start_dt, end_dt = _period_datetime_range(d_start, d_end)
    reports = (
        db.query(MedicalReport)
        .filter(
            MedicalReport.user_id == user_id,
            MedicalReport.created_at >= start_dt,
            MedicalReport.created_at < end_dt,
        )
        .order_by(MedicalReport.created_at.desc())
        .all()
    )

    risk_counts: Dict[str, int] = {"low": 0, "medium": 0, "high": 0, "critical": 0}
    abnormal: List[Dict[str, Any]] = []
    relevant: List[str] = []
    summaries: List[str] = []
    for r in reports:
        data = r.interpretation_json
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except Exception:
                data = {}
        if not isinstance(data, dict):
            data = {}
        risk = str(data.get("risk_level") or "low").lower()
        if risk not in risk_counts:
            risk = "low"
        risk_counts[risk] += 1
        if data.get("summary"):
            summaries.append(str(data["summary"])[:120])
        for item in (data.get("abnormal_items") or []):
            if not isinstance(item, dict):
                continue
            name = str(item.get("indicator_name") or item.get("name") or "").strip()
            if not name:
                continue
            abnormal.append(
                {
                    "indicator": name,
                    "value": str(item.get("value") or ""),
                    "status": str(item.get("status") or ""),
                    "interpretation": str(item.get("interpretation") or "")[:80],
                }
            )
            if _is_vitiligo_relevant(name, item.get("canonical_name")):
                relevant.append(name)

    seen = set()
    abnormal_uniq = []
    for a in abnormal:
        if a["indicator"] not in seen:
            seen.add(a["indicator"])
            abnormal_uniq.append(a)

    return {
        "report_count": len(reports),
        "risk_counts": risk_counts,
        "risk_label": _overall_exam_risk(risk_counts, len(reports)),
        "abnormal_items": abnormal_uniq[:6],
        "relevant_indicators": list(dict.fromkeys(relevant))[:6],
        "summaries": summaries[:3],
    }


def _collect_qa(db, user_id: int, d_start: date, d_end: date) -> Dict[str, Any]:
    """周期内 AI 问答：提问条数与问题列表（供 LLM 提炼高频话题）。"""
    from web.backend.database.models import Conversation, Message

    start_dt, end_dt = _period_datetime_range(d_start, d_end)
    rows = (
        db.query(Message)
        .join(Conversation, Conversation.conversation_id == Message.conversation_id)
        .filter(
            Conversation.user_id == user_id,
            Message.role == "user",
            Message.created_at >= start_dt,
            Message.created_at < end_dt,
        )
        .order_by(Message.created_at.asc())
        .limit(300)
        .all()
    )
    questions = [m.content.strip() for m in rows if m.content and m.content.strip()]
    return {"question_count": len(questions), "questions": questions[:50]}


# ════════════════════════════════════════════════════════════════════════════
# 对比报告：客观变化摘要 + 图对配准产物
# 设计原则（2026-08-30 重构）：对比报告不生成 AI 长文/洞察/建议——
# 只输出客观事实（数字 + 复色迹象），让用户自己看图得出结论，
# 避免"非医生身份"的解读误导用户与合规风险。
# ════════════════════════════════════════════════════════════════════════════


def _build_change_summary(points: List[Dict[str, Any]], metrics: Dict[str, Any]) -> List[str]:
    """客观变化摘要：每条一句话，只陈述数字与观察事实，不做解读、不给建议。"""
    pm = metrics.get("pair_metrics") or {}
    if pm.get("comparison_status") != "measured":
        return [pm.get("capture_note") or "缺少可比较的同位置照片，请按同一视角补拍"]
    lines = [pm.get("summary") or "仅比较照片共同可见范围"]
    size = pm.get("size_change_percent")
    if isinstance(size, (int, float)):
        lines.append(f"共同范围内相对面积变化：{size:+.1f}%（非全身面积）")
    if pm.get("color_reason"):
        lines.append(pm["color_reason"])
    return lines


def _save_aligned_pair(
    user_id: int,
    image_bytes_a,
    image_bytes_b,
    lesion_mask_a=None,
    lesion_mask_b=None,
) -> Optional[Dict[str, Any]]:
    """为图对生成像素级配准产物（配准后图 + 白斑变化热力图），返回 metrics 片段。

    热力图为白斑掩膜差分（绿=复色/缩小，红=扩大/新发）；门禁不通过时
    只返回配准图与 note，不出热力图。
    """
    try:
        from web.backend.services.photo_align import align_and_diff

        res = align_and_diff(image_bytes_a, image_bytes_b, lesion_mask_a, lesion_mask_b)
        out: Dict[str, Any] = {
            "aligned": bool(res.get("aligned")),
            "inlier_count": res.get("inlier_count"),
            "scale": res.get("scale"),
            "note": res.get("note"),
        }
        if res.get("classes") is not None:
            out["classes"] = res.get("classes")
        out_dir = Path("data/uploads/reports")
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = int(datetime.utcnow().timestamp())
        if res.get("warped") is not None:
            name = f"{user_id}_align_{ts}_{secrets.token_hex(4)}.jpg"
            res["warped"].save(out_dir / name, format="JPEG", quality=90)
            out["aligned_after_url"] = f"/uploads/reports/{name}"
        if res.get("heatmap") is not None:
            name = f"{user_id}_diff_{ts}_{secrets.token_hex(4)}.jpg"
            res["heatmap"].save(out_dir / name, format="JPEG", quality=92)
            out["heatmap_url"] = f"/uploads/reports/{name}"
        return out
    except Exception:
        logger.warning("skin_report: 配准对比产物生成失败", exc_info=True)
        return None


def _lesion_mask_from_layer(layer: Optional[str]) -> Optional["np.ndarray"]:
    """测评分割层（PNG data URL）→ bool 掩膜（原图分辨率）。"""
    if not layer:
        return None
    try:
        import base64
        import io

        import numpy as np
        from PIL import Image

        payload = layer.split(",", 1)[1] if layer.startswith("data:") else layer
        img = Image.open(io.BytesIO(base64.b64decode(payload))).convert("L")
        return np.asarray(img) > 127
    except Exception:
        return None


def _lesion_masks_for_images(db, images) -> Dict[int, Any]:
    """vasi_assessment_id → 白斑掩膜（用户修正层优先，AI 层兜底）。

    变化对比直接建立在测评产物之上（同一套分割标准）。
    """
    from web.backend.models.vasi import VASIAssessment

    ids = {img.vasi_assessment_id for img in images if getattr(img, "vasi_assessment_id", None)}
    out: Dict[int, Any] = {}
    if not ids:
        return out
    try:
        rows = db.query(VASIAssessment).filter(VASIAssessment.id.in_(ids)).all()
    except Exception:
        return out
    for va in rows:
        mask = _lesion_mask_from_layer(getattr(va, "user_lesion_layer", None)) or _lesion_mask_from_layer(
            getattr(va, "ai_lesion_layer", None)
        )
        if mask is not None:
            out[va.id] = mask
    return out


class _VasiPhotoRecord:
    """VASI 评估记录 → 仿 PostImage 的对比点外壳。

    对比报告管线（_build_points / 配准 / 时间轴）以 PostImage 属性为接口；
    评估记录路径（测评页多选历史评估生成对比报告）通过本类复用同一管线，
    refs 用 va:{id}（spot_compare 可利用画布快照与掩膜层证据）。
    """

    def __init__(self, va):
        d = va.assessment_date
        if isinstance(d, datetime):
            d = d.date()
        self.id = va.id
        self.image_url = va.image_url
        self.body_site = va.body_site
        self.capture_date = d
        self.created_at = None
        self.order = 0
        self.vasi_assessment_id = va.id
        self.visual_analysis_json = None
        self.user_id = va.user_id


def generate_comparison_report(
    db,
    user_id: int,
    image_ids: Optional[List[int]] = None,
    body_site: Optional[str] = None,
    profile_id: Optional[int] = None,
    report_row: Optional[Any] = None,
    vasi_ids: Optional[List[int]] = None,
):
    """生成对比报告（第一期核心）。

    Args:
        db: Session
        user_id: 用户ID
        image_ids: 选中的 PostImage id 列表（≥2），与 vasi_ids 二选一
        body_site: 聚焦部位（可空，自动推断）
        profile_id: 患者档案ID
        report_row: 已创建的 generating 状态报告行（异步生成时复用，不新建）
        vasi_ids: 选中的 VASI 评估记录 id 列表（≥2），与 image_ids 二选一

    Returns:
        SkinReport 记录
    """
    from web.backend.database.models import PostImage, SkinReport

    # A comparison is only clinically meaningful when the photos represent the
    # same lesion/body site. When the user explicitly picks a report-level site,
    # it overrides per-photo labels; otherwise two different labelled sites must
    # not be silently merged into a single trend.
    if vasi_ids:
        # 评估记录路径：历史 VASI 评估直接作为对比点
        from web.backend.models.vasi import VASIAssessment

        if len(vasi_ids) < 2:
            raise ValueError("对比报告至少需要选择 2 条评估记录")
        vasis = (
            db.query(VASIAssessment)
            .filter(VASIAssessment.id.in_(vasi_ids), VASIAssessment.user_id == user_id)
            .all()
        )
        if len(vasis) < 2:
            raise ValueError("未能找到足够的有效评估记录（至少 2 条）")
        if not body_site:
            labelled_sites = {str(v.body_site).strip() for v in vasis if v.body_site}
            if len(labelled_sites) > 1:
                raise ValueError("请选择同一部位的评估记录生成对比报告")
        images = sorted(
            (_VasiPhotoRecord(v) for v in vasis),
            key=lambda i: (_img_date(i), i.order or 0, i.id),
        )
        points = _build_points(db, images)
        ref_prefix = "va"
    else:
        if not image_ids or len(image_ids) < 2:
            raise ValueError("对比报告至少需要选择 2 张照片")

        if not body_site:
            labelled_sites = {
                str(img.body_site).strip()
                for img in db.query(PostImage.body_site)
                .filter(PostImage.id.in_(image_ids), PostImage.user_id == user_id)
                .all()
                if img.body_site
            }
            if len(labelled_sites) > 1:
                raise ValueError("请选择同一部位的照片生成对比报告")

        images = (
            db.query(PostImage)
            .filter(PostImage.id.in_(image_ids), PostImage.user_id == user_id)
            .order_by(PostImage.order.asc())
            .all()
        )
        if len(images) < 2:
            raise ValueError("未能找到足够的有效照片（至少 2 张）")

        # 按日期排序（旧→新），同日期按用户调整的顺序（order）作二级排序
        images = sorted(images, key=lambda i: (_img_date(i), i.order or 0, i.id))
        points = _build_points(db, images)
        ref_prefix = "pi"

    # 推断部位
    site = body_site or _decide_body_site(images)
    site_label = _site_label(site)

    # 周期
    d_start = _img_date(images[0])
    d_end = _img_date(images[-1])

    # 指标与趋势
    metrics = _compute_metrics(points)
    trend_chart = _build_trend_chart_data(points)

    # ── 首末图对配对识别（spot_compare，结果缓存于 spot_comparisons）──
    from web.backend.services.spot_compare import resolve_image_bytes

    refs = [f"{ref_prefix}:{img.id}" for img in images]
    first_last_pair = None
    try:
        from web.backend.services.spot_compare import compare_pair

        first_last_pair = compare_pair(db, user_id, refs[0], refs[-1])
    except Exception:
        logger.warning("skin_report: 首末配对识别失败", exc_info=True)
    if first_last_pair:
        metrics["pair_metrics"] = first_last_pair.get("merged") or None
        metrics["trend"] = (metrics["pair_metrics"] or {}).get("trend", "无法可靠比较")
        metrics["comparison_status"] = (metrics["pair_metrics"] or {}).get("comparison_status", "not_comparable")

    from web.backend.services.assessment_comparison import save_comparison_preview
    metrics["pair_align"] = save_comparison_preview(db, user_id, first_last_pair)

    # 时间轴帧：日期切换器的数据源（不再生成照片堆叠图）
    metrics["timeline_frames"] = [
        {
            "image_id": p["image_id"],
            "date": p["date"],
            "image_url": p["image_url"],
            "quality": p.get("quality"),
        }
        for p in points
    ]
    # 图对引用（pair-compare 按需补算任意图对时复用）
    metrics["refs"] = refs
    # 客观变化摘要（替代原 AI 叙事/洞察/建议）
    metrics["change_summary"] = _build_change_summary(points, metrics)

    # 上下文（日记 + 治疗事件）
    diary_ctx = _collect_diary_context(db, user_id, d_start, d_end)
    treatment_ctx = _collect_treatment_context(db, user_id, d_start, d_end)
    source_data = _build_source_data(images, points, diary_ctx, treatment_ctx)

    title = f"{site_label}白斑变化报告 {d_start.strftime('%m.%d')}-{d_end.strftime('%m.%d')}"

    if report_row is not None:
        # 异步生成：复用 generating 状态的行
        report = report_row
        report.title = title
        report.profile_id = profile_id
        report.period_start = d_start
        report.period_end = d_end
        report.body_site = site
        report.source_data_json = json.dumps(source_data, ensure_ascii=False)
        report.metrics_json = json.dumps(metrics, ensure_ascii=False)
        report.narrative = None
        report.insights_json = "[]"
        report.recommendations_json = "[]"
        report.trend_chart_data = json.dumps(trend_chart, ensure_ascii=False)
        report.cover_composite_url = None
        report.status = "completed"
        report.error_message = None
        db.commit()
        db.refresh(report)
    else:
        report = SkinReport(
            user_id=user_id,
            profile_id=profile_id,
            report_type="comparison",
            title=title,
            period_start=d_start,
            period_end=d_end,
            body_site=site,
            source_data_json=json.dumps(source_data, ensure_ascii=False),
            metrics_json=json.dumps(metrics, ensure_ascii=False),
            narrative=None,
            insights_json="[]",
            recommendations_json="[]",
            trend_chart_data=json.dumps(trend_chart, ensure_ascii=False),
            cover_composite_url=None,
            status="completed",
            llm_module="skin_report",
            share_token=secrets.token_urlsafe(16),
        )
        db.add(report)
        db.commit()
        db.refresh(report)
    logger.info("skin_report: 对比报告 #%s 生成完成（用户 %s）", report.id, user_id)
    return report


# ════════════════════════════════════════════════════════════════════════════
# 第二期：周报 / 月报
# ════════════════════════════════════════════════════════════════════════════

PERIODIC_REPORT_PROMPT = """你是 SubSkin 的白癜风病情分析助手。请根据用户本{period_name}的白斑追踪 + 体检 + 心情 + 问答等数据，生成一份温暖、专业、非诊断的「综合{period_name}」。

报告范围：{period}
部位概览：{sites_overview}
数据来源：{data_source}

综合数据（JSON，空列表/0 表示该期无此类数据）：
{payload}

说明：payload 含 metrics(白斑指标)、sites(分部位)、mood_social(心情与互动)、exam(体检)、qa(问答)、diary_context、treatment_events。

输出要求（严格 JSON，不要 markdown 代码块或其他文字）：
{{
  "headline": "6-16字亮点标题。优先突出最正面的变化（复色/心情变好/体检改善）；无突出变化时客观描述坚持情况",
  "narrative": "150-300字综合概述，用'你'称呼，语气温暖",
  "narrative_sections": [
    {{"kind":"skin|mood|exam|social|qa","title":"章节小标题(6-10字)","body":"2-4句通俗叙述，把专业数据翻译成大白话"}}
  ],
  "mood_summary": {{"mood_trend":"变好|平稳|波动","comfort_line":"一句给用户的暖心话"}},
  "qa_topics": ["本期你最关心的1-3个话题，如'饮食''复发''用药'"],
  "insights": ["3-5条洞察要点，每条一句话，基于数据，不夸大"],
  "recommendations": ["2-4条建议：遵医嘱、保持规律记录、防晒保湿、规律作息等。不给具体药物/剂量"]
}}

红线：
- comparison_status不是measured时必须说无法可靠比较；缺失值不等于稳定。局部照片面积和颜色不等于病情分期或治疗效果。
- 你不是医生，不做医疗诊断，只用"观察到""数据显示"等客观措辞。
- 只基于提供的数据，不捏造事实或数值。
- 复色（好转）判断必须有复色指数/色素岛/边缘内收等数据支撑，不得为鼓励而拔高。
- 低置信度（low_confidence）的部位结论要注明"仅供参考"。
- 体检指标只做"通俗解释+建议复查/咨询医生"，不据此下结论或推荐用药。
- 若数据来源含"日常照片估算"，需在 narrative 中提示"精确数值建议进行深度白斑评估"。
- narrative_sections 只保留数据实际存在的章节（无体检数据就别写 exam 章节）。
"""

# 周期类型 → 中文名
PERIOD_TYPE_NAMES = {"weekly": "周报", "monthly": "月报"}


def _period_window(period_type: str, anchor: date) -> tuple:
    """计算 anchor 所在的周期窗口（weekly: 周一~周日；monthly: 自然月）。"""
    if period_type == "weekly":
        start = anchor - timedelta(days=anchor.weekday())
        return start, start + timedelta(days=6)
    if period_type == "monthly":
        start = anchor.replace(day=1)
        if start.month == 12:
            nxt = start.replace(year=start.year + 1, month=1)
        else:
            nxt = start.replace(month=start.month + 1)
        return start, nxt - timedelta(days=1)
    raise ValueError("period_type 仅支持 weekly / monthly")


def _photo_point(p) -> Dict[str, Any]:
    """时间线照片 → 报告数据点（不含图片 URL 的公开安全版本另裁）。"""
    return {
        "ref": p["ref"],
        "date": p["date"].isoformat(),
        "body_site": p["body_site"],
        "has_vasi": p["has_vasi"],
        "vasi_score": p.get("vasi_score"),
        "area_percentage": p.get("area_percentage"),
        "stage": p.get("stage"),
    }


def _collect_site_sections(
    db, user_id: int, d_start: date, d_end: date, body_sites: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """按部位聚合周期数据：基线照片 + 周期内照片 → 配对识别 + VASI 点位。"""
    from web.backend.services.spot_compare import (
        compare_pair,
        iter_user_photo_timeline,
        site_label as _cmp_site_label,
    )

    timeline = iter_user_photo_timeline(db, user_id)
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for p in timeline:
        site = p["body_site"]
        if not site:
            continue
        groups.setdefault(site, []).append(p)

    sections: List[Dict[str, Any]] = []
    for site, photos in groups.items():
        if body_sites and site not in body_sites:
            continue
        in_period = [p for p in photos if d_start <= p["date"] <= d_end]
        if not in_period:
            continue
        before = [p for p in photos if p["date"] < d_start]
        baseline = before[-1] if before else None

        pair_start = baseline or in_period[0]
        pair_end = in_period[-1]
        if pair_start["date"] >= pair_end["date"]:
            continue  # 单张且无基线，无法对比

        pair_metrics = None
        try:
            pair_metrics = compare_pair(db, user_id, pair_start["ref"], pair_end["ref"])
        except Exception:
            logger.warning("skin_report: 部位 %s 配对识别失败", site, exc_info=True)
        merged = (pair_metrics or {}).get("merged") or {}

        trend = merged.get("trend") or "无法可靠比较"
        trend_source = "common-roi-v1"
        vasi_a = vasi_b = None
        vasi_points = []

        sections.append(
            {
                "body_site": site,
                "body_site_label": _cmp_site_label(site),
                "photo_count_in_period": len(in_period),
                "has_baseline": baseline is not None,
                "first": _photo_point(pair_start),
                "last": _photo_point(pair_end),
                # 前端渲染前后对比滑块用（仅所有者接口返回）
                "first_image_url": pair_start["image_url"],
                "last_image_url": pair_end["image_url"],
                "pair_metrics": merged,
                "vasi_change": round(vasi_b - vasi_a, 2) if vasi_a is not None and vasi_b is not None else None,
                "trend": trend,
                "trend_source": trend_source,
                "vasi_points": vasi_points,
            }
        )

    # 好转优先展示
    order = {"好转": 0, "稳定": 1, "加重": 2, "待评估": 3}
    sections.sort(key=lambda s: order.get(s["trend"], 9))
    return sections


def _vasi_score_of(photo: Dict[str, Any]) -> Optional[float]:
    v = photo.get("vasi_score")
    return float(v) if isinstance(v, (int, float)) else None


def _compute_periodic_metrics(sections: List[Dict[str, Any]], d_start: date, d_end: date) -> Dict[str, Any]:
    """多部位汇总指标。"""
    summary = {"improving": 0, "stable": 0, "worsening": 0, "pending": 0, "total": len(sections)}
    melanin_sites: List[str] = []
    for s in sections:
        t = s["trend"]
        if t == "面积减小":
            summary["improving"] += 1
        elif t == "面积增大":
            summary["worsening"] += 1
        elif t == "未见明确面积变化":
            summary["stable"] += 1
        else:
            summary["pending"] += 1
        pm = s.get("pair_metrics") or {}
        mc = pm.get("melanin_change")
        signals = pm.get("melanin_signals") or {}
        if (isinstance(mc, (int, float)) and mc > 0) or (
            (signals.get("follicular_repigmentation") or 0) >= 2
            or (signals.get("island_repigmentation") or 0) >= 2
            or signals.get("edge_inward")
        ):
            melanin_sites.append(s["body_site_label"])

    overall = "待评估"
    if summary["improving"] + summary["worsening"] + summary["stable"] > 0:
        if summary["improving"] > 0 and summary["improving"] >= summary["worsening"]:
            overall = "部分位置面积减小"
        elif summary["worsening"] > summary["improving"]:
            overall = "部分位置面积增大"
        else:
            overall = "未见明确面积变化"

    return {
        "measurement_version": "common-roi-v1",
        "comparison_status": "measured" if summary["pending"] < summary["total"] else "not_comparable",
        "period_days": (d_end - d_start).days + 1,
        "sites_summary": summary,
        "melanin_sites": melanin_sites,
        "site_count": len(sections),
        "trend": overall,
        "has_vasi": any(s["vasi_points"] for s in sections),
        "data_source": "vasi" if any(s["vasi_points"] for s in sections) else "light",
    }


def _build_trend_series(sections: List[Dict[str, Any]]) -> Dict[str, Any]:
    """按部位构建多序列趋势数据（兼容旧版单序列字段）。"""
    series = []
    for s in sections:
        pts = s.get("vasi_points") or []
        pm = s.get("pair_metrics") or {}
        melanin_by_date = {}
        if pm and pts and pm.get("comparison_status") == "measured":
            melanin_by_date[pts[-1]["date"]] = pm.get("melanin_score_b") if pts else None
        series.append(
            {
                "body_site": s["body_site"],
                "body_site_label": s["body_site_label"],
                "dates": [p["date"] for p in pts],
                "vasi_scores": [p.get("vasi_score") for p in pts],
                "area_percentages": [p.get("area_percentage") for p in pts],
                "melanin_scores": [
                    melanin_by_date.get(p["date"]) for p in pts
                ],
            }
        )
    return {"series": series}


# ── 封面拼图 ────────────────────────────────────────────────────────────────

_CJK_FONT_CANDIDATES = [
    "/usr/share/fonts/google-noto-cjk/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/google-noto-cjk/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/google-noto-cjk/NotoSansCJK-Medium.ttc",
    "/usr/share/fonts/google-noto-cjk/NotoSansCJK-DemiLight.ttc",
]


def _load_cjk_font(size: int):
    from PIL import ImageFont

    for path in _CJK_FONT_CANDIDATES:
        try:
            if Path(path).exists():
                return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _center_square(img):
    """裁剪为中心正方形。"""
    w, h = img.size
    m = min(w, h)
    left, top = (w - m) // 2, (h - m) // 2
    return img.crop((left, top, left + m, top + m))


def _build_cover_composite(user_id: int, title: str, sections: List[Dict[str, Any]]) -> Optional[str]:
    """生成封面拼图：各部位前后对比并排 + 日期角标，teal 主题。

    Returns:
        封面 URL（/uploads/reports/xxx.jpg），失败返回 None。
    """
    try:
        import io

        from PIL import Image, ImageDraw

        from web.backend.services.spot_compare import resolve_image_bytes
    except ImportError:
        logger.warning("skin_report: PIL 不可用，跳过封面拼图")
        return None

    usable = [s for s in sections if s.get("first_image_url") and s.get("last_image_url")][:4]
    if not usable:
        return None

    W = 1080
    CELL = 480
    GAP = 40
    MARGIN = 40
    HEADER_H = 170
    ROW_LABEL_H = 70
    CAPTION_H = 44
    ROW_H = ROW_LABEL_H + CELL + CAPTION_H
    FOOTER_H = 90

    header_rows = (len(usable) + 1) // 2  # 每行两个部位
    H = HEADER_H + header_rows * ROW_H + FOOTER_H

    canvas = Image.new("RGB", (W, H), "#f8fafc")
    draw = ImageDraw.Draw(canvas)

    # 头部 teal 渐变
    for y in range(HEADER_H):
        t = y / max(HEADER_H - 1, 1)
        r = int(15 + (20 - 15) * t)
        g = int(118 + (184 - 118) * t)
        b = int(110 + (166 - 110) * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    font_title = _load_cjk_font(44)
    font_label = _load_cjk_font(30)
    font_caption = _load_cjk_font(22)
    font_footer = _load_cjk_font(20)

    title_y = HEADER_H // 2 - 26
    draw.text((MARGIN, title_y), title, font=font_title, fill="#ffffff")
    draw.text((MARGIN, title_y + 56), "SubSkin · 小白日记", font=font_caption, fill="#ccfbf1")

    trend_colors = {"好转": "#059669", "稳定": "#d97706", "加重": "#dc2626", "待评估": "#64748b"}

    y = HEADER_H
    for i, s in enumerate(usable):
        col = i % 2
        if col == 0 and i > 0:
            y += ROW_H
        x = MARGIN + col * (CELL + GAP)

        # 部位名 + 趋势
        draw.text((x, y + 16), s["body_site_label"], font=font_label, fill="#0f172a")
        trend_text = s.get("trend", "")
        tw = draw.textlength(trend_text, font=font_caption) if hasattr(draw, "textlength") else 60
        draw.text((x + CELL - tw, y + 24), trend_text, font=font_caption, fill=trend_colors.get(trend_text, "#64748b"))

        cell_y = y + ROW_LABEL_H
        for j, (url_key, date_key, tag) in enumerate(
            [("first_image_url", "first", "前"), ("last_image_url", "last", "后")]
        ):
            cx = x + j * (CELL // 2 + GAP // 4)
            half = CELL // 2 + GAP // 4 - 4
            img_bytes = resolve_image_bytes(s[url_key])
            if not img_bytes:
                continue
            try:
                photo = Image.open(io.BytesIO(img_bytes)).convert("RGB")
                photo = _center_square(photo).resize((half, CELL))
                canvas.paste(photo, (cx, cell_y))
                d1 = draw.textlength("前" if j == 0 else "后", font=font_caption) if hasattr(draw, "textlength") else 22
                draw.rectangle([cx, cell_y, cx + d1 + 16, cell_y + 34], fill="#0f766e")
                draw.text((cx + 8, cell_y + 4), tag, font=font_caption, fill="#ffffff")
            except Exception:
                logger.warning("skin_report: 封面照片处理失败 %s", s[url_key], exc_info=True)
                continue

        # 日期标注
        first_d = (s.get("first") or {}).get("date", "")
        last_d = (s.get("last") or {}).get("date", "")
        draw.text((x, cell_y + CELL + 8), f"{first_d[5:]}  →  {last_d[5:]}", font=font_caption, fill="#475569")

    # 底部
    draw.rectangle([0, H - FOOTER_H, W, H], fill="#0f172a")
    draw.text((MARGIN, H - FOOTER_H + 34), "本文为个人病情记录，不构成医疗诊断建议", font=font_footer, fill="#94a3b8")
    brand = "SubSkin"
    bw = draw.textlength(brand, font=font_footer) if hasattr(draw, "textlength") else 80
    draw.text((W - MARGIN - bw, H - FOOTER_H + 34), brand, font=font_footer, fill="#5eead4")

    try:
        out_dir = Path("data/uploads/reports")
        out_dir.mkdir(parents=True, exist_ok=True)
        name = f"{user_id}_cover_{int(datetime.utcnow().timestamp())}_{secrets.token_hex(4)}.jpg"
        out_path = out_dir / name
        canvas.save(out_path, format="JPEG", quality=90)
        return f"/uploads/reports/{name}"
    except Exception:
        logger.warning("skin_report: 封面保存失败", exc_info=True)
        return None


def _call_periodic_llm(
    payload: Dict[str, Any], period_name: str, period: str, sites_overview: str, data_source: str, n_days: int
) -> Optional[Dict[str, Any]]:
    """调用 LLM 生成周报/月报叙事（含 headline）。"""
    try:
        import openai

        from web.backend.utils.llm_config import get_llm_config

        config = get_llm_config("skin_report")
        if config.get("provider") == "none" or not config.get("api_key"):
            return None

        client = openai.OpenAI(api_key=config["api_key"], base_url=config["base_url"])
        template = _get_prompt_template("skin_report", "periodic_report", PERIODIC_REPORT_PROMPT)
        prompt = template.format(
            period_name=period_name,
            period=period,
            sites_overview=sites_overview,
            data_source=("深度VASI评估+配对视觉对比" if data_source == "vasi" else "日常照片配对对比"),
            payload=json.dumps(payload, ensure_ascii=False)[:8000],
            n_days=n_days,
        )

        response = client.chat.completions.create(
            model=config["chat_model"],
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是 SubSkin 的白癜风病情分析助手，擅长把追踪数据写成温暖、专业、"
                        "非诊断的中文报告。严格输出 JSON。"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.5,
            max_tokens=1400,
        )
        raw = (response.choices[0].message.content or "").strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0]
        return json.loads(raw)
    except Exception:
        logger.warning("skin_report: 周报/月报 LLM 生成失败", exc_info=True)
        return None


def _fallback_periodic_narrative(
    metrics: Dict[str, Any],
    period_name: str,
    mood_social: Optional[Dict[str, Any]] = None,
    exam: Optional[Dict[str, Any]] = None,
    qa: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """LLM 不可用时的降级叙事（含综合健康报告章节）。"""
    summary = metrics.get("sites_summary", {})
    melanin = metrics.get("melanin_sites", [])
    trend = metrics.get("trend", "待评估")
    mood_social = mood_social or {}
    exam = exam or {}
    qa = qa or {}

    if metrics.get("comparison_status") != "measured":
        headline = "坚持记录，等待可比照片"
        narrative = "本期照片暂不足以可靠判断白斑变化。请保持相同位置、视角和光照继续记录。"
    elif trend == "好转":
        headline = f"{summary.get('improving', 0)}个部位好转中"
        narrative = (
            f"本期{period_name}共追踪 {summary.get('total', 0)} 个部位，"
            f"其中 {summary.get('improving', 0)} 个部位呈现好转趋势。"
        )
        if melanin:
            narrative += f"{'、'.join(melanin[:3])}观察到复色迹象，这是坚持记录与护理的回报，请继续保持。"
    elif trend == "加重":
        headline = "有部位变化，建议关注"
        narrative = (
            f"本期{period_name}共追踪 {summary.get('total', 0)} 个部位，"
            f"其中 {summary.get('worsening', 0)} 个部位出现变化，建议及时与主治医生沟通。"
        )
    elif mood_social.get("mood_label") == "积极":
        headline = "心情向好，状态不错"
        narrative = f"本期你记录了 {mood_social.get('post_count', 0)} 次，整体心情积极。保持这份好状态，继续规律记录。"
    else:
        headline = "照片观察记录"
        narrative = f"本期共同可见范围的观察结果：{trend}。照片变化不代表病情分期。"
    if metrics.get("data_source") == "light":
        narrative += "（照片条件不足时不提供定量变化。）"

    # 降级章节（仅含实际有数据的部分）
    narrative_sections = []
    if summary.get("total"):
        narrative_sections.append(
            {"kind": "skin", "title": "白斑变化", "body": f"共追踪 {summary.get('total', 0)} 个部位，趋势：{trend}。"}
        )
    if mood_social.get("post_count"):
        narrative_sections.append(
            {
                "kind": "mood",
                "title": "心情变化",
                "body": f"本期心情以{mood_social.get('mood_label', '平稳')}为主，记录 {mood_social.get('post_count', 0)} 次。",
            }
        )
    if exam.get("report_count"):
        narrative_sections.append(
            {
                "kind": "exam",
                "title": "体检要点",
                "body": f"本期上传 {exam.get('report_count', 0)} 份体检报告，整体状态：{exam.get('risk_label', '暂无')}。",
            }
        )
    if qa.get("question_count"):
        narrative_sections.append(
            {
                "kind": "qa",
                "title": "关心的话题",
                "body": f"本期你在 AI 问答提了 {qa.get('question_count', 0)} 个问题，继续关注自己的身体变化。",
            }
        )

    return {
        "headline": headline,
        "narrative": narrative,
        "narrative_sections": narrative_sections,
        "mood_summary": {
            "mood_trend": mood_social.get("mood_label", "平稳"),
            "comfort_line": "你的每一次记录，都是对自己身体的温柔关注。",
        },
        "qa_topics": [],
        "insights": [f"追踪 {metrics.get('site_count', 0)} 个部位", f"整体趋势：{trend}"],
        "recommendations": ["坚持规律记录，便于观察变化", "做好日常防晒与保湿", "定期复诊，遵医嘱"],
    }


def preview_periodic_reports(db, user_id: int) -> List[Dict[str, Any]]:
    """周报/月报快捷生成入口的可用性预览。"""
    from web.backend.services.spot_compare import iter_user_photo_timeline

    today = date.today()
    timeline = iter_user_photo_timeline(db, user_id)

    candidates: List[Dict[str, Any]] = []
    today_anchor = date(today.year, today.month, today.day)
    anchors = [
        ("weekly", today_anchor - timedelta(days=today_anchor.weekday()), "本周周报"),
        ("weekly", today_anchor - timedelta(days=today_anchor.weekday() + 7), "上周周报"),
        ("monthly", today_anchor.replace(day=1), "本月月报"),
    ]
    if today_anchor.month == 1:
        prev_month_anchor = today_anchor.replace(year=today_anchor.year - 1, month=12, day=15)
    else:
        prev_month_anchor = today_anchor.replace(month=today_anchor.month - 1, day=15)
    anchors.append(("monthly", prev_month_anchor, "上月月报"))

    for period_type, anchor, label in anchors:
        d_start, d_end = _period_window(period_type, anchor)
        in_window = [
            p for p in timeline if p["body_site"] and d_start <= p["date"] <= d_end
        ]
        photos = len(in_window)
        sites = len({p["body_site"] for p in in_window})

        # 综合健康报告：体检/问答/心情数据可用性
        exam_count = _collect_exam(db, user_id, d_start, d_end).get("report_count", 0)
        qa_count = _collect_qa(db, user_id, d_start, d_end).get("question_count", 0)
        post_count = _collect_mood_social(db, user_id, d_start, d_end).get("post_count", 0)

        existing = (
            db.query(SkinReport)
            .filter(
                SkinReport.user_id == user_id,
                SkinReport.report_type == period_type,
                SkinReport.period_start == d_start,
            )
            .first()
        )
        candidates.append(
            {
                "period_type": period_type,
                "label": label,
                "period_start": d_start.isoformat(),
                "period_end": d_end.isoformat(),
                "photo_count": photos,
                "site_count": sites,
                "exam_count": exam_count,
                "qa_count": qa_count,
                "post_count": post_count,
                "can_generate": (photos >= 1 and sites >= 1) or exam_count or qa_count or post_count,
                "existing_report_id": existing.id if existing else None,
                "existing_status": existing.status if existing else None,
            }
        )
    return candidates


def generate_periodic_report(
    db,
    user_id: int,
    period_type: str,
    anchor_date: Optional[date] = None,
    body_sites: Optional[List[str]] = None,
    profile_id: Optional[int] = None,
    force: bool = False,
    report_row: Optional[SkinReport] = None,
):
    """生成周报/月报（多部位聚合 + 配对识别 + 封面拼图 + LLM 叙事）。

    Args:
        db: Session
        user_id: 用户ID
        period_type: 'weekly' | 'monthly'
        anchor_date: 目标周期内的任意日期（默认今天）
        body_sites: 只包含指定部位（None=全部有数据的部位）
        profile_id: 患者档案ID
        force: True 时重新生成已存在的报告
        report_row: 已创建的 generating 状态报告行（后台异步模式），None 则同步创建

    Returns:
        (SkinReport, created: bool)；数据不足抛 ValueError
    """
    from web.backend.services.spot_compare import site_label as _cmp_site_label

    if period_type not in PERIOD_TYPE_NAMES:
        raise ValueError("period_type 仅支持 weekly / monthly")

    anchor = anchor_date or date.today()
    d_start, d_end = _period_window(period_type, anchor)
    period_name = PERIOD_TYPE_NAMES[period_type]

    # 幂等：同周期已有报告直接返回
    if report_row is None:
        existing = (
            db.query(SkinReport)
            .filter(
                SkinReport.user_id == user_id,
                SkinReport.report_type == period_type,
                SkinReport.period_start == d_start,
            )
            .first()
        )
        if existing and not force:
            return existing, False
        if existing and force:
            db.delete(existing)
            db.commit()

    sections = _collect_site_sections(db, user_id, d_start, d_end, body_sites)

    # 综合健康报告：心情/互动、体检、问答 数据源
    mood_social = _collect_mood_social(db, user_id, d_start, d_end)
    exam = _collect_exam(db, user_id, d_start, d_end)
    qa = _collect_qa(db, user_id, d_start, d_end)

    # 上下文（日记 + 治疗事件）
    diary_ctx = _collect_diary_context(db, user_id, d_start, d_end)
    treatment_ctx = _collect_treatment_context(db, user_id, d_start, d_end)

    has_any = (
        bool(sections)
        or bool(diary_ctx)
        or bool(treatment_ctx)
        or mood_social.get("post_count")
        or exam.get("report_count")
        or qa.get("question_count")
    )
    if not has_any:
        raise ValueError("该周期内暂无可汇总的数据，先去记录、测评或上传体检报告吧")

    metrics = _compute_periodic_metrics(sections, d_start, d_end)
    trend_chart = _build_trend_series(sections)

    # LLM 叙事
    sites_overview = "；".join(
        f"{s['body_site_label']}[{s['trend']}"
        + (
            f"，复色指数{ s['pair_metrics'].get('melanin_score_a') }→{ s['pair_metrics'].get('melanin_score_b') }"
            if (s.get("pair_metrics") or {}).get("melanin_score_b") is not None
            else ""
        )
        + (
            f"，VASI {s['vasi_change']:+.1f}"
            if s.get("vasi_change") is not None
            else ""
        )
        + "]"
        for s in sections
    )
    llm_input = {
        "metrics": {k: v for k, v in metrics.items()},
        "sites": [
            {
                "body_site_label": s["body_site_label"],
                "trend": s["trend"],
                "trend_source": s["trend_source"],
                "pair_metrics": {
                    k: v
                    for k, v in (s.get("pair_metrics") or {}).items()
                    if k in ("comparison_status", "measurement_version", "reasons", "trend_en", "change_interval_percent", "melanin_score_a", "melanin_score_b", "melanin_change", "size_change_percent", "color_change", "border_change", "confidence", "low_confidence", "summary")
                },
                "vasi_change": s.get("vasi_change"),
                "photo_count_in_period": s["photo_count_in_period"],
            }
            for s in sections
        ],
        "mood_social": mood_social,
        "exam": exam,
        "qa": {"question_count": qa["question_count"], "questions": qa["questions"][:30]},
        "diary_context": diary_ctx[:10],
        "treatment_events": treatment_ctx[:10],
    }
    llm_result = _call_periodic_llm(
        llm_input,
        period_name,
        f"{d_start.isoformat()} 至 {d_end.isoformat()}",
        sites_overview,
        metrics.get("data_source", "light"),
        metrics.get("period_days", 7),
    )
    if not llm_result or metrics.get("comparison_status") != "measured":
        llm_result = _fallback_periodic_narrative(
            metrics, period_name, mood_social=mood_social, exam=exam, qa=qa
        )

    # 标题（优先突出正面变化，其次心情/体检提醒）
    summary = metrics["sites_summary"]
    if summary["improving"] > 0:
        suffix = f" · {summary['improving']}个位置照片面积减小"
    elif metrics["melanin_sites"]:
        suffix = " · 复色进行中"
    elif summary["worsening"] > 0:
        suffix = f" · {summary['worsening']}个部位需关注"
    elif mood_social.get("mood_label") == "积极":
        suffix = " · 心情向好"
    elif exam.get("risk_label") == "需关注":
        suffix = " · 体检需关注"
    else:
        suffix = " · 观察记录"
    title = f"健康{period_name} · {d_start.strftime('%m月%d日')}-{d_end.strftime('%m月%d日')}{suffix}"
    headline = (llm_result or {}).get("headline") or suffix.lstrip(" · ")

    # 封面拼图
    cover_url = None
    try:
        cover_url = _build_cover_composite(user_id, title, sections)
    except Exception:
        logger.warning("skin_report: 封面拼图生成失败", exc_info=True)

    # 汇总 metrics（前端渲染用；图片 URL 仅所有者可见接口返回）
    metrics["headline"] = headline
    metrics["sites"] = sections
    metrics["diary_count"] = len(diary_ctx)
    metrics["treatment_count"] = len(treatment_ctx)
    # 综合健康报告新增字段
    metrics["mood"] = mood_social
    metrics["exam"] = exam
    metrics["qa"] = {"question_count": qa["question_count"], "topics": (llm_result or {}).get("qa_topics", [])}
    metrics["narrative_sections"] = (llm_result or {}).get("narrative_sections", [])
    mood_note = (llm_result or {}).get("mood_summary") or {}
    metrics["mood"]["comfort_line"] = mood_note.get("comfort_line")
    metrics["mood"]["mood_trend"] = mood_note.get("mood_trend") or mood_social.get("mood_label")

    source_data = {
        "period_type": period_type,
        "sites": [
            {
                "body_site": s["body_site"],
                "first": s["first"],
                "last": s["last"],
                "pair_metrics": s["pair_metrics"],
                "trend": s["trend"],
            }
            for s in sections
        ],
        "diary_context": diary_ctx,
        "treatment_events": treatment_ctx,
    }

    if report_row is not None:
        report = report_row
        report.title = title
        report.body_site = None
        report.source_data_json = json.dumps(source_data, ensure_ascii=False)
        report.metrics_json = json.dumps(metrics, ensure_ascii=False)
        report.narrative = (llm_result or {}).get("narrative")
        report.insights_json = json.dumps((llm_result or {}).get("insights", []), ensure_ascii=False)
        report.recommendations_json = json.dumps((llm_result or {}).get("recommendations", []), ensure_ascii=False)
        report.trend_chart_data = json.dumps(trend_chart, ensure_ascii=False)
        report.cover_composite_url = cover_url
        report.status = "completed"
        report.error_message = None
        db.commit()
        db.refresh(report)
    else:
        report = SkinReport(
            user_id=user_id,
            profile_id=profile_id,
            report_type=period_type,
            title=title,
            period_start=d_start,
            period_end=d_end,
            body_site=None,
            source_data_json=json.dumps(source_data, ensure_ascii=False),
            metrics_json=json.dumps(metrics, ensure_ascii=False),
            narrative=(llm_result or {}).get("narrative"),
            insights_json=json.dumps((llm_result or {}).get("insights", []), ensure_ascii=False),
            recommendations_json=json.dumps((llm_result or {}).get("recommendations", []), ensure_ascii=False),
            trend_chart_data=json.dumps(trend_chart, ensure_ascii=False),
            cover_composite_url=cover_url,
            status="completed",
            llm_module="skin_report",
            share_token=secrets.token_urlsafe(16),
        )
        db.add(report)
        db.commit()
        db.refresh(report)

    logger.info(
        "skin_report: %s #%s 生成完成（用户 %s，%s 个部位）",
        period_name,
        report.id,
        user_id,
        len(sections),
    )
    return report, True


# ════════════════════════════════════════════════════════════════════════════
# 历史报告提炼对比（多份报告 → 一份对比报告）
# ════════════════════════════════════════════════════════════════════════════

SYNTHESIS_PROMPT = """你是 SubSkin 的白癜风病情分析助手。用户选择了 {n} 份历史健康报告，请基于这些报告的信息，提炼并对比，生成一份「历史报告对比」。

各报告摘要（JSON，含标题/周期/趋势/叙事/洞察/心情/体检/问答）：
{payload}

输出要求（严格 JSON，不要 markdown 代码块）：
{{
  "headline": "6-16字亮点标题，概括跨期整体趋势",
  "narrative": "150-300字，对比各期白斑/心情/体检的关键变化，指出好转/稳定/需关注，语气温暖，用'你'称呼",
  "insights": ["3-5条跨期对比洞察，每条一句话"],
  "recommendations": ["2-4条建议：遵医嘱/规律记录/防晒保湿等，不给具体药物剂量"]
}}

红线：
- comparison_status不是measured时必须说无法可靠比较；缺失值不等于稳定。局部照片面积和颜色不等于病情分期或治疗效果。
- 你不是医生，不做医疗诊断，只用"观察到""数据显示"等客观措辞。
- 只基于提供的数据，不捏造事实或数值。
"""


def _call_synthesis_llm(summaries: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """调用 LLM 提炼多份历史报告为对比叙事，失败返回 None。"""
    try:
        import openai

        from web.backend.utils.llm_config import get_llm_config

        config = get_llm_config("skin_report")
        if config.get("provider") == "none" or not config.get("api_key"):
            return None

        client = openai.OpenAI(api_key=config["api_key"], base_url=config["base_url"])
        prompt = SYNTHESIS_PROMPT.format(
            n=len(summaries),
            payload=json.dumps(summaries, ensure_ascii=False)[:8000],
        )
        response = client.chat.completions.create(
            model=config["chat_model"],
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是 SubSkin 的白癜风病情分析助手，擅长把多份报告提炼成温暖、"
                        "专业、非诊断的中文对比总结。严格输出 JSON。"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.5,
            max_tokens=1400,
        )
        raw = (response.choices[0].message.content or "").strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0]
        return json.loads(raw)
    except Exception:
        logger.warning("skin_report: 历史报告对比 LLM 生成失败", exc_info=True)
        return None


def _fallback_synthesis(summaries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """LLM 不可用时的降级对比叙事。"""
    labels = []
    for s in summaries:
        label = s.get("headline") or s.get("title") or ""
        trend = s.get("trend") or ""
        labels.append(f"{label}（{trend}）" if trend else label)
    narrative = (
        f"你选择了 {len(summaries)} 份历史报告：{'、'.join(labels)}。"
        "各期数据已汇总，建议对照查看各期白斑变化趋势与心情波动。"
    )
    return {
        "headline": f"{len(summaries)}份报告对比",
        "narrative": narrative,
        "insights": [f"共对比 {len(summaries)} 份历史报告"],
        "recommendations": ["坚持规律记录，便于观察变化", "做好日常防晒与保湿", "定期复诊，遵医嘱"],
    }


def synthesize_reports(db, user_id: int, report_ids: List[int]) -> SkinReport:
    """把多份历史报告提炼对比，生成一份「历史报告对比」报告。"""
    if len(report_ids) < 2:
        raise ValueError("至少选择 2 份历史报告")

    reports = (
        db.query(SkinReport)
        .filter(SkinReport.id.in_(report_ids), SkinReport.user_id == user_id)
        .all()
    )
    if len(reports) < 2:
        raise ValueError("所选报告不存在或无权访问")

    reports = sorted(reports, key=lambda r: (r.period_start or date.min, r.created_at))

    summaries: List[Dict[str, Any]] = []
    for r in reports:
        m = json.loads(r.metrics_json or "{}") if r.metrics_json else {}
        if not isinstance(m, dict):
            m = {}
        summaries.append(
            {
                "report_id": r.id,
                "title": r.title,
                "period": f"{r.period_start.isoformat() if r.period_start else ''} ~ {r.period_end.isoformat() if r.period_end else ''}",
                "report_type": r.report_type,
                "headline": m.get("headline"),
                "trend": m.get("trend"),
                "narrative": (r.narrative or "")[:200],
                "insights": json.loads(r.insights_json or "[]") if r.insights_json else [],
                "cover_composite_url": r.cover_composite_url,
                "site_count": m.get("site_count"),
                "mood_label": (m.get("mood") or {}).get("mood_label"),
                "exam_risk": (m.get("exam") or {}).get("risk_label"),
                "qa_count": (m.get("qa") or {}).get("question_count"),
            }
        )

    llm_result = _call_synthesis_llm(summaries)
    if not llm_result:
        llm_result = _fallback_synthesis(summaries)

    d_start = min((r.period_start for r in reports if r.period_start), default=None)
    d_end = max((r.period_end for r in reports if r.period_end), default=None)
    title = f"历史报告对比 · {len(reports)}份"

    metrics = {
        "trend": "对比",
        "headline": llm_result.get("headline"),
        "sources": summaries,
    }

    report = SkinReport(
        user_id=user_id,
        report_type="synthesis",
        title=title,
        period_start=d_start,
        period_end=d_end,
        metrics_json=json.dumps(metrics, ensure_ascii=False),
        narrative=llm_result.get("narrative"),
        insights_json=json.dumps(llm_result.get("insights", []), ensure_ascii=False),
        recommendations_json=json.dumps(llm_result.get("recommendations", []), ensure_ascii=False),
        status="completed",
        llm_module="skin_report",
        share_token=secrets.token_urlsafe(16),
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    logger.info("skin_report: 历史报告对比 #%s 生成完成（用户 %s，%s 份）", report.id, user_id, len(reports))
    return report

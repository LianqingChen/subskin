"""白斑照片配对对比识别引擎 — 周报/月报的数据基元（成败关键模块）。

对同一部位的「早期照片A vs 近期照片B」做两级识别并交叉验证：
1. VLM 双图对比：视觉大模型识别复色（黑色素回归）三种经典模式、面积/颜色/边缘变化，
   输出带校准锚点的结构化指标（services 层复用 vasi 模块的视觉模型配置）。
2. CV 像素交叉验证：皮肤掩膜内低饱和高亮度区域作为白斑候选，度量
   「白斑像素/皮肤像素」比例（尺度不变）与「白斑内深色色素岛占比」，
   为 VLM 的面积/复色判断提供客观佐证；两图光线差异过大时降低置信度。

结果按图对缓存到 spot_comparisons 表（ref 形如 "pi:12" / "va:34"，
支持 post_images 与 vasi_assessments 跨表配对），同一图对永不重复调用。

设计原则：诚实优于好看 — 识别条件不足时如实标注 low_confidence，不硬编结论。
"""

import base64
import json
import hashlib
import logging
import os
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np  # 模块级：画布掩膜/轨迹函数签名注解与实现共用

logger = logging.getLogger(__name__)

_MAX_IMAGE_BYTES = 8 * 1024 * 1024  # 与 diary_image 一致
_DOWNSCALE_THRESHOLD_BYTES = 400 * 1024
_DOWNSCALE_MAX_SIDE = 1280

# 中文部位 → 标准英文 key（与 vasi.py / bodySites.ts 对齐；未知值原样保留用于分组）
_CN_TO_KEY: Dict[str, str] = {
    "面部": "face",
    "颈部": "neck",
    "手部": "hands",
    "腹部": "abdomen",
    "背部": "back",
    "上肢": "arms",
    "下肢": "legs",
    "足部": "feet",
    "其他": "other",
    "胸部": "chest",
    "上背部": "upper_back",
    "下背部": "lower_back",
    "左臂": "left_arm",
    "右臂": "right_arm",
    "左手": "left_hand",
    "右手": "right_hand",
    "左腿": "left_leg",
    "右腿": "right_leg",
    "左脚": "left_foot",
    "右脚": "right_foot",
}

_SITE_LABELS: Dict[str, str] = {
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

# 趋势中英文映射
_TREND_CN = {"improving": "好转", "stable": "稳定", "worsening": "加重"}
_TREND_EN = {v: k for k, v in _TREND_CN.items()}


PAIR_COMPARE_PROMPT = """你是 SubSkin 的白癜风图像分析助手。现有同一部位（{body_site}）的两张白斑照片：
- 照片A（{date_a}，较早）
- 照片B（{date_b}，较晚，间隔 {gap_days} 天）

请客观对比两图白斑的变化。你不是医生，不做医疗诊断，只描述"观察到"的变化。

{standard_rules}

重点识别「复色（色素回归）」的三种经典模式（请逐一仔细检查）：
- 毛囊点状复色：白斑内沿毛孔出现的针尖至米粒大小深色斑点
- 边缘内收/色素带：白斑边界由清晰锐利变模糊，或边缘出现环状色素带使白斑范围向内收缩
- 岛状复色：白斑内部出现成片色素岛并逐渐扩大、融合

复色程度评分校准锚点（0-100，与脱失分级对应）：
0=纯白无任何复色迹象（3级脱失）；20=边缘轻微色素带；40=少量点状复色散在；60=点状复色密集或出现小片色素岛；80=多个色素岛扩大融合；100=基本复色（0级，恢复正常肤色）。

面积对比方法：不要比较白斑在画面中的绝对占比（拍摄距离会变），而是估算「白斑相对画面中可见皮肤区域的比例」在两图间的变化。衣物/背景入镜比例的变化不算白斑变化。

请严格按以下 JSON 输出，不要 markdown 代码块或其他文字：
{{
  "melanin": {{
    "score_a": null,
    "score_b": null,
    "follicular_repigmentation": null,
    "island_repigmentation": null,
    "edge_inward": null,
    "note": null
  }},
  "size_change_percent": null,
  "color_change": null,
  "border_change": null,
  "trend": null,
  "confidence": null,
  "summary": null,
  "capture_note": null
}}

字段要求：
- melanin.score_a / score_b：两图各自复色程度评分（0-100 整数，无法判断为 null）
- melanin.follicular_repigmentation / island_repigmentation：照片B中该复色模式的明显度 0-3（0=无，3=非常明显），看不到为 0 而非 null
- melanin.edge_inward：照片B相对A白斑边缘是否内收/出现色素带（true/false）
- melanin.note：一句话复色判断依据
- size_change_percent：B相对A的白斑相对面积变化估算百分比，负数=缩小，正数=扩大（如 -15 表示缩小约15%）；请基于观察给出最优估算，完全无法判断时才填 null，不要为了保守填 0
- color_change：repigment(出现色素/变深) / lighter(变淡) / same(相近) / whiter(更白)
- border_change：inward(边界内收/变模糊) / outward(边界外扩/新发) / stable(稳定)
- trend 判定规则：improving 需复色信号明显（follicular 或 island ≥2，或 edge_inward，或 color_change=repigment）或 size_change_percent ≤ -10；worsening 为 size_change_percent ≥ 10 或 color_change=whiter 或 border_change=outward；其余 stable
- confidence：本次判断置信度 0-1；两图拍摄角度/距离/光线差异大时明显调低；若两图疑似同一张照片或内容几乎一致，confidence 给 0.9 以上并在 capture_note 注明
- summary：一句话总结变化（不超过40字，客观措辞）
- capture_note：两图拍摄条件差异提示（如"角度不一致，面积对比仅供参考"），无则 null
"""


# ── 部位归一化 ───────────────────────────────────────────────────────────────


def normalize_body_site(raw: Optional[str]) -> Optional[str]:
    """中文部位标签 → 英文标准 key；已是 key 或未知值则原样返回。"""
    if not raw:
        return None
    raw = raw.strip()
    if raw in _SITE_LABELS:
        return raw
    return _CN_TO_KEY.get(raw, raw)


def site_label(body_site: Optional[str]) -> str:
    if not body_site:
        return "全身概览"
    return _SITE_LABELS.get(body_site, body_site)


# ── 图片加载 ─────────────────────────────────────────────────────────────────


def resolve_image_bytes(image_url: Optional[str], image_key: Optional[str] = None) -> Optional[bytes]:
    """按优先级解析本地图片 bytes。

    支持 data URL / /api/files/serve/{bucket}/{name} / /uploads/... / image_key / 绝对路径。
    """
    if not image_url and not image_key:
        return None

    if image_url and image_url.startswith("data:"):
        try:
            _, b64 = image_url.split(",", 1)
            return base64.b64decode(b64)
        except Exception:
            return None

    candidates: List[Path] = []
    if image_url:
        u = image_url
        if u.startswith("/api/files/serve/"):
            candidates.append(Path("data/uploads") / u[len("/api/files/serve/"):].lstrip("/"))
        if u.startswith("/uploads/"):
            candidates.append(Path("data") / u.lstrip("/"))
        if u.startswith("/data/uploads/"):
            candidates.append(Path(u.lstrip("/")))
    if image_key:
        candidates.append(Path("data/uploads") / image_key.lstrip("/"))

    for p in candidates:
        try:
            if p.exists() and p.is_file():
                data = p.read_bytes()
                if data:
                    return data
        except Exception:
            continue

    # 绝对路径兜底
    for raw in (image_url, image_key):
        if raw:
            try:
                p = Path(raw)
                if p.is_absolute() and p.exists():
                    return p.read_bytes()
            except Exception:
                continue
    return None


def _detect_mime(image_bytes: bytes) -> str:
    if image_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


def _downscale_for_vlm(image_bytes: bytes) -> bytes:
    """大图降采样到最长边 1280 并重编码，统一 VLM 输入分辨率、控制成本。"""
    if len(image_bytes) <= _DOWNSCALE_THRESHOLD_BYTES:
        return image_bytes
    try:
        import io

        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes))
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        w, h = img.size
        m = max(w, h)
        if m > _DOWNSCALE_MAX_SIDE:
            scale = _DOWNSCALE_MAX_SIDE / m
            img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=88)
        return buf.getvalue()
    except Exception:
        return image_bytes


def _to_data_url(image_bytes: bytes) -> str:
    return f"data:{_detect_mime(image_bytes)};base64,{base64.b64encode(image_bytes).decode('utf-8')}"


# ── 照片引用（PostImage / VASIAssessment 统一视图） ─────────────────────────


def make_ref(source: str, record_id: int) -> str:
    return f"{source}:{record_id}"


_REF_RE = re.compile(r"^(pi|va):(\d+)$")


def load_photo_ref(db, ref: str, vasi_status: str = "active") -> Optional[Dict[str, Any]]:
    """加载照片引用的统一信息。

    Returns:
        dict: {ref, source, record_id, user_id, body_site, body_site_label,
               image_url, image_key, date: date, has_vasi, vasi_score, ...}
    """
    m = _REF_RE.match(ref or "")
    if not m:
        return None
    source, rid = m.group(1), int(m.group(2))

    if source == "pi":
        from web.backend.database.models import PostImage

        img = db.query(PostImage).filter(PostImage.id == rid).first()
        if not img:
            return None
        d = img.capture_date
        if not d and getattr(img, "created_at", None):
            d = img.created_at.date() if isinstance(img.created_at, datetime) else img.created_at
        info = {
            "ref": ref,
            "source": "post_image",
            "record_id": rid,
            "user_id": img.user_id,
            "body_site": normalize_body_site(img.body_site),
            "body_site_label": site_label(normalize_body_site(img.body_site)),
            "image_url": img.image_url,
            "image_key": None,
            "date": d or date.today(),
            "has_vasi": bool(img.vasi_assessment_id),
            "vasi_assessment_id": img.vasi_assessment_id,
        }
        # Only reuse a linked assessment of this exact owned photo, never another image's mask.
        if img.vasi_assessment_id:
            linked = load_photo_ref(db, "va:%s" % img.vasi_assessment_id, vasi_status=vasi_status)
            image_path = str(img.image_url or "").split("?", 1)[0]
            if (linked and linked["user_id"] == img.user_id and image_path
                    and image_path == str(linked.get("image_url") or "").split("?", 1)[0]):
                for key in ("measurement", "observation", "skin_layer", "ai_lesion_layer", "user_lesion_layer", "canvas_json"):
                    info[key] = linked.get(key)
        return info

    # va: VASIAssessment
    from web.backend.models.vasi import VASIAssessment

    va = db.query(VASIAssessment).filter(VASIAssessment.id == rid).first()
    if not va or (vasi_status and va.status != vasi_status):
        return None
    d = va.assessment_date
    if isinstance(d, datetime):
        d = d.date()
    score = va.final_vasi_score if getattr(va, "final_vasi_score", None) is not None else va.vasi_score
    area = (
        va.final_area_percentage
        if getattr(va, "final_area_percentage", None) is not None
        else va.area_percentage
    )
    from web.backend.services.assessment_measurement import context_for, measurement_for
    return {
        "observation": context_for(va), "measurement": measurement_for(va),
        "skin_layer": va.user_skin_layer or va.ai_skin_layer,
        "ref": ref,
        "source": "vasi",
        "record_id": rid,
        "user_id": va.user_id,
        "body_site": normalize_body_site(va.body_site),
        "body_site_label": site_label(normalize_body_site(va.body_site)),
        "image_url": va.image_url,
        "image_key": va.image_key,
        "date": d or date.today(),
        "has_vasi": True,
        "vasi_score": score,
        "area_percentage": area,
        "stage": getattr(va, "stage", None),
        "depigmentation_level": getattr(va, "depigmentation_level", None),
        # ── 全自动自循环：画布快照与掩膜层（对比追踪主证据）──
        "canvas_json": getattr(va, "canvas_json", None),
        "consensus_json": getattr(va, "consensus_json", None),
        "ai_lesion_layer": getattr(va, "ai_lesion_layer", None),
        "user_lesion_layer": getattr(va, "user_lesion_layer", None),
        "auto_finalized": bool(getattr(va, "auto_finalized", False)),
    }


def iter_user_photo_timeline(
    db, user_id: int, body_site: Optional[str] = None, include_vasi_drafts: bool = False
) -> List[Dict[str, Any]]:
    """用户全部白斑照片的统一时间线（旧→新），跨 post_images 与 vasi_assessments。

    按解析到的本地文件名去重（同一张照片可能同时存在测评记录与日记引用）。
    """
    from web.backend.database.models import PostImage
    from web.backend.models.vasi import VASIAssessment

    photos: List[Dict[str, Any]] = []

    pi_query = db.query(PostImage).filter(PostImage.user_id == user_id)
    if body_site:
        pi_query = pi_query.filter(PostImage.body_site == body_site)
    for img in pi_query.all():
        info = load_photo_ref(db, make_ref("pi", img.id))
        if info:
            photos.append(info)

    va_query = db.query(VASIAssessment).filter(VASIAssessment.user_id == user_id)
    if body_site:
        # VASI 存量数据含中文部位，需两种值都匹配
        site_cn = next((cn for cn, k in _CN_TO_KEY.items() if k == body_site), None)
        from sqlalchemy import or_

        conds = [VASIAssessment.body_site == body_site]
        if site_cn:
            conds.append(VASIAssessment.body_site == site_cn)
        va_query = va_query.filter(or_(*conds))
    if not include_vasi_drafts:
        va_query = va_query.filter(VASIAssessment.status == "active")
    for va in va_query.all():
        info = load_photo_ref(db, make_ref("va", va.id), vasi_status=va.status)
        if info:
            photos.append(info)

    # 本地文件名去重（优先保留带 VASI 数值的记录）
    def _file_key(p: Dict[str, Any]) -> Optional[str]:
        u = p.get("image_url") or ""
        if u.startswith("/api/files/serve/"):
            return u.rsplit("/", 1)[-1]
        if p.get("image_key"):
            return p["image_key"].rsplit("/", 1)[-1]
        if u.startswith("/uploads/"):
            return u.rsplit("/", 1)[-1]
        return None

    photos.sort(key=lambda p: (p["date"].toordinal(), 0 if p["has_vasi"] else 1))
    seen: set = set()
    seen_hash_by_site: Dict[str, list] = {}
    deduped: List[Dict[str, Any]] = []
    for p in photos:
        key = _file_key(p)
        if key and key in seen:
            continue
        # 同部位内感知哈希去重（同一张照片多次上传/轻微压缩差异）
        site = p["body_site"] or ""
        p_hash = perceptual_hash(resolve_image_bytes(p.get("image_url"), p.get("image_key")) or b"")
        if p_hash is not None:
            bucket = seen_hash_by_site.setdefault(site, [])
            if any(hash_distance(p_hash, h) is not None and hash_distance(p_hash, h) <= 4 for h in bucket):
                continue
            bucket.append(p_hash)
        if key:
            seen.add(key)
        deduped.append(p)
    return deduped


# ── 感知哈希（近重复照片检测） ──────────────────────────────────────────────


def perceptual_hash(image_bytes: bytes) -> Optional[int]:
    """dHash 感知哈希（64bit）。同一张照片/仅压缩差异的图片汉明距离极小。"""
    try:
        import cv2
        import numpy as np

        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
        if img is None:
            return None
        img = cv2.resize(img, (9, 8))
        bits = 0
        for i in range(8):
            for j in range(8):
                bits = (bits << 1) | (1 if img[i, j] > img[i, j + 1] else 0)
        return bits
    except Exception:
        return None


def hash_distance(h1: Optional[int], h2: Optional[int]) -> Optional[int]:
    if h1 is None or h2 is None:
        return None
    return bin(h1 ^ h2).count("1")


# ── CV 像素交叉验证 ─────────────────────────────────────────────────────────


def _cv_measure(image_bytes: bytes) -> Optional[Dict[str, float]]:
    """单图白斑像素度量（自包含实现，避免跨服务私有依赖）。

    病灶候选 = 皮肤区域内以下两条件之并（亮度按各图皮肤中位数归一化，
    部分抵消曝光差异）：
    1. 低饱和 且 明显亮于肤色（白癜风脱失区失去红色素）
    2. Cr 红度显著低于肤色中位 且 略亮于肤色

    Returns:
        {lesion_ratio, island_ratio, skin_area_ratio, skin_median_v} 或 None
    """
    try:
        import cv2
        import numpy as np
    except ImportError:
        return None

    try:
        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return None
        h, w = img.shape[:2]
        m = max(h, w)
        if m > 800:
            scale = 800 / m
            img = cv2.resize(img, (max(1, int(w * scale)), max(1, int(h * scale))))

        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        ycrcb = cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb)

        # 皮肤掩膜（与 vasi_quality 相同阈值域，HSV ∪ YCrCb）
        skin = cv2.inRange(hsv, (0, 20, 50), (25, 200, 255))
        skin2 = cv2.inRange(hsv, (160, 20, 50), (179, 200, 255))
        skin3 = cv2.inRange(ycrcb, (0, 133, 77), (255, 180, 130))
        skin_mask = cv2.bitwise_or(cv2.bitwise_or(skin, skin2), skin3)

        total = skin_mask.size
        skin_pixels = int(np.count_nonzero(skin_mask))
        if skin_pixels < total * 0.01:
            return None  # 画面内皮肤过少，度量不可靠

        v_ch = hsv[:, :, 2]
        s_ch = hsv[:, :, 1]
        cr_ch = ycrcb[:, :, 1]
        skin_v = v_ch[skin_mask > 0]
        skin_median_v = float(np.median(skin_v))
        p20_s = float(np.percentile(s_ch[skin_mask > 0], 20))
        skin_median_cr = float(np.median(cr_ch[skin_mask > 0]))

        cand_low_sat = (s_ch <= max(45.0, p20_s)) & (v_ch >= skin_median_v * 1.08)
        cand_low_cr = (cr_ch <= skin_median_cr - 6) & (v_ch >= skin_median_v * 1.05)
        lesion = ((cand_low_sat | cand_low_cr) & (skin_mask > 0)).astype(np.uint8)

        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        lesion = cv2.morphologyEx(lesion, cv2.MORPH_OPEN, kernel)
        # 去掉过小连通域（噪点）
        num, labels, stats, _ = cv2.connectedComponentsWithStats(lesion, connectivity=8)
        min_area = total * 0.0005
        clean = np.zeros_like(lesion)
        for i in range(1, num):
            if stats[i, cv2.CC_STAT_AREA] >= min_area:
                clean[labels == i] = 1
        lesion_mask = clean
        lesion_pixels = int(np.count_nonzero(lesion_mask))
        if lesion_pixels <= 0:
            return {
                "lesion_ratio": 0.0,
                "island_ratio": 0.0,
                "skin_area_ratio": round(skin_pixels / total, 4),
                "skin_median_v": skin_median_v,
            }

        # 色素岛：白斑区域内明显暗于白斑中位亮度的像素（复色信号）
        lesion_v = v_ch[lesion_mask > 0]
        lesion_median_v = float(np.median(lesion_v))
        islands = int(np.count_nonzero((lesion_v < lesion_median_v - 18) & (lesion_v < skin_median_v)))

        return {
            "lesion_ratio": round(lesion_pixels / skin_pixels, 5),
            "island_ratio": round(islands / lesion_pixels, 4),
            "skin_area_ratio": round(skin_pixels / total, 4),
            "skin_median_v": skin_median_v,
        }
    except Exception:
        logger.warning("spot_compare: CV 度量失败", exc_info=True)
        return None


# 基准图白斑占皮肤比例低于此值时，比例变化率不稳定，不作为交叉验证依据
_CV_MIN_BASE_LESION_RATIO = 0.01
# 同一病灶短期内相对面积变化的物理上限（%）：超过 ±200% 说明像素检测失效
# （如光线/角度/取景差异导致"病灶"被整体误检），必须判为不可靠，避免出现
# 1342% 这类荒谬结论。
_CV_MAX_SIZE_CHANGE = 200.0


def _cv_compare(m_a: Optional[Dict[str, float]], m_b: Optional[Dict[str, float]]) -> Optional[Dict[str, Any]]:
    """两图 CV 度量的对比派生量。"""
    if not m_a or not m_b:
        return None
    out: Dict[str, Any] = {
        "measure_a": m_a,
        "measure_b": m_b,
        "brightness_gap": round(abs(m_a["skin_median_v"] - m_b["skin_median_v"]), 1),
    }
    if m_a["lesion_ratio"] >= _CV_MIN_BASE_LESION_RATIO:
        size = (m_b["lesion_ratio"] - m_a["lesion_ratio"]) / m_a["lesion_ratio"] * 100
        if abs(size) > _CV_MAX_SIZE_CHANGE:
            out["size_change_percent"] = None  # 变化率超物理上限，判为检测失败
        else:
            out["size_change_percent"] = round(size, 1)
    else:
        out["size_change_percent"] = None  # 基准图白斑过小，比例不稳定
    out["island_ratio_change"] = round(m_b["island_ratio"] - m_a["island_ratio"], 4)
    out["lighting_mismatch"] = out["brightness_gap"] > 30
    return out


def cv_pair_change_score(db, ref_a: str, ref_b: str) -> Optional[Dict[str, Any]]:
    """像素级快速变化打分（不调用 VLM，毫秒级）。

    用于多图对比报告在候选图对中挑选「变化最大」的图对：
    白斑面积相对变化 + 白斑内色素岛比例变化加权计分。

    Returns:
        {size_change_percent, island_ratio_change, lighting_mismatch, score} 或 None（无法度量）
    """
    info_a = load_photo_ref(db, ref_a)
    info_b = load_photo_ref(db, ref_b)
    if not info_a or not info_b:
        return None
    bytes_a = resolve_image_bytes(info_a["image_url"], info_a.get("image_key"))
    bytes_b = resolve_image_bytes(info_b["image_url"], info_b.get("image_key"))
    if not bytes_a or not bytes_b:
        return None
    cv = _cv_compare(_cv_measure(bytes_a), _cv_measure(bytes_b))
    if not cv:
        return None
    size = cv.get("size_change_percent")
    island = cv.get("island_ratio_change") or 0.0
    score = abs(size) if size is not None else 0.0
    score += abs(island) * 100  # 色素岛比例变化加权（1% → 1 分）
    return {
        "size_change_percent": size,
        "island_ratio_change": island,
        "lighting_mismatch": cv.get("lighting_mismatch"),
        "score": round(score, 2),
    }


# ══════════════════════════════════════════════════════════════════════════════
# 画布主证据：对齐+校准画布上的患者掩膜面积对比 + 病灶身份追踪
# （hermes_plan 2026-08-27 §7 — 替代粗糙的未校准阈值法为主证据）
# ══════════════════════════════════════════════════════════════════════════════

_AREA_RATIO_MIN, _AREA_RATIO_MAX = 0.5, 2.0   # 文档 §7 面积连续性正常范围
_TRACK_IOU_MATCH = 0.3                        # 跨照片病灶身份匹配 IoU 阈值
_TRACK_GROW_THRESHOLD = 0.15                  # 面积变化 ±15% 视为扩大/缩小


def _photo_mask_on_canvas(db, info: Dict[str, Any], image_bytes: bytes
                          ) -> Optional[Tuple[Any, Any, Dict[str, Any]]]:
    """评估照片 → (画布白斑掩膜, 有效区, snapshot)。

    优先级：用户修正层 > AI 白斑层 > 患者模型预测。无画布快照返回 None。
    """
    try:
        import base64
        import io
        import cv2
        import numpy as np
        from PIL import Image
    except ImportError:
        return None
    snapshot = info.get("canvas_json")
    if not snapshot:
        return None
    try:
        snap = json.loads(snapshot) if isinstance(snapshot, str) else snapshot
    except Exception:
        return None
    if not snap or not snap.get("calibration"):
        return None

    orig = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
    if orig is None:
        return None

    # 掩膜层（原图坐标）
    layer = info.get("user_lesion_layer") or info.get("ai_lesion_layer")
    mask_orig = None
    if layer:
        try:
            payload = layer.split(",", 1)[1] if layer.startswith("data:") else layer
            img = Image.open(io.BytesIO(base64.b64decode(payload))).convert("L")
            mask_orig = np.asarray(img) > 127
        except Exception:
            mask_orig = None

    if mask_orig is None and snap.get("transform") is not None:
        # 患者模型预测（画布上）；画布尺寸须与训练时一致。
        # 恒等对齐快照（transform=None）无法映射模型输出，跳过。
        try:
            from web.backend.services import vasi_canvas, vasi_patient_model
            canvas_img = vasi_canvas.rebuild_calibrated_canvas(orig, snap)
            if canvas_img is not None:
                validity = canvas_img.max(axis=2) > 10
                clf = vasi_patient_model.load_model(info["user_id"], info["body_site"])
                model_meta = vasi_patient_model.load_model_meta(info["user_id"], info["body_site"])
                if (clf is not None and model_meta and model_meta.get("canvas_shape")
                        and tuple(model_meta["canvas_shape"]) != tuple(canvas_img.shape[:2])):
                    clf = None
                if clf is not None:
                    prob = vasi_patient_model.predict_canvas(clf, canvas_img, validity)
                    if prob is not None:
                        mask_c = vasi_patient_model.postprocess_canvas(
                            prob > 0.5,
                            top_hard_open_rows=(150 if snap.get("kind") == "face" else 0))
                        mask_orig = vasi_patient_model.canvas_mask_to_original(
                            mask_c, np.asarray(snap["transform"], dtype=np.float64),
                            orig.shape[:2])
        except Exception:
            mask_orig = None

    if mask_orig is None:
        return None
    if mask_orig.shape[:2] != orig.shape[:2]:
        mask_orig = cv2.resize(mask_orig.astype(np.uint8), (orig.shape[1], orig.shape[0]),
                               interpolation=cv2.INTER_NEAREST).astype(bool)

    try:
        from web.backend.services import vasi_canvas
        canvas_img = vasi_canvas.rebuild_calibrated_canvas(orig, snap)
        if canvas_img is None:
            return None
        mask_c = vasi_canvas.warp_mask_orig_to_canvas(mask_orig, snap)
        if mask_c is None:
            return None
        validity = canvas_img.max(axis=2) > 10
        return mask_c.astype(bool), validity, snap
    except Exception:
        return None


def _split_components(mask: np.ndarray, min_area: int = 150) -> List[np.ndarray]:
    if mask is None or not mask.any():
        return []
    import cv2
    import numpy as np
    num, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), 8)
    comps = []
    for i in range(1, num):
        if stats[i, cv2.CC_STAT_AREA] >= min_area:
            comps.append((labels == i))
    return comps


def _component_iou(a: np.ndarray, b: np.ndarray) -> float:
    if a.shape != b.shape:
        return 0.0
    inter = int(np.logical_and(a, b).sum())
    union = int(np.logical_or(a, b).sum())
    return inter / union if union else 0.0


def update_lesion_tracks(db, user_id: int, body_site: str, photo_ref: str,
                         photo_date, mask_canvas: np.ndarray,
                         source: str = "canvas") -> List[Dict[str, Any]]:
    """画布掩膜 → 病灶身份匹配 + 轨迹落库。返回本轮各病灶轨迹摘要。"""
    from web.backend.models.vasi import LesionTrack
    import numpy as np

    comps = _split_components(mask_canvas)
    if not comps:
        return []
    # 该患者该部位最近一次照片的病灶轨迹（身份基准）
    latest_ref = (db.query(LesionTrack)
                  .filter(LesionTrack.user_id == user_id,
                          LesionTrack.body_site == body_site,
                          LesionTrack.photo_ref != photo_ref)
                  .order_by(LesionTrack.photo_date.desc(), LesionTrack.id.desc())
                  .first())
    prev_by_key: Dict[str, LesionTrack] = {}
    if latest_ref:
        prev_date = latest_ref.photo_date
        prev_rows = (db.query(LesionTrack)
                     .filter(LesionTrack.user_id == user_id,
                             LesionTrack.body_site == body_site,
                             LesionTrack.photo_date == prev_date)
                     .all())
        prev_by_key = {r.track_key: r for r in prev_rows}

    summary: List[Dict[str, Any]] = []
    used_keys = set()
    for comp in comps:
        area_px = float(comp.sum())
        ys, xs = np.where(comp)
        cx, cy = float(xs.mean()), float(ys.mean())
        # 贪心匹配上一帧病灶
        best_key, best_iou = None, 0.0
        for key, row in prev_by_key.items():
            if key in used_keys:
                continue
            prev_mask = _track_mask_from_row(row, mask_canvas.shape)
            if prev_mask is None:
                continue
            iou = _component_iou(comp, prev_mask)
            if iou > best_iou:
                best_iou, best_key = iou, key
        if best_key is not None and best_iou >= _TRACK_IOU_MATCH:
            track_key = best_key
            prev_area = float(prev_by_key[best_key].area_canvas_px or 0.0)
            ratio = (area_px / prev_area) if prev_area > 0 else 1.0
            if ratio >= 1 + _TRACK_GROW_THRESHOLD:
                status = "grew"
            elif ratio <= 1 - _TRACK_GROW_THRESHOLD:
                status = "shrunk"
            else:
                status = "stable"
            used_keys.add(best_key)
        else:
            track_key = f"u{user_id}_s{body_site}_t{len(prev_by_key) + len(summary) + 1}"
            status = "new"
        row = LesionTrack(user_id=user_id, body_site=body_site, track_key=track_key,
                          photo_ref=photo_ref, photo_date=photo_date,
                          area_canvas_px=round(area_px, 1),
                          center_x=round(cx, 1), center_y=round(cy, 1),
                          status=status, source=source, confidence=best_iou or None)
        db.add(row)
        summary.append({"track_key": track_key, "status": status,
                        "area_canvas_px": round(area_px, 1),
                        "iou": round(best_iou, 3) if best_key else None})
    # 上一帧存在、本帧未匹配的病灶 → 判定消失（仅当本帧完整覆盖上一帧画布范围时）
    for key, row in prev_by_key.items():
        if key not in used_keys:
            db.add(LesionTrack(user_id=user_id, body_site=body_site, track_key=key,
                               photo_ref=photo_ref, photo_date=photo_date,
                               area_canvas_px=0.0, status="disappeared",
                               source=source, confidence=None))
            summary.append({"track_key": key, "status": "disappeared",
                            "area_canvas_px": 0.0, "iou": None})
    try:
        db.commit()
    except Exception:
        db.rollback()
    return summary


def _track_mask_from_row(row, shape) -> Optional[np.ndarray]:
    """由轨迹行重建掩膜（用于 IoU 匹配）。仅存储了面积与中心，用近似圆重建。"""
    import numpy as np
    if not row.area_canvas_px:
        return None
    h, w = shape[:2]
    mask = np.zeros((h, w), dtype=bool)
    r = max(3.0, float(np.sqrt(float(row.area_canvas_px) / np.pi)))
    cx = max(0, min(w - 1, int(row.center_x or w / 2)))
    cy = max(0, min(h - 1, int(row.center_y or h / 2)))
    ys, xs = np.ogrid[:h, :w]
    disk = (xs - cx) ** 2 + (ys - cy) ** 2 <= r * r
    mask[disk] = True
    return mask


def canvas_pair_metrics(db, info_a: Dict[str, Any], info_b: Dict[str, Any],
                        bytes_a: bytes, bytes_b: bytes) -> Optional[Dict[str, Any]]:
    """画布主证据：两图患者掩膜在统一画布上的归一化面积对比 + 病灶追踪。

    仅当两图均带画布快照（vasi 评估）时可算；否则返回 None（回退旧 CV）。
    Returns:
        {"size_change_percent", "area_a_px", "area_b_px", "scale_baseline_px",
         "lighting_mismatch", "tracks_a", "tracks_b"} 或 None
    """
    if not (info_a.get("canvas_json") and info_b.get("canvas_json")):
        return None
    m_a = _photo_mask_on_canvas(db, info_a, bytes_a)
    m_b = _photo_mask_on_canvas(db, info_b, bytes_b)
    if not m_a or not m_b:
        return None
    mask_a, validity_a, snap_a = m_a
    mask_b, validity_b, snap_b = m_b
    if not snap_a.get("aligned") or not snap_b.get("aligned"):
        return None
    if snap_a.get("canvas") != snap_b.get("canvas"):
        return None  # 不同画布定义（锚点被重置），不可直接比较

    common = validity_a & validity_b
    if common.sum() < 1000:
        return None
    if any(mask.any() and (mask & common).sum() / mask.sum() < 0.98 for mask in (mask_a, mask_b)):
        return None
    mask_a, mask_b = mask_a & common, mask_b & common
    area_a = float(mask_a.sum())
    area_b = float(mask_b.sum())
    baseline = snap_a.get("scale_baseline_px") or None
    norm_a = (area_a / (baseline * baseline)) if baseline else None
    norm_b = (area_b / (baseline * baseline)) if baseline else None

    size = None
    if area_a >= 300:  # 基准图病灶过小比例不稳定（对齐旧 CV 逻辑）
        size = (area_b - area_a) / area_a * 100
        if abs(size) > _CV_MAX_SIZE_CHANGE:
            size = None  # 超物理上限：判为检测失败，不硬编结论

    # 光照差异：两图参考 ROI 亮度差（文档 §2.4：校准后同位置 L* 应稳定）
    lighting_mismatch = False
    roi_l_a = (snap_a.get("calibration") or {}).get("roi_l")
    roi_l_b = (snap_b.get("calibration") or {}).get("roi_l")
    if roi_l_a is not None and roi_l_b is not None:
        lighting_mismatch = abs(roi_l_a - roi_l_b) > 8

    # 病灶身份追踪（写入 lesion_tracks）
    tracks_b = None
    try:
        update_lesion_tracks(db, info_a["user_id"], info_a["body_site"],
                             info_a["ref"], info_a["date"], mask_a,
                             source="canvas")
        tracks_b = update_lesion_tracks(db, info_b["user_id"], info_b["body_site"],
                                        info_b["ref"], info_b["date"], mask_b,
                                        source="canvas")
    except Exception:
        db.rollback()

    return {
        "size_change_percent": round(size, 1) if size is not None else None,
        "area_a_px": round(area_a, 1),
        "area_b_px": round(area_b, 1),
        "area_a_normalized": round(norm_a, 4) if norm_a is not None else None,
        "area_b_normalized": round(norm_b, 4) if norm_b is not None else None,
        "scale_baseline_px": baseline,
        "lighting_mismatch": lighting_mismatch,
        "tracks_b": tracks_b,
    }


# ── VLM 双图对比 ─────────────────────────────────────────────────────────────


def _parse_llm_json(raw: str) -> Optional[Dict[str, Any]]:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0]
    try:
        return json.loads(text)
    except Exception:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                return None
    return None


def _call_pair_vlm(
    bytes_a: bytes, bytes_b: bytes, body_site_label: str, date_a: date, date_b: date
) -> Optional[Dict[str, Any]]:
    """调用视觉大模型做双图对比，失败返回 None。"""
    try:
        import openai

        from web.backend.utils.llm_config import get_llm_config

        config = get_llm_config("vasi")
        if config.get("provider") == "none" or not config.get("api_key"):
            logger.info("spot_compare: 无可用视觉模型配置")
            return None

        vision_model = config.get("vision_model") or "qwen-vl-max"
        client = openai.OpenAI(
            api_key=config["api_key"],
            base_url=config["base_url"],
            timeout=float(os.getenv("VASI_VLM_TIMEOUT", "120")),
        )

        gap_days = max((date_b - date_a).days, 0)
        from web.backend.services.vitiligo_vision_standard import standard_rules_text

        prompt = PAIR_COMPARE_PROMPT.format(
            body_site=body_site_label,
            date_a=date_a.isoformat(),
            date_b=date_b.isoformat(),
            gap_days=gap_days,
            standard_rules=standard_rules_text(include_repigmentation_modes=True),
        )

        content = [
            {"type": "text", "text": "照片A（较早）："},
            {"type": "image_url", "image_url": {"url": _to_data_url(_downscale_for_vlm(bytes_a))}},
            {"type": "text", "text": "照片B（较晚）："},
            {"type": "image_url", "image_url": {"url": _to_data_url(_downscale_for_vlm(bytes_b))}},
            {"type": "text", "text": prompt},
        ]

        # deepseek 推理视觉模型偶发「推理耗尽 token、内容为空」，重试提高成功率
        for attempt in range(3):
            response = client.chat.completions.create(
                model=vision_model,
                messages=[{"role": "user", "content": content}],
                temperature=float(os.getenv("VASI_VLM_TEMPERATURE", "0.1")),
                # 推理 token 计入 max_tokens，需留足余量（900→3000 仍不够：2026-09-12 切回
                # DeepSeek V4.1 Flash 后实测双图对比思考消耗 ~4.7–5.8k tokens、正式输出仅 ~0.4k，
                # 3000 被思考耗尽 → finish=length 且内容为空；12000 实测 finish=stop、JSON 可解析。
                max_tokens=int(os.getenv("VASI_PAIR_VLM_MAX_TOKENS", "12000")),
            )
            choice = response.choices[0]
            raw = (choice.message.content or "").strip()
            parsed = _parse_llm_json(raw)
            if parsed is not None:
                return parsed
            logger.warning(
                "spot_compare: VLM 返回不可解析/空内容（第 %s 次，finish=%s, len=%s）",
                attempt + 1,
                choice.finish_reason,
                len(raw),
            )
            if attempt < 2:
                import time as _time

                _time.sleep(1.0)
        return None
    except Exception:
        logger.warning("spot_compare: VLM 双图对比调用失败", exc_info=True)
        return None


# ── 质量门禁 ────────────────────────────────────────────────────────────────


def _quality_factor(db, image_bytes: bytes) -> Tuple[float, str]:
    """照片质量 → 置信度系数。返回 (factor, overall)。"""
    try:
        from web.backend.services.vasi_quality import vasi_quality_checker

        report = vasi_quality_checker.check_all(image_bytes)
        factor = {"good": 1.0, "acceptable": 0.8, "poor": 0.5}.get(report.overall, 0.8)
        return factor, report.overall
    except Exception:
        return 0.8, "unknown"


# ── 结果合并 ────────────────────────────────────────────────────────────────


def _merge_results(
    vlm: Optional[Dict[str, Any]],
    cv: Optional[Dict[str, Any]],
    quality_a: Tuple[float, str],
    quality_b: Tuple[float, str],
) -> Dict[str, Any]:
    """Only validated pixel measurements may supply numeric changes."""
    evidence = (cv or {}).get("evidence") or {}
    good_quality = quality_a[1] in ("good", "acceptable") and quality_b[1] in ("good", "acceptable")
    comparable = evidence.get("status") == "measured" and good_quality
    reasons = list(evidence.get("reasons") or [])
    if not good_quality:
        reasons.append("照片质量不足，请在清晰、均匀光照下重拍")
    if not evidence:
        reasons.append("缺少通过对齐验证的像素测量，不能判断变化")
    direction = evidence.get("area_direction") if comparable else "unknown"
    labels = {"decreasing": "面积减小", "increasing": "面积增大", "uncertain": "未见明确面积变化", "unknown": "无法可靠比较"}
    trend = labels.get(direction, "无法可靠比较")
    result = {
        "measurement_version": "common-roi-v1", "comparison_status": "measured" if comparable else "not_comparable",
        "reasons": reasons, "trend": trend, "trend_en": direction or "unknown",
        "size_change_percent": evidence.get("size_change_percent") if comparable else None,
        "change_interval_percent": evidence.get("change_interval_percent") if comparable else None,
        "color_change": evidence.get("color_change") if comparable else None,
        "border_change": evidence.get("border_change") if comparable else None,
        "color_reason": evidence.get("color_reason") if comparable else "拍摄条件不可比",
        "melanin_score_a": None, "melanin_score_b": None, "melanin_change": None, "melanin_signals": {},
        "confidence": None, "low_confidence": not comparable,
        "capture_note": "；".join(reasons) or None,
        "summary": trend + "。" + ("；".join(reasons) if reasons else "仅描述本次照片共同可见区域，不代表病情分期。"),
        "evidence": evidence,
    }
    return result


def _fallback_summary(merged: Dict[str, Any]) -> str:
    trend = merged.get("trend", "待评估")
    size = merged.get("size_change_percent")
    if size is None:
        return f"白斑整体{trend}，建议保持同角度同光线拍摄以便精确对比"
    direction = "缩小" if size < 0 else ("扩大" if size > 0 else "持平")
    return f"白斑整体{trend}，面积估算约{direction}{abs(size):.0f}%"


def _as_float(v: Any) -> Optional[float]:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    return None


# ── 主入口（带缓存） ─────────────────────────────────────────────────────────


def get_cached(db, ref_a: str, ref_b: str, fingerprint: Optional[str] = None, user_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """读取缓存的配对对比结果（ref_a 为早期、ref_b 为近期）。

    旧算法版本（cv:v1/v2）的缓存自动失效——算法升级后不沿用旧结论。
    """
    from web.backend.database.models import SpotComparison

    row = (
        db.query(SpotComparison)
        .filter(SpotComparison.ref_a == ref_a, SpotComparison.ref_b == ref_b)
        .first()
    )
    if not row or row.status != "completed" or not row.metrics_json:
        return None
    mv = row.model_version or ""
    # 旧算法版本（cv:v1/v2/v3）缓存自动失效——算法/prompt 升级后不沿用旧结论。
    # dupe-shortcut（近重复短路）与 prompt 无关，继续有效。
    if mv != "common-roi-v1" or not fingerprint or row.user_id != user_id:
        return None
    try:
        metrics = json.loads(row.metrics_json)
        return metrics if metrics.get("fingerprint") == fingerprint else None
    except Exception:
        return None


def _save_comparison_cache(db, user_id: int, metrics: Dict[str, Any], model_version: str) -> None:
    """写入/覆盖图对缓存（同图对幂等：先删后插）。"""
    from web.backend.database.models import SpotComparison

    try:
        db.query(SpotComparison).filter(
            SpotComparison.ref_a == metrics["ref_a"], SpotComparison.ref_b == metrics["ref_b"]
        ).delete(synchronize_session=False)
        db.add(
            SpotComparison(
                user_id=user_id,
                ref_a=metrics["ref_a"],
                ref_b=metrics["ref_b"],
                body_site=metrics.get("body_site"),
                metrics_json=json.dumps(metrics, ensure_ascii=False),
                model_version=model_version,
                status="completed",
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.warning("spot_compare: 缓存写入失败", exc_info=True)


def compare_pair(
    db,
    user_id: int,
    ref_a: str,
    ref_b: str,
    force: bool = False,
    vasi_status: str = "active",
) -> Optional[Dict[str, Any]]:
    """对比同部位两张照片（早期 ref_a → 近期 ref_b），结果缓存。

    Args:
        db: Session
        user_id: 用户ID
        ref_a: 早期照片引用 "pi:{id}" / "va:{id}"
        ref_b: 近期照片引用
        force: True 时忽略缓存重新识别
        vasi_status: 加载 va 引用时接受的测评状态

    Returns:
        完整 metrics dict（含 vlm/cv/merged/quality/dates），失败返回 None
    """
    from web.backend.database.models import SpotComparison

    info_a = load_photo_ref(db, ref_a, vasi_status=vasi_status)
    info_b = load_photo_ref(db, ref_b, vasi_status=vasi_status)
    if not info_a or not info_b:
        logger.warning("spot_compare: 照片引用不存在 %s / %s", ref_a, ref_b)
        return None
    if info_a["user_id"] != user_id or info_b["user_id"] != user_id:
        return None
    if not info_a.get("body_site") or info_a.get("body_site") != info_b.get("body_site"):
        return None
    if info_a["date"] > info_b["date"]:
        info_a, info_b = info_b, info_a  # 保证 a 早 b 晚

    bytes_a = resolve_image_bytes(info_a["image_url"], info_a.get("image_key"))
    bytes_b = resolve_image_bytes(info_b["image_url"], info_b.get("image_key"))
    if not bytes_a or not bytes_b:
        logger.warning(
            "spot_compare: 照片文件缺失 %s(%s) / %s(%s)",
            ref_a,
            info_a["image_url"],
            ref_b,
            info_b["image_url"],
        )
        return None
    if len(bytes_a) > _MAX_IMAGE_BYTES or len(bytes_b) > _MAX_IMAGE_BYTES:
        logger.warning("spot_compare: 照片过大，跳过 %s / %s", ref_a, ref_b)
        return None

    body_site = info_a["body_site"] or info_b["body_site"]

    quality_a = _quality_factor(db, bytes_a)
    quality_b = _quality_factor(db, bytes_b)
    from web.backend.services.assessment_comparison import compare_registered_masks, unavailable
    from web.backend.services.assessment_measurement import comparison_fingerprint
    info_a["image_digest"] = hashlib.sha256(bytes_a).hexdigest()
    info_b["image_digest"] = hashlib.sha256(bytes_b).hexdigest()
    fingerprint = comparison_fingerprint(info_a, info_b)
    if not force:
        cached = get_cached(db, info_a["ref"], info_b["ref"], fingerprint, user_id)
        if cached:
            return cached
    if info_a["image_digest"] == info_b["image_digest"]:
        evidence = unavailable("两张照片内容重复，不能用于判断随时间变化")
        evidence["duplicate"] = True
    else:
        evidence = compare_registered_masks(bytes_a, bytes_b, info_a, info_b)
    # VLM is deliberately excluded from numeric measurement. A narrative may
    # explain this structured result, but must not override its availability.
    vlm = None
    cv = {"evidence": evidence}
    merged = _merge_results(vlm, cv, quality_a, quality_b)

    metrics: Dict[str, Any] = {
        "ref_a": info_a["ref"],
        "ref_b": info_b["ref"],
        "body_site": body_site,
        "body_site_label": info_a["body_site_label"],
        "dates": {
            "a": info_a["date"].isoformat(),
            "b": info_b["date"].isoformat(),
            "gap_days": max((info_b["date"] - info_a["date"]).days, 0),
        },
        "vasi": {
            "score_a": info_a.get("vasi_score"),
            "score_b": info_b.get("vasi_score"),
            "area_a": info_a.get("area_percentage"),
            "area_b": info_b.get("area_percentage"),
        },
        "quality": {"a": quality_a[1], "b": quality_b[1]},
        "vlm": vlm,
        "cv": cv,
        "merged": merged,
    }

    metrics["fingerprint"] = fingerprint
    _save_comparison_cache(db, user_id, metrics, "common-roi-v1")

    logger.info(
        "spot_compare: %s→%s (%s) trend=%s conf=%s",
        metrics["ref_a"],
        metrics["ref_b"],
        body_site,
        merged["trend"],
        merged["confidence"],
    )
    return metrics


def merge_measurement_evidence(evidence: Dict[str, Any], quality_a: Tuple[float, str], quality_b: Tuple[float, str]) -> Dict[str, Any]:
    """Public result formatter; narrative never supplies numeric measurements."""
    return _merge_results(None, {"evidence": evidence}, quality_a, quality_b)

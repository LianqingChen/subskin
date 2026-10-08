"""医评（/hospitals）服务层 — 医院目录 + 病友公开评价。

分层约束：本模块不导入 FastAPI，业务失败抛 ``exceptions.py`` 中的领域异常。
公开可见性：``status='visible'`` 且 ``moderation_status != 'blocked'``。
"""

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Sequence, Tuple

from sqlalchemy import String, case, cast, func, or_
from sqlalchemy.orm import Session

from web.backend.database.models import (
    Hospital,
    HospitalReview,
    HospitalReviewAppeal,
    HospitalReviewHelpful,
    HospitalReviewReport,
    User,
)
from web.backend.exceptions import (
    HospitalNotFoundError,
    HospitalReviewNotFoundError,
    HospitalReviewRejectedError,
)
from web.backend.models.hospital import (
    MAX_REVIEW_IMAGES,
    REVIEW_IMAGE_LABELS,
    REVIEW_TARGETS,
    ExperienceDimensionCount,
    HospitalCreate,
    HospitalRatingStats,
    HospitalResponse,
    HospitalReviewAppealCreate,
    HospitalReviewAppealResponse,
    HospitalReviewAuthor,
    HospitalReviewCreate,
    HospitalReviewImage,
    HospitalReviewResponse,
    HospitalRiskAdminItem,
    HospitalRiskAdminResponse,
    TagCount,
)
from web.backend.services.review_risk import (
    BANNED_DIMENSIONS,
    EXPERIENCE_DIMENSIONS,
    PROMOTION_TERMS,
    aggregate_delay_seconds,
    clean_experience_scores,
    dimension_distribution,
    moderation_status_for_level,
    level_for_score,
    sanitize_doctor_name,
    score_review,
)
from web.backend.services.audit import AuditLogService
from web.backend.services.content_safety import moderate_text
from web.backend.utils.pii_detect import detect_pii, redact_pii
from web.backend.utils.upload_validation import validate_image_upload

logger = logging.getLogger(__name__)

# 疗效夸大/推广用语：统一取自风控规则引擎（好评与差评同一套词库 ——
# 调研实测好大夫被拒评价中约 85% 是好评，只审差评会漏掉变相推荐位）
EXAGGERATED_WORDS = list(PROMOTION_TERMS)

# 举报原因码与自动受限阈值
REPORT_REASON_CODES = ("fake", "abuse", "privacy", "ad", "promotion", "other")
REPORT_RESTRICT_THRESHOLD = 3
# 申诉处理时限：3 个工作日（对齐同类平台商户评价申诉规则）
APPEAL_DUE_WORKING_DAYS = 3
# 申诉人身份
APPEAL_CLAIMANT_TYPES = ("hospital", "doctor", "author", "other")

MAX_RATINGS = 6
MAX_TAGS = 8
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 凭证图单张上限 5MB
MAX_TAG_LENGTH = 20

# 城市中心坐标（非院区导航坐标）— 与前端 data/hospitals.ts 的 HOSPITAL_CITIES 一致
CITY_CENTERS: Dict[str, Tuple[float, float]] = {
    "北京": (39.9042, 116.4074),
    "上海": (31.2304, 121.4737),
    "南京": (32.0603, 118.7969),
    "成都": (30.5728, 104.0668),
    "西安": (34.3416, 108.9398),
    "广州": (23.1291, 113.2644),
}

# 官方来源目录（种子数据，与 web/app/src/data/hospitals.ts 的 slug 一致）
OFFICIAL_HOSPITALS: List[dict] = [
    {"slug": "pumch", "name": "北京协和医院", "province": "北京", "city": "北京", "department": "皮肤科", "kind": "综合医院", "features": ["皮肤科诊疗"], "summary": "官方皮肤科医师介绍列有白癜风诊疗方向。请在官方渠道核对院区及普通、专病或专家门诊。", "source": "https://www.pumch.cn/department_ims/dsearchs/dockerinfo/__techang__/__keshiname__/__title__/1%C3%9F%27/13.html"},
    {"slug": "huashan", "name": "复旦大学附属华山医院", "province": "上海", "city": "上海", "department": "皮肤科", "kind": "综合医院", "features": ["白癜风专病门诊", "皮肤外科"], "summary": "官方科室介绍列有白癜风专病门诊及相关皮肤外科诊疗。具体适用方案需经面诊评估。", "source": "https://www.huashan.org.cn/xueke/detail/12.html"},
    {"slug": "pumcderm", "name": "中国医学科学院皮肤病医院", "province": "江苏", "city": "南京", "department": "皮肤内科", "kind": "皮肤病专科", "features": ["皮肤科诊疗"], "summary": "官方皮肤内科介绍列有白癜风的基础与临床诊疗研究。就诊科室及排班以医院发布为准。", "source": "https://www.pumcderm.net/list/92.html"},
    {"slug": "westchina", "name": "四川大学华西医院", "province": "四川", "city": "成都", "department": "皮肤性病科", "kind": "综合医院", "features": ["白癜风诊疗组", "光疗中心"], "summary": "官方科室介绍列有白癜风专病研究诊疗组、光疗中心和皮肤外科等服务。", "source": "https://www.wchscu.cn/department_pfxbk.html"},
    {"slug": "xjtu1", "name": "西安交通大学第一附属医院", "province": "陕西", "city": "西安", "department": "皮肤科", "kind": "综合医院", "features": ["窄谱UVB", "308准分子光"], "summary": "官方科室介绍列有用于白癜风诊疗的窄谱中波紫外线、308准分子光设备。当前可用情况请向科室确认。", "source": "https://www.dyyy.xjtu.edu.cn/lmby/ksdh_bf/nkxt/pfk.htm"},
    {"slug": "gz12", "name": "广州市第十二人民医院", "province": "广东", "city": "广州", "department": "皮肤科", "kind": "综合医院", "features": ["皮肤科诊疗"], "summary": "官方皮肤科介绍列有白癜风相关诊疗服务。治疗方式和就诊安排以科室评估及最新公告为准。", "source": "https://www.gz12hospital.cn/zk/mz/pf/"},
    {"slug": "yueyang", "name": "上海中医药大学附属岳阳中西医结合医院", "province": "上海", "city": "上海", "department": "皮肤科", "kind": "综合医院", "features": ["白癜风专病门诊", "中西医结合"], "summary": "医院官方健康教育页面列有皮肤科白癜风专病门诊。具体出诊院区及安排需在官方渠道核对。", "source": "https://www.shyueyanghospital.com/Html/News/Articles/16097.html"},
]

_CHECKED_AT = "2026-09-10"


def seed_official_hospitals(db: Session) -> int:
    """幂等写入官方目录：按 slug 判重，已存在则保留（不覆盖人工/病友后续补充）。"""
    existing = {slug for (slug,) in db.query(Hospital.slug).all()}
    created = 0
    for item in OFFICIAL_HOSPITALS:
        if item["slug"] in existing:
            continue
        center = CITY_CENTERS.get(item["city"])
        db.add(Hospital(
            slug=item["slug"], name=item["name"], province=item["province"], city=item["city"],
            department=item["department"], kind=item["kind"], features=item["features"],
            summary=item["summary"], source=item["source"], checked_at=_CHECKED_AT,
            origin="official", status="visible",
            lat=center[0] if center else None, lng=center[1] if center else None,
        ))
        created += 1
    if created:
        db.commit()
        logger.info("Seeded %s official hospitals", created)
    return created


# ── 统计聚合 ──

def _stats_for(db: Session, hospital_ids: Sequence[int]) -> Dict[int, HospitalRatingStats]:
    """一次性聚合一批医院的评价统计（避免逐院查询）。"""
    stats: Dict[int, HospitalRatingStats] = {hid: HospitalRatingStats() for hid in hospital_ids}
    if not hospital_ids:
        return stats
    # 聚合口径（v3）：只统计 approved/flagged（restricted 不进聚合，仅公开可见），
    # 且必须已过「聚合冷处理」窗口 —— 给人工审核留时间，也抑制瞬时组织化刷评。
    # 注意：冷处理只延迟聚合，**不延迟发布**（发布后立即可见）。
    now = _utcnow_naive()
    rows = (
        db.query(
            HospitalReview.hospital_id, HospitalReview.target, HospitalReview.ratings,
            HospitalReview.experience_scores, HospitalReview.tags,
        )
        .filter(
            HospitalReview.hospital_id.in_(list(hospital_ids)),
            HospitalReview.status == "visible",
            HospitalReview.moderation_status.in_(("approved", "flagged")),
            or_(HospitalReview.aggregate_after.is_(None), HospitalReview.aggregate_after <= now),
        )
        .all()
    )
    scores: Dict[int, List[float]] = {}
    tag_counts: Dict[int, Dict[str, int]] = {}
    dim_rows: Dict[int, List[dict]] = {}
    for hospital_id, target, ratings, experience_scores, tags in rows:
        item = stats.get(hospital_id)
        if item is None:
            continue
        item.review_count += 1
        item.targets[target] = item.targets.get(target, 0) + 1
        if target == "doctor":
            item.doctor_review_count += 1
        elif target == "treatment":
            item.treatment_review_count += 1
        if isinstance(tags, list):
            for tag in tags:
                label = _clean_text(str(tag))[:MAX_TAG_LENGTH]
                if label:
                    bucket = tag_counts.setdefault(hospital_id, {})
                    bucket[label] = bucket.get(label, 0) + 1
        if isinstance(ratings, dict):
            for value in ratings.values():
                try:
                    score = float(value)
                except (TypeError, ValueError):
                    continue
                if 1 <= score <= 5:
                    scores.setdefault(hospital_id, []).append(score)
        dim_rows.setdefault(hospital_id, []).append(experience_scores)
    for hospital_id, values in scores.items():
        if values:
            stats[hospital_id].rating_count = len(values)
            # 保留字段以兼容既有数据，但 v3 起前端不再展示、也不用于任何排序
            stats[hospital_id].rating_avg = round(sum(values) / len(values), 1)
    for hospital_id, counts in tag_counts.items():
        stats[hospital_id].top_tags = _top_tags(counts)
    for hospital_id, items in dim_rows.items():
        stats[hospital_id].dimension_distribution = [
            ExperienceDimensionCount(**item) for item in dimension_distribution(items)
        ]
    return stats


def _utcnow_naive() -> datetime:
    """与 ``models._utcnow`` 一致的 naive UTC，用于数据库时间比较。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _top_tags(counts: Dict[str, int], limit: int = 8) -> List[TagCount]:
    """病友常提到的标签（中性聚合，只做展示，不做排名）。"""
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]
    return [TagCount(tag=tag, count=count) for tag, count in ordered]


def _to_response(hospital: Hospital, stats: Optional[HospitalRatingStats]) -> HospitalResponse:
    return HospitalResponse(
        id=hospital.id, slug=hospital.slug, name=hospital.name, province=hospital.province,
        city=hospital.city, district=hospital.district, address=hospital.address,
        department=hospital.department, kind=hospital.kind,
        features=list(hospital.features or []), summary=hospital.summary, source=hospital.source,
        lat=hospital.lat, lng=hospital.lng, checked_at=hospital.checked_at,
        origin=hospital.origin, status=hospital.status,
        created_at=hospital.created_at, updated_at=hospital.updated_at,
        stats=stats or HospitalRatingStats(),
    )


# ── 目录查询 ──

def list_hospitals(
    db: Session,
    province: Optional[str] = None,
    city: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = 500,
) -> List[HospitalResponse]:
    query = db.query(Hospital).filter(Hospital.status == "visible")
    if province:
        query = query.filter(Hospital.province == province)
    if city:
        query = query.filter(Hospital.city == city)
    if q:
        words = [w for w in re.split(r"\s+", q.strip().lower()) if w]
        for word in words[:5]:
            like = f"%{word}%"
            query = query.filter(or_(
                func.lower(Hospital.name).like(like),
                func.lower(Hospital.province).like(like),
                func.lower(Hospital.city).like(like),
                func.lower(func.coalesce(Hospital.district, "")).like(like),
                func.lower(func.coalesce(Hospital.address, "")).like(like),
                func.lower(func.coalesce(Hospital.department, "")).like(like),
                # 诊疗服务与简介也参与搜索（如「光疗」「308」）
                func.lower(func.coalesce(cast(Hospital.features, String), "")).like(like),
                func.lower(func.coalesce(Hospital.summary, "")).like(like),
            ))
    hospitals = query.order_by(Hospital.origin.desc(), Hospital.province, Hospital.city, Hospital.id).limit(limit).all()
    stats = _stats_for(db, [h.id for h in hospitals])
    return [_to_response(h, stats.get(h.id)) for h in hospitals]


def get_hospital_by_ident(db: Session, ident: str, include_hidden: bool = False) -> Hospital:
    query = db.query(Hospital)
    if not include_hidden:
        query = query.filter(Hospital.status == "visible")
    hospital = None
    if str(ident).isdigit():
        hospital = query.filter(Hospital.id == int(ident)).first()
    if hospital is None:
        hospital = query.filter(Hospital.slug == str(ident)).first()
    if hospital is None:
        raise HospitalNotFoundError()
    return hospital


def get_hospital_response(db: Session, ident: str, include_hidden: bool = False) -> HospitalResponse:
    hospital = get_hospital_by_ident(db, ident, include_hidden=include_hidden)
    return _to_response(hospital, _stats_for(db, [hospital.id]).get(hospital.id))


def create_hospital(db: Session, user_id: int, payload: HospitalCreate) -> HospitalResponse:
    """病友补充医院 —— 立即可见但明确标注「病友补充·待核实」（origin=community）。"""
    name = _clean_text(payload.name)
    if len(name) < 2:
        raise HospitalReviewRejectedError("请填写医院全称")
    pii_types = detect_pii("\n".join([
        name, payload.district or "", payload.address or "", payload.department or "", payload.note or "",
    ]))
    address, note = payload.address, payload.note
    if pii_types and not payload.confirm_no_pii:
        name, _ = redact_pii(name)
        if address:
            address, _ = redact_pii(address)
        if note:
            note, _ = redact_pii(note)
        logger.info("Hospital PII auto-redacted: user=%s types=%s", user_id, pii_types)

    slug_base = _slugify(name) or f"hospital-{user_id}"
    slug = slug_base
    suffix = 1
    while db.query(Hospital.id).filter(Hospital.slug == slug).first() is not None:
        suffix += 1
        slug = f"{slug_base}-{suffix}"

    hospital = Hospital(
        slug=slug, name=name, province=_clean_text(payload.province), city=_clean_text(payload.city),
        district=_clean_text(payload.district) or None, address=_clean_text(address) or None,
        department=_clean_text(payload.department) or None, kind=_clean_text(payload.kind) or None,
        features=[], summary=_clean_text(note) or None, source=_clean_text(payload.source) or None,
        lat=CITY_CENTERS.get(payload.city, (None, None))[0],
        lng=CITY_CENTERS.get(payload.city, (None, None))[1],
        origin="community", status="visible", checked_at=None, submitted_by=user_id,
    )
    db.add(hospital)
    db.commit()
    db.refresh(hospital)

    try:
        AuditLogService(db).create_log(
            user_id=user_id, action="publish", target_type="hospital", target_id=hospital.id,
            scope="public",
            detail=json.dumps({"name": hospital.name, "city": hospital.city,
                               "pii_redacted": bool(pii_types) and not payload.confirm_no_pii},
                              ensure_ascii=False),
        )
    except Exception:
        logger.warning("Audit log failed for hospital %s", hospital.id, exc_info=True)

    return _to_response(hospital, HospitalRatingStats())


# ── 评价查询 ──

def _visible_reviews(db: Session, hospital_id: Optional[int], target: Optional[str]):
    query = db.query(HospitalReview).join(Hospital, Hospital.id == HospitalReview.hospital_id).filter(
        Hospital.status == "visible",
        HospitalReview.status == "visible",
        HospitalReview.moderation_status != "blocked",
    )
    if hospital_id is not None:
        query = query.filter(HospitalReview.hospital_id == hospital_id)
    if target:
        query = query.filter(HospitalReview.target == target)
    return query


def list_reviews(
    db: Session,
    hospital_id: Optional[int],
    target: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    viewer_id: Optional[int] = None,
    sort: str = "recent",
) -> Tuple[int, List[HospitalReviewResponse], HospitalRatingStats]:
    if target and target not in REVIEW_TARGETS:
        raise HospitalReviewRejectedError("评价类型不支持")
    if sort not in ("recent", "helpful"):
        raise HospitalReviewRejectedError("排序方式不支持")
    query = _visible_reviews(db, hospital_id, target)
    total = query.count()
    # restricted（被举报/风险受限）仍然公开可见，但排序垫底并发起人工复核
    restricted_rank = case((HospitalReview.moderation_status == "restricted", 1), else_=0)
    if sort == "helpful":
        # 有用优先：先按有用数聚合排序（同分再按时间倒序）
        helpful_rank = dict(
            db.query(HospitalReviewHelpful.review_id, func.count(HospitalReviewHelpful.id))
            .group_by(HospitalReviewHelpful.review_id)
            .all()
        )
        rows = query.all()
        rows.sort(key=lambda r: (
            1 if r.moderation_status == "restricted" else 0,
            -int(helpful_rank.get(r.id, 0)), -(r.id or 0),
        ))
        rows = rows[offset:offset + limit]
    else:
        rows = (
            query.order_by(
                restricted_rank, HospitalReview.created_at.desc(), HospitalReview.id.desc()
            )
            .offset(offset).limit(limit).all()
        )
    stats = (_stats_for(db, [hospital_id]).get(hospital_id) if hospital_id is not None else None) or HospitalRatingStats()
    hospitals = {h.id: h for h in db.query(Hospital).filter(Hospital.id.in_({r.hospital_id for r in rows})).all()}
    authors = _authors(db, [r.user_id for r in rows])
    helpful_counts, mine_helpful = _helpful_map(db, [r.id for r in rows], viewer_id)
    items = [
        _review_to_response(review, author=authors.get(review.user_id), hospital=hospitals.get(review.hospital_id),
                            viewer_id=viewer_id, helpful_count=helpful_counts.get(review.id, 0),
                            is_helpful=review.id in mine_helpful)
        for review in rows
    ]
    return total, items, stats


def _authors(db: Session, user_ids: Sequence[int]) -> Dict[int, HospitalReviewAuthor]:
    ids = sorted({uid for uid in user_ids if uid})
    if not ids:
        return {}
    rows = db.query(User.id, User.username, User.avatar_url).filter(User.id.in_(ids)).all()
    return {uid: HospitalReviewAuthor(id=uid, username=username, avatar_url=avatar_url)
            for uid, username, avatar_url in rows}


def _detail_score(review: HospitalReview) -> int:
    """结构化信息完整度：达到 2 项即视为「完整分享」（列表给徽标并轻微优先）。"""
    signals = [
        bool(review.experience_scores) or bool(review.ratings),
        bool(review.cost),
        bool(review.duration),
        bool(review.visit_month),
        bool(review.images),
        bool(review.doctor_name) or bool(review.treatment_name),
        bool(review.treatment_detail),
    ]
    return sum(1 for signal in signals if signal)


def _review_images(review: HospitalReview) -> List[HospitalReviewImage]:
    return [
        HospitalReviewImage(url=str(item.get("url", "")), label=str(item.get("label", "")))
        for item in (review.images or [])
        if isinstance(item, dict) and item.get("url")
    ]


def _review_to_response(
    review: HospitalReview,
    author: Optional[HospitalReviewAuthor] = None,
    hospital: Optional[Hospital] = None,
    viewer_id: Optional[int] = None,
    helpful_count: int = 0,
    is_helpful: bool = False,
    include_private: bool = False,
) -> HospitalReviewResponse:
    """构造评价响应。

    ``include_private``（作者本人或管理员）才会返回：
      - 凭证图 URL（v3 起凭证图默认不公开，公开层只给「已上传 xx」徽标）
      - 受限/驳回原因
    """
    is_mine = bool(viewer_id and viewer_id == review.user_id)
    private = include_private or is_mine
    images = _review_images(review)
    ratings: Dict[str, int] = {}
    if private:
        # 旧版 1-5 星评分仅在作者视角保留，公开层不再输出（避免被当作医院得分）
        ratings = {}
        for key, value in (review.ratings or {}).items():
            try:
                ratings[str(key)] = int(value)
            except (TypeError, ValueError):
                continue
    return HospitalReviewResponse(
        id=review.id, hospital_id=review.hospital_id,
        hospital_name=hospital.name if hospital else None,
        hospital_city=hospital.city if hospital else None,
        target=review.target, doctor_name=review.doctor_name, doctor_title=review.doctor_title,
        doctor_department=review.doctor_department, treatment_name=review.treatment_name,
        treatment_detail=review.treatment_detail, visit_month=review.visit_month,
        duration=review.duration, cost=review.cost, outcome=review.outcome,
        ratings=ratings,
        experience_scores={
            str(k): str(v) for k, v in (review.experience_scores or {}).items()
            if str(k) in EXPERIENCE_DIMENSIONS
        },
        tags=list(review.tags or []),
        images=images if private else [],
        credential_labels=[item.label for item in images],
        content=review.content,
        moderation_status=review.moderation_status, status=review.status,
        restricted_reason=(review.restricted_reason if private else None),
        helpful_count=helpful_count, is_helpful=is_helpful,
        detail_score=_detail_score(review),
        author=author, is_mine=is_mine,
        created_at=review.created_at,
    )


def _helpful_map(db: Session, review_ids: Sequence[int], viewer_id: Optional[int]) -> Tuple[Dict[int, int], set]:
    """批量取有用数（避免逐条查询）与当前用户已投票的评价集合。"""
    ids = [rid for rid in review_ids if rid]
    if not ids:
        return {}, set()
    counts = dict(
        db.query(HospitalReviewHelpful.review_id, func.count(HospitalReviewHelpful.id))
        .filter(HospitalReviewHelpful.review_id.in_(ids))
        .group_by(HospitalReviewHelpful.review_id)
        .all()
    )
    mine: set = set()
    if viewer_id:
        mine = {
            rid for (rid,) in db.query(HospitalReviewHelpful.review_id)
            .filter(HospitalReviewHelpful.review_id.in_(ids), HospitalReviewHelpful.user_id == viewer_id)
            .all()
        }
    return {int(k): int(v) for k, v in counts.items()}, mine


def list_user_reviews(db: Session, user_id: int, limit: int = 50, offset: int = 0) -> List[HospitalReviewResponse]:
    query = db.query(HospitalReview).filter(
        HospitalReview.user_id == user_id, HospitalReview.status == "visible"
    )
    rows = query.order_by(HospitalReview.created_at.desc()).offset(offset).limit(limit).all()
    hospitals = {
        h.id: h for h in db.query(Hospital).filter(Hospital.id.in_([r.hospital_id for r in rows] or [0])).all()
    }
    helpful_counts, _ = _helpful_map(db, [r.id for r in rows], None)
    return [
        _review_to_response(r, hospital=hospitals.get(r.hospital_id), viewer_id=user_id,
                            helpful_count=helpful_counts.get(r.id, 0), is_helpful=False)
        for r in rows
    ]


# ── 评价发布 / 删除 ──

def create_review(
    db: Session,
    user_id: int,
    hospital_ident: str,
    payload: HospitalReviewCreate,
) -> Tuple[HospitalReviewResponse, bool, List[str], List[str], Dict[str, object]]:
    """发布公开评价。

    返回 ``(响应, 是否脱敏, PII 类型, 命中的疗效用语, 风控信息)``。

    v3 关键行为（见 docs/specs/2026-09-11-medical-review-v3-design.md 第五节）：
      1. **医生称谓脱敏**落库，不保存可识别真名；
      2. **PIPL 单独同意**（``health_consent``）必须显式勾选，禁止默认；
      3. **疗效维度黑名单**：疗效/医术类评分一律拒绝；
      4. 服务端风险评分 → 四档处置（approved/flagged/restricted/blocked）；
      5. **聚合冷处理**：``aggregate_after`` 只延迟进入标签聚合与维度分布，
         **不延迟发布**（发布后立即可见）。
    """
    hospital = get_hospital_by_ident(db, hospital_ident)
    target = payload.target if payload.target in REVIEW_TARGETS else "hospital"

    content = _clean_text(payload.content)
    if len(content) < 20:
        raise HospitalReviewRejectedError("请至少写 20 个字，说清楚这次就诊或治疗的实际情况")
    if target == "doctor" and not _clean_text(payload.doctor_name):
        raise HospitalReviewRejectedError("医生评价请填写医生称呼（如「张医生」）")
    if target == "treatment" and not _clean_text(payload.treatment_name):
        raise HospitalReviewRejectedError("治疗方案评价请填写方案或用药名称")

    # ── PIPL 第 28/29 条：就医体验属敏感个人信息，需单独同意（禁止默认勾选） ──
    if not payload.health_consent:
        raise HospitalReviewRejectedError(
            "请先勾选同意公开你的就医体验（其中可能包含与健康相关的信息）；我们不会替你默认勾选"
        )

    # ── 疗效/医术维度黑名单：既不采集也不聚合（广告法 16 条 / 医疗广告管理办法 7 条） ──
    for key in (payload.ratings or {}):
        key_text = str(key)
        if any(banned in key_text for banned in BANNED_DIMENSIONS):
            raise HospitalReviewRejectedError(
                f"平台不采集「{key_text}」这类疗效/医术评分，请改用就医体验维度（沟通、费用、复诊等）"
            )
    for tag in (payload.tags or []):
        tag_text = str(tag)
        if any(banned in tag_text for banned in BANNED_DIMENSIONS):
            raise HospitalReviewRejectedError(
                f"「{tag_text}」属于疗效类表述，平台不采集；请改用中性体验标签"
            )
    # 黑名单同样约束 6 维档位的键名（防止用 experience_scores 绕过 ratings 校验）
    for key in (payload.experience_scores or {}):
        key_text = str(key)
        if any(banned in key_text for banned in BANNED_DIMENSIONS):
            raise HospitalReviewRejectedError(
                f"「{key_text}」属于疗效/医术类维度，平台不采集；请改用就医体验维度"
            )
    experience_scores = clean_experience_scores(payload.experience_scores)

    # ── 医生称谓脱敏（基本医疗卫生与健康促进法 57 条 + 名誉权判例） ──
    raw_doctor_name = _clean_text(payload.doctor_name)
    doctor_department = _clean_text(payload.doctor_department)
    doctor_name = sanitize_doctor_name(raw_doctor_name, doctor_department) if raw_doctor_name else None

    treatment_detail = _clean_text(payload.treatment_detail) or None
    visit_month = _clean_text(payload.visit_month) or None
    if visit_month:
        if not re.fullmatch(r"\d{4}-\d{2}", visit_month):
            raise HospitalReviewRejectedError("就诊月份格式应为 YYYY-MM")
        if visit_month > datetime.now(timezone.utc).strftime("%Y-%m"):
            raise HospitalReviewRejectedError("就诊月份不能晚于本月")

    ratings = _clean_ratings(payload.ratings)
    tags = _clean_tags(payload.tags)
    images = _clean_images(payload.images, payload.images_confirmed)

    pii_types = detect_pii("\n".join([content, raw_doctor_name or "", treatment_detail or ""]))
    pii_redacted = False
    if pii_types and not payload.confirm_pii:
        content, _ = redact_pii(content)
        if treatment_detail:
            treatment_detail, _ = redact_pii(treatment_detail)
        pii_redacted = True
        logger.info("Hospital review PII auto-redacted: user=%s types=%s", user_id, pii_types)

    claims = [w for w in EXAGGERATED_WORDS if w in content]

    # ── 服务端风控评分（可解释规则 + 分档处置） ──
    risk = score_review(content, doctor_name=raw_doctor_name or doctor_name, tags=tags)
    if risk.blocked:
        hint = risk.hints[0] if risk.hints else "请修改后重新提交。"
        raise HospitalReviewRejectedError("这条评价含有需要修改的内容：" + hint)
    if risk.level != "safe" and not payload.risk_ack:
        raise HospitalReviewRejectedError(
            "这条评价包含情绪化或结论性表述，请先阅读「发布前提醒」并确认后再发布"
        )

    moderation_status = moderation_status_for_level(risk.level)
    if moderation_status == "restricted":
        restricted_reason = "该评价涉及结论性指控，已进入人工复核（内容仍公开，排序靠后）"
    elif moderation_status == "blocked":
        restricted_reason = "该评价含未证实的结论性指控，修改后可重新提交"
    else:
        restricted_reason = None

    delay = aggregate_delay_seconds(risk.level)
    # 异常集中度：同一用户 1 小时内对同一医院 ≥3 条 → 延长冷处理（钝化组织化刷评）
    recent_same = db.query(HospitalReview).filter(
        HospitalReview.user_id == user_id,
        HospitalReview.hospital_id == hospital.id,
        HospitalReview.created_at >= _utcnow_naive() - timedelta(hours=1),
    ).count()
    if recent_same >= 3:
        delay = max(delay, 3600)
        logger.info("Review burst detected: user=%s hospital=%s count=%s", user_id, hospital.id, recent_same)
    aggregate_after = _utcnow_naive() + timedelta(seconds=delay) if delay else None

    review = HospitalReview(
        hospital_id=hospital.id, user_id=user_id, target=target,
        doctor_name=doctor_name, doctor_title=_clean_text(payload.doctor_title)[:40] or None,
        doctor_department=doctor_department[:60] or None,
        treatment_name=_clean_text(payload.treatment_name)[:120] or None,
        treatment_detail=treatment_detail, visit_month=visit_month,
        duration=_clean_text(payload.duration)[:20] or None, cost=_clean_text(payload.cost)[:20] or None,
        outcome=_clean_text(payload.outcome)[:20] or None,
        ratings=ratings, experience_scores=experience_scores or None, tags=tags,
        images=images, content=content,
        moderation_status=moderation_status,
        risk_score=risk.score, risk_flags=[f.code for f in risk.flags] or None,
        restricted_reason=restricted_reason, aggregate_after=aggregate_after,
        health_consent=True,
        risk_reason=("命中疗效夸大用语：" + "、".join(claims)) if claims else (
            "风控标签：" + "、".join(risk.categories) if risk.flags else None
        ),
        status="visible",
    )
    db.add(review)
    db.commit()
    db.refresh(review)

    try:
        audit = AuditLogService(db)
        audit.create_log(
            user_id=user_id, action="publish", target_type="hospital_review", target_id=review.id,
            scope="public",
            detail=json.dumps({
                "hospital_id": hospital.id, "hospital_name": hospital.name,
                "target": target, "pii_redacted": pii_redacted, "claims": claims,
                "risk_level": risk.level, "risk_score": risk.score,
                "risk_flags": [f.code for f in risk.flags],
                "health_consent": True, "doctor_name_redacted": bool(raw_doctor_name),
            }, ensure_ascii=False),
        )
        if pii_types and payload.confirm_pii:
            audit.create_log(
                user_id=user_id, action="hospital.pii_confirm", target_type="hospital_review",
                target_id=review.id, scope="public",
                detail=json.dumps({"pii_types": pii_types}, ensure_ascii=False),
            )
    except Exception:
        logger.warning("Audit log failed for hospital review %s", review.id, exc_info=True)

    author = _authors(db, [user_id]).get(user_id)
    response = _review_to_response(review, author=author, hospital=hospital, viewer_id=user_id)
    risk_info: Dict[str, object] = {
        "level": risk.level, "score": risk.score, "categories": risk.categories,
        "hints": risk.hints, "aggregate_pending": bool(aggregate_after),
    }
    return response, pii_redacted, pii_types, claims, risk_info


def delete_review(db: Session, user_id: int, review_id: int) -> None:
    review = db.query(HospitalReview).filter(
        HospitalReview.id == review_id, HospitalReview.user_id == user_id,
        HospitalReview.status == "visible",
    ).first()
    if review is None:
        raise HospitalReviewNotFoundError()
    review.status = "deleted"
    db.commit()
    try:
        AuditLogService(db).create_log(
            user_id=user_id, action="delete", target_type="hospital_review", target_id=review_id,
            scope="private", detail=json.dumps({"hospital_id": review.hospital_id}, ensure_ascii=False),
        )
    except Exception:
        logger.warning("Audit log failed for review delete %s", review_id, exc_info=True)


def hide_hospital(db: Session, hospital_id: int, hidden: bool) -> None:
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if hospital is None:
        raise HospitalNotFoundError()
    hospital.status = "hidden" if hidden else "visible"
    db.commit()


def hide_review(db: Session, review_id: int, hidden: bool) -> None:
    review = db.query(HospitalReview).filter(HospitalReview.id == review_id).first()
    if review is None:
        raise HospitalReviewNotFoundError()
    review.moderation_status = "blocked" if hidden else "approved"
    db.commit()


# ── 异步内容安全审核（与社区帖子同模式，不阻塞发布） ──

def moderate_text_async(review_id: int) -> None:
    """后台线程审核入口：命中高危则把评价置为 blocked（不再公开）。"""
    from web.backend.database.database import get_db

    db_gen = get_db()
    db: Session = next(db_gen)
    try:
        review = db.query(HospitalReview).filter(HospitalReview.id == review_id).first()
        if review is None:
            return
        result = moderate_text("hospital_review", review.content, review.user_id)
        action = str(result.get("action") or "none")
        if action == "blocked":
            review.moderation_status = "blocked"
            review.risk_reason = str(result.get("risk_level"))
            db.commit()
            logger.warning("Hospital review %s blocked by content safety", review_id)
        elif action == "flagged" and review.moderation_status == "approved":
            review.moderation_status = "flagged"
            review.risk_reason = str(result.get("risk_level"))
            db.commit()
    except Exception:
        logger.error("Moderate hospital review %s failed", review_id, exc_info=True)
        db.rollback()
    finally:
        db_gen.close()


# ── 工具 ──

def _clean_text(value: Optional[str]) -> str:
    if not value:
        return ""
    text = re.sub(r"<[^>]+>", "", str(value))
    return re.sub(r"[ \t\u3000]+", " ", text).strip()


def _slugify(name: str) -> str:
    ascii_part = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if ascii_part:
        return ascii_part[:60]
    return "hospital-" + str(abs(hash(name)) % 10**8)


def _clean_ratings(ratings: Dict[str, int]) -> Dict[str, int]:
    cleaned: Dict[str, int] = {}
    for key, value in list(ratings.items())[:MAX_RATINGS]:
        label = _clean_text(str(key))[:20]
        try:
            score = int(value)
        except (TypeError, ValueError):
            continue
        if label and 1 <= score <= 5:
            cleaned[label] = score
    return cleaned


def _clean_images(images: Sequence[HospitalReviewImage], confirmed: bool) -> List[dict]:
    """凭证图清洗：仅白名单标签、最多 3 张、必须确认不含病情照片与个人信息。"""
    cleaned: List[dict] = []
    for image in list(images)[:MAX_REVIEW_IMAGES]:
        url = str(image.url or "").strip()
        label = _clean_text(image.label)[:20]
        if not url.startswith("/uploads/hospital/"):
            raise HospitalReviewRejectedError("凭证图地址无效，请重新上传")
        if label not in REVIEW_IMAGE_LABELS:
            raise HospitalReviewRejectedError("凭证图类型仅支持：" + "、".join(REVIEW_IMAGE_LABELS))
        cleaned.append({"url": url, "label": label})
    if cleaned and not confirmed:
        raise HospitalReviewRejectedError("请先确认凭证图已遮盖姓名、手机号、病历号，且不含病情照片")
    return cleaned


def save_review_image(user_id: int, filename: str, content: bytes) -> str:
    """保存评价凭证图（费用单/挂号单/处方/检查单），返回可访问 URL。

    安全：调用共享的扩展名白名单 + 魔数校验；文件名带 user_id 前缀以便归属校验。
    """
    import hashlib
    from pathlib import Path

    try:
        ext = validate_image_upload(filename, content, max_bytes=MAX_IMAGE_BYTES)
    except ValueError as e:
        raise HospitalReviewRejectedError(str(e))

    upload_dir = Path("data/uploads/hospital")
    upload_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(content).hexdigest()[:16]
    new_filename = f"{user_id}_{digest}{ext}"
    (upload_dir / new_filename).write_bytes(content)
    return f"/uploads/hospital/{new_filename}"


def toggle_helpful(db: Session, user_id: int, review_id: int) -> Tuple[int, bool]:
    """切换「有用」投票，返回 (有用数, 当前用户是否已投)。自己的评价不能投票。"""
    review = db.query(HospitalReview).filter(
        HospitalReview.id == review_id, HospitalReview.status == "visible",
    ).first()
    if review is None or review.moderation_status == "blocked":
        raise HospitalReviewNotFoundError()
    if review.user_id == user_id:
        raise HospitalReviewRejectedError("不能给自己的评价点有用")

    existing = db.query(HospitalReviewHelpful).filter(
        HospitalReviewHelpful.review_id == review_id, HospitalReviewHelpful.user_id == user_id,
    ).first()
    if existing is None:
        db.add(HospitalReviewHelpful(review_id=review_id, user_id=user_id))
        is_helpful = True
    else:
        db.delete(existing)
        is_helpful = False
    db.commit()

    count = int(
        db.query(func.count(HospitalReviewHelpful.id))
        .filter(HospitalReviewHelpful.review_id == review_id)
        .scalar() or 0
    )
    return count, is_helpful


def _clean_tags(tags: Sequence[str]) -> List[str]:
    cleaned: List[str] = []
    for tag in tags:
        label = _clean_text(str(tag))[:MAX_TAG_LENGTH]
        if label and label not in cleaned:
            cleaned.append(label)
        if len(cleaned) >= MAX_TAGS:
            break
    return cleaned


# ── 举报 / 申诉 / 管理后台风控（v3） ────────────────────────────────────────
#
# 法规依据：
#   - 《网络信息内容生态治理规定》15/16 条：须公开管理规则、设便捷投诉举报入口并反馈结果；
#   - 《民法典》第 1028 条：对失实内容应及时采取更正或删除等必要措施；
#   - 《互联网信息服务管理办法》16 条：发现违法信息应停止传输、保存记录。
# 因此举报与申诉都必须落库留痕（AuditLog），处置动作可追溯。


def _add_working_days(start: datetime, days: int) -> datetime:
    """从 start 起顺延 days 个工作日（跳过周六周日）。"""
    current = start
    remaining = max(0, days)
    while remaining > 0:
        current += timedelta(days=1)
        if current.weekday() < 5:  # 0-4 = 周一至周五
            remaining -= 1
    return current


def report_review(
    db: Session,
    user_id: int,
    review_id: int,
    reason_code: str,
    detail: Optional[str] = None,
) -> Tuple[HospitalReviewReport, int]:
    """举报一条评价（一人一条，幂等）。返回 (举报记录, 该评价当前举报数)。"""
    if reason_code not in REPORT_REASON_CODES:
        raise HospitalReviewRejectedError("举报原因不支持")
    review = db.query(HospitalReview).filter(
        HospitalReview.id == review_id, HospitalReview.status == "visible",
    ).first()
    if review is None:
        raise HospitalReviewNotFoundError()
    if review.user_id == user_id:
        raise HospitalReviewRejectedError("不能举报自己的评价")

    existing = db.query(HospitalReviewReport).filter(
        HospitalReviewReport.review_id == review_id,
        HospitalReviewReport.reporter_id == user_id,
    ).first()
    if existing is not None:
        raise HospitalReviewRejectedError("你已经举报过这条评价，我们正在处理")

    report = HospitalReviewReport(
        review_id=review_id, reporter_id=user_id, reason_code=reason_code,
        detail=_clean_text(detail)[:500] or None,
    )
    db.add(report)

    count = db.query(HospitalReviewReport).filter(
        HospitalReviewReport.review_id == review_id, HospitalReviewReport.status == "pending",
    ).count() + 1

    # 达阈值自动降权：仍公开可见，但不进标签聚合/维度分布且排序垫底，同时进入人工队列
    if count >= REPORT_RESTRICT_THRESHOLD and review.moderation_status in ("approved", "flagged"):
        review.moderation_status = "restricted"
        review.restricted_reason = "收到多条病友举报，已进入人工复核（内容仍公开，排序靠后）"
        review.aggregate_after = None

    db.commit()
    db.refresh(report)
    try:
        AuditLogService(db).create_log(
            user_id=user_id, action="report", target_type="hospital_review", target_id=review_id,
            scope="public",
            detail=json.dumps({"reason_code": reason_code, "report_count": count}, ensure_ascii=False),
        )
    except Exception:
        logger.warning("Audit log failed for review report %s", review_id, exc_info=True)
    return report, count


def report_count(db: Session, review_id: int) -> int:
    return int(
        db.query(HospitalReviewReport)
        .filter(HospitalReviewReport.review_id == review_id)
        .count()
    )


def create_appeal(db: Session, payload: HospitalReviewAppealCreate) -> HospitalReviewAppealResponse:
    """提交申诉（公开可达，不要求登录）。

    被评价机构/医生与「认为自己的评价被误判」的作者共用同一通道；
    默认 3 个工作日时限，超时在管理后台标红。
    """
    claimant_type = payload.claimant_type if payload.claimant_type in APPEAL_CLAIMANT_TYPES else "other"
    review = db.query(HospitalReview).filter(
        HospitalReview.id == payload.review_id, HospitalReview.status != "deleted",
    ).first()
    if review is None:
        raise HospitalReviewNotFoundError()
    name = _clean_text(payload.claimant_name)[:80]
    contact = _clean_text(payload.contact)[:120]
    reason = _clean_text(payload.reason)
    if not name:
        raise HospitalReviewRejectedError("请填写申诉人/机构名称")
    if not contact:
        raise HospitalReviewRejectedError("请留下联系方式，便于核实与反馈")
    if len(reason) < 20:
        raise HospitalReviewRejectedError("请至少写 20 个字说明申诉理由")

    now = _utcnow_naive()
    appeal = HospitalReviewAppeal(
        review_id=review.id, claimant_type=claimant_type, claimant_name=name,
        contact=redact_pii(contact)[0] if detect_pii(contact) else contact,
        reason=reason, evidence_urls=[str(u)[:500] for u in (payload.evidence_urls or [])][:5],
        status="pending", due_at=_add_working_days(now, APPEAL_DUE_WORKING_DAYS),
    )
    db.add(appeal)
    review.appeal_status = "pending"
    db.commit()
    db.refresh(appeal)
    try:
        AuditLogService(db).create_log(
            user_id=review.user_id, action="appeal", target_type="hospital_review",
            target_id=review.id, scope="public",
            detail=json.dumps({"appeal_id": appeal.id, "claimant_type": claimant_type},
                              ensure_ascii=False),
        )
    except Exception:
        logger.warning("Audit log failed for appeal on review %s", review.id, exc_info=True)
    return _appeal_to_response(appeal)


def _appeal_to_response(appeal: HospitalReviewAppeal) -> HospitalReviewAppealResponse:
    now = _utcnow_naive()
    return HospitalReviewAppealResponse(
        id=appeal.id, review_id=appeal.review_id, claimant_type=appeal.claimant_type,
        claimant_name=appeal.claimant_name, status=appeal.status,
        resolution=appeal.resolution, resolved_action=appeal.resolved_action,
        due_at=appeal.due_at, created_at=appeal.created_at,
        overdue=bool(appeal.status == "pending" and appeal.due_at and appeal.due_at < now),
    )


def resolve_report(
    db: Session, admin_id: int, report_id: int, upheld: bool, note: Optional[str] = None,
) -> None:
    """管理员处置举报：upheld=True 认定举报成立（评价转为 blocked 下架）。"""
    report = db.query(HospitalReviewReport).filter(HospitalReviewReport.id == report_id).first()
    if report is None:
        raise HospitalReviewRejectedError("举报记录不存在")
    report.status = "upheld" if upheld else "dismissed"
    report.handled_by = admin_id
    report.handled_at = _utcnow_naive()
    review = db.query(HospitalReview).filter(HospitalReview.id == report.review_id).first()
    if review is not None and upheld:
        review.moderation_status = "blocked"
        review.restricted_reason = "经人工复核，该评价不符合社区公约，已下架（仅本人可见）"
    elif review is not None:
        # 举报不成立：把仍在受限状态的评价恢复公开聚合
        pending = db.query(HospitalReviewReport).filter(
            HospitalReviewReport.review_id == review.id,
            HospitalReviewReport.status == "pending",
        ).count()
        if pending == 0 and review.moderation_status == "restricted":
            review.moderation_status = "approved"
            review.restricted_reason = None
    db.commit()
    try:
        AuditLogService(db).create_log(
            user_id=admin_id, action="resolve", target_type="hospital_review_report",
            target_id=report_id, scope="admin",
            detail=json.dumps({"upheld": upheld, "note": _clean_text(note)[:200]},
                              ensure_ascii=False),
        )
    except Exception:
        logger.warning("Audit log failed for report resolve %s", report_id, exc_info=True)


def resolve_appeal(
    db: Session, admin_id: int, appeal_id: int, accepted: bool,
    action: str = "keep", resolution: Optional[str] = None,
) -> HospitalReviewAppealResponse:
    """管理员处置申诉：action ∈ keep / request_edit / hide / append_note。"""
    appeal = db.query(HospitalReviewAppeal).filter(HospitalReviewAppeal.id == appeal_id).first()
    if appeal is None:
        raise HospitalReviewRejectedError("申诉记录不存在")
    if action not in ("keep", "request_edit", "hide", "append_note"):
        raise HospitalReviewRejectedError("处置动作不支持")

    appeal.status = "accepted" if accepted else "rejected"
    appeal.resolved_action = action
    appeal.resolution = _clean_text(resolution)[:300] or None
    appeal.handled_by = admin_id
    appeal.handled_at = _utcnow_naive()

    review = db.query(HospitalReview).filter(HospitalReview.id == appeal.review_id).first()
    if review is not None:
        if accepted and action == "hide":
            review.moderation_status = "blocked"
            review.restricted_reason = "经申诉复核，该评价已下架（《民法典》第 1028 条）"
        elif accepted and action == "request_edit":
            review.moderation_status = "restricted"
            review.restricted_reason = "经申诉复核，请作者补充事实依据（内容仍公开，排序靠后）"
        remaining = db.query(HospitalReviewAppeal).filter(
            HospitalReviewAppeal.review_id == review.id,
            HospitalReviewAppeal.status == "pending",
        ).count()
        review.appeal_status = "pending" if remaining else "resolved"
    db.commit()
    db.refresh(appeal)
    try:
        AuditLogService(db).create_log(
            user_id=admin_id, action="resolve", target_type="hospital_review_appeal",
            target_id=appeal_id, scope="admin",
            detail=json.dumps({"accepted": accepted, "action": action},
                              ensure_ascii=False),
        )
    except Exception:
        logger.warning("Audit log failed for appeal resolve %s", appeal_id, exc_info=True)
    return _appeal_to_response(appeal)


def list_admin_risk(
    db: Session, limit: int = 50, offset: int = 0, only_pending: bool = True,
) -> HospitalRiskAdminResponse:
    """管理后台风控看板：待处理举报/申诉 + 高冲突评价。"""
    now = _utcnow_naive()
    pending_reports = int(
        db.query(HospitalReviewReport).filter(HospitalReviewReport.status == "pending").count()
    )
    pending_appeals = int(
        db.query(HospitalReviewAppeal).filter(HospitalReviewAppeal.status == "pending").count()
    )
    overdue_appeals = int(
        db.query(HospitalReviewAppeal).filter(
            HospitalReviewAppeal.status == "pending", HospitalReviewAppeal.due_at < now,
        ).count()
    )

    query = db.query(HospitalReview).filter(HospitalReview.status == "visible")
    if only_pending:
        query = query.filter(
            or_(
                HospitalReview.moderation_status.in_(("restricted", "blocked")),
                HospitalReview.risk_score >= 30,
                HospitalReview.id.in_(
                    db.query(HospitalReviewReport.review_id).filter(
                        HospitalReviewReport.status == "pending"
                    )
                ),
                HospitalReview.id.in_(
                    db.query(HospitalReviewAppeal.review_id).filter(
                        HospitalReviewAppeal.status == "pending"
                    )
                ),
            )
        )
    total = query.count()
    rows = (
        query.order_by(HospitalReview.risk_score.desc().nullslast(), HospitalReview.id.desc())
        .offset(offset).limit(limit).all()
    )

    hospital_ids = [r.hospital_id for r in rows]
    names = {
        hid: name for hid, name in
        db.query(Hospital.id, Hospital.name).filter(Hospital.id.in_(hospital_ids or [0])).all()
    } if hospital_ids else {}
    review_ids = [r.id for r in rows]
    report_counts: Dict[int, int] = {}
    appeal_counts: Dict[int, int] = {}
    if review_ids:
        report_counts = {
            int(rid): int(cnt) for rid, cnt in
            db.query(HospitalReviewReport.review_id, func.count(HospitalReviewReport.id))
            .filter(HospitalReviewReport.review_id.in_(review_ids))
            .group_by(HospitalReviewReport.review_id).all()
        }
        appeal_counts = {
            int(rid): int(cnt) for rid, cnt in
            db.query(HospitalReviewAppeal.review_id, func.count(HospitalReviewAppeal.id))
            .filter(HospitalReviewAppeal.review_id.in_(review_ids))
            .group_by(HospitalReviewAppeal.review_id).all()
        }

    items = [
        HospitalRiskAdminItem(
            review_id=r.id, hospital_id=r.hospital_id, hospital_name=names.get(r.hospital_id),
            target=r.target, risk_score=int(r.risk_score or 0),
            risk_level=level_for_score(int(r.risk_score or 0)),
            risk_flags=[str(x) for x in (r.risk_flags or [])],
            moderation_status=r.moderation_status,
            report_count=report_counts.get(r.id, 0), appeal_count=appeal_counts.get(r.id, 0),
            content_excerpt=(r.content or "")[:160],
            created_at=r.created_at,
        )
        for r in rows
    ]
    return HospitalRiskAdminResponse(
        total=total, pending_reports=pending_reports, pending_appeals=pending_appeals,
        overdue_appeals=overdue_appeals,
        high_risk_count=int(
            db.query(HospitalReview).filter(
                HospitalReview.status == "visible", HospitalReview.risk_score >= 60,
            ).count()
        ),
        items=items,
    )

"""Purpose-gated contribution aggregates and idempotent honours.

No clinical claims are inferred from admin/AI/self-reported labels. Public
distributions are entirely suppressed if any small non-zero bucket exists,
so the totals cannot reveal a hidden cell by subtraction.
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session, joinedload, load_only

from web.backend.database.models import MedicalReport, User
from web.backend.models.contribution import ContributionCredit
from web.backend.models.image_label import ImageLabel
from web.backend.models.vasi import VASIAssessment
from web.backend.services.data_consent import active_summary, label_training_decision
from web.backend.utils.contribution_rules import (
    BODY_SITES,
    LEVELS,
    RULES,
    VERSION,
    award_key,
    body_site_code,
    membership,
)

MIN_PUBLIC_COUNT = 5


def metric(
    value: Optional[int], note: str, status: str = "available", unit: str = "张"
) -> dict:
    return {"value": value, "status": status, "unit": unit, "note": note}


def public_count(value: int, note: str, unit: str) -> dict:
    if 0 < value < MIN_PUBLIC_COUNT:
        return metric(None, note + "；小样本数量暂不公开", "suppressed", unit)
    return metric(value, note, unit=unit)


def eligible_labels(db: Session, user_id: Optional[int] = None) -> List[ImageLabel]:
    """Only user-owned, currently consented and accepted, deduplicated assets."""
    query = (
        db.query(ImageLabel)
        .join(User, User.id == ImageLabel.original_user_id)
        .filter(
            User.is_active.is_(True),
            User.is_test.isnot(True),
            User.user_status != "banned",
            ImageLabel.is_user_deleted.is_(False),
            ImageLabel.label_status == "labeled",
            ImageLabel.training_eligible.is_(True),
            ImageLabel.image_hash.isnot(None),
        )
        .options(
            load_only(
                ImageLabel.id,
                ImageLabel.original_user_id,
                ImageLabel.assessment_id,
                ImageLabel.image_hash,
                ImageLabel.is_user_deleted,
                ImageLabel.user_body_site,
                ImageLabel.admin_body_site,
                ImageLabel.labeled_at,
            ),
            joinedload(ImageLabel.assessment).load_only(
                VASIAssessment.id,
                VASIAssessment.user_id,
                VASIAssessment.created_at,
                VASIAssessment.body_site,
                VASIAssessment.is_user_corrected,
                VASIAssessment.auto_finalized,
                VASIAssessment.status,
            ),
        )
    )
    if user_id is not None:
        query = query.filter(ImageLabel.original_user_id == user_id)
    seen = set()
    rows = []
    for label in query.order_by(ImageLabel.id).all():
        assessment = label.assessment
        # Prevent ownership mismatches, drafts and legacy records with no evidence.
        if (
            not assessment
            or assessment.user_id != label.original_user_id
            or assessment.status != "active"
        ):
            continue
        if assessment.image_hash != label.image_hash:
            continue
        if (
            not label.image_hash
            or label.image_hash in seen
            or not label_training_decision(db, label).allowed
        ):
            continue
        seen.add(label.image_hash)
        rows.append(label)
    return rows


def overview(db: Session) -> dict:
    rows = eligible_labels(db)
    contributors = len({r.original_user_id for r in rows})
    users = (
        db.query(func.count(User.id))
        .filter(
            User.is_active.is_(True),
            User.is_test.isnot(True),
            User.user_status != "banned",
        )
        .scalar()
        or 0
    )
    checked = sum(1 for r in rows if r.assessment.is_user_corrected)
    return {
        "updated_at": datetime.utcnow().isoformat() + "Z",
        "version": VERSION,
        "users": metric(
            users, "当前有效注册账号，排除测试与封禁账号；账号不等于独立病友", unit="人"
        ),
        "contributors": public_count(
            contributors, "当前至少贡献一张有效授权图片的用户", "人"
        ),
        "images": public_count(
            len(rows), "去重、有效用途授权、质量审核和采纳全部通过的用户图片", "张"
        ),
        "checked": public_count(
            checked, "有效图片中具有明确本人范围核对记录的数量", "张"
        ),
        "doctor_ratio": metric(
            None, "认证医生参考与独立病友关联完善后统计", "unavailable", "%"
        ),
        "followup": metric(
            None, "同部位合格序列与病友关联完善后统计", "unavailable", "人"
        ),
        "rules": RULES,
        "levels": LEVELS,
    }


def distribution(db: Session) -> dict:
    counts = dict.fromkeys(dict(BODY_SITES), 0)
    for row in eligible_labels(db):
        code = body_site_code(
            row.user_body_site or row.admin_body_site or row.assessment.body_site
        )
        counts[code] += 1
    suppressed = any(0 < n < MIN_PUBLIC_COUNT for n in counts.values())
    return {
        "status": "suppressed" if suppressed else "available",
        "updated_at": datetime.utcnow().isoformat() + "Z",
        "version": VERSION,
        "note": (
            "按主部位统计，每图一次；稀疏分布整体隐藏，避免通过其他格与总数推算。"
            if suppressed
            else "按主部位统计，每图一次；上肢/下肢待细分项保留原始信息精度。"
        ),
        "rows": [
            {
                "code": code,
                "label": label,
                "count": None if suppressed else counts[code],
            }
            for code, label in BODY_SITES
        ],
        "types": {
            "status": "unavailable",
            "note": "现有AI、用户和管理员分型不能代替医生分型。",
            "columns": ["节段型", "非节段型", "混合型", "未分类", "待医生分型"],
        },
        "dimensions": [
            {"name": "部位", "status": "available"},
            {"name": "MST肤色", "status": "unavailable"},
            {"name": "设备", "status": "unavailable"},
            {"name": "年龄段", "status": "unavailable"},
            {"name": "成像方式", "status": "unavailable"},
        ],
        "coverage": metric(
            None,
            "采集目标格与各格门槛配置后计算，不把缺字段填成已覆盖",
            "unavailable",
            "%",
        ),
    }


def sync_credits(db: Session, user_id: int) -> int:
    """Explicit POST reconciliation; GETs never mutate the ledger.

    SQLite ON CONFLICT protects concurrent page refreshes. No user-provided
    points or object IDs are accepted. Revocation does not remove old honours.
    """
    added = 0
    for label in eligible_labels(db, user_id):
        kinds = [("image_accepted", 10)]
        if label.assessment.is_user_corrected:
            kinds.append(("mask_confirmed", 5))
        for kind, points in kinds:
            statement = (
                insert(ContributionCredit)
                .values(
                    user_id=user_id,
                    event_key=award_key(label.image_hash, kind),
                    kind=kind,
                    points=points,
                    rule_version=VERSION,
                    awarded_at=datetime.utcnow(),
                )
                .on_conflict_do_nothing(index_elements=["user_id", "event_key"])
            )
            added += db.execute(statement).rowcount
    db.commit()
    return added


def my_summary(db: Session, user_id: int) -> dict:
    rows = eligible_labels(db, user_id)
    uploads = (
        db.query(func.count(func.distinct(VASIAssessment.image_hash)))
        .filter(
            VASIAssessment.user_id == user_id,
            VASIAssessment.status == "active",
        )
        .scalar()
        or 0
    )
    checked = (
        db.query(func.count(func.distinct(VASIAssessment.image_hash)))
        .filter(
            VASIAssessment.user_id == user_id,
            VASIAssessment.status == "active",
            VASIAssessment.is_user_corrected.is_(True),
        )
        .scalar()
        or 0
    )
    pending = (
        db.query(func.count(ImageLabel.id))
        .filter(
            ImageLabel.original_user_id == user_id,
            ImageLabel.is_user_deleted.is_(False),
            ImageLabel.label_status == "pending",
        )
        .scalar()
        or 0
    )
    reports = (
        db.query(func.count(MedicalReport.id))
        .filter(MedicalReport.user_id == user_id)
        .scalar()
        or 0
    )
    points = (
        db.query(func.coalesce(func.sum(ContributionCredit.points), 0))
        .filter(ContributionCredit.user_id == user_id)
        .scalar()
    )
    award_counts = dict(
        db.query(ContributionCredit.kind, func.count(ContributionCredit.id))
        .filter(
            ContributionCredit.user_id == user_id,
        )
        .group_by(ContributionCredit.kind)
        .all()
    )
    return {
        "updated_at": datetime.utcnow().isoformat() + "Z",
        "version": VERSION,
        "images": metric(len(rows), "当前有效授权且通过质量审核与采纳的去重图片"),
        "checked": metric(
            sum(1 for r in rows if r.assessment.is_user_corrected),
            "有效图片中本人明确完成范围核对的图片，每图计一次",
        ),
        "reports": metric(
            reports, "本人已上传的体检报告份数，非页数；共建授权尚未开放", unit="份"
        ),
        "doctor": metric(
            None,
            "有认证医生、确认依据和版本后统计，用户自报不计入",
            "unavailable",
            "条",
        ),
        "impact": metric(
            None,
            "已发布数据版本及去重使用统计积累后，预测共同覆盖人数",
            "unavailable",
            "人",
        ),
        "uploaded": uploads,
        "personally_checked": checked,
        "pending": pending,
        "report_contribution": metric(
            None, "体检资料的独立共建授权尚未开放", "unavailable", "份"
        ),
        "membership": membership(int(points or 0)),
        "active_consent": active_summary(db, user_id)["model_training"],
        "badges": [
            {
                "name": "第一份记录",
                "icon": "ri-seedling-line",
                "earned": award_counts.get("image_accepted", 0) > 0,
            },
            {
                "name": "认真核对",
                "icon": "ri-checkbox-circle-line",
                "earned": award_counts.get("mask_confirmed", 0) > 0,
            },
            {"name": "持续同行", "icon": "ri-route-line", "earned": False},
            {"name": "补全拼图", "icon": "ri-puzzle-line", "earned": False},
        ],
    }


def my_events(db: Session, user_id: int, offset: int, limit: int) -> dict:
    query = db.query(ContributionCredit).filter(ContributionCredit.user_id == user_id)
    total = query.count()
    names = {r["kind"]: r["title"] for r in RULES}
    rows = (
        query.order_by(ContributionCredit.id.desc()).offset(offset).limit(limit).all()
    )
    return {
        "total": total,
        "items": [
            {
                "id": row.id,
                "title": names.get(row.kind, "贡献积分"),
                "points": row.points,
                "rule_version": row.rule_version,
                "awarded_at": row.awarded_at.isoformat() + "Z",
            }
            for row in rows
        ],
    }

"""Review and task-state transitions.

pending → in_review (submitted) → gold (approved) | returned → in_review …
any open state → skipped / rejected (unusable) → pending (reopen)

Gold is always bound to one approved submission revision. Approval by the
author is allowed but recorded as ``single_review``; benchmark (locked test)
tasks require a different reviewer.
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from web.backend.exceptions import RGBSegmentationError
from web.backend.models.image_label import ImageLabel, ImageLabelLog
from web.backend.models.label_submission import LabelSubmission
from web.backend.services.labeling import sources
from web.backend.services.labeling.attributes import normalize_reasons
from web.backend.services.rgb_segmentation import dataset_pipeline as pipeline


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log(db: Session, label: ImageLabel, actor: int, action: str, value: Dict[str, Any]) -> None:
    db.add(ImageLabelLog(image_label_id=label.id, operator_id=actor, action=action,
                         new_value=json.dumps(value, ensure_ascii=False)))


def _submission(db: Session, submission_id: int) -> LabelSubmission:
    row = db.get(LabelSubmission, submission_id)
    if row is None:
        raise RGBSegmentationError("NOT_FOUND", "提交版本不存在", 404)
    return row


def _label(db: Session, row: LabelSubmission) -> ImageLabel:
    label = db.get(ImageLabel, row.image_label_id)
    if label is None or label.is_user_deleted or sources.kind(label) is None:
        raise RGBSegmentationError("NOT_FOUND", "原记录已删除", 404)
    return label


def approve(db: Session, submission_id: int, reviewer: int, note: str = "") -> LabelSubmission:
    row = _submission(db, submission_id)
    label = _label(db, row)
    if row.status != "submitted":
        raise RGBSegmentationError("INVALID_STATE", "只能复核待复核的提交", 409)
    mode = "dual" if reviewer != row.author_id else "single_review"
    if label.benchmark and mode != "dual":
        raise RGBSegmentationError("DUAL_REVIEW_REQUIRED", "基准集样本须由提交人以外的管理员复核", 409)
    if label.benchmark and not row.blind:
        raise RGBSegmentationError("BLIND_REQUIRED", "基准集样本须盲标后才能通过", 409)
    db.query(LabelSubmission).filter_by(image_label_id=label.id, status="approved").update(
        {"status": "superseded"}, synchronize_session="fetch"
    )
    row.status = "approved"
    row.reviewer_id = reviewer
    row.review_mode = mode
    row.review_note = (note or "").strip()[:500] or None
    row.reviewed_at = datetime.utcnow()
    pipeline.approve_gold(
        db,
        label,
        reviewer,
        revision=row.revision,
        extra={"submission_id": row.id, "author_id": row.author_id, "review_mode": mode},
    )
    label.label_status = "gold"
    return row


def return_submission(db: Session, submission_id: int, reviewer: int, note: str) -> LabelSubmission:
    row = _submission(db, submission_id)
    label = _label(db, row)
    if row.status != "submitted":
        raise RGBSegmentationError("INVALID_STATE", "只能退回待复核的提交", 409)
    note = (note or "").strip()
    if not note:
        raise RGBSegmentationError("INVALID_REQUEST", "请写明退回意见")
    row.status = "returned"
    row.reviewer_id = reviewer
    row.review_note = note[:500]
    row.reviewed_at = datetime.utcnow()
    label.label_status = "gold" if sources.sync_of(label).get("gold") else "returned"
    _log(db, label, reviewer, "label-returned", {"submission_id": row.id, "note": row.review_note})
    return row


def _close_open(db: Session, label: ImageLabel, actor: int) -> None:
    pipeline.revoke_gold(db, label, actor)
    db.query(LabelSubmission).filter(
        LabelSubmission.image_label_id == label.id,
        LabelSubmission.status.in_(("submitted", "approved")),
    ).update({"status": "superseded"}, synchronize_session="fetch")


def set_status(db: Session, label: ImageLabel, actor: int, status: str, reasons: List[str]) -> None:
    """skipped / rejected (unusable, with reasons) / pending (reopen)."""
    if label.is_user_deleted or sources.kind(label) is None:
        raise RGBSegmentationError("NOT_FOUND", "原记录已删除", 404)
    sync = sources.sync_of(label)
    if status in ("skipped", "rejected"):
        value = {"status": status, "by": actor, "at": _now()}
        if status == "rejected":
            value["reasons"] = normalize_reasons(reasons)
        _close_open(db, label, actor)
        sync = sources.sync_of(label)  # revoke_gold rewrote it
        sync["rejection"] = value
        label.label_status = status
    elif status == "pending":
        if label.label_status not in ("skipped", "rejected"):
            raise RGBSegmentationError("INVALID_STATE", "只有跳过/不可用的任务可以恢复", 409)
        sync.pop("rejection", None)
        label.label_status = "pending"
        value = {"status": "pending", "by": actor, "at": _now()}
    else:
        raise RGBSegmentationError("INVALID_REQUEST", "状态无效")
    pipeline.write_sync(label, sync)
    _log(db, label, actor, "label-status", value)


def set_benchmark(db: Session, label: ImageLabel, actor: int, flag: bool) -> None:
    """Benchmark tasks need blind labels and dual review; other versions stop counting."""
    if label.is_user_deleted or sources.kind(label) is None:
        raise RGBSegmentationError("NOT_FOUND", "原记录已删除", 404)
    if bool(label.benchmark) == flag:
        return
    label.benchmark = flag
    if flag:
        gold = sources.sync_of(label).get("gold") or {}
        gold_row = db.get(LabelSubmission, gold["submission_id"]) if gold.get("submission_id") else None
        if not (gold_row and gold_row.blind and gold.get("review_mode") == "dual"):
            pipeline.revoke_gold(db, label, actor)
            gold_row = None
        db.query(LabelSubmission).filter(
            LabelSubmission.image_label_id == label.id,
            LabelSubmission.status.in_(("submitted", "approved")),
            LabelSubmission.blind.is_(False),
        ).update({"status": "superseded"}, synchronize_session="fetch")
        waiting = db.query(LabelSubmission).filter_by(
            image_label_id=label.id, status="submitted"
        ).count()
        if label.label_status in ("in_review", "gold", "returned"):
            label.label_status = "gold" if gold_row else "in_review" if waiting else "pending"
    _log(db, label, actor, "label-benchmark", {"benchmark": flag, "at": _now()})

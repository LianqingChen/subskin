"""Owner scoped, idempotent job persistence; inference runs outside the API."""

import hashlib
import json
import math
import re
import shutil
from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional
from uuid import uuid4
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from web.backend.exceptions import RGBSegmentationError
from web.backend.models.rgb_segmentation import RGBSegmentationJob
from web.backend.models.vasi import VASIAssessment
from web.backend.services.rgb_segmentation import artifacts
from web.backend.services.assessment_measurement import context_for
from web.backend.utils.assessment_body_sites import BODY_SITE_LABELS

ACTIVE = ("queued", "running")
JOB_TIMEOUT_SECONDS = 90
MAX_ACTIVE_PER_USER = 2
MAX_ACTIVE_GLOBAL = 16
MAX_JOBS_PER_DAY = 260  # assessment and interactive requests share one bounded budget
MAX_ESTIMATED_USER_BYTES = 1024 * 1024 * 1024
MIN_FREE_BYTES = 2 * 1024 * 1024 * 1024


def owned_job(db: Session, job_id: str, user_id: int) -> RGBSegmentationJob:
    job = db.query(RGBSegmentationJob).filter_by(id=job_id, user_id=user_id).first()
    if job is None:
        raise RGBSegmentationError("NOT_FOUND", "记录不存在", 404)
    return job


def capture_context(
    db: Session, user_id: int, body_site: str, supplied: Dict[str, Any]
) -> Dict[str, Any]:
    if body_site not in BODY_SITE_LABELS:
        raise RGBSegmentationError("INVALID_INPUT", "请选择身体部位")
    try:
        captured = date.fromisoformat(
            supplied.get("capture_date") or date.today().isoformat()
        )
        if captured > date.today():
            raise ValueError()
    except (ValueError, TypeError):
        raise RGBSegmentationError("INVALID_INPUT", "照片日期无效")
    label = str(supplied.get("label") or "").strip()
    if len(label) > 60 or supplied.get("intent", "discovery") not in (
        "discovery",
        "tracking",
    ):
        raise RGBSegmentationError("INVALID_INPUT", "照片信息无效")
    baseline_id = supplied.get("baseline_id")
    prior = {}
    if baseline_id is not None:
        baseline = (
            db.query(VASIAssessment)
            .filter_by(id=baseline_id, user_id=user_id, status="active")
            .first()
        )
        if baseline is None or baseline.body_site != BODY_SITE_LABELS[body_site]:
            raise RGBSegmentationError("INVALID_INPUT", "请选择同部位的有效基线记录")
        prior = context_for(baseline)
    calibration = supplied.get("calibration")
    if calibration is not None:
        try:
            points = calibration["points"]
            if (
                not isinstance(calibration, dict)
                or len(json.dumps(calibration)) > 1000
                or len(points) != 2
                or any(
                    len(p) != 2
                    or not all(
                        isinstance(v, (int, float)) and math.isfinite(v) and 0 <= v <= 1
                        for v in p
                    )
                    for p in points
                )
                or not isinstance(calibration["length_mm"], (int, float))
                or not math.isfinite(calibration["length_mm"])
                or not 1 <= calibration["length_mm"] <= 1000
                or type(calibration["same_plane"]) is not bool
            ):
                raise ValueError()
        except (TypeError, KeyError, ValueError):
            raise RGBSegmentationError("INVALID_INPUT", "参照物信息无效")
    return {
        "body_site": body_site,
        "calibration": calibration,
        "observation": {
            "id": prior.get("id") or uuid4().hex,
            "label": prior.get("label") or label,
            "view": prior.get("view") or "",
            "intent": supplied.get("intent", "discovery"),
            "capture_date": captured.isoformat(),
            "date_confirmed": True,
            "baseline_id": baseline_id,
        },
    }


def ensure_storage_capacity(
    db: Session, user_id: int, source_bytes: int = 0, jobs: int = 0, revisions: int = 0
) -> None:
    count, saved_bytes, saved_revisions = (
        db.query(
            func.count(RGBSegmentationJob.id),
            func.coalesce(func.sum(RGBSegmentationJob.source_bytes), 0),
            func.coalesce(func.sum(RGBSegmentationJob.revision), 0),
        )
        .filter(RGBSegmentationJob.user_id == user_id)
        .one()
    )
    estimated = (
        int(saved_bytes)
        + source_bytes
        + (int(count) + jobs) * 8 * 1024 * 1024
        + (int(saved_revisions) + revisions) * 1024 * 1024
    )
    if estimated > MAX_ESTIMATED_USER_BYTES:
        raise RGBSegmentationError(
            "QUOTA_EXCEEDED", "图像存储额度已达上限，请稍后重试", 429
        )
    disk_path = artifacts.ROOT if artifacts.ROOT.exists() else artifacts.ROOT.parent
    if shutil.disk_usage(disk_path).free < MIN_FREE_BYTES:
        raise RGBSegmentationError("STORAGE_BUSY", "图像存储暂不可用，请稍后重试", 503)


def find_duplicate_image(
    db: Session, user_id: int, body_site: Optional[str], source_sha256: str
) -> Optional[Any]:
    """Same owner + same site + identical photo bytes already recorded or in flight.

    One photograph should become one observation per body site: repeated uploads
    of the same file used to become separate records, which made trend and
    comparison views unusable. Historical duplicates are left untouched.
    """
    label = BODY_SITE_LABELS.get(body_site or "")
    if label is None:
        return None
    recorded = (
        db.query(VASIAssessment)
        .filter(
            VASIAssessment.user_id == user_id,
            VASIAssessment.image_hash == source_sha256,
            VASIAssessment.body_site == label,
            VASIAssessment.status != "abandoned",
            VASIAssessment.assessment_source != "quality-reject",
        )
        .order_by(VASIAssessment.id.desc())
        .first()
    )
    if recorded is not None:
        return recorded
    for job in (
        db.query(RGBSegmentationJob)
        .filter(
            RGBSegmentationJob.user_id == user_id,
            RGBSegmentationJob.state.in_(ACTIVE),
        )
        .all()
    ):
        try:
            context = json.loads(job.context_json or "{}")
            if context.get("operation") == "refine" or context.get("body_site") != body_site:
                continue
            if hashlib.sha256(artifacts.read_input(job.id)).hexdigest() == source_sha256:
                return job
        except (OSError, ValueError):
            continue
    return None


def create_job(
    db: Session,
    user_id: int,
    key: str,
    source: bytes,
    body_site: str,
    supplied: Dict[str, Any],
    context_override: Optional[Dict[str, Any]] = None,
) -> RGBSegmentationJob:
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", key):
        raise RGBSegmentationError("INVALID_INPUT", "请求编号无效")
    if not source or len(source) > 10 * 1024 * 1024:
        raise RGBSegmentationError("INVALID_IMAGE", "请选择10MB以内的照片")
    fingerprint = hashlib.sha256(
        source
        + json.dumps(
            {"body_site": body_site, "context": supplied}, sort_keys=True
        ).encode()
    ).hexdigest()
    existing = (
        db.query(RGBSegmentationJob)
        .filter_by(user_id=user_id, idempotency_key=key)
        .first()
    )
    if existing:
        if existing.request_hash != fingerprint:
            raise RGBSegmentationError(
                "REVISION_CONFLICT", "请求已用于另一张照片，请重新开始", 409
            )
        return existing
    context = (
        context_override
        if context_override is not None
        else capture_context(db, user_id, body_site, supplied)
    )
    # Serialize admission with SQLite's write lock; the unique constraint handles duplicate requests.
    from sqlalchemy import text

    if db.bind.dialect.name == "sqlite":
        db.rollback()
        db.execute(text("BEGIN IMMEDIATE"))
    active = db.query(RGBSegmentationJob).filter(RGBSegmentationJob.state.in_(ACTIVE))
    if (
        active.filter_by(user_id=user_id).count() >= MAX_ACTIVE_PER_USER
        or active.count() >= MAX_ACTIVE_GLOBAL
    ):
        db.rollback()
        raise RGBSegmentationError("QUEUE_FULL", "分析任务较多，请稍后重试", 429)
    # Only assessment jobs are duplicate-checked: refine/outline jobs reuse the
    # parent's own photo bytes by design.
    if context.get("operation", "assessment") == "assessment":
        duplicate = find_duplicate_image(
            db, user_id, context.get("body_site"), hashlib.sha256(source).hexdigest()
        )
        if duplicate is not None:
            if isinstance(duplicate, VASIAssessment):
                when = (
                    duplicate.assessment_date.strftime("%Y-%m-%d")
                    if duplicate.assessment_date
                    else "此前"
                )
                message = (
                    f"这张照片已作为 {when} 的{duplicate.body_site}记录保存过，"
                    "请打开该记录调整范围，或删除后重新记录"
                )
            else:
                message = "这张照片正在分析中，请稍后在白斑记录中查看结果"
            db.rollback()
            raise RGBSegmentationError("DUPLICATE_IMAGE", message, 409)
    recent = (
        db.query(RGBSegmentationJob)
        .filter(
            RGBSegmentationJob.user_id == user_id,
            RGBSegmentationJob.created_at >= datetime.utcnow() - timedelta(days=1),
        )
        .count()
    )
    if recent >= MAX_JOBS_PER_DAY:
        db.rollback()
        raise RGBSegmentationError(
            "QUOTA_EXCEEDED", "今天的分析次数已达上限，请稍后重试", 429
        )
    try:
        ensure_storage_capacity(db, user_id, source_bytes=len(source), jobs=1)
    except RGBSegmentationError:
        db.rollback()
        raise
    job = RGBSegmentationJob(
        id=uuid4().hex,
        user_id=user_id,
        idempotency_key=key,
        request_hash=fingerprint,
        context_json=json.dumps(context, ensure_ascii=False),
        source_bytes=len(source),
        state="queued",
        stage="queued",
        deadline_at=datetime.utcnow() + timedelta(seconds=JOB_TIMEOUT_SECONDS),
    )
    try:
        artifacts.write_input(job.id, source)
        db.add(job)
        db.commit()
        db.refresh(job)
        return job
    except IntegrityError:
        db.rollback()
        shutil.rmtree(artifacts.job_directory(job.id), ignore_errors=True)
        existing = (
            db.query(RGBSegmentationJob)
            .filter_by(user_id=user_id, idempotency_key=key)
            .first()
        )
        if existing and existing.request_hash == fingerprint:
            return existing
        raise RGBSegmentationError("REVISION_CONFLICT", "请求编号冲突，请重试", 409)


def cancel_job(db: Session, job_id: str, user_id: int) -> RGBSegmentationJob:
    job = owned_job(db, job_id, user_id)
    if job.state in ACTIVE:
        db.query(RGBSegmentationJob).filter(
            RGBSegmentationJob.id == job_id, RGBSegmentationJob.state.in_(ACTIVE)
        ).update(
            {
                "state": "cancelled",
                "stage": "cancelled",
                "updated_at": datetime.utcnow(),
            },
            synchronize_session=False,
        )
        db.commit()
        db.refresh(job)
    elif job.state == "completed" and job.assessment_id:
        assessment = (
            db.query(VASIAssessment)
            .filter_by(id=job.assessment_id, user_id=user_id, status="draft")
            .first()
        )
        if assessment:
            assessment.status = "abandoned"
            job.state = "cancelled"
            db.commit()
    return job


def serialize_job(job: RGBSegmentationJob) -> Dict[str, Any]:
    expired = job.state in ACTIVE and job.deadline_at <= datetime.utcnow()
    return {
        "id": job.id,
        "operation": json.loads(job.context_json).get("operation", "assessment"),
        "state": "failed" if expired else job.state,
        "stage": "failed" if expired else job.stage,
        "assessment_id": job.assessment_id,
        "revision": job.revision,
        "result": json.loads(job.result_json) if job.result_json else None,
        "error_code": "TIMEOUT" if expired else job.error_code,
        "created_at": job.created_at.isoformat() + "Z",
    }


def claim_job(db: Session) -> Optional[RGBSegmentationJob]:
    now = datetime.utcnow()
    db.query(RGBSegmentationJob).filter(
        RGBSegmentationJob.state.in_(ACTIVE), RGBSegmentationJob.deadline_at < now
    ).update(
        {
            "state": "failed",
            "stage": "failed",
            "error_code": "TIMEOUT",
            "updated_at": now,
        },
        synchronize_session=False,
    )
    db.commit()
    job = (
        db.query(RGBSegmentationJob)
        .filter_by(state="queued")
        .order_by(RGBSegmentationJob.created_at)
        .first()
    )
    if not job:
        return None
    lease = uuid4().hex
    changed = (
        db.query(RGBSegmentationJob)
        .filter_by(id=job.id, state="queued")
        .update(
            {
                "state": "running",
                "stage": "preprocessing",
                "lease": lease,
                "updated_at": now,
            },
            synchronize_session=False,
        )
    )
    db.commit()
    if changed != 1:
        return None
    db.refresh(job)
    return job

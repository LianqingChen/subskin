"""Admin labeling workbench: five-class tasks aligned with the diary and the trainer.

Replaces the legacy ``/admin/image-labels`` editing endpoints for the admin UI.
Images are served only with an ``Authorization`` header (no token in URLs).
"""

import io
import logging
from typing import Any, Dict, List, Optional

import anyio
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from web.backend.database.database import get_db
from web.backend.database.models import User
from web.backend.exceptions import RGBSegmentationError
from web.backend.models.vasi import VASIAssessment
from web.backend.services.labeling import attributes as attribute_rules
from web.backend.services.labeling import progress as progress_service
from web.backend.services.labeling import sources, submissions, tasks, uploads, workflow
from web.backend.services.rgb_segmentation.images import MAX_UPLOAD_BYTES
from web.backend.services.unified_auth import get_current_admin_user
from web.backend.utils.body_sites import taxonomy

router = APIRouter(prefix="/admin/labeling", tags=["打标工作台"])
logger = logging.getLogger(__name__)


def _fail(exc: RGBSegmentationError):
    raise HTTPException(status_code=exc.http_status, detail=str(exc))


def _task(db: Session, label_id: int):
    try:
        return tasks.get_visible(db, label_id)
    except RGBSegmentationError as exc:
        _fail(exc)


class SubmitRequest(BaseModel):
    labels: str = Field(..., description="五类类别图 PNG data URL（L 灰度或 R 通道）")
    attributes: Dict[str, Any] = Field(default_factory=dict)
    prefill_source: str = "none"
    duration_ms: Optional[int] = None


class ReviewRequest(BaseModel):
    note: str = ""


class StatusRequest(BaseModel):
    status: str
    reasons: List[str] = Field(default_factory=list)


class BenchmarkRequest(BaseModel):
    benchmark: bool


class SnapRequest(BaseModel):
    labels: str


class LegacyImportRequest(BaseModel):
    rights_confirmed: bool = False


@router.get("/choices")
async def choices(admin_user: User = Depends(get_current_admin_user)):
    return {**attribute_rules.choices(), "body_sites": taxonomy()}


@router.get("/stats")
async def stats(admin_user: User = Depends(get_current_admin_user), db: Session = Depends(get_db)):
    return tasks.stats(db)


@router.get("/progress")
async def progress(admin_user: User = Depends(get_current_admin_user), db: Session = Depends(get_db)):
    return progress_service.progress(db)


@router.get("/tasks")
async def list_tasks(
    status: str = Query("all"),
    origin: Optional[str] = Query(None),
    group: Optional[str] = Query(None),
    benchmark: Optional[bool] = Query(None),
    escalate: bool = Query(False),
    mine: bool = Query(False),
    external: Optional[str] = Query(None, pattern="^(any|pmc_oa|wikimedia_commons)$"),
    sort: str = Query("queue"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    filters = {"status": status, "origin": origin, "group": group, "benchmark": benchmark,
               "escalate": escalate, "mine": mine, "external": external, "sort": sort}
    return tasks.list_tasks(db, admin_user.id, filters, limit, offset)


@router.get("/tasks/{label_id:int}")
async def task_detail(label_id: int, admin_user: User = Depends(get_current_admin_user), db: Session = Depends(get_db)):
    label = _task(db, label_id)
    try:
        return tasks.detail(db, label, admin_user.id)
    except RGBSegmentationError as exc:
        _fail(exc)


@router.get("/tasks/{label_id:int}/image")
async def task_image(
    label_id: int,
    size: str = Query("full", pattern="^(full|thumb)$"),
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    label = _task(db, label_id)
    try:
        image, _ = sources.canonical(label)
    except RGBSegmentationError as exc:
        _fail(exc)
    headers = {"Cache-Control": "private, no-store"}
    if size == "full":
        return Response(content=image, media_type="image/png", headers=headers)
    from PIL import Image

    with Image.open(io.BytesIO(image)) as photo:
        photo.thumbnail((240, 240))
        out = io.BytesIO()
        photo.convert("RGB").save(out, format="JPEG", quality=80)
    return Response(content=out.getvalue(), media_type="image/jpeg", headers=headers)


@router.get("/tasks/{label_id:int}/submissions/{submission_id:int}/labels")
async def submission_labels(
    label_id: int, submission_id: int,
    admin_user: User = Depends(get_current_admin_user), db: Session = Depends(get_db),
):
    from web.backend.models.label_submission import LabelSubmission
    from web.backend.services.labeling import class_map

    _task(db, label_id)
    row = db.get(LabelSubmission, submission_id)
    if row is None or row.image_label_id != label_id:
        raise HTTPException(status_code=404, detail="提交版本不存在")
    try:
        return {"labels": class_map.to_data_url(submissions.read_snapshot(label_id, row.revision))}
    except RGBSegmentationError as exc:
        _fail(exc)


@router.post("/tasks/{label_id:int}/submissions")
async def submit(
    label_id: int, body: SubmitRequest,
    admin_user: User = Depends(get_current_admin_user), db: Session = Depends(get_db),
):
    label = _task(db, label_id)
    try:
        row = submissions.submit(db, label, admin_user.id, body.labels, body.attributes,
                                 body.prefill_source, body.duration_ms)
        db.commit()
    except RGBSegmentationError as exc:
        db.rollback()
        _fail(exc)
    return {"submission_id": row.id, "status": label.label_status}


@router.post("/submissions/{submission_id:int}/approve")
async def approve(
    submission_id: int, body: ReviewRequest,
    admin_user: User = Depends(get_current_admin_user), db: Session = Depends(get_db),
):
    try:
        row = workflow.approve(db, submission_id, admin_user.id, body.note)
        db.commit()
    except RGBSegmentationError as exc:
        db.rollback()
        _fail(exc)
    return {"submission_id": row.id, "review_mode": row.review_mode}


@router.post("/submissions/{submission_id:int}/return")
async def return_submission(
    submission_id: int, body: ReviewRequest,
    admin_user: User = Depends(get_current_admin_user), db: Session = Depends(get_db),
):
    try:
        row = workflow.return_submission(db, submission_id, admin_user.id, body.note)
        db.commit()
    except RGBSegmentationError as exc:
        db.rollback()
        _fail(exc)
    return {"submission_id": row.id, "status": row.status}


@router.post("/tasks/{label_id:int}/status")
async def set_status(
    label_id: int, body: StatusRequest,
    admin_user: User = Depends(get_current_admin_user), db: Session = Depends(get_db),
):
    label = _task(db, label_id)
    try:
        workflow.set_status(db, label, admin_user.id, body.status, body.reasons)
        db.commit()
    except RGBSegmentationError as exc:
        db.rollback()
        _fail(exc)
    return {"status": label.label_status}


@router.post("/tasks/{label_id:int}/benchmark")
async def set_benchmark(
    label_id: int, body: BenchmarkRequest,
    admin_user: User = Depends(get_current_admin_user), db: Session = Depends(get_db),
):
    label = _task(db, label_id)
    try:
        workflow.set_benchmark(db, label, admin_user.id, body.benchmark)
        db.commit()
    except RGBSegmentationError as exc:
        db.rollback()
        _fail(exc)
    return {"benchmark": bool(label.benchmark), "status": label.label_status}


@router.post("/tasks/{label_id:int}/snap")
async def snap(
    label_id: int, body: SnapRequest,
    admin_user: User = Depends(get_current_admin_user), db: Session = Depends(get_db),
):
    label = _task(db, label_id)
    try:
        return {"labels": await anyio.to_thread.run_sync(tasks.edge_snap, label, body.labels)}
    except RGBSegmentationError as exc:
        _fail(exc)


@router.post("/tasks/{label_id:int}/redraft")
async def redraft(label_id: int, admin_user: User = Depends(get_current_admin_user), db: Session = Depends(get_db)):
    label = _task(db, label_id)
    if label.benchmark:
        raise HTTPException(status_code=409, detail="基准集任务须盲标，不提供 AI 初稿")
    try:
        return await anyio.to_thread.run_sync(tasks.redraft, label)
    except RGBSegmentationError as exc:
        _fail(exc)


@router.post("/sync")
async def sync_diary(admin_user: User = Depends(get_current_admin_user), db: Session = Depends(get_db)):
    """Project diary RGB records into tasks; only consented ones become visible."""
    from web.backend.services.rgb_segmentation.label_sync import sync_rgb_label

    synced = 0
    for assessment in db.query(VASIAssessment).filter_by(assessment_source="rgb-tools-v1").all():
        try:
            label = sync_rgb_label(db, assessment)
        except RGBSegmentationError:
            logger.warning("Skipped diary sync for assessment %s", assessment.id)
            continue
        if label is not None:
            synced += 1
            tasks.refresh_priority(db, label)
    db.commit()
    return {"synced": synced, **tasks.stats(db)}


@router.post("/uploads")
async def upload(
    files: List[UploadFile] = File(...),
    source_note: str = Form(...),
    subject_ref: Optional[str] = Form(None),
    rights_confirmed: bool = Form(False),
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    payload = []
    for item in files[: uploads.MAX_FILES + 1]:
        data = await item.read(MAX_UPLOAD_BYTES + 1)
        payload.append((item.filename or "image", data))
    try:
        result = await anyio.to_thread.run_sync(
            lambda: uploads.upload_photos(db, admin_user.id, payload, source_note, subject_ref, rights_confirmed)
        )
        db.commit()
    except RGBSegmentationError as exc:
        db.rollback()
        _fail(exc)
    return result


@router.post("/legacy/import")
async def import_legacy(
    body: LegacyImportRequest, admin_user: User = Depends(get_current_admin_user), db: Session = Depends(get_db),
):
    result = await anyio.to_thread.run_sync(
        lambda: uploads.import_all_legacy(db, admin_user.id, body.rights_confirmed)
    )
    db.commit()
    return result

"""Owner-scoped preview for the diary's Bailian assessment."""

import json
import time
import logging

from fastapi import Depends, FastAPI, File, Form, HTTPException, Response, UploadFile
from sqlalchemy.orm import Session

from web.backend.database.database import get_db
from web.backend.database.models import User
from web.backend.exceptions import RGBSegmentationError
from web.backend.services.auth import get_current_user
from web.backend.services.consent import HEALTH_CONSENT_REQUIRED_DETAIL, health_data_consent_missing
from web.backend.services.rgb_segmentation import artifacts, bailian_consent as consent
from web.backend.services.rgb_segmentation.jobs import (
    cancel_job, capture_context, create_job, owned_job, serialize_job,
)

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
logger = logging.getLogger(__name__)
PREFIX = "/api/vasi/bailian-preview"
HEARTBEAT = consent.HEARTBEAT


def require_preview_user(user: User = Depends(get_current_user)):
    if not consent.allowed(user.id):
        raise HTTPException(status_code=404)
    return user


def available():
    try:
        return bool(consent.provider_key()) and time.time() - float(HEARTBEAT.read_text()) < 12
    except (OSError, ValueError):
        return False


def error_response(exc):
    return HTTPException(exc.http_status, str(exc), headers={"X-RGB-Error-Code": exc.code})


@app.get(PREFIX + "/capabilities")
def capabilities(user: User = Depends(require_preview_user)):
    return {"ready": available(), "notice": consent.NOTICE, "model": consent.MODEL,
            "provider": "阿里云百炼", "privacy_url": consent.PRIVACY_URL}


@app.post(PREFIX + "/jobs", status_code=202)
def submit(
    image: UploadFile = File(...), body_site: str = Form(...), idempotency_key: str = Form(...),
    notice: str = Form(...), context: str = Form("{}"),
    user: User = Depends(require_preview_user), db: Session = Depends(get_db),
):
    if notice != consent.NOTICE:
        raise HTTPException(409, "分析说明已更新，请刷新页面后再试")
    if health_data_consent_missing(db, user.id):
        raise HTTPException(403, HEALTH_CONSENT_REQUIRED_DETAIL)
    if not available():
        raise HTTPException(503, "百炼试测尚未接通，可继续本地分析")
    try:
        supplied = json.loads(context) if len(context) <= 2500 else None
        if not isinstance(supplied, dict):
            raise ValueError()
    except ValueError:
        raise HTTPException(400, "照片信息无效") from None
    source = image.file.read(10 * 1024 * 1024 + 1)
    try:
        grant = consent.authorization(source)
        prepared = capture_context(db, user.id, body_site, supplied)
        prepared["external_analysis"] = grant
        return serialize_job(create_job(
            db, user.id, idempotency_key, source, body_site,
            {**supplied, "external_analysis": grant}, context_override=prepared,
        ))
    except RGBSegmentationError as exc:
        raise error_response(exc) from None
    except Exception as exc:
        db.rollback()
        logger.error("Bailian job admission failed (%s)", type(exc).__name__)
        raise HTTPException(503, "百炼分析暂不可用，可继续本地分析") from None


def preview_job(db, job_id, user):
    job = owned_job(db, job_id, user.id)
    if not json.loads(job.context_json).get("external_analysis"):
        raise RGBSegmentationError("NOT_FOUND", "记录不存在", 404)
    return job


@app.get(PREFIX + "/jobs/{job_id}")
def status(job_id: str, user: User = Depends(require_preview_user), db: Session = Depends(get_db)):
    try:
        return serialize_job(preview_job(db, job_id, user))
    except RGBSegmentationError as exc:
        raise error_response(exc) from None


@app.get(PREFIX + "/jobs/{job_id}/fusion/{revision}/{kind}")
def fusion_layer(
    job_id: str, revision: str, kind: str,
    user: User = Depends(require_preview_user), db: Session = Depends(get_db),
):
    try:
        job = preview_job(db, job_id, user)
        state = json.loads(job.result_json or "{}")
        if (job.state != "completed" or state.get("review_state") != "pending"
                or state.get("mask_revision") != revision
                or kind not in artifacts.FUSION_KINDS | {"lesion"}):
            raise RGBSegmentationError("NOT_FOUND", "试测涂层不存在", 404)
        raw = artifacts.read_artifact(job_id, revision, kind, fusion_preview=True)
        from web.backend.services.annotation_contract import encode_layer
        from web.backend.services.rgb_segmentation.images import decode_binary

        image = artifacts.read_manifest(job_id, revision)["metadata"]["image"]
        mask = decode_binary(raw, (image["height"], image["width"]))
        return Response(json.dumps({"mask_data_url": encode_layer(mask, (0, 170, 100))}),
                        media_type="application/json", headers={"Cache-Control": "private, no-store"})
    except RGBSegmentationError as exc:
        raise error_response(exc) from None


@app.post(PREFIX + "/jobs/{job_id}/cancel")
def cancel(job_id: str, user: User = Depends(require_preview_user), db: Session = Depends(get_db)):
    try:
        preview_job(db, job_id, user)
        return serialize_job(cancel_job(db, job_id, user.id))
    except RGBSegmentationError as exc:
        raise error_response(exc) from None


@app.post(PREFIX + "/requests/{request_key}/cancel")
def cancel_request(request_key: str, user: User = Depends(require_preview_user), db: Session = Depends(get_db)):
    from web.backend.models.rgb_segmentation import RGBSegmentationJob

    job = db.query(RGBSegmentationJob).filter_by(user_id=user.id, idempotency_key=request_key).first()
    if job is None:
        raise HTTPException(404, "记录不存在")
    return cancel(job.id, user, db)

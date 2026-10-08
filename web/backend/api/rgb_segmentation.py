"""Private RGB segmentation API; no raw model result or arbitrary URL submission."""

import json
import logging
import time
from typing import List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from web.backend.database.database import get_db
from web.backend.database.models import User
from web.backend.exceptions import RGBSegmentationError
from web.backend.models.rgb_segmentation import RGBSegmentationJob
from web.backend.services.auth import get_current_user
from web.backend.services.rgb_segmentation import artifacts
from web.backend.services.rgb_segmentation.jobs import (
    create_job,
    owned_job,
    cancel_job,
    serialize_job,
)
from web.backend.services.rgb_segmentation.review import review_job

router = APIRouter()
logger = logging.getLogger(__name__)


def worker_ready() -> bool:
    try:
        heartbeat = json.loads((artifacts.ROOT / "worker-heartbeat.json").read_text())
        return time.time() - float(heartbeat["at"]) < 10
    except (OSError, ValueError, KeyError, TypeError):
        return False


def domain_http(exc: RGBSegmentationError) -> HTTPException:
    return HTTPException(
        status_code=exc.http_status,
        detail=str(exc),
        headers={"X-RGB-Error-Code": exc.code},
    )


@router.get("/rgb-capabilities")
def capabilities():
    return {
        "protocol": "skin-seg-v2",
        "worker_ready": worker_ready(),
        "manual_review_required": True,
        "automatic_model_validated": False,
        "input_type": "rgb_photo",
    }


@router.post("/segmentation-jobs", status_code=202)
def submit_job(
    image: UploadFile = File(...),
    body_site: str = Form(...),
    idempotency_key: str = Form(...),
    context: str = Form("{}"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not worker_ready():
        raise HTTPException(status_code=503, detail="图像分析服务正在准备，请稍后重试")
    try:
        source = image.file.read(10 * 1024 * 1024 + 1)
        if len(context) > 2500:
            raise RGBSegmentationError("INVALID_INPUT", "照片信息过长")
        supplied = json.loads(context)
        if not isinstance(supplied, dict):
            raise RGBSegmentationError("INVALID_INPUT", "照片信息无效")
        return serialize_job(
            create_job(
                db, current_user.id, idempotency_key, source, body_site, supplied
            )
        )
    except RGBSegmentationError as exc:
        raise domain_http(exc)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="照片信息无效")
    except Exception:
        db.rollback()
        logger.exception("RGB job admission failed")
        raise HTTPException(status_code=503, detail="图像分析服务暂不可用，请稍后重试")


@router.get("/segmentation-jobs/{job_id}")
def get_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return serialize_job(owned_job(db, job_id, current_user.id))
    except RGBSegmentationError as exc:
        raise domain_http(exc)


@router.post("/segmentation-jobs/{job_id}/cancel")
def cancel(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return serialize_job(cancel_job(db, job_id, current_user.id))
    except RGBSegmentationError as exc:
        raise domain_http(exc)


@router.get("/segmentation-jobs/{job_id}/artifacts/{revision}/{kind}")
def artifact(
    job_id: str,
    revision: str,
    kind: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        owned_job(db, job_id, current_user.id)
        value = artifacts.read_artifact(job_id, revision, kind)
        return Response(
            content=value,
            media_type="image/png",
            headers={
                "Cache-Control": "private, no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )
    except RGBSegmentationError as exc:
        raise domain_http(exc)


class ReviewRequest(BaseModel):
    base_revision: str = Field(..., min_length=64, max_length=64)
    skin_mask: str = Field(..., max_length=8 * 1024 * 1024)
    lesion_mask: str = Field(..., max_length=8 * 1024 * 1024)
    acknowledged: bool = False


@router.patch("/segmentation-jobs/{job_id}/review")
def review(
    job_id: str,
    request: ReviewRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return review_job(
            db,
            job_id,
            current_user.id,
            request.base_revision,
            request.skin_mask,
            request.lesion_mask,
            request.acknowledged,
        )
    except RGBSegmentationError as exc:
        db.rollback()
        raise domain_http(exc)
    except Exception:
        db.rollback()
        logger.exception("RGB reference update failed")
        raise HTTPException(status_code=503, detail="标注保存暂未完成，请重试")


class RefinementPoint(BaseModel):
    x: float = Field(..., ge=0, le=1)
    y: float = Field(..., ge=0, le=1)
    label: int = Field(1, ge=0, le=1)


class RefinementRequest(BaseModel):
    idempotency_key: str = Field(..., min_length=8, max_length=80)
    base_revision: str = Field(..., min_length=64, max_length=64)
    skin_mask: str = Field(..., max_length=8 * 1024 * 1024)
    points: List[RefinementPoint] = Field(..., min_length=1, max_length=32)
    box: Optional[List[float]] = None


@router.post("/segmentation-jobs/{job_id}/refine", status_code=202)
def refine(
    job_id: str,
    request: RefinementRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not worker_ready():
        raise HTTPException(status_code=503, detail="图像分析服务正在准备，请稍后重试")
    from web.backend.services.rgb_segmentation.refinement import enqueue_refinement

    try:
        job = enqueue_refinement(
            db,
            job_id,
            current_user.id,
            request.idempotency_key,
            request.base_revision,
            request.skin_mask,
            [p.model_dump() for p in request.points],
            request.box,
        )
        return serialize_job(job)
    except RGBSegmentationError as exc:
        db.rollback()
        raise domain_http(exc)
    except Exception:
        db.rollback()
        logger.exception("RGB refinement admission failed")
        raise HTTPException(status_code=503, detail="交互分割暂不可用，可使用画笔调整")


class OutlineRequest(BaseModel):
    idempotency_key: str = Field(..., min_length=8, max_length=80)
    base_revision: str = Field(..., min_length=64, max_length=64)


@router.post("/segmentation-jobs/{job_id}/outline", status_code=202)
def outline(
    job_id: str,
    request: OutlineRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not worker_ready():
        raise HTTPException(status_code=503, detail="图像分析服务正在准备，请稍后重试")
    from web.backend.services.rgb_segmentation.outline import enqueue_outline

    try:
        return serialize_job(
            enqueue_outline(
                db, job_id, current_user.id, request.idempotency_key, request.base_revision
            )
        )
    except RGBSegmentationError as exc:
        db.rollback()
        raise domain_http(exc)
    except Exception:
        db.rollback()
        logger.exception("RGB outline admission failed")
        raise HTTPException(status_code=503, detail="视觉粗定位暂不可用，请稍后重试")


@router.get("/segmentation-jobs/{job_id}/overlays/{revision}/{kind}")
def overlay(
    job_id: str,
    revision: str,
    kind: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from web.backend.services.rgb_segmentation.images import decode_binary
    from web.backend.services.annotation_contract import encode_layer

    try:
        owned_job(db, job_id, current_user.id)
        if kind not in {"skin", "lesion", "uncertain", "excluded"}:
            raise RGBSegmentationError("NOT_FOUND", "标注不存在", 404)
        metadata = artifacts.read_manifest(job_id, revision)["metadata"]["image"]
        mask = decode_binary(
            artifacts.read_artifact(job_id, revision, kind),
            (metadata["height"], metadata["width"]),
        )
        colors = {
            "skin": (96, 165, 250),
            "lesion": (0, 170, 100),
            "uncertain": (240, 143, 0),
            "excluded": (100, 116, 139),
        }
        return {"mask_data_url": encode_layer(mask, colors[kind]), "revision": revision}
    except RGBSegmentationError as exc:
        raise domain_http(exc)


@router.post("/segmentation-requests/{key}/cancel")
def cancel_request(
    key: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        job = (
            db.query(RGBSegmentationJob)
            .filter_by(user_id=current_user.id, idempotency_key=key)
            .first()
        )
        return (
            serialize_job(cancel_job(db, job.id, current_user.id))
            if job
            else {"cancelled": False}
        )
    except RGBSegmentationError as exc:
        raise domain_http(exc)

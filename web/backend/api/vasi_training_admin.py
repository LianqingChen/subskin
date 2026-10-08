"""
VASI 模型训练管理 API — U-Net 训练管道的管理端点

提供:
  - 训练样本列表（三图走 image_label_id 关联的现有端点）
  - 触发训练 / 训练进度 / 训练历史
  - 模型版本手动上线（activate）
"""
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from web.backend.database.database import get_db
from web.backend.api.image_label import anonymize_label_username as _mask_username
from web.backend.database.models import User
from web.backend.models.image_label import ImageLabel
from web.backend.models.vasi import VasiModelVersion, VasiTrainingRun, VasiTrainingSample
from web.backend.services.unified_auth import get_current_admin_user

router = APIRouter()
logger = logging.getLogger(__name__)


def _format_dt(dt) -> Optional[str]:
    return dt.strftime("%Y-%m-%d %H:%M") if dt else None


def _parse_metrics(raw: Optional[str]) -> dict:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


def _run_to_dict(run: VasiTrainingRun) -> dict:
    return {
        "id": run.id,
        "status": run.status,
        "progress": run.progress,
        "stage": run.stage,
        "train_size": run.train_size,
        "test_size": run.test_size,
        "baseline_metrics": _parse_metrics(run.baseline_metrics_json),
        "new_metrics": _parse_metrics(run.new_metrics_json),
        "version_tag": run.version_tag,
        "error": run.error,
        "started_by": run.started_by,
        "created_at": _format_dt(run.created_at),
        "finished_at": _format_dt(run.finished_at),
    }


# ── 训练样本列表 ──────────────────────────────────────────────────


class TrainingSampleItem(BaseModel):
    id: int
    image_label_id: Optional[int] = None
    image_hash: Optional[str] = None
    body_site: Optional[str] = None
    vitiligo_type: Optional[str] = None
    stage: Optional[str] = None
    quality_level: Optional[str] = None
    sample_source: Optional[str] = None
    dice_score: Optional[float] = None
    has_user_mask: bool = False
    has_admin_mask: bool = False
    username: Optional[str] = None
    created_at: Optional[str] = None


class TrainingSampleListResponse(BaseModel):
    total: int
    items: list[TrainingSampleItem]


@router.get("/admin/training/samples", response_model=TrainingSampleListResponse)
async def list_training_samples(
    body_site: Optional[str] = Query(None, description="按身体部位筛选"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """训练样本列表 — 图片通过 image_label_id 走现有三图端点加载"""
    query = (
        db.query(VasiTrainingSample, ImageLabel, User.username)
        .outerjoin(ImageLabel, VasiTrainingSample.image_label_id == ImageLabel.id)
        .outerjoin(User, ImageLabel.original_user_id == User.id)
        .filter(VasiTrainingSample.is_active == True)  # noqa: E712
    )
    if body_site:
        query = query.filter(VasiTrainingSample.body_site == body_site)

    total = query.count()
    rows = (
        query.order_by(VasiTrainingSample.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    items = []
    for sample, label, username in rows:
        items.append(TrainingSampleItem(
            id=sample.id,
            image_label_id=sample.image_label_id,
            image_hash=sample.image_hash,
            body_site=sample.body_site,
            vitiligo_type=sample.vitiligo_type,
            stage=sample.stage,
            quality_level=sample.quality_level,
            sample_source=sample.sample_source,
            dice_score=sample.dice_score,
            has_user_mask=bool(sample.user_mask_b64),
            has_admin_mask=bool(sample.admin_mask_b64),
            # 2026-08-30 隐私加固：训练样本列表展示匿名编号
            username=_mask_username(username),
            created_at=_format_dt(sample.created_at),
        ))

    return TrainingSampleListResponse(total=total, items=items)


# ── 训练触发与状态 ────────────────────────────────────────────────


@router.post("/admin/training/train")
async def start_training(
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """触发 U-Net 模型训练（后台线程执行，前端轮询 status）"""
    from web.backend.services import vasi_model_trainer

    usable = vasi_model_trainer.count_usable_samples(db)
    if usable < vasi_model_trainer.MIN_SAMPLES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"有效训练样本不足（需≥{vasi_model_trainer.MIN_SAMPLES}，当前{usable}），"
                "请先完成打标并添加至训练样本"
            ),
        )

    run_id, error = vasi_model_trainer.start_training_run(started_by=admin_user.id)
    if error:
        raise HTTPException(status_code=409, detail=error)

    return {"status": "ok", "run_id": run_id}


@router.get("/admin/training/train/status")
async def get_training_status(
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """当前训练进度 — running 标志 + 最新 run 详情"""
    from web.backend.services import vasi_model_trainer

    run = db.query(VasiTrainingRun).order_by(VasiTrainingRun.id.desc()).first()
    return {
        "running": vasi_model_trainer.is_training_active(),
        "run": _run_to_dict(run) if run else None,
    }


@router.get("/admin/training/runs")
async def list_training_runs(
    limit: int = Query(10, ge=1, le=50),
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """训练历史（含前后对比指标）"""
    runs = (
        db.query(VasiTrainingRun)
        .order_by(VasiTrainingRun.id.desc())
        .limit(limit)
        .all()
    )
    return {"items": [_run_to_dict(r) for r in runs]}


# ── 模型版本上线 ──────────────────────────────────────────────────


class ActivateResponse(BaseModel):
    status: str
    version_tag: str
    metrics: dict


@router.post("/admin/training/models/{version_id}/activate", response_model=ActivateResponse)
async def activate_model_version(
    version_id: int,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """手动上线指定模型版本 — 立即对测评/白斑报告的分割链路生效"""
    from datetime import datetime

    from web.backend.services.vasi_segmentation import reset_unet_cache

    version = db.query(VasiModelVersion).filter(VasiModelVersion.id == version_id).first()
    if not version:
        raise HTTPException(status_code=404, detail="模型版本不存在")
    if version.evolution_layer != "model_weights":
        raise HTTPException(status_code=400, detail="仅支持上线 model_weights 类型版本")
    if version.is_active:
        return ActivateResponse(
            status="already_active",
            version_tag=version.version_tag,
            metrics=_parse_metrics(version.metrics_json),
        )

    # 下线旧的 active model_weights 版本
    old_versions = db.query(VasiModelVersion).filter(
        VasiModelVersion.is_active == True,  # noqa: E712
        VasiModelVersion.evolution_layer == "model_weights",
        VasiModelVersion.id != version_id,
    ).all()
    for old in old_versions:
        old.is_active = False

    version.is_active = True
    version.deployed_at = datetime.utcnow()
    version.deployed_by = admin_user.id
    db.commit()

    reset_unet_cache()
    logger.info("Model version %s activated by admin %s", version.version_tag, admin_user.id)

    return ActivateResponse(
        status="ok",
        version_tag=version.version_tag,
        metrics=_parse_metrics(version.metrics_json),
    )


@router.post("/admin/training/models/{version_id}/deactivate", response_model=ActivateResponse)
async def deactivate_model_version(
    version_id: int,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """手动下线指定模型版本 — 识别立即回退到 SAM→CV 回退链路"""
    from web.backend.services.vasi_segmentation import reset_unet_cache

    version = db.query(VasiModelVersion).filter(VasiModelVersion.id == version_id).first()
    if not version:
        raise HTTPException(status_code=404, detail="模型版本不存在")
    if version.evolution_layer != "model_weights":
        raise HTTPException(status_code=400, detail="仅支持下线 model_weights 类型版本")
    if not version.is_active:
        return ActivateResponse(
            status="already_inactive",
            version_tag=version.version_tag,
            metrics=_parse_metrics(version.metrics_json),
        )

    version.is_active = False
    db.commit()

    reset_unet_cache()
    logger.info("Model version %s deactivated by admin %s", version.version_tag, admin_user.id)

    return ActivateResponse(
        status="ok",
        version_tag=version.version_tag,
        metrics=_parse_metrics(version.metrics_json),
    )

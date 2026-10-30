"""Admin: RGB gold review → dataset export → training → gated registration."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from web.backend.database.database import get_db
from web.backend.database.models import User
from web.backend.exceptions import RGBSegmentationError
from web.backend.models.image_label import ImageLabel
from web.backend.services.rgb_segmentation import dataset_pipeline as pipeline
from web.backend.services.rgb_segmentation.label_sync import is_rgb_label
from web.backend.services.unified_auth import get_current_admin_user

router = APIRouter()


def _fail(exc: RGBSegmentationError):
    raise HTTPException(status_code=exc.http_status, detail=str(exc))


def _rgb_label(db: Session, label_id: int) -> ImageLabel:
    label = db.query(ImageLabel).filter(ImageLabel.id == label_id).first()
    if not label or not is_rgb_label(label):
        raise HTTPException(status_code=404, detail="不是新流程（RGB）标注")
    return label


class ApproveRequest(BaseModel):
    label_source: str = Field("admin_reviewed", description="admin_reviewed 或 clinician")


class TrainRequest(BaseModel):
    dataset_id: str
    epochs: int = 30


@router.get("/admin/rgb-labels/{label_id:int}/gold")
async def get_gold(label_id: int, admin_user: User = Depends(get_current_admin_user), db: Session = Depends(get_db)):
    return pipeline.gold_state(db, _rgb_label(db, label_id))


@router.post("/admin/rgb-labels/{label_id:int}/gold")
async def approve(label_id: int, body: ApproveRequest, admin_user: User = Depends(get_current_admin_user)):
    """Retired 2026-10-21: gold now comes only from reviewing a versioned submission
    (``/admin/labeling/submissions/{id}/approve``)."""
    raise HTTPException(status_code=410, detail="请在打标工作台复核通过提交版本")


@router.delete("/admin/rgb-labels/{label_id:int}/gold")
async def revoke(label_id: int, admin_user: User = Depends(get_current_admin_user), db: Session = Depends(get_db)):
    label = _rgb_label(db, label_id)
    pipeline.revoke_gold(db, label, admin_user.id)
    db.commit()
    return pipeline.gold_state(db, label)


@router.post("/admin/rgb-labels/{label_id:int}/redraft")
async def redraft(label_id: int, admin_user: User = Depends(get_current_admin_user), db: Session = Depends(get_db)):
    """Re-run today's automatic draft on the canonical photo (admin prefill only)."""
    import anyio
    from web.backend.services.annotation_contract import encode_layer
    from web.backend.services.assessment_measurement import read_details
    from web.backend.services.rgb_segmentation import artifacts
    from web.backend.services.rgb_segmentation.images import canonical_image
    from web.backend.services.rgb_segmentation.inference import infer_rgb

    sync = read_details(_rgb_label(db, label_id).ai_details).get("rgb_sync") or {}
    try:
        image = artifacts.read_artifact(sync["job_id"], sync["ai_revision"], "image")
    except (KeyError, RGBSegmentationError):
        raise HTTPException(status_code=404, detail="原图已过期或不可用")

    def work():
        rgb, _ = canonical_image(image)
        return infer_rgb(rgb)

    masks, meta = await anyio.to_thread.run_sync(work)
    return {
        "skin_mask_data": encode_layer(masks["skin"] & ~masks["lesion"], (96, 165, 250)),
        "mask_data": encode_layer(masks["lesion"], (236, 72, 153)),
        "uncertain_mask_data": encode_layer(masks["uncertain"], (240, 143, 0)),
        "source": meta.get("source"),
        "check": meta.get("draft_check"),
    }


@router.get("/admin/rgb-training/status")
async def status(admin_user: User = Depends(get_current_admin_user), db: Session = Depends(get_db)):
    return pipeline.dataset_status(db)


@router.post("/admin/rgb-training/datasets")
async def export(admin_user: User = Depends(get_current_admin_user), db: Session = Depends(get_db)):
    try:
        return pipeline.export_dataset(db, admin_user.id)
    except RGBSegmentationError as exc:
        _fail(exc)


@router.post("/admin/rgb-training/runs")
async def train(body: TrainRequest, admin_user: User = Depends(get_current_admin_user)):
    try:
        return pipeline.start_training(body.dataset_id, admin_user.id, body.epochs)
    except RGBSegmentationError as exc:
        _fail(exc)


@router.delete("/admin/rgb-training/runs/{run_id}")
async def cancel(run_id: str, admin_user: User = Depends(get_current_admin_user)):
    try:
        pipeline.cancel_training(run_id)
    except RGBSegmentationError as exc:
        _fail(exc)
    return {"status": "cancelling"}


@router.post("/admin/rgb-training/runs/{run_id}/register")
async def register(run_id: str, admin_user: User = Depends(get_current_admin_user)):
    try:
        return pipeline.register_run(run_id, admin_user.id)
    except RGBSegmentationError as exc:
        _fail(exc)


@router.post("/admin/rgb-training/registry/disable")
async def disable(admin_user: User = Depends(get_current_admin_user)):
    return pipeline.disable_registry(admin_user.id)

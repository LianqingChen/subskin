"""
图片打标管理 API — 管理员对用户上传的白斑图片进行专业标注

提供:
  - 图片列表（支持筛选、分页）
  - 单张图片详情（含 AI/用户/管理员三级标注数据）
  - 管理员打标（提交最终审核标注）
  - 批量操作（跳过、标记不适合训练）
  - 训练数据导出
  - 隐私保护：用户删除的图片仍保留但标记不可展示
"""

import hashlib
import json
import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import and_, case, func, or_
from sqlalchemy.orm import Session, joinedload

from web.backend.database.database import get_db
from web.backend.database.models import User
from web.backend.models.image_label import (
    BODY_SITE_CHOICES,
    VITILIGO_TYPE_CHOICES,
    STAGE_CHOICES,
    ImageLabel,
    ImageLabelAnnotation,
    ImageLabelLog,
)
from web.backend.models.vasi import VASIAssessment, ImageQualityTag
from web.backend.services.unified_auth import get_current_admin_user

router = APIRouter()
logger = logging.getLogger(__name__)


# ── Pydantic Schemas ──────────────────────────────────────────────


class AnnotationItem(BaseModel):
    source: str = Field(..., description="ai/user/admin")
    region_index: int = 0
    body_site: Optional[str] = None
    is_vitiligo: Optional[bool] = None
    vitiligo_type: Optional[str] = None
    vitiligo_stage: Optional[str] = None
    area_percentage: Optional[float] = None
    depigmentation_level: Optional[float] = None
    region_contour: Optional[str] = None
    region_bbox: Optional[str] = None
    mask_data: Optional[str] = None
    skin_mask_data: Optional[str] = None
    confidence: Optional[float] = None
    notes: Optional[str] = None


class ImageLabelDetail(BaseModel):
    id: int
    assessment_id: Optional[int] = None
    original_user_id: Optional[int] = None
    image_url: str
    image_key: Optional[str] = None
    image_hash: Optional[str] = None
    is_user_deleted: bool = False
    is_face_detected: bool = False
    is_face_blurred: bool = False
    is_phi_removed: bool = False

    ai_body_site: Optional[str] = None
    ai_is_vitiligo: Optional[bool] = None
    ai_vitiligo_type: Optional[str] = None
    ai_vitiligo_stage: Optional[str] = None
    ai_area_percentage: Optional[float] = None
    ai_vasi_score: Optional[float] = None
    ai_confidence: Optional[float] = None

    user_body_site: Optional[str] = None
    user_is_vitiligo: Optional[bool] = None
    user_vitiligo_type: Optional[str] = None
    user_area_percentage: Optional[float] = None
    user_vasi_score: Optional[float] = None
    user_depigmentation_level: Optional[float] = None
    user_notes: Optional[str] = None

    admin_body_site: Optional[str] = None
    admin_is_vitiligo: Optional[bool] = None
    admin_vitiligo_type: Optional[str] = None
    admin_vitiligo_stage: Optional[str] = None
    admin_area_percentage: Optional[float] = None
    admin_vasi_score: Optional[float] = None
    admin_depigmentation_level: Optional[float] = None
    admin_notes: Optional[str] = None
    labeled_by: Optional[int] = None
    labeled_at: Optional[str] = None

    label_status: str = "pending"
    training_eligible: bool = False
    training_set_split: Optional[str] = None

    annotated_image_path: Optional[str] = None
    annotated_image_url: Optional[str] = None
    annotated_layers_path: Optional[str] = None

    annotations: List[AnnotationItem] = []

    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


class ImageLabelListItem(BaseModel):
    id: int
    assessment_id: Optional[int] = None
    image_url: str
    image_hash: Optional[str] = None
    body_site: Optional[str] = None
    ai_is_vitiligo: Optional[bool] = None
    ai_vitiligo_type: Optional[str] = None
    ai_area_percentage: Optional[float] = None
    admin_is_vitiligo: Optional[bool] = None
    admin_vitiligo_type: Optional[str] = None
    admin_area_percentage: Optional[float] = None
    label_status: str = "pending"
    is_user_deleted: bool = False
    training_eligible: bool = False
    created_at: Optional[str] = None
    labeled_at: Optional[str] = None


class ImageLabelListResponse(BaseModel):
    total: int
    items: List[ImageLabelListItem]


class AdminLabelRequest(BaseModel):
    body_site: Optional[str] = Field(None, description="管理员标注的身体部位")
    is_vitiligo: Optional[bool] = Field(None, description="管理员标注是否为白癜风")
    vitiligo_type: Optional[str] = Field(None, description="管理员标注白癜风分型")
    vitiligo_stage: Optional[str] = Field(None, description="管理员标注病情阶段")
    area_percentage: Optional[float] = Field(None, ge=0, le=100, description="管理员标注白斑面积占比")
    vasi_score: Optional[float] = Field(None, ge=0, description="管理员标注 VASI 评分")
    depigmentation_level: Optional[float] = Field(None, ge=0, le=1, description="管理员标注脱色程度")
    notes: Optional[str] = Field(None, description="管理员备注")
    training_eligible: Optional[bool] = Field(None, description="是否适合作为训练数据")
    annotations: Optional[List[AnnotationItem]] = Field(None, description="细粒度白斑标注（可选）")
    annotated_image: Optional[str] = Field(None, description="前端合成的标注预览图 PNG data URL（base64），保存为文件并返回 URL")
    draft_mode: bool = Field(False, description="是否为保存草稿（不最终提交，仅保存进度）")


class BatchStatusRequest(BaseModel):
    ids: List[int]
    label_status: str = Field(..., description="目标状态: skipped/rejected")
    training_eligible: Optional[bool] = None


class TrainingExportRequest(BaseModel):
    split_ratio: str = Field("80/10/10", description="train/val/test 划分比例")
    include_ai: bool = Field(True, description="是否包含 AI 标注数据")
    include_user: bool = Field(True, description="是否包含用户校准数据")
    only_admin_labeled: bool = Field(True, description="是否仅导出管理员已标注的")


class TrainingExportResponse(BaseModel):
    total_count: int
    train_count: int
    val_count: int
    test_count: int
    export_url: Optional[str] = None


# ── Helpers ────────────────────────────────────────────────────────


def _format_dt(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


def _label_to_detail(label: ImageLabel) -> ImageLabelDetail:
    annotations = [
        AnnotationItem(
            source=a.source,
            region_index=a.region_index,
            body_site=a.body_site,
            is_vitiligo=a.is_vitiligo,
            vitiligo_type=a.vitiligo_type,
            vitiligo_stage=a.vitiligo_stage,
            area_percentage=a.area_percentage,
            depigmentation_level=a.depigmentation_level,
            region_contour=a.region_contour,
            region_bbox=a.region_bbox,
            mask_data=a.mask_data,
            skin_mask_data=a.skin_mask_data,
            confidence=a.confidence,
            notes=a.notes,
        )
        for a in label.annotations
    ]
    return ImageLabelDetail(
        id=label.id,
        assessment_id=label.assessment_id,
        original_user_id=label.original_user_id,
        image_url=label.image_url,
        image_key=label.image_key,
        image_hash=label.image_hash,
        is_user_deleted=label.is_user_deleted,
        is_face_detected=label.is_face_detected,
        is_face_blurred=label.is_face_blurred,
        is_phi_removed=label.is_phi_removed,
        ai_body_site=label.ai_body_site,
        ai_is_vitiligo=label.ai_is_vitiligo,
        ai_vitiligo_type=label.ai_vitiligo_type,
        ai_vitiligo_stage=label.ai_vitiligo_stage,
        ai_area_percentage=label.ai_area_percentage,
        ai_vasi_score=label.ai_vasi_score,
        ai_confidence=label.ai_confidence,
        user_body_site=label.user_body_site,
        user_is_vitiligo=label.user_is_vitiligo,
        user_vitiligo_type=label.user_vitiligo_type,
        user_area_percentage=label.user_area_percentage,
        user_vasi_score=label.user_vasi_score,
        user_depigmentation_level=label.user_depigmentation_level,
        user_notes=label.user_notes,
        admin_body_site=label.admin_body_site,
        admin_is_vitiligo=label.admin_is_vitiligo,
        admin_vitiligo_type=label.admin_vitiligo_type,
        admin_vitiligo_stage=label.admin_vitiligo_stage,
        admin_area_percentage=label.admin_area_percentage,
        admin_vasi_score=label.admin_vasi_score,
        admin_depigmentation_level=label.admin_depigmentation_level,
        admin_notes=label.admin_notes,
        labeled_by=label.labeled_by,
        labeled_at=_format_dt(label.labeled_at),
        label_status=label.label_status,
        training_eligible=label.training_eligible,
        training_set_split=label.training_set_split,
        annotated_image_path=label.annotated_image_path,
        annotated_image_url=label.annotated_image_url,
        annotated_layers_path=label.annotated_layers_path,
        annotations=annotations,
        created_at=_format_dt(label.created_at),
        updated_at=_format_dt(label.updated_at),
    )


def _log_change(db: Session, label_id: int, operator_id: int, action: str,
                field_name: Optional[str] = None,
                old_value: Optional[str] = None,
                new_value: Optional[str] = None):
    log = ImageLabelLog(
        image_label_id=label_id,
        operator_id=operator_id,
        action=action,
        field_name=field_name,
        old_value=old_value,
        new_value=new_value,
    )
    db.add(log)


# ── API Endpoints ──────────────────────────────────────────────────


@router.get("/admin/image-labels", response_model=ImageLabelListResponse)
async def list_image_labels(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    label_status: Optional[str] = Query(None, description="pending/labeled/skipped/rejected"),
    is_vitiligo: Optional[bool] = Query(None, description="AI 判定是否为白癜风"),
    body_site: Optional[str] = Query(None, description="身体部位筛选"),
    training_eligible: Optional[bool] = Query(None, description="是否适合训练"),
    is_user_deleted: Optional[bool] = Query(None, description="是否用户已删除"),
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """管理员获取图片打标列表 — 支持多维度筛选和分页"""
    query = db.query(ImageLabel)

    if label_status is not None:
        query = query.filter(ImageLabel.label_status == label_status)
    if is_vitiligo is not None:
        query = query.filter(ImageLabel.ai_is_vitiligo == is_vitiligo)
    if body_site is not None:
        query = query.filter(
            or_(
                ImageLabel.ai_body_site == body_site,
                ImageLabel.admin_body_site == body_site,
            )
        )
    if training_eligible is not None:
        query = query.filter(ImageLabel.training_eligible == training_eligible)
    if is_user_deleted is not None:
        query = query.filter(ImageLabel.is_user_deleted == is_user_deleted)

    total = query.count()
    rows = query.order_by(
        case((ImageLabel.label_status == "pending", 0), else_=1),
        ImageLabel.created_at.desc(),
    ).offset(offset).limit(limit).all()

    items = []
    for r in rows:
        items.append(ImageLabelListItem(
            id=r.id,
            assessment_id=r.assessment_id,
            image_url=r.image_url,
            image_hash=r.image_hash,
            body_site=r.admin_body_site or r.ai_body_site or r.user_body_site,
            ai_is_vitiligo=r.ai_is_vitiligo,
            ai_vitiligo_type=r.ai_vitiligo_type,
            ai_area_percentage=r.ai_area_percentage,
            admin_is_vitiligo=r.admin_is_vitiligo,
            admin_vitiligo_type=r.admin_vitiligo_type,
            admin_area_percentage=r.admin_area_percentage,
            label_status=r.label_status,
            is_user_deleted=r.is_user_deleted,
            training_eligible=r.training_eligible,
            created_at=_format_dt(r.created_at),
            labeled_at=_format_dt(r.labeled_at),
        ))

    return ImageLabelListResponse(total=total, items=items)


@router.get("/admin/image-labels/stats")
async def get_label_stats(
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """管理员打标统计概览"""
    total = db.query(func.count(ImageLabel.id)).scalar() or 0
    pending = db.query(func.count(ImageLabel.id)).filter(ImageLabel.label_status == "pending").scalar() or 0
    labeled = db.query(func.count(ImageLabel.id)).filter(ImageLabel.label_status == "labeled").scalar() or 0
    skipped = db.query(func.count(ImageLabel.id)).filter(ImageLabel.label_status == "skipped").scalar() or 0
    rejected = db.query(func.count(ImageLabel.id)).filter(ImageLabel.label_status == "rejected").scalar() or 0
    training_ready = db.query(func.count(ImageLabel.id)).filter(
        ImageLabel.training_eligible == True,
        ImageLabel.label_status == "labeled",
    ).scalar() or 0
    user_deleted = db.query(func.count(ImageLabel.id)).filter(ImageLabel.is_user_deleted == True).scalar() or 0

    return {
        "total": total,
        "pending": pending,
        "labeled": labeled,
        "skipped": skipped,
        "rejected": rejected,
        "training_ready": training_ready,
        "user_deleted": user_deleted,
    }


@router.get("/admin/image-labels/{label_id}", response_model=ImageLabelDetail)
async def get_image_label_detail(
    label_id: int,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """管理员获取单张图片标注详情 — 含三级标注数据"""
    label = db.query(ImageLabel).filter(ImageLabel.id == label_id).first()
    if not label:
        raise HTTPException(status_code=404, detail="标注记录不存在")
    return _label_to_detail(label)


def _generate_annotated_image(
    label: ImageLabel,
    annotations_data: Optional[list],
) -> dict:
    """Generate annotated images: composite + individual layer PNGs.

    The original image is ALWAYS preserved unchanged (via image_url).
    This function creates:
      1. A composite image overlaying admin's brush strokes on the original (JPEG)
      2. Individual layer mask PNGs (skin mask, lesion mask) for training
      3. A layers metadata JSON pointing to all artifacts

    Returns a dict with paths, or {'annotated_image_path': None} on failure.
    """
    result = {
        "annotated_image_path": None,
        "annotated_image_url": None,
        "annotated_layers_path": None,
    }

    if not annotations_data:
        return result

    # Collect masks from annotations
    lesion_masks: list[str] = []
    skin_masks: list[str] = []
    for ann_data in annotations_data:
        if ann_data.get("source") != "admin":
            continue
        mask_data = ann_data.get("mask_data")
        if mask_data and isinstance(mask_data, str) and len(mask_data) > 100:
            lesion_masks.append(mask_data)
        skin_mask_data = ann_data.get("skin_mask_data")
        if skin_mask_data and isinstance(skin_mask_data, str) and len(skin_mask_data) > 100:
            skin_masks.append(skin_mask_data)

    if not lesion_masks and not skin_masks:
        return result

    try:
        from PIL import Image
        import base64
        import io as _io
        import json as _json
        from pathlib import Path as _Path

        # Load the original image
        original_img = _load_image_from_label(label)
        if not original_img:
            logger.warning(
                "Cannot generate annotated image: failed to load original for label %s", label.id
            )
            return result

        # Convert to RGBA for compositing
        if original_img.mode != 'RGBA':
            original_img = original_img.convert('RGBA')
        orig_w, orig_h = original_img.size

        # Set up output directories
        output_dir = _Path("/root/subskin/data/uploads/vasi/annotated")
        layers_dir = _Path("/root/subskin/data/uploads/vasi/annotated/layers")
        output_dir.mkdir(parents=True, exist_ok=True)
        layers_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        base_name = f"admin_{label.id}_{timestamp}"

        # ── Save individual layer PNGs ──
        layers_manifest = {
            "label_id": label.id,
            "image_url": label.image_url,
            "image_hash": label.image_hash,
            "generated_at": datetime.utcnow().isoformat(),
            "original_size": [orig_w, orig_h],
            "skin_masks": [],
            "lesion_masks": [],
        }

        # Save skin mask PNGs
        composite_img = original_img.copy()
        for i, mask_b64 in enumerate(skin_masks):
            mask_img = _decode_data_url_image(mask_b64)
            if not mask_img:
                continue
            if mask_img.mode != 'RGBA':
                mask_img = mask_img.convert('RGBA')
            if mask_img.size != (orig_w, orig_h):
                mask_img = mask_img.resize((orig_w, orig_h), Image.LANCZOS)
            skin_png_path = layers_dir / f"{base_name}_skin_{i}.png"
            mask_img.save(str(skin_png_path), "PNG")
            layers_manifest["skin_masks"].append({
                "index": i,
                "path": str(skin_png_path),
                "url": f"/api/files/serve/vasi/annotated/layers/{skin_png_path.name}",
            })

        # Save lesion mask PNGs and composite onto image
        for i, mask_b64 in enumerate(lesion_masks):
            mask_img = _decode_data_url_image(mask_b64)
            if not mask_img:
                continue
            if mask_img.mode != 'RGBA':
                mask_img = mask_img.convert('RGBA')
            if mask_img.size != (orig_w, orig_h):
                mask_img = mask_img.resize((orig_w, orig_h), Image.LANCZOS)
            # Save individual lesion layer PNG
            lesion_png_path = layers_dir / f"{base_name}_lesion_{i}.png"
            mask_img.save(str(lesion_png_path), "PNG")
            layers_manifest["lesion_masks"].append({
                "index": i,
                "path": str(lesion_png_path),
                "url": f"/api/files/serve/vasi/annotated/layers/{lesion_png_path.name}",
            })
            # Alpha composite: mask on top of original
            composite_img = Image.alpha_composite(composite_img, mask_img)

        # ── Save composite annotated image ──
        result_img = composite_img.convert('RGB')
        composite_filename = f"{base_name}_annotated.jpg"
        composite_path = output_dir / composite_filename
        result_img.save(str(composite_path), "JPEG", quality=92)

        # ── Save layers manifest JSON ──
        manifest_path = output_dir / f"{base_name}_layers.json"
        with open(str(manifest_path), "w", encoding="utf-8") as f:
            _json.dump(layers_manifest, f, ensure_ascii=False, indent=2)

        result["annotated_image_path"] = str(composite_path)
        result["annotated_image_url"] = f"/api/files/serve/vasi/annotated/{composite_filename}"
        result["annotated_layers_path"] = str(manifest_path)

        logger.info(
            "Generated annotated image for label %s: composite=%s (%dx%d), skin_layers=%d, lesion_layers=%d",
            label.id, composite_path, result_img.width, result_img.height,
            len(layers_manifest["skin_masks"]), len(layers_manifest["lesion_masks"]),
        )
        return result

    except ImportError:
        logger.warning(
            "Pillow not available — skipping annotated image generation for label %s", label.id
        )
        return result
    except Exception as e:
        logger.warning(
            "Failed to generate annotated image for label %s: %s", label.id, e
        )
        return result


def _load_image_from_label(label: ImageLabel):
    """Load the original PIL Image from an ImageLabel's image_url."""
    from pathlib import Path as _Path
    import re as _re

    image_url: str = label.image_url or ""
    if not image_url:
        return None

    # Try local path resolution (same logic as get_image_label_image endpoint)
    local_path: Optional[str] = None
    path_in_url: Optional[str] = None

    api_match = _re.search(r"/api/files/serve/(.+?)(?:\?|$)", image_url)
    if api_match:
        path_in_url = api_match.group(1)
    elif "data/uploads" in image_url:
        idx = image_url.find("data/uploads")
        path_in_url = image_url[idx + len("data/uploads/"):]
    elif image_url.startswith("/data/"):
        path_in_url = image_url[len("/data/"):]

    if path_in_url:
        safe_path = path_in_url.split("?")[0].split("#")[0]
        if ".." not in safe_path and not safe_path.startswith("/"):
            candidate = _Path("/root/subskin/data/uploads") / safe_path
            if candidate.exists() and candidate.is_file():
                local_path = str(candidate)

    if local_path:
        from PIL import Image as _PILImage
        return _PILImage.open(local_path)

    # External URL — fetch
    if image_url.startswith("http://") or image_url.startswith("https://"):
        try:
            import requests as _requests
            from PIL import Image as _PILImage
            import io as _io
            r = _requests.get(image_url, timeout=30)
            r.raise_for_status()
            return _PILImage.open(_io.BytesIO(r.content))
        except Exception:
            return None

    return None


def _decode_data_url_image(data_url: str):
    """Decode a base64 PNG data URL into a PIL Image."""
    import base64 as _b64
    import io as _io
    from PIL import Image as _PILImage

    if not data_url:
        return None
    try:
        # Handle both "data:image/png;base64,xxx" and raw base64
        if data_url.startswith("data:"):
            _header, b64 = data_url.split(",", 1)
        else:
            b64 = data_url
        img_data = _b64.b64decode(b64)
        return _PILImage.open(_io.BytesIO(img_data))
    except Exception as e:
        logger.warning("Failed to decode data URL image: %s", e)
        return None


@router.post("/admin/image-labels/{label_id}/label")
async def admin_label_image(
    label_id: int,
    request: AdminLabelRequest,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """管理员提交最终标注 — 核心打标接口"""
    label = db.query(ImageLabel).filter(ImageLabel.id == label_id).first()
    if not label:
        raise HTTPException(status_code=404, detail="标注记录不存在")

    update_data: dict = request.model_dump(exclude_unset=True)
    annotations_data: Optional[list] = update_data.pop("annotations", None)
    annotated_image_data_url: Optional[str] = update_data.pop("annotated_image", None)
    training_eligible: Optional[bool] = update_data.pop("training_eligible", None)

    changes = []
    column_map = {
        "body_site": "admin_body_site",
        "is_vitiligo": "admin_is_vitiligo",
        "vitiligo_type": "admin_vitiligo_type",
        "vitiligo_stage": "admin_vitiligo_stage",
        "area_percentage": "admin_area_percentage",
        "vasi_score": "admin_vasi_score",
        "depigmentation_level": "admin_depigmentation_level",
        "notes": "admin_notes",
    }

    for field_name, column_name in column_map.items():
        if field_name not in update_data:
            continue
        new_value = update_data[field_name]
        old_value = getattr(label, column_name)
        setattr(label, column_name, new_value)
        changes.append((field_name, str(old_value), str(new_value)))

    if request.draft_mode:
        # 保存草稿：保存标注数据但不标记为已标注
        label.label_status = "pending"
        log_action = "save_draft"
    else:
        # 正式提交：标记为已标注
        label.label_status = "labeled"
        label.labeled_by = admin_user.id
        label.labeled_at = datetime.utcnow()
        log_action = "update"

    if training_eligible is not None:
        label.training_eligible = training_eligible
        changes.append(("training_eligible", str(label.training_eligible), str(training_eligible)))

    for field_name, old_val, new_val in changes:
        _log_change(db, label.id, admin_user.id, log_action, field_name, old_val, new_val)

    if annotations_data:
        logger.info(
            "Saving %d admin annotations for label %s (draft=%s)",
            len(annotations_data), label.id, request.draft_mode,
        )
        db.query(ImageLabelAnnotation).filter(
            ImageLabelAnnotation.image_label_id == label.id,
            ImageLabelAnnotation.source == "admin",
        ).delete(synchronize_session=False)

        for ann_data in annotations_data:
            if ann_data.get("source") != "admin":
                continue
            mask_val = ann_data.get("mask_data")
            skin_mask_val = ann_data.get("skin_mask_data")
            logger.info(
                "Annotation for label %s: mask_data=%s chars, skin_mask_data=%s chars",
                label.id,
                len(mask_val) if mask_val and isinstance(mask_val, str) else "None",
                len(skin_mask_val) if skin_mask_val and isinstance(skin_mask_val, str) else "None",
            )
            annotation = ImageLabelAnnotation(
                image_label_id=label.id,
                source="admin",
                region_index=ann_data.get("region_index", 0),
                body_site=ann_data.get("body_site"),
                is_vitiligo=ann_data.get("is_vitiligo"),
                vitiligo_type=ann_data.get("vitiligo_type"),
                vitiligo_stage=ann_data.get("vitiligo_stage"),
                area_percentage=ann_data.get("area_percentage"),
                depigmentation_level=ann_data.get("depigmentation_level"),
                region_contour=ann_data.get("region_contour"),
                region_bbox=ann_data.get("region_bbox"),
                mask_data=mask_val,
                skin_mask_data=skin_mask_val,
                confidence=ann_data.get("confidence"),
                notes=ann_data.get("notes"),
            )
            db.add(annotation)

    db.commit()

    # ── Save / generate annotated image (original + admin mask overlay) ──
    # Uses FIXED filename so each draft overwrites the previous — only keeps latest
    try:
        from PIL import Image
        import base64 as _base64
        import io as _io
        from pathlib import Path as _Path

        output_dir = _Path("/root/subskin/data/uploads/vasi/annotated")
        output_dir.mkdir(parents=True, exist_ok=True)

        # Fixed filename — overwrites on each save
        fixed_name = f"admin_{label.id}_composite"
        composite_jpg = output_dir / f"{fixed_name}.jpg"

        if annotated_image_data_url and isinstance(annotated_image_data_url, str) and len(annotated_image_data_url) > 100:
            # ── Frontend-supplied composite: decode & save directly (fixed name) ──
            header, b64_data = annotated_image_data_url.split(",", 1)
            img_bytes = _base64.b64decode(b64_data)
            img = Image.open(_io.BytesIO(img_bytes))
            img = img.convert("RGB")
            img.save(str(composite_jpg), "JPEG", quality=85)
            label.annotated_image_path = str(composite_jpg)
            # Use cache-busting timestamp so browser reloads after update
            label.annotated_image_url = f"/api/files/serve/vasi/annotated/{fixed_name}.jpg?t={int(datetime.utcnow().timestamp())}"
            logger.info("Saved draft composite for label %s (%dx%d) → %s", label.id, *img.size, fixed_name)
        elif annotations_data:
            # ── Server-side fallback: generate from stored mask_data ──
            gen_result = _generate_annotated_image(label, annotations_data)
            if gen_result.get("annotated_image_path"):
                label.annotated_image_path = gen_result["annotated_image_path"]
                label.annotated_image_url = gen_result["annotated_image_url"]
                label.annotated_layers_path = gen_result.get("annotated_layers_path")

        # Persist annotated image paths to DB
        db.commit()
        logger.info("Annotated image path persisted for label %s: %s", label.id, label.annotated_image_url)

    except Exception as e:
        logger.warning("Annotated image save failed for label %s (non-blocking): %s", label.id, e)

    # ── Phase 1A: Sync admin label to training sample center ──
    try:
        # Eagerly load annotations and assessment for training sync
        label = db.query(ImageLabel).options(
            joinedload(ImageLabel.annotations),
            joinedload(ImageLabel.assessment),
        ).filter(ImageLabel.id == label_id).first()
        if label:
            from web.backend.services.vasi_feedback import get_feedback_collector
            collector = get_feedback_collector(db)
            sample = collector.upsert_from_admin_label(label)
            if sample:
                logger.info(
                    "Admin label %s synced to training sample %s", label_id, sample.id
                )
    except Exception as e:
        logger.warning("Admin label %s training sync failed (non-blocking): %s", label_id, e)

    return {
        "status": "ok",
        "label_id": label.id,
        "changes": len(changes),
        "draft": request.draft_mode,
        "label_status": label.label_status,
    }


@router.get("/admin/image-labels/{label_id}/annotated-image")
async def get_annotated_image(
    label_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """返回管理员标注合成图（原始照片 + 画笔涂层叠加）

    用于 <img> 标签直接加载，优先 header auth，兜底 query string。
    如果合成图文件不存在则实时生成。
    """
    from fastapi.responses import StreamingResponse
    from pathlib import Path
    from web.backend.services.auth import get_user_from_access_token

    # ── 鉴权: 优先 header, 兜底 query ──
    admin_user = None
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        admin_user = get_user_from_access_token(auth_header[7:], db)

    if admin_user is None:
        token = request.query_params.get("access_token", "") or request.query_params.get("token", "")
        if token:
            admin_user = get_user_from_access_token(token, db)

    if admin_user is None or not admin_user.is_active or not admin_user.is_admin:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # ── 查 label ──
    label = db.query(ImageLabel).filter(ImageLabel.id == label_id).first()
    if not label:
        raise HTTPException(status_code=404, detail="标注记录不存在")

    # ── 尝试从已保存的合成图文件返回 ──
    if label.annotated_image_path:
        file_path = Path(label.annotated_image_path)
        if file_path.exists() and file_path.is_file():
            ext = file_path.suffix.lower().lstrip(".") or "jpg"
            media_type = {
                "jpg": "image/jpeg", "jpeg": "image/jpeg",
                "png": "image/png", "webp": "image/webp",
            }.get(ext, "image/jpeg")

            def file_iter(p: Path = file_path):
                with open(p, "rb") as f:
                    chunk = f.read(64 * 1024)
                    while chunk:
                        yield chunk
                        chunk = f.read(64 * 1024)
            return StreamingResponse(
                file_iter(),
                media_type=media_type,
                headers={"Cache-Control": "private, max-age=300"},
            )

    # ── 实时生成：从 annotations 合成 ──
    annotations = db.query(ImageLabelAnnotation).filter(
        ImageLabelAnnotation.image_label_id == label_id,
        ImageLabelAnnotation.source == "admin",
    ).all()

    if not annotations:
        raise HTTPException(status_code=404, detail="该标注没有合成图，请先使用像素填涂并暂存")

    annot_list = [
        {
            "source": a.source,
            "mask_data": a.mask_data,
            "skin_mask_data": a.skin_mask_data,
        }
        for a in annotations
    ]
    gen_result = _generate_annotated_image(label, annot_list)
    if gen_result.get("annotated_image_path"):
        file_path = Path(gen_result["annotated_image_path"])
        if file_path.exists():
            # Update label with the newly generated path
            label.annotated_image_path = gen_result["annotated_image_path"]
            label.annotated_image_url = gen_result["annotated_image_url"]
            label.annotated_layers_path = gen_result.get("annotated_layers_path")
            db.commit()

            def file_iter2(p: Path = file_path):
                with open(p, "rb") as f:
                    chunk = f.read(64 * 1024)
                    while chunk:
                        yield chunk
                        chunk = f.read(64 * 1024)
            return StreamingResponse(
                file_iter2(),
                media_type="image/jpeg",
                headers={"Cache-Control": "private, max-age=300"},
            )

    raise HTTPException(status_code=404, detail="合成图生成失败，请重试")


@router.post("/admin/image-labels/batch-status")
async def batch_update_status(
    request: BatchStatusRequest,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """批量更新标注状态 — 跳过或拒绝不适合的图片"""
    valid_statuses = {"skipped", "rejected"}
    if request.label_status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"label_status must be one of: {valid_statuses}")

    rows = db.query(ImageLabel).filter(ImageLabel.id.in_(request.ids)).all()
    updated = 0
    for row in rows:
        row.label_status = request.label_status
        if request.training_eligible is not None:
            row.training_eligible = request.training_eligible
        _log_change(db, row.id, admin_user.id, request.label_status)
        updated += 1

    db.commit()
    return {"status": "ok", "updated": updated}


class BatchUploadResponse(BaseModel):
    """批量上传图片的返回结构"""
    created: int = 0
    skipped: int = 0
    errors: List[str] = Field(default_factory=list)
    items: List[dict] = Field(default_factory=list)


@router.post("/admin/image-labels/upload", response_model=BatchUploadResponse)
async def batch_upload_images(
    files: List[UploadFile] = File(...),
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """批量上传图片 — 管理员从本地上传图片到打标系统

    每张图片独立存储并创建 ImageLabel 记录，支持直接进行人工标注，
    无需关联 VASI 评估记录。已存在的图片 (SHA-256 碰撞) 自动跳过。
    """
    import hashlib as hl
    import uuid
    from pathlib import Path

    ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/jpg"}
    MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB per file

    upload_dir = Path("data/uploads/vasi")
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Collect existing hashes for dedup
    existing_hashes = set(
        row[0] for row in db.query(ImageLabel.image_hash).filter(ImageLabel.image_hash.isnot(None)).all()
    )

    created = 0
    skipped = 0
    errors: List[str] = []
    items: List[dict] = []

    for file in files:
        try:
            # ── Validate ──
            if not file.filename:
                errors.append("跳过无文件名")
                skipped += 1
                continue

            content = await file.read()
            if len(content) == 0:
                errors.append(f"{file.filename}: 文件为空")
                skipped += 1
                continue

            if len(content) > MAX_FILE_SIZE:
                errors.append(f"{file.filename}: 超过 20MB 限制")
                skipped += 1
                continue

            # Detect content type
            import mimetypes
            mime_type, _ = mimetypes.guess_type(file.filename)
            if not mime_type or mime_type not in ALLOWED_TYPES:
                # Fallback: detect from magic bytes
                if content[:4] == b"\x89PNG":
                    mime_type = "image/png"
                elif content[:2] == b"\xff\xd8":
                    mime_type = "image/jpeg"
                elif content[:4] == b"RIFF" and len(content) >= 12 and content[8:12] == b"WEBP":
                    mime_type = "image/webp"
                else:
                    errors.append(f"{file.filename}: 不支持的格式 (仅支持 JPG/PNG/WebP)")
                    skipped += 1
                    continue

            # ── Compute hash for dedup ──
            sha256_hash = hl.sha256(content).hexdigest()
            if sha256_hash in existing_hashes:
                skipped += 1
                continue

            # ── Save to disk ──
            ext = Path(file.filename).suffix or ".jpg"
            stored_name = f"{int(datetime.utcnow().timestamp())}_{uuid.uuid4().hex[:8]}{ext}"
            file_path = upload_dir / stored_name
            file_path.write_bytes(content)

            image_url = f"/api/files/serve/vasi/{stored_name}"
            image_key = f"vasi/admin_upload/{stored_name}"

            # ── Create ImageLabel record ──
            label = ImageLabel(
                original_user_id=admin_user.id,
                image_url=image_url,
                image_key=image_key,
                image_hash=sha256_hash,
                label_status="pending",
                is_user_deleted=False,
            )
            db.add(label)
            db.flush()  # get the id

            existing_hashes.add(sha256_hash)
            created += 1
            items.append({"id": label.id, "image_url": image_url})

        except Exception as e:
            logger.error("Batch upload: failed for %s: %s", file.filename, str(e), exc_info=True)
            errors.append(f"{file.filename}: 上传失败 - {e}")
            skipped += 1

    db.commit()

    logger.info(
        "Batch upload complete: created=%d, skipped=%d, errors=%d (user=%d)",
        created, skipped, len(errors), admin_user.id,
    )

    return BatchUploadResponse(created=created, skipped=skipped, errors=errors, items=items)


@router.post("/admin/image-labels/sync-assessments")
async def sync_from_assessments(
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """从现有 VASI 评估记录中同步创建打标记录
    
    将所有已有的评估图片导入打标系统，自动填充 AI 和用户标注数据。
    已同步过的记录不会重复创建。
    
    增强：同步用户的填涂图层（skin/lesion mask）作为预填充数据，
    管理员可以在用户的基础上修改，无需从零开始。
    """
    existing_hashes = set(
        row[0] for row in db.query(ImageLabel.image_hash).filter(ImageLabel.image_hash.isnot(None)).all()
    )
    existing_assessment_ids = set(
        row[0] for row in db.query(ImageLabel.assessment_id).filter(ImageLabel.assessment_id.isnot(None)).all()
    )

    assessments = db.query(VASIAssessment).order_by(VASIAssessment.assessment_date.desc()).all()
    created = 0
    skipped = 0
    user_annotations_synced = 0

    for a in assessments:
        if a.id in existing_assessment_ids:
            skipped += 1
            continue

        image_hash = a.image_hash
        if image_hash and image_hash in existing_hashes:
            skipped += 1
            continue

        # Determine AI is_vitiligo
        ai_is_vit = (a.classification in ("节段型", "非节段型", "混合型", "未定型") if a.classification else True)

        label = ImageLabel(
            assessment_id=a.id,
            original_user_id=a.user_id,
            image_url=a.image_url,
            image_key=a.image_key,
            image_hash=image_hash,
            ai_body_site=a.body_site,
            ai_is_vitiligo=ai_is_vit,
            ai_vitiligo_type=a.classification if a.classification in ("节段型", "非节段型", "混合型", "未定型") else None,
            ai_vitiligo_stage=a.stage,
            ai_area_percentage=a.area_percentage if a.area_percentage is not None else (
                a.final_area_percentage if a.final_area_percentage is not None else None
            ),
            ai_vasi_score=a.vasi_score if a.vasi_score is not None else (
                a.final_vasi_score if a.final_vasi_score is not None else None
            ),
            ai_confidence=a.confidence,
            ai_details=a.details,
            user_body_site=a.body_site if a.is_user_corrected else None,
            user_is_vitiligo=ai_is_vit if a.is_user_corrected else None,
            user_vitiligo_type=a.classification if a.is_user_corrected else None,
            user_area_percentage=a.final_area_percentage if a.is_user_corrected else None,
            user_vasi_score=a.final_vasi_score if a.is_user_corrected else None,
            user_depigmentation_level=a.depigmentation_level if a.is_user_corrected else None,
            is_user_deleted=False,
        )
        db.add(label)
        db.flush()  # get label.id for annotations

        # ── Sync user's mask data as ImageLabelAnnotation (source='user') ──
        user_has_data = False

        if a.user_skin_layer and isinstance(a.user_skin_layer, str) and len(a.user_skin_layer) > 100:
            user_ann = ImageLabelAnnotation(
                image_label_id=label.id,
                source="user",
                region_index=0,
                body_site=a.body_site,
                is_vitiligo=ai_is_vit,
                vitiligo_type=a.classification if a.classification in ("节段型", "非节段型", "混合型", "未定型") else None,
                area_percentage=a.final_area_percentage,
                depigmentation_level=a.depigmentation_level,
                skin_mask_data=a.user_skin_layer,
                mask_data=a.user_lesion_layer if a.user_lesion_layer else None,
                confidence=None,
                notes="用户测评页面填涂结果 — 管理员可在此基础上修改",
            )
            db.add(user_ann)
            user_has_data = True

        if a.user_lesion_layer and isinstance(a.user_lesion_layer, str) and len(a.user_lesion_layer) > 100 and not user_has_data:
            user_ann = ImageLabelAnnotation(
                image_label_id=label.id,
                source="user",
                region_index=0,
                body_site=a.body_site,
                is_vitiligo=ai_is_vit,
                vitiligo_type=a.classification if a.classification in ("节段型", "非节段型", "混合型", "未定型") else None,
                area_percentage=a.final_area_percentage,
                depigmentation_level=a.depigmentation_level,
                mask_data=a.user_lesion_layer,
                confidence=None,
                notes="用户测评页面填涂结果 — 管理员可在此基础上修改",
            )
            db.add(user_ann)
            user_has_data = True

        # AI layers for reference
        if a.ai_skin_layer and isinstance(a.ai_skin_layer, str) and len(a.ai_skin_layer) > 100:
            ai_ann = ImageLabelAnnotation(
                image_label_id=label.id,
                source="ai",
                region_index=0,
                body_site=a.body_site,
                is_vitiligo=ai_is_vit,
                vitiligo_type=a.classification if a.classification in ("节段型", "非节段型", "混合型", "未定型") else None,
                area_percentage=a.area_percentage,
                skin_mask_data=a.ai_skin_layer,
                mask_data=a.ai_lesion_layer if a.ai_lesion_layer else None,
                confidence=a.confidence,
                notes="AI 自动填涂图层（推理结果）— 参考用",
            )
            db.add(ai_ann)

        if user_has_data:
            user_annotations_synced += 1
        created += 1

    db.commit()

    return {
        "status": "ok",
        "created": created,
        "skipped": skipped,
        "total_assessments": len(assessments),
        "user_annotations_synced": user_annotations_synced,
    }


@router.post("/admin/image-labels/training-export", response_model=TrainingExportResponse)
async def export_training_data(
    request: TrainingExportRequest,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """导出训练数据 — 为 VASI 大模型训练和校准提供结构化数据

    将管理员审核后的标注数据导出为训练集/验证集/测试集划分。
    增强: 返回 manifest, 含 (image, mask) 配对下载链接与 (image, contour) 结构化坐标。
    """
    import random

    query = db.query(ImageLabel).filter(ImageLabel.label_status == "labeled")

    if request.only_admin_labeled:
        query = query.filter(ImageLabel.admin_is_vitiligo.isnot(None))

    labels = query.all()

    if not labels:
        return TrainingExportResponse(
            total_count=0, train_count=0, val_count=0, test_count=0,
        )

    parts = request.split_ratio.split("/")
    train_pct = float(parts[0]) / 100 if len(parts) == 3 else 0.8
    val_pct = float(parts[1]) / 100 if len(parts) == 3 else 0.1

    randomized = list(labels)
    random.shuffle(randomized)
    n = len(randomized)
    train_end = int(n * train_pct)
    val_end = train_end + int(n * val_pct)

    # 收集训练数据 manifest
    manifest_items = []
    for i, label in enumerate(randomized):
        if i < train_end:
            label.training_set_split = "train"
        elif i < val_end:
            label.training_set_split = "val"
        else:
            label.training_set_split = "test"
        label.training_exported_at = datetime.utcnow()

        # 收集每张图的人工标注 contours + mask
        annotations = db.query(ImageLabelAnnotation).filter(
            ImageLabelAnnotation.image_label_id == label.id,
            ImageLabelAnnotation.source == "admin",
        ).all()
        contour_list = []
        mask_count = 0
        for ann in annotations:
            if ann.region_contour:
                try:
                    contour_list.append({
                        "region_index": ann.region_index,
                        "body_site": ann.body_site,
                        "is_vitiligo": ann.is_vitiligo,
                        "vitiligo_type": ann.vitiligo_type,
                        "vitiligo_stage": ann.vitiligo_stage,
                        "area_percentage": ann.area_percentage,
                        "polygon": json.loads(ann.region_contour) if ann.region_contour else None,
                        "bbox": json.loads(ann.region_bbox) if ann.region_bbox else None,
                        "notes": ann.notes,
                    })
                except (json.JSONDecodeError, TypeError):
                    continue
            if ann.mask_data:
                mask_count += 1

        manifest_items.append({
            "image_label_id": label.id,
            "image_url": label.image_url,
            "image_hash": label.image_hash,
            "annotated_image_path": label.annotated_image_path,
            "annotated_image_url": label.annotated_image_url,
            "annotated_layers_path": label.annotated_layers_path,
            "split": label.training_set_split,
            "body_site": label.admin_body_site or label.ai_body_site,
            "is_vitiligo": label.admin_is_vitiligo,
            "vitiligo_type": label.admin_vitiligo_type or label.ai_vitiligo_type,
            "vitiligo_stage": label.admin_vitiligo_stage or label.ai_vitiligo_stage,
            "area_percentage": label.admin_area_percentage or label.ai_area_percentage,
            "vasi_score": label.admin_vasi_score or label.ai_vasi_score,
            "depigmentation_level": label.admin_depigmentation_level or label.ai_depigmentation_level,
            "admin_notes": label.admin_notes,
            "contours": contour_list,
            "mask_count": mask_count,
        })

    db.commit()

    # 写 manifest 到文件, 供后续下载 (image, mask) 对打包
    import os
    manifest_dir = "/root/subskin/data/training_manifests"
    os.makedirs(manifest_dir, exist_ok=True)
    manifest_path = os.path.join(manifest_dir, f"manifest_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump({
            "export_time": datetime.utcnow().isoformat(),
            "split_ratio": request.split_ratio,
            "total_count": n,
            "include_ai": request.include_ai,
            "include_user": request.include_user,
            "items": manifest_items,
        }, f, ensure_ascii=False, indent=2)

    train_count = sum(1 for m in manifest_items if m["split"] == "train")
    val_count = sum(1 for m in manifest_items if m["split"] == "val")
    test_count = sum(1 for m in manifest_items if m["split"] == "test")

    return TrainingExportResponse(
        total_count=n,
        train_count=train_count,
        val_count=val_count,
        test_count=test_count,
        export_url=f"/api/vasi/admin/image-labels/training-manifest?path={manifest_path}",
    )


@router.get("/admin/image-labels/training-manifest")
async def download_training_manifest(
    path: str = Query(..., description="manifest 文件路径"),
    admin_user: User = Depends(get_current_admin_user),
):
    """下载训练数据 manifest (含所有 image_url + mask_data + contours)"""
    from fastapi.responses import FileResponse
    import os

    # 安全检查: 必须是 /root/subskin/data/training_manifests/ 下的文件
    if not path.startswith("/root/subskin/data/training_manifests/"):
        raise HTTPException(status_code=400, detail="非法路径")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="manifest 不存在")

    return FileResponse(
        path,
        media_type="application/json",
        filename=os.path.basename(path),
    )


@router.get("/admin/image-labels/export")
async def export_labels_data(
    label_status: Optional[str] = Query(None, description="Filter by status: pending/labeled/skipped/rejected"),
    format: str = Query("json", description="Export format: json or csv"),
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """批量导出标注数据 — JSON 或 CSV 格式下载"""
    import csv
    import io

    query = db.query(ImageLabel)
    if label_status:
        query = query.filter(ImageLabel.label_status == label_status)

    labels = query.order_by(ImageLabel.created_at.asc()).all()

    rows = []
    for r in labels:
        rows.append({
            "id": r.id,
            "assessment_id": r.assessment_id,
            "image_url": r.image_url,
            "label_status": r.label_status,
            "ai_body_site": r.ai_body_site,
            "ai_is_vitiligo": r.ai_is_vitiligo,
            "ai_vitiligo_type": r.ai_vitiligo_type,
            "ai_vitiligo_stage": r.ai_vitiligo_stage,
            "ai_area_percentage": r.ai_area_percentage,
            "ai_vasi_score": r.ai_vasi_score,
            "ai_confidence": r.ai_confidence,
            "admin_body_site": r.admin_body_site,
            "admin_is_vitiligo": r.admin_is_vitiligo,
            "admin_vitiligo_type": r.admin_vitiligo_type,
            "admin_vitiligo_stage": r.admin_vitiligo_stage,
            "admin_area_percentage": r.admin_area_percentage,
            "admin_vasi_score": r.admin_vasi_score,
            "admin_depigmentation_level": r.admin_depigmentation_level,
            "admin_notes": r.admin_notes,
            "training_eligible": r.training_eligible,
            "training_set_split": r.training_set_split,
            "created_at": _format_dt(r.created_at),
            "labeled_at": _format_dt(r.labeled_at),
        })

    if format == "csv":
        output = io.StringIO()
        if rows:
            writer = csv.DictWriter(output, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        from fastapi.responses import Response
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=image_labels_export.csv"},
        )

    from fastapi.responses import Response as Resp
    content = json.dumps(rows, ensure_ascii=False, indent=2)
    return Resp(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=image_labels_export.json"},
    )


@router.get("/admin/image-labels/choices")
async def get_label_choices(
    admin_user: User = Depends(get_current_admin_user),
):
    """获取打标选项的枚举值 — 供前端表单下拉框使用"""
    return {
        "body_sites": BODY_SITE_CHOICES,
        "vitiligo_types": VITILIGO_TYPE_CHOICES,
        "stages": STAGE_CHOICES,
        "label_statuses": ["pending", "labeled", "skipped", "rejected"],
        "training_splits": ["train", "val", "test"],
    }


class AiPretrainResponse(BaseModel):
    contours: List[dict] = Field(default_factory=list)
    body_site: Optional[str] = None
    is_vitiligo: Optional[bool] = None
    vitiligo_type: Optional[str] = None
    vitiligo_stage: Optional[str] = None
    area_percentage: Optional[float] = None
    vasi_score: Optional[float] = None
    depigmentation_level: Optional[float] = None
    confidence: Optional[float] = None
    lesion_layer_data_url: Optional[str] = None
    skin_layer_data_url: Optional[str] = None
    suspected_lesions: Optional[List[dict]] = None
    source: Optional[str] = None
    duration_ms: Optional[int] = None


async def _download_image_to_bytes(image_url: str, base_url: str = "http://127.0.0.1:8000") -> bytes:
    """下载图片到 bytes — 内部用, 用于 AI 预标注

    支持:
    1. 本地路径 (如 /api/files/serve/..., data/uploads/...) — 直接从磁盘读取
    2. 完整 URL (http:// 或 https://) — 通过 HTTP 下载
    3. 相对路径 (如 /api/files/serve/..., /api/...) — 通过本地服务器代理获取
    """
    import re
    import httpx
    from pathlib import Path

    # ── 尝试解析为本地路径 ──
    path_in_url: Optional[str] = None

    api_match = re.search(r"/api/files/serve/(.+?)(?:\?|$)", image_url)
    if api_match:
        path_in_url = api_match.group(1)
    elif "data/uploads" in image_url:
        idx = image_url.find("data/uploads")
        path_in_url = image_url[idx + len("data/uploads/"):]
    elif image_url.startswith("/data/"):
        path_in_url = image_url[len("/data/"):]

    if path_in_url:
        path_in_url = path_in_url.split("?")[0].split("#")[0]
        if ".." not in path_in_url and not path_in_url.startswith("/"):
            candidate = Path("/root/subskin/data/uploads") / path_in_url
            if candidate.exists() and candidate.is_file():
                return candidate.read_bytes()

    # ── HTTP 下载 (完整 URL) ──
    if image_url.startswith("http://") or image_url.startswith("https://"):
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            r = await client.get(image_url)
            r.raise_for_status()
            return r.content

    # ── 兜底: 相对路径 — 通过内部文件解析直接读取 (避免 HTTP 代理鉴权问题) ──
    if image_url.startswith("/"):
        try:
            from web.backend.api.files import _resolve_requested_file
            relative = image_url.split("?")[0].split("#")[0]
            # Strip known prefixes to get the relative path for file resolution
            for prefix in ("/api/files/serve/", "/api/", "/uploads/", "/data/"):
                if relative.startswith(prefix):
                    relative = relative[len(prefix):]
                    break
            else:
                relative = relative.lstrip("/")
            if ".." not in relative and not relative.startswith("/"):
                resolved = _resolve_requested_file(relative)
                if resolved.exists() and resolved.is_file():
                    return resolved.read_bytes()
        except Exception as e:
            logger.warning("Internal file resolution failed: %s, falling back to HTTP proxy", e)

        # Last resort: HTTP proxy via localhost (may fail if endpoint requires auth)
        proxy_url = f"{base_url.rstrip('/')}{image_url}"
        logger.info("AI pretrain: local file not found, proxying via %s", proxy_url)
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            r = await client.get(proxy_url)
            r.raise_for_status()
            return r.content

    raise HTTPException(status_code=400, detail=f"无法解析图片 URL: {image_url}")


@router.post("/admin/image-labels/{label_id}/ai-pretrain", response_model=AiPretrainResponse)
async def admin_ai_pretrain(
    label_id: int,
    request: Request,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """AI 一键预标注 — 对已上传图片重新跑 VLM, 返回 contours 供管理员微调

    这条接口不会写入数据库, 仅返回 VLM 实时推理结果。
    管理员点击确认后, contours 才会被保存为 image_label_annotations 记录。
    """
    import time
    import json
    from web.backend.services.vasi import VASIService

    label = db.query(ImageLabel).filter(ImageLabel.id == label_id).first()
    if not label:
        raise HTTPException(status_code=404, detail="标注记录不存在")

    if not label.image_url:
        raise HTTPException(status_code=400, detail="图片 URL 为空, 无法进行 AI 预标注")

    # 从 request 构造 base_url 用于代理相对路径的图片
    base_url = f"{request.url.scheme}://{request.url.netloc}"

    body_site = label.ai_body_site or label.user_body_site or "面部"
    # 标准化 body_site 到 VASI 服务的标签
    body_site_label = body_site if body_site in (
        "面部", "颈部", "头皮", "躯干前面", "躯干后面",
        "上肢近端", "上肢远端", "手部", "下肢近端", "下肢远端", "足部", "生殖器"
    ) else "面部"

    t0 = time.time()
    try:
        # 下载图片
        image_bytes = await _download_image_to_bytes(label.image_url, base_url=base_url)
        image_type = "image/jpeg"
        if image_bytes[:8] == b"\x89PNG\r\n\x1a\n":
            image_type = "image/png"
        elif image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
            image_type = "image/webp"

        service = VASIService(db)
        vasi_result = await service._call_vasi_api(
            image_file=image_bytes,
            precision="quick",
            body_site=body_site_label,
        )
    except Exception as e:
        logger.error("AI 预标注失败: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"AI 推理失败: {e}")

    # 解析 VLM 输出
    contours: List[dict] = []
    lesion_layer_data_url = None
    skin_layer_data_url = None
    suspected_lesions = None
    source = None
    is_vitiligo = None
    vitiligo_type = None
    vitiligo_stage = None
    area_percentage = None
    vasi_score = None
    depigmentation_level = None
    confidence = None

    if vasi_result:
        contours = vasi_result.get("contours", []) or []
        lesion_layer_data_url = vasi_result.get("lesion_layer_data_url")
        skin_layer_data_url = vasi_result.get("skin_layer_data_url")
        suspected_lesions = vasi_result.get("suspected_lesions")
        source = vasi_result.get("source") or vasi_result.get("assessment_source")
        is_vitiligo = vasi_result.get("is_vitiligo")
        vitiligo_type = vasi_result.get("classification") or vasi_result.get("vitiligo_type")
        vitiligo_stage = vasi_result.get("stage") or vasi_result.get("vitiligo_stage")
        area_percentage = vasi_result.get("area_percentage")
        vasi_score = vasi_result.get("vasi_score")
        depigmentation_level = vasi_result.get("depigmentation_level")
        confidence = vasi_result.get("confidence")

    return AiPretrainResponse(
        contours=contours,
        body_site=body_site,
        is_vitiligo=is_vitiligo,
        vitiligo_type=vitiligo_type,
        vitiligo_stage=vitiligo_stage,
        area_percentage=area_percentage,
        vasi_score=vasi_score,
        depigmentation_level=depigmentation_level,
        confidence=confidence,
        lesion_layer_data_url=lesion_layer_data_url,
        skin_layer_data_url=skin_layer_data_url,
        suspected_lesions=suspected_lesions,
        source=source,
        duration_ms=int((time.time() - t0) * 1000),
    )


@router.get("/admin/image-labels/{label_id}/image")
async def get_image_label_image(
    label_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """图片代理端点 — 流式返回原图给 <img> 标签使用

    解决: <img> 标签无法设 Authorization header, 改用 query string 鉴权。
    优先读 Authorization header (axios), 兜底读 ?access_token=xxx (<img> 用)。
    """
    from fastapi.responses import StreamingResponse
    from pathlib import Path
    from web.backend.services.auth import get_user_from_access_token
    import re

    # ── 鉴权: 优先 header, 兜底 query ──
    admin_user = None
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        admin_user = get_user_from_access_token(auth_header[7:], db)

    if admin_user is None:
        token = request.query_params.get("access_token", "") or request.query_params.get("token", "")
        if token:
            admin_user = get_user_from_access_token(token, db)

    if admin_user is None or not admin_user.is_active or not admin_user.is_admin:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # ── 查 label ──
    label = db.query(ImageLabel).filter(ImageLabel.id == label_id).first()
    if not label:
        raise HTTPException(status_code=404, detail="标注记录不存在")
    if not label.image_url:
        raise HTTPException(status_code=404, detail="图片 URL 为空")

    image_url: str = label.image_url

    # ── 解析为本地文件路径 (复用 files.py 的解析逻辑) ──
    local_path: Optional[Path] = None
    path_in_url: Optional[str] = None

    # 情况 1a: 内部 API 路径 (如 /api/files/serve/vasi/xxx.jpg)
    api_match = re.search(r"/api/files/serve/(.+?)(?:\?|$)", image_url)
    if api_match:
        path_in_url = api_match.group(1)
    # 情况 1b: data/uploads/ 路径
    elif "data/uploads" in image_url:
        idx = image_url.find("data/uploads")
        path_in_url = image_url[idx + len("data/uploads/"):]
    elif image_url.startswith("/data/"):
        path_in_url = image_url[len("/data/"):]

    if path_in_url:
        # _resolve_requested_file 在 files.py 内部, 简单复刻其逻辑
        # 实际存储根目录: /root/subskin/data/uploads
        path_in_url = path_in_url.split("?")[0].split("#")[0]
        # 防止路径穿越
        if ".." in path_in_url or path_in_url.startswith("/"):
            pass
        else:
            candidate = Path("/root/subskin/data/uploads") / path_in_url
            if candidate.exists() and candidate.is_file():
                local_path = candidate

    if local_path:
        ext = local_path.suffix.lower().lstrip(".") or "jpg"
        media_type = {
            "jpg": "image/jpeg", "jpeg": "image/jpeg",
            "png": "image/png", "webp": "image/webp",
            "gif": "image/gif", "bmp": "image/bmp",
        }.get(ext, "application/octet-stream")

        def file_iter(p: Path = local_path):
            with open(p, "rb") as f:
                chunk = f.read(64 * 1024)
                while chunk:
                    yield chunk
                    chunk = f.read(64 * 1024)
        return StreamingResponse(
            file_iter(),
            media_type=media_type,
            headers={"Cache-Control": "private, max-age=300"},
        )

    # ── 情况 2: 外部 URL ──
    if image_url.startswith("http://") or image_url.startswith("https://"):
        import httpx
        try:
            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                r = await client.get(image_url)
                r.raise_for_status()
                return StreamingResponse(
                    iter([r.content]),
                    media_type=r.headers.get("content-type", "image/jpeg"),
                    headers={"Cache-Control": "private, max-age=300"},
                )
        except (httpx.HTTPError, OSError) as e:
            # CDN / OSS 链接失效, 返回 SVG placeholder 提示
            # 1x1 透明 PNG 是占位, 但 SVG 更友好
            placeholder_svg = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300" viewBox="0 0 400 300">'
                '<rect width="400" height="300" fill="#f5f5f5"/>'
                '<rect x="1" y="1" width="398" height="298" fill="none" stroke="#d9d9d9" stroke-width="2" stroke-dasharray="6 4"/>'
                '<g transform="translate(200,130)" text-anchor="middle" font-family="sans-serif" fill="#999">'
                '<text font-size="20" y="-10">⚠ 图片源失效</text>'
                '<text font-size="12" y="14" fill="#bbb">原始 URL</text>'
                f'<text font-size="11" y="32" fill="#999">{image_url[:60]}</text>'
                '</g>'
                '</svg>'
            ).encode("utf-8")
            logger.warning(
                "Image label %d external URL unreachable: %s — returning placeholder",
                label_id, image_url, exc_info=False,
            )
            return StreamingResponse(
                iter([placeholder_svg]),
                media_type="image/svg+xml",
                headers={"Cache-Control": "no-cache", "X-Image-Status": "source-unreachable"},
            )

    raise HTTPException(
        status_code=404,
        detail=f"无法加载图片 (URL={image_url}, 解析路径={path_in_url})",
    )


@router.get("/admin/image-labels/{label_id}/annotations")
async def get_admin_annotations(
    label_id: int,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """获取图片已有的人工标注明细 — 编辑已标注图片时回显用"""
    label = db.query(ImageLabel).filter(ImageLabel.id == label_id).first()
    if not label:
        raise HTTPException(status_code=404, detail="标注记录不存在")

    annotations = db.query(ImageLabelAnnotation).filter(
        ImageLabelAnnotation.image_label_id == label_id,
        ImageLabelAnnotation.source == "admin",
    ).order_by(ImageLabelAnnotation.region_index.asc()).all()

    logger.info(
        "get_admin_annotations label=%s: found %d annotations, has_mask=%s, has_skin=%s",
        label_id, len(annotations),
        any(a.mask_data and len(a.mask_data) > 100 for a in annotations),
        any(a.skin_mask_data and len(a.skin_mask_data) > 100 for a in annotations),
    )

    return {
        "label_id": label_id,
        "annotations": [
            {
                "id": a.id,
                "source": a.source,
                "region_index": a.region_index,
                "body_site": a.body_site,
                "is_vitiligo": a.is_vitiligo,
                "vitiligo_type": a.vitiligo_type,
                "vitiligo_stage": a.vitiligo_stage,
                "area_percentage": a.area_percentage,
                "depigmentation_level": a.depigmentation_level,
                "region_contour": a.region_contour,
                "region_bbox": a.region_bbox,
                "mask_data": a.mask_data,
                "skin_mask_data": a.skin_mask_data,
                "confidence": a.confidence,
                "notes": a.notes,
                "created_at": _format_dt(a.created_at),
                "updated_at": _format_dt(a.updated_at),
            }
            for a in annotations
        ],
    }


@router.get("/admin/image-labels/{label_id}/user-annotations")
async def get_user_annotations_for_admin(
    label_id: int,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """获取用户测评页面的填涂/标注数据 — 供管理员预填充画布使用
    
    返回用户在测评页面的最终填涂结果（skin layer + lesion layer），
    以及用户和AI的评估数据（body_site, is_vitiligo, area %等），
    管理员可以在此基础上修改，无需从零开始填涂。
    
    ⚠️ 重要：此端点仅读取数据，不修改用户的原始测评记录。
    管理员的修改保存到 ImageLabel 和 ImageLabelAnnotation (source='admin')，
    不会影响 VASIAssessment 表中的用户数据。
    """
    label = db.query(ImageLabel).filter(ImageLabel.id == label_id).first()
    if not label:
        raise HTTPException(status_code=404, detail="标注记录不存在")
    
    result = {
        "label_id": label_id,
        "has_user_data": False,
        "has_ai_data": False,
        "user_annotations": [],
        "ai_annotations": [],
        "assessment_summary": None,
    }
    
    # ── 1. Get user annotations from image_label_annotations ──
    user_anns = db.query(ImageLabelAnnotation).filter(
        ImageLabelAnnotation.image_label_id == label_id,
        ImageLabelAnnotation.source == "user",
    ).order_by(ImageLabelAnnotation.region_index.asc()).all()
    
    if user_anns:
        result["has_user_data"] = True
        result["user_annotations"] = [
            {
                "id": a.id, "source": a.source, "region_index": a.region_index,
                "body_site": a.body_site, "is_vitiligo": a.is_vitiligo,
                "vitiligo_type": a.vitiligo_type, "vitiligo_stage": a.vitiligo_stage,
                "area_percentage": a.area_percentage, "depigmentation_level": a.depigmentation_level,
                "skin_mask_data": a.skin_mask_data, "mask_data": a.mask_data,
                "confidence": a.confidence, "notes": a.notes,
            }
            for a in user_anns
        ]
    
    # ── 2. Get AI annotations for reference ──
    ai_anns = db.query(ImageLabelAnnotation).filter(
        ImageLabelAnnotation.image_label_id == label_id,
        ImageLabelAnnotation.source == "ai",
    ).order_by(ImageLabelAnnotation.region_index.asc()).all()
    
    if ai_anns:
        result["has_ai_data"] = True
        result["ai_annotations"] = [
            {
                "id": a.id, "source": a.source, "region_index": a.region_index,
                "body_site": a.body_site, "is_vitiligo": a.is_vitiligo,
                "vitiligo_type": a.vitiligo_type, "vitiligo_stage": a.vitiligo_stage,
                "area_percentage": a.area_percentage, "depigmentation_level": a.depigmentation_level,
                "skin_mask_data": a.skin_mask_data, "mask_data": a.mask_data,
                "confidence": a.confidence, "notes": a.notes,
            }
            for a in ai_anns
        ]
    
    # ── 3. Also check VASIAssessment for live data (may not have been synced yet) ──
    if label.assessment_id:
        assessment = db.query(VASIAssessment).filter(
            VASIAssessment.id == label.assessment_id
        ).first()
        if assessment:
            result["assessment_summary"] = {
                "assessment_id": assessment.id,
                "is_user_corrected": assessment.is_user_corrected,
                "body_site": assessment.body_site,
                "classification": assessment.classification,
                "stage": assessment.stage,
                "vasi_score": assessment.vasi_score,
                "final_vasi_score": assessment.final_vasi_score,
                "area_percentage": assessment.area_percentage,
                "final_area_percentage": assessment.final_area_percentage,
                "depigmentation_level": assessment.depigmentation_level,
                "confidence": assessment.confidence,
            }
            
            # Live user layers
            if assessment.user_skin_layer and not result["has_user_data"]:
                result["has_user_data"] = True
                result["user_annotations"].append({
                    "source": "user", "region_index": 0,
                    "body_site": assessment.body_site,
                    "is_vitiligo": assessment.classification in ("节段型","非节段型","混合型","未定型") if assessment.classification else True,
                    "vitiligo_type": assessment.classification,
                    "area_percentage": assessment.final_area_percentage or assessment.area_percentage,
                    "depigmentation_level": assessment.depigmentation_level,
                    "skin_mask_data": assessment.user_skin_layer,
                    "mask_data": assessment.user_lesion_layer,
                    "notes": "用户测评页面填涂结果（实时数据）— 管理员可在此基础上修改",
                })
            
            # Live AI layers
            if assessment.ai_skin_layer and not result["has_ai_data"]:
                result["has_ai_data"] = True
                result["ai_annotations"].append({
                    "source": "ai", "region_index": 0,
                    "body_site": assessment.body_site,
                    "is_vitiligo": assessment.classification in ("节段型","非节段型","混合型","未定型") if assessment.classification else True,
                    "vitiligo_type": assessment.classification,
                    "area_percentage": assessment.area_percentage,
                    "skin_mask_data": assessment.ai_skin_layer,
                    "mask_data": assessment.ai_lesion_layer,
                    "confidence": assessment.confidence,
                    "notes": "AI 自动填涂图层（实时数据）— 参考用",
                })
    
    return result


@router.delete("/admin/image-labels/{label_id}/annotations")
async def delete_admin_annotations(
    label_id: int,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """删除图片所有人工标注明细 — 重新标注前的清理"""
    label = db.query(ImageLabel).filter(ImageLabel.id == label_id).first()
    if not label:
        raise HTTPException(status_code=404, detail="标注记录不存在")

    deleted = db.query(ImageLabelAnnotation).filter(
        ImageLabelAnnotation.image_label_id == label_id,
        ImageLabelAnnotation.source == "admin",
    ).delete(synchronize_session=False)

    db.commit()
    _log_change(db, label_id, admin_user.id, "delete_all_annotations", "annotations", str(deleted), "0")
    db.commit()

    return {"status": "ok", "deleted": deleted}


@router.get("/admin/image-labels/{label_id}/history")
async def get_label_history(
    label_id: int,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """获取标注变更历史 — 审计追溯"""
    label = db.query(ImageLabel).filter(ImageLabel.id == label_id).first()
    if not label:
        raise HTTPException(status_code=404, detail="标注记录不存在")

    logs = db.query(ImageLabelLog).filter(
        ImageLabelLog.image_label_id == label_id
    ).order_by(ImageLabelLog.created_at.desc()).all()

    return {
        "label_id": label_id,
        "history": [
            {
                "id": log.id,
                "operator_id": log.operator_id,
                "action": log.action,
                "field_name": log.field_name,
                "old_value": log.old_value,
                "new_value": log.new_value,
                "created_at": _format_dt(log.created_at),
            }
            for log in logs
        ],
    }
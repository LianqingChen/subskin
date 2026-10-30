"""Admin-supplied photos into the five-class workflow: batch upload and legacy import.

Both paths canonicalize the photo (EXIF applied and stripped, sRGB, long side
≤ 1024) and store an AI draft, so every task shares the diary's frame.
Only local files under ``data/uploads`` are read — never remote URLs.
"""

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from web.backend.database.models import User
from web.backend.exceptions import RGBSegmentationError
from web.backend.models.image_label import ImageLabel, ImageLabelLog
from web.backend.services.assessment_measurement import read_details
from web.backend.services.labeling import sources
from web.backend.services.rgb_segmentation import artifacts

MAX_FILES = 20
SUBJECT_REF = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _known_sources(db: Session) -> set:
    found = set()
    for (details,) in db.query(ImageLabel.ai_details).filter(ImageLabel.is_user_deleted.is_(False)).all():
        sha = (read_details(details).get("rgb_sync") or {}).get("source_sha256")
        if sha:
            found.add(sha)
    return found


def _provenance(origin: str, actor: int, source_note: str, subject_ref: Optional[str]) -> Dict[str, Any]:
    note = (source_note or "").strip()
    if not note or len(note) > 200:
        raise RGBSegmentationError("INVALID_REQUEST", "请填写图片来源与授权说明（200 字内）")
    if subject_ref and not SUBJECT_REF.fullmatch(subject_ref):
        raise RGBSegmentationError("INVALID_REQUEST", "患者编号只能用字母、数字、下划线或短横线，且不能含真实姓名/手机号")
    return {"origin": origin, "uploaded_by": actor, "source_note": note, "subject_ref": subject_ref or None}


def upload_photos(
    db: Session,
    actor: int,
    files: List[Tuple[str, bytes]],
    source_note: str,
    subject_ref: Optional[str],
    rights_confirmed: bool,
    external: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not rights_confirmed:
        raise RGBSegmentationError("INVALID_REQUEST", "请确认已取得将这些图片用于模型训练的授权")
    if not files or len(files) > MAX_FILES:
        raise RGBSegmentationError("INVALID_REQUEST", "每次上传 1~%d 张" % MAX_FILES)
    provenance = _provenance("admin_upload", actor, source_note, subject_ref)
    if external:
        provenance["external"] = external  # attribution for openly licensed sources (CC BY etc.)
    known = _known_sources(db)
    created, skipped = [], []
    for name, data in files:
        try:
            sync = sources.create_upload_source(data, dict(provenance))
        except RGBSegmentationError as exc:
            skipped.append({"name": name[:80], "reason": str(exc)})
            continue
        if sync["source_sha256"] in known:
            sources.delete_upload_source(ImageLabel(ai_details=json.dumps({"rgb_sync": sync})))
            skipped.append({"name": name[:80], "reason": "重复图片"})
            continue
        known.add(sync["source_sha256"])
        sync["provenance"] = provenance
        label = ImageLabel(
            original_user_id=None,
            assessment_id=None,
            image_url="label-source:" + sync["source_id"],
            label_status="pending",
            is_phi_removed=True,
            ai_details=json.dumps({"rgb_sync": sync}, ensure_ascii=False),
            last_model_version=sync["model"].get("model_id") or sync["model"].get("source"),
            priority_score=0.5,  # no diary version to disagree with; same default as diary tasks
        )
        db.add(label)
        db.flush()
        db.add(ImageLabelLog(image_label_id=label.id, operator_id=actor, action="label-upload",
                             new_value=json.dumps({"origin": "admin_upload", "source_id": sync["source_id"]})))
        created.append(label.id)
    return {"created": created, "skipped": skipped}


def _local_upload(image_url: str) -> Optional[bytes]:
    root = (artifacts.PROJECT_ROOT / "data" / "uploads").resolve()
    match = re.search(r"/api/files/serve/([^?#]+)", image_url or "")
    if match:
        relative = match.group(1)
    elif "data/uploads/" in (image_url or ""):
        relative = image_url.split("data/uploads/", 1)[1]
    else:
        return None
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
        return path.read_bytes() if path.is_file() else None
    except (ValueError, OSError):
        return None


def legacy_candidates(db: Session) -> List[ImageLabel]:
    rows = db.query(ImageLabel).filter(ImageLabel.is_user_deleted.is_(False)).all()
    return [r for r in rows if sources.kind(r) is None and not sources.sync_of(r).get("deleted")]


def import_legacy(db: Session, actor: int, label: ImageLabel, rights_confirmed: bool = False) -> Dict[str, Any]:
    """Turn an old-pipeline row into a five-class task, keeping its id and history."""
    if label.is_user_deleted or sources.kind(label) is not None:
        raise RGBSegmentationError("INVALID_STATE", "该记录无需转换", 409)
    data = _local_upload(label.image_url)
    if data is None:
        raise RGBSegmentationError("NOT_FOUND", "原图不在本地存储中，无法转换", 404)
    owner_id = label.original_user_id
    if label.assessment_id is None and owner_id is not None:
        owner = db.get(User, owner_id)
        if owner is not None and owner.is_admin:
            owner_id = None  # old batch upload recorded the uploading admin as owner
    if owner_id is None and not rights_confirmed:
        raise RGBSegmentationError("INVALID_REQUEST", "旧版后台上传图片须确认有权用于模型训练后才能转入")
    provenance = {"origin": "legacy_import", "uploaded_by": actor, "source_note": "旧版打标记录转入",
                  "subject_ref": None, "rights_confirmed_by": actor if owner_id is None else None}
    sync = sources.create_upload_source(data, dict(provenance))
    label.original_user_id = owner_id
    sync["provenance"] = provenance
    details = read_details(label.ai_details)
    label.ai_details = json.dumps({"rgb_sync": sync, "legacy": details}, ensure_ascii=False)
    label.label_status = "pending"
    label.training_eligible = False
    label.is_phi_removed = True
    db.add(ImageLabelLog(image_label_id=label.id, operator_id=actor, action="label-legacy-import",
                         new_value=json.dumps({"source_id": sync["source_id"]})))
    return {"id": label.id, "source_id": sync["source_id"]}


def import_all_legacy(db: Session, actor: int, rights_confirmed: bool = False) -> Dict[str, Any]:
    done, failed = [], []
    for label in legacy_candidates(db):
        try:
            done.append(import_legacy(db, actor, label, rights_confirmed)["id"])
        except RGBSegmentationError as exc:
            failed.append({"id": label.id, "reason": str(exc)})
    return {"imported": done, "failed": failed}

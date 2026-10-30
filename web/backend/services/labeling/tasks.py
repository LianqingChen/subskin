"""Labeling task queue: visibility, listing, detail and reference layers.

Visibility rule (2026-10-21 decision): diary photos are only visible to admins
when the owner has an active 「帮助改进白斑识别」(``model_training``) grant
covering that record. Admin-supplied photos (no user source) are always visible.
"""

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from sqlalchemy.orm import Session

from web.backend.database.models import User
from web.backend.exceptions import RGBSegmentationError
from web.backend.models.image_label import ImageLabel
from web.backend.models.label_submission import LabelSubmission
from web.backend.services.assessment_measurement import read_details
from web.backend.services.labeling import class_map, sources
from web.backend.utils.body_sites import group_of, label_of, normalize

STATUSES = ("pending", "in_review", "returned", "gold", "rejected", "skipped")
OPEN = ("pending", "returned")


class ConsentCache:
    def __init__(self, db: Session):
        self.db = db
        self.memo: Dict[Tuple[Optional[int], Optional[int]], Any] = {}

    def decision(self, label: ImageLabel):
        from web.backend.services.data_consent import label_training_decision

        key = (label.original_user_id, label.assessment_id)
        if key not in self.memo:
            self.memo[key] = label_training_decision(self.db, label)
        return self.memo[key]


def visible(label: ImageLabel, cache: ConsentCache) -> bool:
    if label.is_user_deleted or sources.kind(label) is None:
        return False
    return label.original_user_id is None or cache.decision(label).allowed


def get_visible(db: Session, label_id: int) -> ImageLabel:
    label = db.get(ImageLabel, label_id)
    if label is None or not visible(label, ConsentCache(db)):
        raise RGBSegmentationError("NOT_FOUND", "任务不存在、已删除或未获训练授权", 404)
    return label


def origin(label: ImageLabel) -> str:
    sync = sources.sync_of(label)
    if sources.kind(label) == "job":
        return "diary"
    return sync.get("origin") or "admin_upload"


def _site(label: ImageLabel, attrs: Optional[Dict[str, Any]] = None) -> Optional[str]:
    value = (attrs or {}).get("body_site") or label.admin_body_site or label.user_body_site or label.ai_body_site
    return normalize(value)


def _latest_submission(db: Session, label_id: int) -> Optional[LabelSubmission]:
    return (
        db.query(LabelSubmission)
        .filter(LabelSubmission.image_label_id == label_id, LabelSubmission.status != "superseded")
        .order_by(LabelSubmission.id.desc())
        .first()
    )


def names_for(db: Session, ids: List[Optional[int]]) -> Dict[int, str]:
    wanted = {i for i in ids if i}
    if not wanted:
        return {}
    rows = db.query(User.id, User.username).filter(User.id.in_(wanted)).all()
    return {r.id: r.username or "管理员%s" % r.id for r in rows}


def submission_summary(row: LabelSubmission, names: Dict[int, str]) -> Dict[str, Any]:
    return {
        "id": row.id,
        "revision": row.revision,
        "status": row.status,
        "author_id": row.author_id,
        "author": names.get(row.author_id),
        "reviewer": names.get(row.reviewer_id) if row.reviewer_id else None,
        "review_mode": row.review_mode,
        "review_note": row.review_note,
        "prefill_source": row.prefill_source,
        "blind": row.blind,
        "duration_ms": row.duration_ms,
        "attributes": read_details(row.attributes),
        "stats": read_details(row.stats),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
    }


def summarize(db: Session, label: ImageLabel, names: Dict[int, str]) -> Dict[str, Any]:
    sync = sources.sync_of(label)
    latest = _latest_submission(db, label.id)
    attrs = read_details(latest.attributes) if latest else {}
    site = _site(label, attrs)
    stats = read_details(latest.stats) if latest else {}
    current_user = sources.current_user_revision(db, label)
    return {
        "id": label.id,
        "origin": origin(label),
        "status": label.label_status,
        "benchmark": bool(label.benchmark),
        "body_site": site,
        "body_site_label": label_of(site),
        "body_group": group_of(site),
        "created_at": label.created_at.isoformat() if label.created_at else None,
        "capture_date": (
            label.assessment.assessment_date.isoformat()
            if label.assessment is not None and label.assessment.assessment_date else None
        ),
        "user_ratio": label.user_area_percentage,
        "lesion_ratio": stats.get("lesion_ratio"),
        "priority": label.priority_score,
        "latest": submission_summary(latest, names) if latest else None,
        "gold": sync.get("gold"),
        "rejection": sync.get("rejection"),
        "escalate": bool(attrs.get("escalate")),
        # Diary owner re-confirmed after this version was labeled.
        "user_revision_newer": bool(latest and current_user and stats.get("user_revision") != current_user),
        "external": _external(sync),
    }


def _external(sync: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Attribution of openly licensed photos (PMC OA / Wikimedia Commons); None otherwise."""
    ext = (sync.get("provenance") or {}).get("external")
    if not ext:
        return None
    keys = ("source", "license", "license_url", "share_alike", "citation", "doi", "pmcid", "figure",
            "caption", "artist", "url")
    return {k: ext.get(k) for k in keys if ext.get(k) is not None}


def list_tasks(db: Session, actor: int, filters: Dict[str, Any], limit: int, offset: int) -> Dict[str, Any]:
    cache = ConsentCache(db)
    rows = [l for l in db.query(ImageLabel).filter(ImageLabel.is_user_deleted.is_(False)).all() if visible(l, cache)]
    names = names_for(db, [])
    items = [summarize(db, l, names) for l in rows]
    items = [i for i in items if _match(i, filters, actor)]
    if filters.get("sort") == "newest":
        items.sort(key=lambda i: i["created_at"] or "", reverse=True)
    else:  # queue order: open work first, highest disagreement first, then oldest
        rank = {"returned": 0, "pending": 1, "in_review": 2, "gold": 3, "rejected": 4, "skipped": 5}
        items.sort(key=lambda i: (rank.get(i["status"], 9), -(i["priority"] or 0), i["created_at"] or ""))
    page = items[offset: offset + limit]
    names = names_for(db, [i["latest"]["author_id"] for i in page if i["latest"]])
    for item in page:
        if item["latest"]:
            item["latest"]["author"] = names.get(item["latest"]["author_id"])
    return {"total": len(items), "items": page, "ids": [i["id"] for i in items][:1000]}


def _match(item: Dict[str, Any], f: Dict[str, Any], actor: int) -> bool:
    status = f.get("status") or "all"
    if status == "open" and item["status"] not in OPEN:
        return False
    if status == "review" and not (item["status"] == "in_review" and item["latest"]):
        return False
    if status not in ("all", "open", "review") and item["status"] != status:
        return False
    if f.get("origin") and item["origin"] != f["origin"]:
        return False
    if f.get("external") and not (
        item["external"] and f["external"] in ("any", item["external"].get("source"))
    ):
        return False
    if f.get("group") and item["body_group"] != f["group"]:
        return False
    if f.get("benchmark") is not None and item["benchmark"] != f["benchmark"]:
        return False
    if f.get("escalate") and not item["escalate"]:
        return False
    if f.get("mine") and not (item["latest"] and item["latest"]["author_id"] == actor):
        return False
    return True


def stats(db: Session) -> Dict[str, Any]:
    cache = ConsentCache(db)
    counts = {s: 0 for s in STATUSES}
    hidden = legacy = 0
    for label in db.query(ImageLabel).filter(ImageLabel.is_user_deleted.is_(False)).all():
        if sources.kind(label) is None:
            legacy += not sources.sync_of(label).get("deleted")
            continue
        if not visible(label, cache):
            hidden += 1
            continue
        counts[label.label_status] = counts.get(label.label_status, 0) + 1
    return {"counts": counts, "total": sum(counts.values()), "hidden_unconsented": hidden, "legacy": legacy}


def detail(db: Session, label: ImageLabel, actor: int) -> Dict[str, Any]:
    history = (
        db.query(LabelSubmission).filter_by(image_label_id=label.id).order_by(LabelSubmission.id.desc()).all()
    )
    names = names_for(db, [r.author_id for r in history] + [r.reviewer_id for r in history])
    item = summarize(db, label, names)
    _, (height, width) = sources.canonical(label)
    blind = bool(label.benchmark) and label.label_status in OPEN
    ai = None if blind else sources.ai_draft(label)
    user = None if blind else sources.user_version(db, label)
    latest = _latest_submission(db, label.id)
    latest_map = None
    if latest is not None:
        from web.backend.services.labeling.submissions import read_snapshot

        try:
            latest_map = class_map.to_data_url(read_snapshot(label.id, latest.revision))
        except RGBSegmentationError:
            latest_map = None
    from web.backend.services.data_consent import label_training_decision

    consent = label_training_decision(db, label) if label.original_user_id is not None else None
    return {
        "task": item,
        "image": {"width": width, "height": height},
        "blind": blind,
        "layers": {
            "ai": class_map.to_data_url(ai) if ai is not None else None,
            "user": class_map.to_data_url(user["labels"]) if user else None,
            "user_revision": user["revision"] if user else None,
            "latest": latest_map,
        },
        "submissions": [submission_summary(r, names) for r in history],
        "consent": {"required": consent is not None, "allowed": consent.allowed if consent else True},
        "provenance": (sources.sync_of(label).get("provenance") or None),
    }


def refresh_priority(db: Session, label: ImageLabel) -> None:
    """Active-learning hint: disagreement between AI draft and diary-confirmed mask."""
    ai = sources.ai_draft(label)
    user = sources.user_version(db, label)
    if ai is None:
        return
    if user is None:
        label.priority_score = 0.5
        return
    agree = class_map.agreement(ai, user["labels"])
    lesion = agree["lesion_dice"]
    label.priority_score = round(1 - lesion, 4) if lesion is not None else 0.0


def edge_snap(label: ImageLabel, labels_data_url: str) -> str:
    """Snap the lesion class onto colour edges inside skin; returns an updated class map."""
    import io

    from PIL import Image

    from web.backend.services.rgb_segmentation.inference import snap_visible_mask

    image, shape = sources.canonical(label)
    labels = class_map.from_data_url(labels_data_url, shape)
    lesion = labels == class_map.LESION
    if not lesion.any():
        raise RGBSegmentationError("INVALID_INPUT", "还没有白斑范围可贴合")
    skin = np.isin(labels, (class_map.NORMAL, class_map.LESION))
    rgb = np.asarray(Image.open(io.BytesIO(image)).convert("RGB"))
    snapped = snap_visible_mask(rgb, skin, lesion)
    out = labels.copy()
    out[lesion & ~snapped] = class_map.NORMAL
    out[snapped] = class_map.LESION
    return class_map.to_data_url(out)


def redraft(label: ImageLabel) -> Dict[str, Any]:
    import io

    from PIL import Image

    image, _ = sources.canonical(label)
    rgb = np.asarray(Image.open(io.BytesIO(image)).convert("RGB"))
    # Prefer face-plaque HistGB (L-180-5); falls back to infer_rgb when mediapipe/model unavailable.
    labels, meta = sources.draft_for_labeling_workspace(rgb)
    return {"labels": class_map.to_data_url(labels), "source": meta.get("source"), "check": meta.get("draft_check")}

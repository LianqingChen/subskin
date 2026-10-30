"""Labeling progress: throughput, review load, agreement and coverage vs. the gate."""

from collections import defaultdict
from datetime import datetime, timedelta
from statistics import mean
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from web.backend.exceptions import RGBSegmentationError
from web.backend.models.image_label import ImageLabel
from web.backend.models.label_submission import LabelSubmission
from web.backend.services.assessment_measurement import read_details
from web.backend.services.labeling import class_map, tasks
from web.backend.services.rgb_segmentation.dataset_pipeline import GATE


def _avg(values: List[Optional[float]]) -> Optional[float]:
    clean = [v for v in values if v is not None]
    return round(mean(clean), 3) if clean else None


def _inter_annotator(db: Session, label_ids: List[int]) -> Dict[str, Any]:
    """Dice between the latest versions of two different annotators on the same task."""
    from web.backend.services.labeling.submissions import read_snapshot

    lesion, skin = [], []
    for label_id in label_ids[:50]:
        rows = (
            db.query(LabelSubmission).filter_by(image_label_id=label_id)
            .order_by(LabelSubmission.id.desc()).all()
        )
        latest_by_author: Dict[int, LabelSubmission] = {}
        for row in rows:
            latest_by_author.setdefault(row.author_id, row)
        if len(latest_by_author) < 2:
            continue
        a, b = list(latest_by_author.values())[:2]
        try:
            agree = class_map.agreement(read_snapshot(label_id, a.revision), read_snapshot(label_id, b.revision))
        except RGBSegmentationError:
            continue
        lesion.append(agree["lesion_dice"])
        skin.append(agree["skin_dice"])
    return {"pairs": len(lesion), "lesion_dice": _avg(lesion), "skin_dice": _avg(skin)}


def progress(db: Session) -> Dict[str, Any]:
    since = datetime.utcnow() - timedelta(days=30)
    recent = db.query(LabelSubmission).filter(LabelSubmission.created_at >= since).all()
    names = tasks.names_for(db, [r.author_id for r in recent])
    per_author: Dict[int, Dict[str, Any]] = defaultdict(lambda: {"submitted": 0, "approved": 0, "returned": 0, "durations": []})
    for row in recent:
        entry = per_author[row.author_id]
        entry["submitted"] += 1
        entry["approved"] += row.status == "approved"
        entry["returned"] += row.status == "returned"
        if row.duration_ms:
            entry["durations"].append(row.duration_ms / 60000)
    annotators = [
        {
            "author_id": author,
            "author": names.get(author),
            "submitted": e["submitted"],
            "approved": e["approved"],
            "returned": e["returned"],
            "minutes_per_image": _avg(e["durations"]),
        }
        for author, e in sorted(per_author.items(), key=lambda kv: -kv[1]["submitted"])
    ]
    stats = [read_details(r.stats) for r in recent]
    draft_quality = {
        "vs_ai_lesion_dice": _avg([(s.get("vs_ai") or {}).get("lesion_dice") for s in stats]),
        "vs_ai_skin_dice": _avg([(s.get("vs_ai") or {}).get("skin_dice") for s in stats]),
        "vs_user_lesion_dice": _avg([(s.get("vs_user") or {}).get("lesion_dice") for s in stats]),
    }

    cache = tasks.ConsentCache(db)
    coverage: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    gold = negatives = benchmark = 0
    subjects, multi_author = set(), []
    for label in db.query(ImageLabel).filter(ImageLabel.is_user_deleted.is_(False)).all():
        if not tasks.visible(label, cache):
            continue
        if db.query(LabelSubmission.author_id).filter_by(image_label_id=label.id).distinct().count() > 1:
            multi_author.append(label.id)
        if label.label_status != "gold":
            continue
        gold += 1
        benchmark += bool(label.benchmark)
        approved = (
            db.query(LabelSubmission).filter_by(image_label_id=label.id, status="approved")
            .order_by(LabelSubmission.id.desc()).first()
        )
        attrs = read_details(approved.attributes) if approved else {}
        summary = read_details(approved.stats) if approved else {}
        negatives += not summary.get("has_lesion", True)
        tone = attrs.get("monk_skin_tone")
        band = "unknown" if not tone else "mst_1_3" if tone <= 3 else "mst_4_6" if tone <= 6 else "mst_7_10"
        coverage[tasks.summarize(db, label, {})["body_group"]][band] += 1
        subjects.add((label.original_user_id, None if label.original_user_id else label.id))
    return {
        "window_days": 30,
        "annotators": annotators,
        "awaiting_review": db.query(LabelSubmission).filter_by(status="submitted").count(),
        "draft_quality": draft_quality,
        "inter_annotator": _inter_annotator(db, multi_author),
        "gold": {
            "total": gold,
            "negatives": negatives,
            "benchmark": benchmark,
            "subjects_estimate": len(subjects),
            "coverage": {group: dict(bands) for group, bands in coverage.items()},
        },
        "gate": GATE,
    }

"""Read-only, deduplicated experience aggregates; never return contributor IDs."""
from datetime import datetime, timedelta, timezone
from math import sqrt
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from web.backend.database.models import Hospital, HospitalReview
from web.backend.models.hospital_discovery import (
    ExperienceDimensionSummary,
    HospitalExperienceResponse,
    HospitalExperienceSummary,
)
from web.backend.services.review_risk import EXPERIENCE_DIMENSIONS

MINIMUM = 20
WINDOW_DAYS = 365


def wilson_lower(satisfied: int, answered: int) -> float:
    """95% Wilson lower bound for satisfied vs all other answered responses."""
    if answered <= 0:
        return 0.0
    z = 1.96
    p = satisfied / answered
    return (p + z * z / (2 * answered) - z * sqrt(
        p * (1 - p) / answered + z * z / (4 * answered * answered)
    )) / (1 + z * z / answered)


def experience_summary(
    db: Session, now: Optional[datetime] = None
) -> HospitalExperienceResponse:
    """Use the latest eligible review per account and hospital in a 365-day window."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is not None:
        now = now.astimezone(timezone.utc).replace(tzinfo=None)
    start = now - timedelta(days=WINDOW_DAYS)
    hospital_ids = [row.id for row in db.query(Hospital.id).filter(Hospital.status == "visible").all()]
    rows = (
        db.query(HospitalReview.hospital_id, HospitalReview.user_id, HospitalReview.experience_scores)
        .join(Hospital, Hospital.id == HospitalReview.hospital_id)
        .filter(
            Hospital.status == "visible", HospitalReview.status == "visible",
            HospitalReview.moderation_status == "approved",
            HospitalReview.health_consent.is_(True),
            HospitalReview.created_at >= start, HospitalReview.created_at <= now,
            or_(HospitalReview.aggregate_after.is_(None), HospitalReview.aggregate_after <= now),
        )
        .order_by(HospitalReview.created_at.desc(), HospitalReview.id.desc()).all()
    )
    seen = set()
    counts = {hid: {name: dict(satisfied=0, neutral=0, unsatisfied=0, na=0)
                    for name in EXPERIENCE_DIMENSIONS} for hid in hospital_ids}
    participants = {hid: 0 for hid in hospital_ids}
    for row in rows:
        key = (row.hospital_id, row.user_id)
        if key in seen:
            continue
        seen.add(key)
        scores = row.experience_scores if isinstance(row.experience_scores, dict) else {}
        valid = {name: level for name, level in scores.items()
                 if name in counts[row.hospital_id] and level in ("satisfied", "neutral", "unsatisfied", "na")}
        if valid:
            participants[row.hospital_id] += 1
        for name, level in valid.items():
            counts[row.hospital_id][name][level] += 1
    items = []
    for hid in hospital_ids:
        dimensions = []
        for name, values in counts[hid].items():
            answered = values["satisfied"] + values["neutral"] + values["unsatisfied"]
            eligible = answered >= MINIMUM
            dimensions.append(ExperienceDimensionSummary(
                dimension=name, answered=answered, **values, eligible=eligible,
                reference_score=round(wilson_lower(values["satisfied"], answered) * 100, 6) if eligible else None,
            ))
        items.append(HospitalExperienceSummary(hospital_id=hid, participants=participants[hid], dimensions=dimensions))
    return HospitalExperienceResponse(
        window_start=start.isoformat() + "Z", as_of=now.isoformat() + "Z",
        minimum=MINIMUM, window_days=WINDOW_DAYS, items=items,
    )

"""Read-only cohort-safe chart data; acceptance dates need immutable logs."""

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from web.backend.models.image_label import ImageLabelLog
from web.backend.services.contribution import MIN_PUBLIC_COUNT, eligible_labels, metric
from web.backend.utils.contribution_rules import BODY_SITES, VERSION, body_site_code

WINDOW_MONTHS = 6
SHANGHAI = timezone(timedelta(hours=8))


def month_keys(now: Optional[datetime] = None) -> list[str]:
    """Six calendar months in the user's reporting timezone."""
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    local = current.astimezone(SHANGHAI)
    last = local.year * 12 + local.month - 1
    return [
        f"{n // 12:04d}-{n % 12 + 1:02d}"
        for n in range(last - WINDOW_MONTHS + 1, last + 1)
    ]


def acceptance_months(db: Session, labels: list) -> dict[int, str]:
    """First verifiable acceptance event, never mutable labeled_at/credit time.

    save_draft and generic updates do not prove acceptance. A historical
    missing log stays unknown, rather than being reconstructed from uploads.
    """
    ids = [row.id for row in labels]
    if not ids:
        return {}
    dates = (
        db.query(ImageLabelLog.image_label_id, func.min(ImageLabelLog.created_at))
        .filter(
            ImageLabelLog.image_label_id.in_(ids),
            ImageLabelLog.action.in_(["update", "add_training_sample"]),
            ImageLabelLog.field_name == "training_eligible",
            ImageLabelLog.new_value.in_(["True", "true", "1"]),
        )
        .group_by(ImageLabelLog.image_label_id)
        .all()
    )
    result = {}
    now = datetime.now(timezone.utc)
    for label_id, date in dates:
        if date is None:
            continue
        utc = (
            date.replace(tzinfo=timezone.utc)
            if date.tzinfo is None
            else date.astimezone(timezone.utc)
        )
        if utc > now:
            continue
        result[label_id] = utc.astimezone(SHANGHAI).strftime("%Y-%m")
    return result


def timeline(db: Session, user_id: Optional[int] = None) -> dict:
    """Currently valid images grouped by their verifiable acceptance month.

    Public bins, including unknown/outside-window remainders, need both five
    images and five contributing accounts. Suppress the whole timeline if a
    remainder can otherwise be inferred by subtracting bins from the total.
    """
    keys = month_keys()
    all_rows = eligible_labels(db)
    dates = acceptance_months(db, all_rows)
    buckets = {key: [] for key in keys}
    buckets.update({"unknown": [], "earlier": []})
    for row in all_rows:
        month = dates.get(row.id)
        key = month if month in keys else "unknown" if month is None else "earlier"
        buckets[key].append(row)
    suppressed = any(
        rows
        and (
            len(rows) < MIN_PUBLIC_COUNT
            or len({r.original_user_id for r in rows}) < MIN_PUBLIC_COUNT
        )
        for rows in buckets.values()
    )
    periods = []
    for key in keys:
        rows = buckets[key]
        own = (
            sum(1 for r in rows if r.original_user_id == user_id)
            if user_id is not None
            else None
        )
        others = len(rows) - own if own is not None else None
        # Do not explicitly expose a small residual subgroup in the stacked bar.
        split_safe = not suppressed and (
            others is None or others == 0 or others >= MIN_PUBLIC_COUNT
        )
        periods.append(
            {
                "month": key,
                "total": None if suppressed else len(rows),
                "mine": own,
                "others": others if split_safe else None,
            }
        )
    result = {
        "status": "suppressed" if suppressed else "available",
        "updated_at": datetime.utcnow().isoformat() + "Z",
        "version": VERSION,
        "timezone": "Asia/Shanghai",
        "periods": periods,
        "unknown_dates": metric(
            None if suppressed else len(buckets["unknown"]),
            "采纳日期缺少可核验日志",
            "suppressed" if suppressed else "available",
        ),
        "earlier": metric(
            None if suppressed else len(buckets["earlier"]),
            "当前仍有效、在展示月份之前采纳的图片",
            "suppressed" if suppressed else "available",
        ),
        "note": "只统计当前有效图片，按首次可核验采纳日志归入月份；不是历史库规模快照。授权撤回后相应数量会更新。日期缺失不推测，当前月份为截至更新时间的部分月份。",
    }
    if user_id is not None:
        result["own_unknown_dates"] = metric(
            sum(1 for r in buckets["unknown"] if r.original_user_id == user_id),
            "本人有效图片中采纳日期待补充的数量",
        )
        result["own_earlier"] = metric(
            sum(1 for r in buckets["earlier"] if r.original_user_id == user_id),
            "本人在展示月份之前采纳的有效图片",
        )
    return result


def personal_visuals(db: Session, user_id: int) -> dict:
    """Only the authenticated person's distribution; no other user IDs."""
    counts = dict.fromkeys(dict(BODY_SITES), 0)
    for row in eligible_labels(db, user_id):
        counts[
            body_site_code(
                row.user_body_site or row.admin_body_site or row.assessment.body_site
            )
        ] += 1
    return {
        "updated_at": datetime.utcnow().isoformat() + "Z",
        "body_sites": [
            {"code": code, "count": count} for code, count in counts.items()
        ],
        "timeline": timeline(db, user_id),
    }

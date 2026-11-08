"""Knowledge hub reads, review transitions and seed loading.

Public readers only ever see ``published`` rows. Admins may pass ``preview``
to see unpublished rows (each tagged with its status) on the main app.
Publishing requires a recorded medical review; editing a reviewed row is not
done here — content changes go through the seed file and back to draft.
"""

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from web.backend.exceptions import KnowledgeError
from web.backend.models.data_consent import DataConsentGrant
from web.backend.models.knowledge import (
    EVIDENCE_LEVELS,
    KnowledgeAlias,
    KnowledgeCard,
    KnowledgeDigest,
    KnowledgeEntity,
    KnowledgePipelineItem,
    KnowledgeRelation,
    KnowledgeReviewLog,
)
from web.backend.services import data_consent

DISCLAIMER = "本文不构成医疗建议。内容为健康科普，具体诊断与治疗请咨询皮肤科医生。"
CARD_REVIEW_DAYS = 365
MIN_PUBLIC_COUNT = 5
OPEN_PURPOSES = ("model_training",)
PURPOSE_DESCRIPTIONS = {
    "model_training": "把你授权的日记照片用于训练和评估白斑识别模型。不会公开照片，可随时撤回。",
    "research_project": "逐个研究项目单独授权，项目须经合作机构伦理审查并在这里公示后才开放。",
    "public_share": "在「分享」中公开你选定的内容，由你逐条决定。",
    "clinician_review": "让你指定的医生查看并确认记录，医生工具上线后开放。",
}
KINDS = {
    "cards": KnowledgeCard,
    "pipeline": KnowledgePipelineItem,
    "digests": KnowledgeDigest,
    "relations": KnowledgeRelation,
}
# from → allowed targets (any non-draft state may also go back to draft)
TRANSITIONS = {
    "draft": ("editor_reviewed",),
    "editor_reviewed": ("medical_reviewed",),
    "medical_reviewed": ("published",),
    "published": ("retired",),
    "retired": (),
}


def _loads(value: Optional[str], default: Any) -> Any:
    try:
        parsed = json.loads(value) if value else default
    except (TypeError, ValueError):
        return default
    return parsed if isinstance(parsed, type(default)) else default


def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() + "Z" if value else None


def _visible(query, model, preview: bool):
    if preview:
        return query.filter(model.status != "retired")
    return query.filter(model.status == "published")


def _reviewed_at(row) -> Optional[str]:
    return _iso(row.medical_reviewed_at)


# ---------------------------------------------------------------- public reads


def topics_from(cards: List[KnowledgeCard], labels: Dict[str, str]) -> List[dict]:
    seen = []
    for card in cards:
        if card.topic not in seen:
            seen.append(card.topic)
    return [{"key": key, "label": labels.get(key, key)} for key in seen]


def card_summary(card: KnowledgeCard) -> dict:
    return {
        "slug": card.slug,
        "topic": card.topic,
        "title": card.title,
        "summary": card.summary,
        "evidence_level": card.evidence_level,
        "source_count": len(_loads(card.sources_json, [])),
        "reviewed_at": _reviewed_at(card),
        "ai_assisted": bool(card.ai_assisted),
        "status": card.status,
    }


def list_cards(db: Session, topic: Optional[str], preview: bool, labels: Dict[str, str]) -> dict:
    query = _visible(db.query(KnowledgeCard), KnowledgeCard, preview)
    cards = query.order_by(KnowledgeCard.sort_order, KnowledgeCard.id).all()
    items = [c for c in cards if not topic or c.topic == topic]
    return {"topics": topics_from(cards, labels), "items": [card_summary(c) for c in items]}


def get_card(db: Session, slug: str, preview: bool) -> dict:
    card = _visible(db.query(KnowledgeCard), KnowledgeCard, preview).filter_by(slug=slug).first()
    if card is None:
        raise KnowledgeError("NOT_FOUND", "内容不存在或尚未发布", 404)
    visible_related = {
        row.slug
        for row in _visible(db.query(KnowledgeCard.slug, KnowledgeCard.status), KnowledgeCard, preview)
    }
    return {
        **card_summary(card),
        "body_md": card.body_md,
        "sources": _loads(card.sources_json, []),
        "next_review_at": _iso(card.next_review_at),
        "related": [s for s in _loads(card.related_json, []) if s in visible_related],
        "disclaimer": DISCLAIMER,
    }


def list_pipeline(db: Session, preview: bool) -> dict:
    rows = (
        _visible(db.query(KnowledgePipelineItem), KnowledgePipelineItem, preview)
        .order_by(KnowledgePipelineItem.sort_order, KnowledgePipelineItem.id)
        .all()
    )
    return {
        "updated_at": max((r.checked_at for r in rows if r.checked_at), default=None),
        "items": [
            {
                "key": r.key,
                "drug_zh": r.drug_zh,
                "drug_en": r.drug_en,
                "mechanism": r.mechanism,
                "route": r.route,
                "sponsor": r.sponsor,
                "phase": r.phase,
                "regions": _loads(r.regions_json, []),
                "latest_event": r.latest_event,
                "event_date": r.event_date,
                "sources": _loads(r.sources_json, []),
                "checked_at": r.checked_at,
                "status": r.status,
            }
            for r in rows
        ],
    }


def list_digests(db: Session, preview: bool, limit: int) -> dict:
    rows = (
        _visible(db.query(KnowledgeDigest), KnowledgeDigest, preview)
        .order_by(KnowledgeDigest.published_on.desc(), KnowledgeDigest.id.desc())
        .limit(limit)
        .all()
    )
    return {
        "items": [
            {
                "key": r.key,
                "title_zh": r.title_zh,
                "title_en": r.title_en,
                "one_liner": r.one_liner,
                "why_it_matters": r.why_it_matters,
                "limitations": r.limitations,
                "study_type": r.study_type,
                "sample_size": r.sample_size,
                "is_preprint": bool(r.is_preprint),
                "published_on": r.published_on,
                "journal": r.journal,
                "url": r.url,
                "pmid": r.pmid,
                "status": r.status,
            }
            for r in rows
        ]
    }


def research_overview(db: Session) -> dict:
    """Where community data goes. Counts are people with an active grant, k≥5."""
    now = datetime.utcnow()
    active: Dict[str, set] = {p: set() for p in data_consent.PURPOSES}
    for grant in db.query(DataConsentGrant).all():
        if data_consent.grant_state(db, grant, now) == "active":
            active[grant.purpose].add(grant.user_id)
    purposes = []
    for purpose, meta in data_consent.PURPOSES.items():
        count = len(active.get(purpose, ()))
        is_open = purpose in OPEN_PURPOSES
        if not is_open:
            metric = {"value": None, "status": "unavailable", "note": "尚未开放"}
        elif 0 < count < MIN_PUBLIC_COUNT:
            metric = {"value": None, "status": "suppressed", "note": "人数较少暂不公开"}
        else:
            metric = {"value": count, "status": "available", "note": "当前有效授权人数"}
        purposes.append(
            {
                "purpose": purpose,
                "title": meta["title"],
                "description": PURPOSE_DESCRIPTIONS.get(purpose, ""),
                "open": is_open,
                "active": metric,
            }
        )
    return {
        "purposes": purposes,
        "projects": [],
        "note": "目前没有使用社区数据的外部研究项目。任何项目上线前都会在这里公示，并单独征得你的同意。",
    }


def entity_graph(db: Session, key: str, preview: bool) -> dict:
    entity = db.query(KnowledgeEntity).filter_by(key=key).first()
    if entity is None:
        alias = db.query(KnowledgeAlias).filter_by(alias=key).first()
        entity = db.get(KnowledgeEntity, alias.entity_id) if alias else None
    if entity is None:
        raise KnowledgeError("NOT_FOUND", "没有找到这个概念", 404)
    rels = (
        _visible(db.query(KnowledgeRelation), KnowledgeRelation, preview)
        .filter(
            (KnowledgeRelation.subject_id == entity.id)
            | (KnowledgeRelation.object_id == entity.id)
        )
        .all()
    )
    ids = {entity.id} | {r.subject_id for r in rels} | {r.object_id for r in rels}
    nodes = {e.id: e for e in db.query(KnowledgeEntity).filter(KnowledgeEntity.id.in_(ids))}

    def node(e: KnowledgeEntity) -> dict:
        return {
            "key": e.key,
            "type": e.type,
            "name_zh": e.name_zh,
            "name_en": e.name_en,
            "description_zh": e.description_zh,
            "external_ids": _loads(e.external_ids_json, {}),
        }

    return {
        "entity": node(entity),
        "nodes": [node(e) for e in nodes.values()],
        "edges": [
            {
                "subject": nodes[r.subject_id].key,
                "predicate": r.predicate,
                "object": nodes[r.object_id].key,
                "evidence_level": r.evidence_level,
                "region": r.region,
                "sources": _loads(r.sources_json, []),
                "status": r.status,
            }
            for r in rels
            if r.subject_id in nodes and r.object_id in nodes
        ],
    }


# ---------------------------------------------------------------- admin review


def _model(kind: str):
    model = KINDS.get(kind)
    if model is None:
        raise KnowledgeError("INVALID_REQUEST", "内容类型无效")
    return model


def _admin_row(kind: str, row) -> dict:
    base = {
        "id": row.id,
        "status": row.status,
        "seed_version": row.seed_version,
        "reviewer_notes": row.reviewer_notes,
        "medical_reviewer_label": row.medical_reviewer_label,
        "medical_reviewed_at": _iso(row.medical_reviewed_at),
        "published_at": _iso(row.published_at),
        "updated_at": _iso(row.updated_at),
    }
    if kind == "cards":
        return {**base, **card_summary(row), "body_md": row.body_md,
                "sources": _loads(row.sources_json, []), "status": row.status}
    if kind == "pipeline":
        return {**base, "key": row.key, "title": f"{row.drug_zh}（{row.drug_en or ''}）",
                "phase": row.phase, "latest_event": row.latest_event,
                "regions": _loads(row.regions_json, []), "sources": _loads(row.sources_json, [])}
    if kind == "digests":
        return {**base, "key": row.key, "title": row.title_zh, "title_en": row.title_en,
                "one_liner": row.one_liner, "why_it_matters": row.why_it_matters,
                "limitations": row.limitations, "url": row.url, "pmid": row.pmid}
    return {**base, "title": f"{row.subject_id} {row.predicate} {row.object_id}",
            "evidence_level": row.evidence_level, "sources": _loads(row.sources_json, [])}


def admin_list(db: Session, kind: str, status: Optional[str]) -> dict:
    model = _model(kind)
    query = db.query(model)
    if status:
        query = query.filter(model.status == status)
    rows = query.order_by(model.id).all()
    counts: Dict[str, int] = {}
    for row in db.query(model.status).all():
        counts[row.status] = counts.get(row.status, 0) + 1
    return {"items": [_admin_row(kind, r) for r in rows], "counts": counts}


def transition(
    db: Session,
    kind: str,
    item_id: int,
    to: str,
    actor_id: int,
    note: str = "",
    reviewer_label: str = "",
) -> dict:
    model = _model(kind)
    row = db.get(model, item_id)
    if row is None:
        raise KnowledgeError("NOT_FOUND", "内容不存在", 404)
    current = row.status
    note = (note or "").strip()[:1000]
    reviewer_label = (reviewer_label or "").strip()[:100]
    if to == current:
        raise KnowledgeError("INVALID_STATE", "状态没有变化", 409)
    if to != "draft" and to not in TRANSITIONS.get(current, ()):
        raise KnowledgeError("INVALID_STATE", f"不能从 {current} 变为 {to}", 409)
    if to == "draft" and not note:
        raise KnowledgeError("INVALID_REQUEST", "退回草稿请写明原因")
    if to == "medical_reviewed" and not reviewer_label:
        raise KnowledgeError("INVALID_REQUEST", "请填写医学审核人（姓名与资质）")
    now = datetime.utcnow()
    if to == "editor_reviewed":
        row.editor_reviewed_by = actor_id
    elif to == "medical_reviewed":
        row.medical_reviewer_label = reviewer_label
        row.medical_reviewed_at = now
    elif to == "published":
        row.published_at = now
        if kind == "cards":
            row.next_review_at = now + timedelta(days=CARD_REVIEW_DAYS)
    elif to == "draft":
        # Any return to draft voids previous reviews; it must be reviewed again.
        row.editor_reviewed_by = None
        row.medical_reviewer_label = None
        row.medical_reviewed_at = None
        row.published_at = None
    row.status = to
    db.add(
        KnowledgeReviewLog(
            kind=kind,
            item_id=row.id,
            actor_id=actor_id,
            from_status=current,
            to_status=to,
            note=note or None,
            reviewer_label=reviewer_label or None,
        )
    )
    db.commit()
    return _admin_row(kind, row)


def review_logs(db: Session, kind: str, item_id: int) -> List[dict]:
    _model(kind)
    rows = (
        db.query(KnowledgeReviewLog)
        .filter_by(kind=kind, item_id=item_id)
        .order_by(KnowledgeReviewLog.id)
        .all()
    )
    return [
        {
            "from": r.from_status,
            "to": r.to_status,
            "actor_id": r.actor_id,
            "note": r.note,
            "reviewer_label": r.reviewer_label,
            "at": _iso(r.created_at),
        }
        for r in rows
    ]


# ---------------------------------------------------------------- seed loading


def _level(value: Optional[str]) -> str:
    return value if value in EVIDENCE_LEVELS else "D"


def _dump(value: Any) -> Optional[str]:
    return json.dumps(value, ensure_ascii=False) if value is not None else None


def _upsert_reviewed(db: Session, model, key_field: str, key: str, fields: dict, version: str) -> str:
    """Insert new rows as draft; refresh only rows that are still draft."""
    row = db.query(model).filter(getattr(model, key_field) == key).first()
    if row is None:
        db.add(model(**{key_field: key}, **fields, status="draft", seed_version=version))
        return "created"
    if row.status != "draft":
        return "kept"
    for name, value in fields.items():
        setattr(row, name, value)
    row.seed_version = version
    return "updated"


def load_seed(db: Session, data: dict) -> Dict[str, Dict[str, int]]:
    version = str(data.get("version") or "unversioned")[:40]
    stats: Dict[str, Dict[str, int]] = {}

    def bump(section: str, outcome: str) -> None:
        stats.setdefault(section, {}).setdefault(outcome, 0)
        stats[section][outcome] += 1

    for order, card in enumerate(data.get("cards", [])):
        bump("cards", _upsert_reviewed(db, KnowledgeCard, "slug", card["slug"], {
            "topic": card["topic"],
            "title": card["title"][:120],
            "summary": card["summary"][:300],
            "body_md": card["body_md"],
            "evidence_level": _level(card.get("evidence_level")),
            "sources_json": _dump(card.get("sources", [])),
            "related_json": _dump(card.get("related", [])),
            "reviewer_notes": card.get("reviewer_notes"),
            "ai_assisted": 1,
            "sort_order": order,
        }, version))
    for order, item in enumerate(data.get("pipeline", [])):
        bump("pipeline", _upsert_reviewed(db, KnowledgePipelineItem, "key", item["key"], {
            "drug_zh": item["drug_zh"],
            "drug_en": item.get("drug_en"),
            "mechanism": item.get("mechanism"),
            "route": item.get("route"),
            "sponsor": item.get("sponsor"),
            "phase": item.get("phase"),
            "regions_json": _dump(item.get("regions", [])),
            "latest_event": item.get("latest_event"),
            "event_date": item.get("event_date"),
            "sources_json": _dump(item.get("sources", [])),
            "checked_at": item.get("checked_at"),
            "reviewer_notes": item.get("reviewer_notes"),
            "sort_order": order,
        }, version))
    for item in data.get("digests", []):
        bump("digests", _upsert_reviewed(db, KnowledgeDigest, "key", item["key"], {
            "title_zh": item["title_zh"],
            "title_en": item.get("title_en"),
            "one_liner": item["one_liner"],
            "why_it_matters": item.get("why_it_matters"),
            "limitations": item.get("limitations"),
            "study_type": item.get("study_type"),
            "sample_size": item.get("sample_size"),
            "is_preprint": 1 if item.get("is_preprint") else 0,
            "published_on": item.get("published_on"),
            "journal": item.get("journal"),
            "url": item.get("url"),
            "pmid": item.get("pmid"),
            "reviewer_notes": item.get("reviewer_notes"),
        }, version))

    for item in data.get("entities", []):
        row = db.query(KnowledgeEntity).filter_by(key=item["key"]).first()
        if row is None:
            row = KnowledgeEntity(key=item["key"])
            db.add(row)
            bump("entities", "created")
        else:
            bump("entities", "updated")
        row.type = item["type"]
        row.name_zh = item["name_zh"]
        row.name_en = item.get("name_en")
        row.description_zh = item.get("description_zh")
        row.external_ids_json = _dump(item.get("external_ids") or {})
        row.seed_version = version
        db.flush()
        existing = {a.alias for a in db.query(KnowledgeAlias).filter_by(entity_id=row.id)}
        for alias in item.get("aliases", []):
            if alias and alias not in existing:
                db.add(KnowledgeAlias(entity_id=row.id, alias=alias[:120]))
                existing.add(alias)
    all_ids = {e.key: e.id for e in db.query(KnowledgeEntity.key, KnowledgeEntity.id)}
    for item in data.get("relations", []):
        subject, obj = all_ids.get(item["subject"]), all_ids.get(item["object"])
        if subject is None or obj is None:
            bump("relations", "skipped_unknown_entity")
            continue
        fields = {
            "evidence_level": _level(item.get("evidence_level")),
            "region": item.get("region"),
            "sources_json": _dump(item.get("sources", [])),
            "extracted_by": "seed",
        }
        row = db.query(KnowledgeRelation).filter_by(
            subject_id=subject, predicate=item["predicate"], object_id=obj
        ).first()
        if row is None:
            db.add(KnowledgeRelation(subject_id=subject, predicate=item["predicate"],
                                     object_id=obj, status="draft", seed_version=version, **fields))
            bump("relations", "created")
        elif row.status == "draft":
            for name, value in fields.items():
                setattr(row, name, value)
            row.seed_version = version
            bump("relations", "updated")
        else:
            bump("relations", "kept")
    db.commit()
    return stats

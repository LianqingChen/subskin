"""Vitiligo knowledge hub: ontology-backed, evidence-graded, review-gated content.

Nothing here holds personal data. Public content is only what reached
``published`` through medical review; everything starts as ``draft``.
"""

from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from web.backend.database.database import Base

# draft → editor_reviewed → medical_reviewed → published → retired; any → draft
STATUSES = ("draft", "editor_reviewed", "medical_reviewed", "published", "retired")
EVIDENCE_LEVELS = ("A", "B", "C", "D", "E")


class _Reviewed:
    status = Column(String(20), nullable=False, default="draft", index=True)
    seed_version = Column(String(40), nullable=True)
    reviewer_notes = Column(Text, nullable=True)  # internal only, never public
    editor_reviewed_by = Column(Integer, nullable=True)
    medical_reviewer_label = Column(String(100), nullable=True)
    medical_reviewed_at = Column(DateTime, nullable=True)
    published_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class KnowledgeEntity(Base):
    __tablename__ = "knowledge_entities"

    id = Column(Integer, primary_key=True)
    key = Column(String(80), nullable=False, unique=True)
    type = Column(String(30), nullable=False, index=True)
    name_zh = Column(String(120), nullable=False)
    name_en = Column(String(160), nullable=True)
    description_zh = Column(Text, nullable=True)
    external_ids_json = Column(Text, nullable=True)
    seed_version = Column(String(40), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class KnowledgeAlias(Base):
    __tablename__ = "knowledge_aliases"
    __table_args__ = (UniqueConstraint("entity_id", "alias", name="uq_knowledge_alias"),)

    id = Column(Integer, primary_key=True)
    entity_id = Column(
        Integer, ForeignKey("knowledge_entities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    alias = Column(String(120), nullable=False, index=True)


class KnowledgeRelation(_Reviewed, Base):
    __tablename__ = "knowledge_relations"
    __table_args__ = (
        UniqueConstraint("subject_id", "predicate", "object_id", name="uq_knowledge_relation"),
    )

    id = Column(Integer, primary_key=True)
    subject_id = Column(Integer, ForeignKey("knowledge_entities.id", ondelete="CASCADE"), nullable=False, index=True)
    predicate = Column(String(40), nullable=False)
    object_id = Column(Integer, ForeignKey("knowledge_entities.id", ondelete="CASCADE"), nullable=False, index=True)
    evidence_level = Column(String(1), nullable=False, default="D")
    region = Column(String(40), nullable=True)
    extracted_by = Column(String(80), nullable=False, default="seed")
    sources_json = Column(Text, nullable=True)  # [{type, ref, quote}]


class KnowledgeCard(_Reviewed, Base):
    __tablename__ = "knowledge_cards"

    id = Column(Integer, primary_key=True)
    slug = Column(String(80), nullable=False, unique=True)
    topic = Column(String(40), nullable=False, index=True)
    title = Column(String(120), nullable=False)
    summary = Column(String(300), nullable=False)
    body_md = Column(Text, nullable=False)
    evidence_level = Column(String(1), nullable=False, default="D")
    sources_json = Column(Text, nullable=True)
    related_json = Column(Text, nullable=True)
    ai_assisted = Column(Integer, nullable=False, default=1)
    sort_order = Column(Integer, nullable=False, default=0)
    next_review_at = Column(DateTime, nullable=True)


class KnowledgePipelineItem(_Reviewed, Base):
    __tablename__ = "knowledge_pipeline_items"

    id = Column(Integer, primary_key=True)
    key = Column(String(80), nullable=False, unique=True)
    drug_zh = Column(String(80), nullable=False)
    drug_en = Column(String(120), nullable=True)
    mechanism = Column(String(120), nullable=True)
    route = Column(String(40), nullable=True)
    sponsor = Column(String(120), nullable=True)
    phase = Column(String(40), nullable=True)
    regions_json = Column(Text, nullable=True)
    latest_event = Column(Text, nullable=True)
    event_date = Column(String(20), nullable=True)
    sources_json = Column(Text, nullable=True)
    checked_at = Column(String(20), nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)


class KnowledgeDigest(_Reviewed, Base):
    __tablename__ = "knowledge_digests"

    id = Column(Integer, primary_key=True)
    key = Column(String(80), nullable=False, unique=True)
    title_zh = Column(String(200), nullable=False)
    title_en = Column(String(400), nullable=True)
    one_liner = Column(Text, nullable=False)
    why_it_matters = Column(Text, nullable=True)
    limitations = Column(Text, nullable=True)
    study_type = Column(String(40), nullable=True)
    sample_size = Column(Integer, nullable=True)
    is_preprint = Column(Integer, nullable=False, default=0)
    published_on = Column(String(20), nullable=True)
    journal = Column(String(160), nullable=True)
    url = Column(String(500), nullable=True)
    pmid = Column(String(20), nullable=True)


class KnowledgeReviewLog(Base):
    """Append-only trail of every status change (who, from, to, note)."""

    __tablename__ = "knowledge_review_logs"

    id = Column(Integer, primary_key=True)
    kind = Column(String(20), nullable=False, index=True)  # cards|pipeline|digests|relations
    item_id = Column(Integer, nullable=False, index=True)
    actor_id = Column(Integer, nullable=True)
    from_status = Column(String(20), nullable=True)
    to_status = Column(String(20), nullable=False)
    note = Column(Text, nullable=True)
    reviewer_label = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

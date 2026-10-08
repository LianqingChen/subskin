"""分用途数据授权模型（图像数据库专项 SS-04）。

与既有 ``UserConsent``（terms/privacy/ai_data/medical_photo，管 AI 服务外送）并存、互不替代：
本模块只管“是否允许把用户的记录用于训练/研究/公开/医生查看”这类**贡献用途**。

设计要点：
- ``DataConsentGrant`` 一经创建不再修改；用户重新同意 = 新建一条 grant。
- 状态完全由 ``DataConsentEvent`` 追加式事件决定（granted → withdrawn），事件带哈希链，
  任何一条被改动都会让后续哈希对不上。
- 默认拒绝：没有有效 grant 就不允许（见 ``services/data_consent.can_use``）。
- 仅增量新表，不改任何既有表。
"""

from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)

from web.backend.database.database import Base


class DataConsentGrant(Base):
    __tablename__ = "data_consent_grants"
    __table_args__ = (Index("idx_dcg_user_purpose", "user_id", "purpose"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    profile_id = Column(Integer, nullable=True)  # 病友档案；不加外键，避免与档案表循环依赖
    purpose = Column(String(30), nullable=False)  # model_training/research_project/public_share/clinician_review
    scope = Column(String(20), nullable=False)  # future_only / all_records / selected
    project_id = Column(String(64), nullable=True)  # research_project 必填：具体研究项目标识
    text_version = Column(String(32), nullable=False)  # 用户当时看到的文案版本
    platform = Column(String(20), nullable=True)
    source = Column(String(30), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True)


class DataConsentObject(Base):
    """scope=selected 时，授权覆盖的具体对象。"""

    __tablename__ = "data_consent_objects"
    __table_args__ = (
        Index("idx_dco_grant", "grant_id"),
        Index("idx_dco_object", "object_type", "object_id"),
    )

    id = Column(Integer, primary_key=True)
    grant_id = Column(Integer, ForeignKey("data_consent_grants.id"), nullable=False)
    object_type = Column(String(30), nullable=False)  # 目前仅 assessment
    object_id = Column(Integer, nullable=False)


class DataConsentEvent(Base):
    """追加式事件：只允许 INSERT。"""

    __tablename__ = "data_consent_events"
    __table_args__ = (Index("idx_dce_grant", "grant_id"),)

    id = Column(Integer, primary_key=True)
    grant_id = Column(Integer, ForeignKey("data_consent_grants.id"), nullable=False)
    event_type = Column(String(20), nullable=False)  # granted / withdrawn
    actor = Column(String(20), nullable=False)  # user / system
    reason = Column(String(40), nullable=True)  # 如 user_request / account_deletion
    occurred_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    prev_hash = Column(String(64), nullable=True)
    event_hash = Column(String(64), nullable=False)


class DataRightsJob(Base):
    """撤回/删除触发的回收工单。本迭代只建单与展示，实际回收由后续工作包（SS-06）执行。"""

    __tablename__ = "data_rights_jobs"
    __table_args__ = (Index("idx_drj_user", "user_id"),)

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    grant_id = Column(Integer, ForeignKey("data_consent_grants.id"), nullable=True)
    job_type = Column(String(20), nullable=False)  # withdrawal
    status = Column(String(20), nullable=False, default="pending")  # pending/in_progress/done
    note = Column(Text, nullable=True)  # 不存原始图片/聊天/联系方式
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

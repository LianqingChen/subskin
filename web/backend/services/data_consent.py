"""分用途数据授权服务（图像数据库专项 SS-04）。

回答一个问题：**这条用户数据，现在能不能用于这个用途？** 默认拒绝。

与 ``services/consent.py`` 的区别：后者管 AI 服务外送（ai_data/medical_photo），
本服务管贡献用途（训练、具体研究、公开、医生查看）。两者互不替代、互不继承。

约定：
- ``can_use`` 是唯一的判定入口；API、worker、导出、训练清单发布前都应调用它，
  不要只在前端隐藏按钮，也不要只存一个布尔值。
- grant 不可修改，状态由追加式事件决定（带哈希链）。
- 授权/撤回都写 ``AuditLog``（项目规则：授权操作必须留不可篡改记录）。
- 未成年人/监护人流程不在本模块范围；首期不征集未成年人，由上层入口拦截。
"""

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List, Optional

from sqlalchemy.orm import Session

from web.backend.models.data_consent import (
    DataConsentEvent,
    DataConsentGrant,
    DataConsentObject,
    DataRightsJob,
)
from web.backend.models.vasi import VASIAssessment

logger = logging.getLogger(__name__)

# 文案版本：改文案必须升版本，旧客户端提交旧版本会被拒绝（STALE_TEXT），从而重新展示新文案。
CURRENT_TEXT_VERSION = "2026-10-v1"

PURPOSES: Dict[str, Dict[str, str]] = {
    "model_training": {"title": "帮助改进白斑识别"},
    "research_project": {"title": "参与白癜风研究"},
    "public_share": {"title": "公开给病友"},
    "clinician_review": {"title": "让医生查看并确认"},
}
SCOPES = ("future_only", "all_records", "selected")
OBJECT_TYPES = ("assessment",)


class ConsentError(ValueError):
    """业务校验失败；``code`` 供 API 层映射状态码。"""

    def __init__(self, code: str, message: str = ""):
        super().__init__(message or code)
        self.code = code


@dataclass
class ConsentDecision:
    allowed: bool
    grant_id: Optional[int] = None
    reason: str = ""


def _hash_event(
    grant_id: int,
    event_type: str,
    actor: str,
    reason: Optional[str],
    occurred_at: datetime,
    prev_hash: Optional[str],
) -> str:
    raw = "|".join(
        [str(grant_id), event_type, actor, reason or "", occurred_at.isoformat(), prev_hash or ""]
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def _append_event(
    db: Session, grant_id: int, event_type: str, actor: str, reason: Optional[str]
) -> DataConsentEvent:
    last = (
        db.query(DataConsentEvent)
        .filter_by(grant_id=grant_id)
        .order_by(DataConsentEvent.id.desc())
        .first()
    )
    now = datetime.utcnow()
    prev = last.event_hash if last else None
    event = DataConsentEvent(
        grant_id=grant_id,
        event_type=event_type,
        actor=actor,
        reason=reason,
        occurred_at=now,
        prev_hash=prev,
        event_hash=_hash_event(grant_id, event_type, actor, reason, now, prev),
    )
    db.add(event)
    return event


def _audit(
    db: Session, user_id: int, action: str, grant_id: int, purpose: str, detail: dict
) -> None:
    from web.backend.services.audit import AuditLogService

    # 审计记录不含图片、聊天或联系方式，只记谁、做了什么、对哪条授权。
    AuditLogService(db).create_log(
        user_id=user_id,
        action=action,
        target_type="data_consent",
        target_id=grant_id,
        scope=purpose[:20],
        detail=json.dumps(detail, ensure_ascii=False),
        revokeable=True,
    )


def create_grant(
    db: Session,
    user_id: int,
    purpose: str,
    scope: str,
    *,
    text_version: str,
    project_id: Optional[str] = None,
    object_ids: Optional[Iterable[int]] = None,
    profile_id: Optional[int] = None,
    platform: Optional[str] = None,
    source: Optional[str] = None,
    expires_at: Optional[datetime] = None,
) -> DataConsentGrant:
    if purpose not in PURPOSES:
        raise ConsentError("BAD_PURPOSE", "未知的用途")
    if scope not in SCOPES:
        raise ConsentError("BAD_SCOPE", "未知的范围")
    if text_version != CURRENT_TEXT_VERSION:
        raise ConsentError("STALE_TEXT", "同意文案已更新，请重新查看后再确认")
    if purpose == "research_project" and not project_id:
        raise ConsentError("PROJECT_REQUIRED", "研究授权必须指定具体项目")
    if purpose != "research_project" and project_id:
        raise ConsentError("PROJECT_NOT_ALLOWED", "只有研究授权可以指定项目")

    if profile_id is not None:
        from web.backend.database.models import PatientProfile

        if not db.query(PatientProfile.id).filter_by(id=profile_id, user_id=user_id).first():
            raise ConsentError("FORBIDDEN_PROFILE", "档案不属于当前用户")

    ids: List[int] = sorted({int(i) for i in (object_ids or [])})
    if scope == "selected":
        if not ids:
            raise ConsentError("OBJECTS_REQUIRED", "请选择要授权的记录")
        owned = {
            a.id
            for a in db.query(VASIAssessment.id)
            .filter(VASIAssessment.user_id == user_id, VASIAssessment.id.in_(ids))
            .all()
        }
        if owned != set(ids):
            raise ConsentError("FORBIDDEN_OBJECT", "只能授权属于自己的记录")
    elif ids:
        raise ConsentError("OBJECTS_NOT_ALLOWED", "仅“选定记录”范围可以带记录列表")

    grant = DataConsentGrant(
        user_id=user_id,
        profile_id=profile_id,
        purpose=purpose,
        scope=scope,
        project_id=project_id,
        text_version=text_version,
        platform=platform,
        source=source,
        expires_at=expires_at,
    )
    db.add(grant)
    db.flush()
    for oid in ids:
        db.add(DataConsentObject(grant_id=grant.id, object_type="assessment", object_id=oid))
    _append_event(db, grant.id, "granted", "user", None)
    db.commit()
    _audit(
        db, user_id, "authorize", grant.id, purpose,
        {"scope": scope, "project_id": project_id, "objects": len(ids), "text_version": text_version},
    )
    db.refresh(grant)
    return grant


def _last_event(db: Session, grant_id: int) -> Optional[DataConsentEvent]:
    return (
        db.query(DataConsentEvent)
        .filter_by(grant_id=grant_id)
        .order_by(DataConsentEvent.id.desc())
        .first()
    )


def grant_state(db: Session, grant: DataConsentGrant, now: Optional[datetime] = None) -> str:
    last = _last_event(db, grant.id)
    if last is None or last.event_type == "withdrawn":
        return "withdrawn"
    if grant.expires_at is not None and grant.expires_at <= (now or datetime.utcnow()):
        return "expired"
    return "active"


def withdraw_grant(
    db: Session,
    user_id: int,
    grant_id: int,
    *,
    actor: str = "user",
    reason: str = "user_request",
) -> DataConsentGrant:
    """撤回一条授权；重复撤回是幂等的（不重复建事件和工单）。"""
    grant = db.query(DataConsentGrant).filter_by(id=grant_id, user_id=user_id).first()
    if grant is None:
        raise ConsentError("NOT_FOUND", "授权不存在")
    last = _last_event(db, grant.id)
    if last is not None and last.event_type == "withdrawn":
        return grant
    _append_event(db, grant.id, "withdrawn", actor, reason)
    db.add(
        DataRightsJob(
            user_id=user_id,
            grant_id=grant.id,
            job_type="withdrawal",
            status="pending",
            note=f"purpose={grant.purpose}",
        )
    )
    db.commit()
    _audit(db, user_id, "revoke", grant.id, grant.purpose, {"reason": reason, "actor": actor})
    return grant


def withdraw_all(db: Session, user_id: int, *, reason: str) -> int:
    """撤回用户全部有效授权（账号注销时由系统执行）。返回撤回条数。"""
    count = 0
    for grant in db.query(DataConsentGrant).filter_by(user_id=user_id).all():
        last = _last_event(db, grant.id)
        if last is not None and last.event_type == "granted":
            withdraw_grant(db, user_id, grant.id, actor="system", reason=reason)
            count += 1
    return count


def can_use(
    db: Session,
    user_id: Optional[int],
    purpose: str,
    *,
    object_type: Optional[str] = None,
    object_id: Optional[int] = None,
    object_created_at: Optional[datetime] = None,
    project_id: Optional[str] = None,
    at: Optional[datetime] = None,
) -> ConsentDecision:
    """判定某条数据当前能否用于某用途。默认拒绝。

    - ``all_records``：该用户的任何对象；不需要传对象，可做用户级检查。
    - ``future_only``：必须传 ``object_created_at``，且不早于授权时间；缺失则拒绝，不猜测。
    - ``selected``：必须传 ``object_type``/``object_id`` 且在授权清单内。
    - ``research_project``：``project_id`` 必须与授权一致。
    """
    if user_id is None or purpose not in PURPOSES:
        return ConsentDecision(False, None, "invalid_request")
    now = at or datetime.utcnow()
    grants = (
        db.query(DataConsentGrant)
        .filter(DataConsentGrant.user_id == user_id, DataConsentGrant.purpose == purpose)
        .order_by(DataConsentGrant.id.desc())
        .all()
    )
    for grant in grants:
        if grant_state(db, grant, now) != "active":
            continue
        if purpose == "research_project" and grant.project_id != project_id:
            continue
        if grant.scope == "all_records":
            return ConsentDecision(True, grant.id, "all_records")
        if grant.scope == "future_only":
            if object_created_at is not None and object_created_at >= grant.created_at:
                return ConsentDecision(True, grant.id, "future_only")
            continue
        if grant.scope == "selected" and object_type and object_id is not None:
            hit = (
                db.query(DataConsentObject.id)
                .filter_by(grant_id=grant.id, object_type=object_type, object_id=object_id)
                .first()
            )
            if hit:
                return ConsentDecision(True, grant.id, "selected")
    return ConsentDecision(False, None, "no_active_grant")


def verify_chain(db: Session, grant_id: int) -> bool:
    """重算该授权的事件哈希链；任何一条被改动都会返回 False。"""
    prev: Optional[str] = None
    events = (
        db.query(DataConsentEvent)
        .filter_by(grant_id=grant_id)
        .order_by(DataConsentEvent.id.asc())
        .all()
    )
    for e in events:
        expected = _hash_event(e.grant_id, e.event_type, e.actor, e.reason, e.occurred_at, prev)
        if e.prev_hash != prev or e.event_hash != expected:
            return False
        prev = e.event_hash
    return True


def active_summary(db: Session, user_id: int) -> Dict[str, bool]:
    """每个用途当前是否有有效授权（供“我的数据与贡献”页的开关状态）。"""
    now = datetime.utcnow()
    result = {p: False for p in PURPOSES}
    for grant in db.query(DataConsentGrant).filter_by(user_id=user_id).all():
        if grant_state(db, grant, now) == "active":
            result[grant.purpose] = True
    return result


def list_grants(db: Session, user_id: int) -> List[dict]:
    now = datetime.utcnow()
    rows = []
    for grant in (
        db.query(DataConsentGrant)
        .filter_by(user_id=user_id)
        .order_by(DataConsentGrant.id.desc())
        .all()
    ):
        job = (
            db.query(DataRightsJob)
            .filter_by(grant_id=grant.id)
            .order_by(DataRightsJob.id.desc())
            .first()
        )
        rows.append(
            {
                "id": grant.id,
                "purpose": grant.purpose,
                "title": PURPOSES[grant.purpose]["title"],
                "scope": grant.scope,
                "project_id": grant.project_id,
                "text_version": grant.text_version,
                "state": grant_state(db, grant, now),
                "created_at": grant.created_at,
                "expires_at": grant.expires_at,
                "withdrawal_status": job.status if job else None,
            }
        )
    return rows


def label_training_decision(db: Session, label) -> ConsentDecision:
    """某条 ImageLabel 能否进入训练/导出。训练链路的统一闸门。

    - 用户来源（``original_user_id`` 非空）：必须有覆盖该测评的有效 ``model_training`` 授权；
      ``future_only`` 以**测评创建时间**判断（不是标签行创建时间，后者可能晚得多）。
    - 无用户来源（管理员批量上传的图片）：不属于用户贡献，权利依据在上传环节，不在本服务范围。
    - 已被用户删除的标签始终拒绝。
    """
    if getattr(label, "is_user_deleted", False):
        return ConsentDecision(False, None, "user_deleted")
    user_id = getattr(label, "original_user_id", None)
    if user_id is None:
        return ConsentDecision(True, None, "not_user_contributed")
    assessment = getattr(label, "assessment", None)
    return can_use(
        db,
        user_id,
        "model_training",
        object_type="assessment",
        object_id=getattr(label, "assessment_id", None),
        object_created_at=getattr(assessment, "created_at", None),
    )

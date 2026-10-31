"""用户同意（consent）查询服务 — 供服务层使用。

隐私加固（2026-08-30）：将 L3 健康数据发往第三方 LLM 前，必须查询
用户是否已对相应授权类型（ai_data / medical_photo）给出有效同意。
API 层的记录/查询端点见 ``api/consent.py``；本模块只做只读判断，
避免服务层反向依赖 API 层。
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from web.backend.database.models import UserConsent

logger = logging.getLogger(__name__)

CONSENT_TYPE_AI_DATA = "ai_data"
CONSENT_TYPE_MEDICAL_PHOTO = "medical_photo"
# PIPL：健康照片/评估属敏感个人信息，存储处理前需单独同意（与外送 AI 的 medical_photo 区分）
CONSENT_TYPE_HEALTH_DATA = "health_data"
# 首期仅面向成年人：注册时确认年满 18 周岁
CONSENT_TYPE_AGE_18 = "age_18"

HEALTH_DATA_VERSION = "1.0"
# 403 detail：前端按 code 识别后弹出健康数据单独授权
HEALTH_CONSENT_REQUIRED_DETAIL = {
    "code": "health_data_consent_required",
    "message": "上传病情照片前，请先阅读并同意健康数据单独授权",
}
AGE_18_VERSION = "1.0"

KNOWN_CONSENT_TYPES = (
    "terms",
    "privacy",
    CONSENT_TYPE_AI_DATA,
    CONSENT_TYPE_MEDICAL_PHOTO,
    CONSENT_TYPE_HEALTH_DATA,
    CONSENT_TYPE_AGE_18,
)
REVOCABLE_CONSENT_TYPES = (
    "terms",
    "privacy",
    CONSENT_TYPE_AI_DATA,
    CONSENT_TYPE_MEDICAL_PHOTO,
    CONSENT_TYPE_HEALTH_DATA,
)
# 敏感授权的授予/撤销额外写入不可篡改的 AuditLog
_AUDITED_TYPES = (CONSENT_TYPE_HEALTH_DATA, CONSENT_TYPE_AGE_18, CONSENT_TYPE_MEDICAL_PHOTO)


def record_consent(
    db: Session,
    user_id: int,
    consent_type: str,
    version: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    device_fingerprint: Optional[str] = None,
    platform: Optional[str] = None,
    source: Optional[str] = None,
    is_active: bool = True,
) -> UserConsent:
    """追加一条同意（is_active=True）或撤销（is_active=False）记录。"""
    consent = UserConsent(
        user_id=user_id,
        consent_type=consent_type,
        consent_version=version,
        consented_at=datetime.now(timezone.utc),
        ip_address=ip_address,
        user_agent=user_agent[:500] if user_agent else None,
        device_fingerprint=device_fingerprint,
        platform=platform,
        source=source,
        is_active=is_active,
    )
    db.add(consent)
    db.commit()
    db.refresh(consent)
    if consent_type in _AUDITED_TYPES:
        from web.backend.services.audit import AuditLogService

        AuditLogService(db).create_log(
            user_id=user_id,
            action="consent_granted" if is_active else "consent_revoked",
            target_type="user_consent",
            target_id=consent.id,
            scope=consent_type[:20],
            detail=json.dumps({"version": version, "source": source}, ensure_ascii=False),
            revokeable=False,
            ip_address=ip_address,
        )
    logger.info(
        "Consent recorded: user_id=%s, type=%s, version=%s, active=%s, source=%s",
        user_id, consent_type, version, is_active, source,
    )
    return consent


def latest_consent(
    db: Session, user_id: Optional[int], consent_type: str
) -> Optional[UserConsent]:
    """取该授权类型的最新一条记录（含撤销记录）。

    撤销是追加一条 is_active=False 的行，所以必须先取最新一行再看它是否有效；
    先过滤 is_active=True 会让撤销行永远查不到，旧授权继续生效。
    """
    if user_id is None:
        return None
    return (
        db.query(UserConsent)
        .filter(
            UserConsent.user_id == user_id,
            UserConsent.consent_type == consent_type,
        )
        .order_by(UserConsent.consented_at.desc(), UserConsent.id.desc())
        .first()
    )


def has_active_consent(
    db: Session, user_id: Optional[int], consent_type: str
) -> bool:
    """判断用户对某授权类型当前是否有效同意（最新记录有效且未被撤销）。"""
    latest = latest_consent(db, user_id, consent_type)
    return latest is not None and bool(latest.is_active)


def health_data_consent_missing(db: Session, user_id: Optional[int]) -> bool:
    """强制开关打开（REQUIRE_HEALTH_DATA_CONSENT=1）且用户未单独同意健康数据处理时返回 True。

    默认关闭：先让前端上线同意弹窗，旧版 PWA 缓存过期后再打开强制，避免上传突然失败。
    """
    if os.getenv("REQUIRE_HEALTH_DATA_CONSENT", "0") != "1":
        return False
    return not has_active_consent(db, user_id, CONSENT_TYPE_HEALTH_DATA)

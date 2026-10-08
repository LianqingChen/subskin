"""用户同意（consent）查询服务 — 供服务层使用。

隐私加固（2026-08-30）：将 L3 健康数据发往第三方 LLM 前，必须查询
用户是否已对相应授权类型（ai_data / medical_photo）给出有效同意。
API 层的记录/查询端点见 ``api/consent.py``；本模块只做只读判断，
避免服务层反向依赖 API 层。
"""

import logging
from typing import Optional

from sqlalchemy.orm import Session

from web.backend.database.models import UserConsent

logger = logging.getLogger(__name__)

CONSENT_TYPE_AI_DATA = "ai_data"
CONSENT_TYPE_MEDICAL_PHOTO = "medical_photo"


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

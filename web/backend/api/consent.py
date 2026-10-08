"""
用户同意记录 API
记录用户对隐私政策、服务条款等的同意行为
"""
from web.backend.utils.timeutils import iso_utc

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from web.backend.database.database import get_db
from web.backend.database.models import UserConsent
from web.backend.services.auth import get_current_user, get_current_user_optional
from web.backend.database.models import User as DBUser
from web.backend.services.consent import latest_consent

logger = logging.getLogger(__name__)
router = APIRouter()

# 当前版本配置
TERMS_VERSION = "1.2"
PRIVACY_VERSION = "1.1"


class ConsentRecordRequest(BaseModel):
    consent_type: str  # terms, privacy, ai_data, medical_photo
    version: str
    platform: Optional[str] = None  # web, pwa, ios, android
    source: Optional[str] = None  # register, login, oauth, ai_prompt, vasi_upload


class ConsentRecordResponse(BaseModel):
    id: int
    consent_type: str
    consent_version: str
    consented_at: datetime
    is_active: bool

    class Config:
        from_attributes = True


class ConsentStatusResponse(BaseModel):
    terms: Optional[dict] = None
    privacy: Optional[dict] = None
    ai_data: Optional[dict] = None
    medical_photo: Optional[dict] = None


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
) -> UserConsent:
    """记录用户同意行为（可在其他模块中直接调用）"""
    consent = UserConsent(
        user_id=user_id,
        consent_type=consent_type,
        consent_version=version,
        consented_at=datetime.now(timezone.utc),
        ip_address=ip_address,
        user_agent=user_agent[:500] if user_agent and len(user_agent) > 500 else user_agent,
        device_fingerprint=device_fingerprint,
        platform=platform,
        source=source,
        is_active=True,
    )
    db.add(consent)
    db.commit()
    db.refresh(consent)
    logger.info(f"Consent recorded: user_id={user_id}, type={consent_type}, version={version}, source={source}")
    return consent


def get_client_ip(request: Request) -> str:
    """从请求中提取客户端IP"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("/record", response_model=ConsentRecordResponse)
async def record_user_consent(
    data: ConsentRecordRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    """记录用户同意行为"""
    consent = record_consent(
        db=db,
        user_id=current_user.id,
        consent_type=data.consent_type,
        version=data.version,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("User-Agent"),
        device_fingerprint=request.headers.get("X-Device-Fingerprint"),
        platform=data.platform or "web",
        source=data.source or "manual",
    )
    return consent


@router.post("/batch-record")
async def batch_record_consent(
    consent_types: list[str],
    request: Request,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    """批量记录用户同意（如同时同意条款和隐私政策）"""
    records = []
    version_map = {
        "terms": TERMS_VERSION,
        "privacy": PRIVACY_VERSION,
        "ai_data": "1.0",
        "medical_photo": "1.0",
    }
    for ct in consent_types:
        version = version_map.get(ct, "1.0")
        consent = record_consent(
            db=db,
            user_id=current_user.id,
            consent_type=ct,
            version=version,
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("User-Agent"),
            device_fingerprint=request.headers.get("X-Device-Fingerprint"),
            platform="web",
            source="manual",
        )
        records.append(consent)
    return {"success": True, "recorded": len(records)}


@router.get("/status", response_model=ConsentStatusResponse)
async def get_consent_status(
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    """查询当前用户的同意状态"""
    result = ConsentStatusResponse()
    for consent_type in ["terms", "privacy", "ai_data", "medical_photo"]:
        latest = latest_consent(db, current_user.id, consent_type)
        if latest and latest.is_active:
            setattr(result, consent_type, {
                "version": latest.consent_version,
                "consented_at": iso_utc(latest.consented_at),
                "platform": latest.platform,
                "source": latest.source,
            })
    return result


class ConsentRevokeRequest(BaseModel):
    consent_type: str


@router.post("/revoke")
async def revoke_user_consent(
    data: ConsentRevokeRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    """撤销某项授权（2026-08-30）：写入一条 is_active=False 的记录，
    后续 has_active_consent 查询即不再命中，数据外送立即停止。"""
    if data.consent_type not in ("terms", "privacy", "ai_data", "medical_photo"):
        raise HTTPException(status_code=400, detail="未知的授权类型")
    consent = UserConsent(
        user_id=current_user.id,
        consent_type=data.consent_type,
        consent_version="revoked",
        consented_at=datetime.now(timezone.utc),
        ip_address=get_client_ip(request),
        user_agent=(request.headers.get("User-Agent") or "")[:500] or None,
        platform="web",
        source="manual",
        is_active=False,
    )
    db.add(consent)
    db.commit()
    return {"success": True, "consent_type": data.consent_type, "is_active": False}


@router.get("/versions")
async def get_current_versions():
    """获取当前条款和隐私政策版本号"""
    return {
        "terms_version": TERMS_VERSION,
        "privacy_version": PRIVACY_VERSION,
    }

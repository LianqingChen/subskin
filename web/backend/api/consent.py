"""
用户同意记录 API
记录用户对隐私政策、服务条款等的同意行为
"""
from web.backend.utils.timeutils import iso_utc

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from web.backend.database.database import get_db
from web.backend.utils.client_ip import get_real_client_ip
from web.backend.services.auth import get_current_user, get_current_user_optional
from web.backend.database.models import User as DBUser
from web.backend.services.consent import (
    AGE_18_VERSION,
    HEALTH_DATA_VERSION,
    KNOWN_CONSENT_TYPES,
    REVOCABLE_CONSENT_TYPES,
    latest_consent,
    record_consent,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# 当前版本配置
TERMS_VERSION = "1.2"
PRIVACY_VERSION = "1.1"


class ConsentRecordRequest(BaseModel):
    consent_type: str  # terms, privacy, ai_data, medical_photo, health_data, age_18
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
    health_data: Optional[dict] = None
    age_18: Optional[dict] = None


def get_client_ip(request: Request) -> str:
    """真实客户端 IP（XFF 首值可被伪造，统一走 client_ip 工具）。"""
    return get_real_client_ip(request) or "unknown"


@router.post("/record", response_model=ConsentRecordResponse)
async def record_user_consent(
    data: ConsentRecordRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    """记录用户同意行为"""
    if data.consent_type not in KNOWN_CONSENT_TYPES:
        raise HTTPException(status_code=400, detail="未知的授权类型")
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
        "health_data": HEALTH_DATA_VERSION,
        "age_18": AGE_18_VERSION,
    }
    if any(ct not in KNOWN_CONSENT_TYPES for ct in consent_types):
        raise HTTPException(status_code=400, detail="未知的授权类型")
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
    for consent_type in KNOWN_CONSENT_TYPES:
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
    if data.consent_type not in REVOCABLE_CONSENT_TYPES:
        raise HTTPException(status_code=400, detail="未知的授权类型")
    record_consent(
        db=db,
        user_id=current_user.id,
        consent_type=data.consent_type,
        version="revoked",
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("User-Agent"),
        platform="web",
        source="manual",
        is_active=False,
    )
    return {"success": True, "consent_type": data.consent_type, "is_active": False}


@router.get("/versions")
async def get_current_versions():
    """获取当前条款和隐私政策版本号"""
    return {
        "terms_version": TERMS_VERSION,
        "privacy_version": PRIVACY_VERSION,
        "health_data_version": HEALTH_DATA_VERSION,
        "age_18_version": AGE_18_VERSION,
    }

"""
医生认证 API
"""

import json
import secrets
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from web.backend.database.database import get_db
from web.backend.database.models import User, DoctorVerification, DoctorInvitation
from web.backend.services.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Pydantic Models ──


class VerificationCreate(BaseModel):
    real_name: str = Field(..., max_length=50, description="真实姓名")
    hospital: str = Field(..., max_length=100, description="医院")
    department: Optional[str] = Field(None, max_length=100, description="科室")
    title: Optional[str] = Field(None, max_length=50, description="职称")
    license_number: Optional[str] = Field(None, max_length=50, description="执业医师资格证号")
    specialty: Optional[str] = Field(None, max_length=200, description="擅长领域")
    proof_images: Optional[List[str]] = Field(None, description="证明材料图片URL列表")
    invitation_code: Optional[str] = Field(None, description="邀请码（可选）")


class VerificationResponse(BaseModel):
    id: int
    real_name: str
    hospital: str
    department: Optional[str]
    title: Optional[str]
    specialty: Optional[str]
    status: str
    review_note: Optional[str]
    created_at: str


class AdminVerificationReview(BaseModel):
    status: str = Field(..., description="审核结果: approved/rejected")
    review_note: Optional[str] = Field(None, description="审核备注")


class InvitationCreate(BaseModel):
    expires_days: Optional[int] = Field(30, description="有效天数")


class InvitationResponse(BaseModel):
    id: int
    code: str
    used_by: Optional[int]
    used_at: Optional[str]
    expires_at: Optional[str]
    is_active: bool
    created_at: str


# ── Helper Functions ──


def _verification_to_response(v: DoctorVerification) -> dict:
    return {
        "id": v.id,
        "real_name": v.real_name,
        "hospital": v.hospital,
        "department": v.department,
        "title": v.title,
        "specialty": v.specialty,
        "status": v.status,
        "review_note": v.review_note,
        "created_at": v.created_at.isoformat() if v.created_at else None,
    }


def _invitation_to_response(inv: DoctorInvitation) -> dict:
    return {
        "id": inv.id,
        "code": inv.code,
        "used_by": inv.used_by,
        "used_at": inv.used_at.isoformat() if inv.used_at else None,
        "expires_at": inv.expires_at.isoformat() if inv.expires_at else None,
        "is_active": inv.is_active,
        "created_at": inv.created_at.isoformat() if inv.created_at else None,
    }


def _require_admin(user: User):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")


# ── User Endpoints ──


@router.get("/verification/status")
async def get_verification_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取当前用户的医生认证状态"""
    verification = (
        db.query(DoctorVerification)
        .filter(DoctorVerification.user_id == current_user.id)
        .order_by(DoctorVerification.created_at.desc())
        .first()
    )
    return {
        "is_doctor": current_user.is_doctor,
        "verification": _verification_to_response(verification) if verification else None,
    }


@router.post("/verification/apply", response_model=VerificationResponse)
async def apply_verification(
    data: VerificationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """申请医生认证"""
    # Check if already a doctor
    if current_user.is_doctor:
        raise HTTPException(status_code=400, detail="您已经是认证医生")

    # Check if has pending application
    existing = (
        db.query(DoctorVerification)
        .filter(
            DoctorVerification.user_id == current_user.id,
            DoctorVerification.status == "pending",
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="您已有待审核的认证申请")

    # If invitation code provided, validate it
    if data.invitation_code:
        invitation = (
            db.query(DoctorInvitation)
            .filter(
                DoctorInvitation.code == data.invitation_code,
                DoctorInvitation.is_active == True,
            )
            .first()
        )
        if not invitation:
            raise HTTPException(status_code=400, detail="邀请码无效")
        if invitation.used_by:
            raise HTTPException(status_code=400, detail="邀请码已被使用")
        if invitation.expires_at and invitation.expires_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=400, detail="邀请码已过期")

    verification = DoctorVerification(
        user_id=current_user.id,
        real_name=data.real_name,
        hospital=data.hospital,
        department=data.department,
        title=data.title,
        license_number=data.license_number,
        specialty=data.specialty,
        proof_images=json.dumps(data.proof_images) if data.proof_images else None,
        status="pending",
    )
    db.add(verification)
    db.commit()
    db.refresh(verification)
    return _verification_to_response(verification)


# ── Admin Endpoints ──


@router.get("/admin/verifications")
async def list_verifications(
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取所有认证申请（管理员）"""
    _require_admin(current_user)

    query = db.query(DoctorVerification)
    if status:
        query = query.filter(DoctorVerification.status == status)
    verifications = query.order_by(DoctorVerification.created_at.desc()).all()

    return [
        {
            **_verification_to_response(v),
            "user_id": v.user_id,
            "username": v.user.username if v.user else None,
            "license_number": v.license_number,
            "proof_images": json.loads(v.proof_images) if v.proof_images else [],
        }
        for v in verifications
    ]


@router.post("/admin/verifications/{verification_id}/review")
async def review_verification(
    verification_id: int,
    data: AdminVerificationReview,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """审核认证申请（管理员）"""
    _require_admin(current_user)

    verification = db.query(DoctorVerification).filter(
        DoctorVerification.id == verification_id
    ).first()
    if not verification:
        raise HTTPException(status_code=404, detail="认证申请不存在")

    if verification.status != "pending":
        raise HTTPException(status_code=400, detail="该申请已审核")

    verification.status = data.status
    verification.review_note = data.review_note
    verification.reviewed_by = current_user.id
    verification.reviewed_at = datetime.now(timezone.utc)

    # If approved, update user's is_doctor flag
    if data.status == "approved":
        verification.user.is_doctor = True

    db.commit()
    return {"success": True, "status": data.status}


@router.post("/admin/invitations", response_model=InvitationResponse)
async def create_invitation(
    data: InvitationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建医生邀请码（管理员）"""
    _require_admin(current_user)

    code = secrets.token_urlsafe(8)[:12].upper()
    expires_at = None
    if data.expires_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=data.expires_days)

    invitation = DoctorInvitation(
        code=code,
        created_by=current_user.id,
        expires_at=expires_at,
        is_active=True,
    )
    db.add(invitation)
    db.commit()
    db.refresh(invitation)
    return _invitation_to_response(invitation)


@router.get("/admin/invitations")
async def list_invitations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取所有邀请码（管理员）"""
    _require_admin(current_user)

    invitations = (
        db.query(DoctorInvitation)
        .order_by(DoctorInvitation.created_at.desc())
        .all()
    )
    return [_invitation_to_response(inv) for inv in invitations]

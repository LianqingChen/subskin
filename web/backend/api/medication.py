"""
用药提醒 API
"""

import json
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from web.backend.database.database import get_db
from web.backend.database.models import User, MedicationReminder, PushSubscription
from web.backend.services.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Pydantic Models ──


class ReminderCreate(BaseModel):
    medication_name: str = Field(..., max_length=100, description="药品名称")
    dosage: Optional[str] = Field(None, max_length=100, description="剂量")
    frequency: str = Field(..., description="频率: daily/twice_daily/weekly/custom")
    reminder_times: Optional[List[str]] = Field(None, description="提醒时间列表")
    reminder_days: Optional[List[int]] = Field(None, description="提醒日期列表 (1=周一)")
    notes: Optional[str] = Field(None, description="备注")


class ReminderUpdate(BaseModel):
    medication_name: Optional[str] = None
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    reminder_times: Optional[List[str]] = None
    reminder_days: Optional[List[int]] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class ReminderResponse(BaseModel):
    id: int
    medication_name: str
    dosage: Optional[str]
    frequency: str
    reminder_times: Optional[List[str]]
    reminder_days: Optional[List[int]]
    notes: Optional[str]
    is_active: bool
    created_at: str

    class Config:
        from_attributes = True


class PushSubscriptionCreate(BaseModel):
    endpoint: str
    p256dh_key: str
    auth_key: str
    user_agent: Optional[str] = None


# ── Helper Functions ──


def _reminder_to_response(reminder: MedicationReminder) -> dict:
    return {
        "id": reminder.id,
        "medication_name": reminder.medication_name,
        "dosage": reminder.dosage,
        "frequency": reminder.frequency,
        "reminder_times": json.loads(reminder.reminder_times) if reminder.reminder_times else None,
        "reminder_days": json.loads(reminder.reminder_days) if reminder.reminder_days else None,
        "notes": reminder.notes,
        "is_active": reminder.is_active,
        "created_at": reminder.created_at.isoformat() if reminder.created_at else None,
    }


# ── API Endpoints ──


@router.get("/reminders", response_model=List[ReminderResponse])
async def list_reminders(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取用户的所有用药提醒"""
    reminders = (
        db.query(MedicationReminder)
        .filter(MedicationReminder.user_id == current_user.id)
        .order_by(MedicationReminder.created_at.desc())
        .all()
    )
    return [_reminder_to_response(r) for r in reminders]


@router.post("/reminders", response_model=ReminderResponse)
async def create_reminder(
    data: ReminderCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建新的用药提醒"""
    reminder = MedicationReminder(
        user_id=current_user.id,
        medication_name=data.medication_name,
        dosage=data.dosage,
        frequency=data.frequency,
        reminder_times=json.dumps(data.reminder_times) if data.reminder_times else None,
        reminder_days=json.dumps(data.reminder_days) if data.reminder_days else None,
        notes=data.notes,
        is_active=True,
    )
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    return _reminder_to_response(reminder)


@router.put("/reminders/{reminder_id}", response_model=ReminderResponse)
async def update_reminder(
    reminder_id: int,
    data: ReminderUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新用药提醒"""
    reminder = (
        db.query(MedicationReminder)
        .filter(
            MedicationReminder.id == reminder_id,
            MedicationReminder.user_id == current_user.id,
        )
        .first()
    )
    if not reminder:
        raise HTTPException(status_code=404, detail="提醒不存在")

    if data.medication_name is not None:
        reminder.medication_name = data.medication_name
    if data.dosage is not None:
        reminder.dosage = data.dosage
    if data.frequency is not None:
        reminder.frequency = data.frequency
    if data.reminder_times is not None:
        reminder.reminder_times = json.dumps(data.reminder_times)
    if data.reminder_days is not None:
        reminder.reminder_days = json.dumps(data.reminder_days)
    if data.notes is not None:
        reminder.notes = data.notes
    if data.is_active is not None:
        reminder.is_active = data.is_active

    db.commit()
    db.refresh(reminder)
    return _reminder_to_response(reminder)


@router.delete("/reminders/{reminder_id}")
async def delete_reminder(
    reminder_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除用药提醒"""
    reminder = (
        db.query(MedicationReminder)
        .filter(
            MedicationReminder.id == reminder_id,
            MedicationReminder.user_id == current_user.id,
        )
        .first()
    )
    if not reminder:
        raise HTTPException(status_code=404, detail="提醒不存在")

    db.delete(reminder)
    db.commit()
    return {"success": True}


@router.post("/push/subscribe")
async def subscribe_push(
    data: PushSubscriptionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """注册 Web Push 订阅"""
    # Check if subscription already exists
    existing = (
        db.query(PushSubscription)
        .filter(PushSubscription.endpoint == data.endpoint)
        .first()
    )
    if existing:
        existing.user_id = current_user.id
        existing.p256dh_key = data.p256dh_key
        existing.auth_key = data.auth_key
        existing.is_active = True
        db.commit()
        return {"success": True, "subscription_id": existing.id}

    subscription = PushSubscription(
        user_id=current_user.id,
        endpoint=data.endpoint,
        p256dh_key=data.p256dh_key,
        auth_key=data.auth_key,
        user_agent=data.user_agent,
        is_active=True,
    )
    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    return {"success": True, "subscription_id": subscription.id}


@router.delete("/push/unsubscribe")
async def unsubscribe_push(
    endpoint: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """取消 Web Push 订阅"""
    subscription = (
        db.query(PushSubscription)
        .filter(
            PushSubscription.endpoint == endpoint,
            PushSubscription.user_id == current_user.id,
        )
        .first()
    )
    if subscription:
        subscription.is_active = False
        db.commit()
    return {"success": True}


@router.get("/push/vapid-public-key")
async def get_vapid_public_key():
    """获取 VAPID 公钥（用于前端注册推送）"""
    import os
    public_key = os.getenv("VAPID_PUBLIC_KEY", "")
    return {"public_key": public_key}

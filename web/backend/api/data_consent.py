"""分用途数据授权 API（图像数据库专项 SS-04）。

新建授权由环境变量 ``DATA_CONSENT_GRANTS_ENABLED`` 控制，默认关闭：同意文案经法务审定前，
线上不能产生新的贡献授权。查询、撤回始终可用（撤回权不应被开关挡住）。
"""
import logging
import os
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from web.backend.database.database import get_db
from web.backend.database.models import User as DBUser
from web.backend.services import data_consent as svc
from web.backend.services.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()

_STATUS = {
    "NOT_FOUND": 404,
    "STALE_TEXT": 409,
    "FORBIDDEN_OBJECT": 403,
    "FORBIDDEN_PROFILE": 403,
    "GRANTS_DISABLED": 503,
}


def grants_enabled() -> bool:
    return os.getenv("DATA_CONSENT_GRANTS_ENABLED", "false").strip().lower() in ("1", "true", "yes")


def _raise(err: svc.ConsentError) -> None:
    raise HTTPException(status_code=_STATUS.get(err.code, 400), detail={"code": err.code, "message": str(err)})


class GrantCreate(BaseModel):
    purpose: str = Field(..., max_length=30)
    scope: str = Field(..., max_length=20)
    text_version: str = Field(..., max_length=32)
    project_id: Optional[str] = Field(None, max_length=64)
    object_ids: Optional[List[int]] = Field(None, max_items=500)
    profile_id: Optional[int] = None
    platform: Optional[str] = Field(None, max_length=20)
    source: Optional[str] = Field(None, max_length=30)


class GrantOut(BaseModel):
    id: int
    purpose: str
    title: str
    scope: str
    project_id: Optional[str] = None
    text_version: str
    state: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    withdrawal_status: Optional[str] = None


def _one(db: Session, user_id: int, grant_id: int) -> dict:
    return next(r for r in svc.list_grants(db, user_id) if r["id"] == grant_id)


@router.get("/purposes")
def list_purposes(current_user: DBUser = Depends(get_current_user)):
    return {
        "text_version": svc.CURRENT_TEXT_VERSION,
        "grants_enabled": grants_enabled(),
        "purposes": [{"purpose": k, "title": v["title"]} for k, v in svc.PURPOSES.items()],
        "scopes": list(svc.SCOPES),
    }


@router.get("/status")
def status(db: Session = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    return {"active": svc.active_summary(db, current_user.id), "grants_enabled": grants_enabled()}


@router.get("", response_model=List[GrantOut])
def list_my_grants(db: Session = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    return svc.list_grants(db, current_user.id)


@router.post("", response_model=GrantOut, status_code=201)
def create_grant(
    data: GrantCreate,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    if not grants_enabled():
        _raise(svc.ConsentError("GRANTS_DISABLED", "该功能暂未开放"))
    try:
        grant = svc.create_grant(
            db, current_user.id, data.purpose, data.scope,
            text_version=data.text_version, project_id=data.project_id,
            object_ids=data.object_ids, profile_id=data.profile_id,
            platform=data.platform, source=data.source,
        )
    except svc.ConsentError as err:
        _raise(err)
    return _one(db, current_user.id, grant.id)


@router.post("/{grant_id:int}/withdraw", response_model=GrantOut)
def withdraw(
    grant_id: int,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    try:
        svc.withdraw_grant(db, current_user.id, grant_id)
    except svc.ConsentError as err:
        _raise(err)
    return _one(db, current_user.id, grant_id)

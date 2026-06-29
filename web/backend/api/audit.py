from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from web.backend.database.database import get_db
from web.backend.database.models import User
from web.backend.services.auth import auth
from web.backend.services.audit import AuditLogService
from web.backend.models.audit import (
    AuditLogCreate,
    AuditLogResponse,
    AuditLogRevokeRequest,
    AuditLogListResponse,
)

router = APIRouter()


def _log_to_response(log) -> AuditLogResponse:
    return AuditLogResponse(
        id=log.id,
        user_id=log.user_id,
        action=log.action,
        target_type=log.target_type,
        target_id=log.target_id,
        scope=log.scope,
        detail=log.detail,
        revokeable=log.revokeable,
        revoked_at=log.revoked_at,
        created_at=log.created_at,
    )


@router.post("/logs", response_model=AuditLogResponse)
async def create_audit_log(
    body: AuditLogCreate,
    request: Request,
    current_user: User = Depends(auth),
    db: Session = Depends(get_db),
):
    service = AuditLogService(db)
    ip_address = request.client.host if request.client else None
    log = service.create_log(
        user_id=current_user.id,
        action=body.action,
        target_type=body.target_type,
        target_id=body.target_id,
        scope=body.scope,
        detail=body.detail,
        revokeable=body.revokeable,
        ip_address=ip_address,
    )
    return _log_to_response(log)


@router.get("/logs", response_model=AuditLogListResponse)
async def list_audit_logs(
    limit: int = 20,
    offset: int = 0,
    current_user: User = Depends(auth),
    db: Session = Depends(get_db),
):
    service = AuditLogService(db)
    total, logs = service.get_user_logs(
        user_id=current_user.id, limit=limit, offset=offset
    )
    return AuditLogListResponse(
        total=total, items=[_log_to_response(log) for log in logs]
    )


@router.get("/logs/{log_id}", response_model=AuditLogResponse)
async def get_audit_log(
    log_id: int,
    current_user: User = Depends(auth),
    db: Session = Depends(get_db),
):
    service = AuditLogService(db)
    log = service.get_log_detail(log_id=log_id, user_id=current_user.id)
    if not log:
        raise HTTPException(status_code=404, detail="审计日志不存在")
    return _log_to_response(log)


@router.post("/logs/{log_id}/revoke", response_model=AuditLogResponse)
async def revoke_audit_log(
    log_id: int,
    body: AuditLogRevokeRequest,
    current_user: User = Depends(auth),
    db: Session = Depends(get_db),
):
    if not body.confirm:
        raise HTTPException(status_code=400, detail="请确认撤销操作")
    service = AuditLogService(db)
    try:
        log = service.revoke_log(log_id=log_id, user_id=current_user.id)
        return _log_to_response(log)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/target/{target_type}/{target_id}", response_model=AuditLogListResponse)
async def get_target_audit_trail(
    target_type: str,
    target_id: int,
    limit: int = 20,
    offset: int = 0,
    current_user: User = Depends(auth),
    db: Session = Depends(get_db),
):
    # Non-admins only see their own actions on the target (prevents enumerating
    # other users' audit trails by naming a target they can see).
    actor_filter = None if bool(getattr(current_user, "is_admin", False)) else current_user.id
    service = AuditLogService(db)
    total, logs = service.get_log_by_target(
        target_type=target_type,
        target_id=target_id,
        limit=limit,
        offset=offset,
        actor_user_id=actor_filter,
    )
    return AuditLogListResponse(
        total=total, items=[_log_to_response(log) for log in logs]
    )

from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy import desc
from sqlalchemy.orm import Session

from web.backend.database.models import AuditLog
from web.backend.utils.redact import mask_ip


class AuditLogService:
    def __init__(self, db: Session):
        self.db = db

    def create_log(
        self,
        user_id: int,
        action: str,
        target_type: str,
        target_id: Optional[int] = None,
        scope: str = "public",
        detail: Optional[str] = None,
        revokeable: bool = True,
        ip_address: Optional[str] = None,
    ) -> AuditLog:
        log = AuditLog(
            user_id=user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            scope=scope,
            detail=detail,
            revokeable=revokeable,
            ip_address=mask_ip(ip_address),
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def revoke_log(self, log_id: int, user_id: int) -> AuditLog:
        log = self.db.query(AuditLog).filter_by(id=log_id, user_id=user_id).first()
        if not log:
            raise ValueError("审计日志不存在或无权操作")
        if not log.revokeable:
            raise ValueError("该审计日志不可撤销")
        if log.revoked_at is not None:
            raise ValueError("该审计日志已被撤销")

        log.revoked_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(log)
        return log

    def get_user_logs(
        self, user_id: int, limit: int = 20, offset: int = 0
    ) -> Tuple[int, List[AuditLog]]:
        query = self.db.query(AuditLog).filter_by(user_id=user_id)
        total = query.count()
        logs = (
            query.order_by(desc(AuditLog.created_at)).offset(offset).limit(limit).all()
        )
        return total, logs

    def get_log_detail(self, log_id: int, user_id: int) -> Optional[AuditLog]:
        return self.db.query(AuditLog).filter_by(id=log_id, user_id=user_id).first()

    def get_log_by_target(
        self,
        target_type: str,
        target_id: int,
        limit: int = 20,
        offset: int = 0,
    ) -> Tuple[int, List[AuditLog]]:
        query = self.db.query(AuditLog).filter_by(
            target_type=target_type, target_id=target_id
        )
        total = query.count()
        logs = (
            query.order_by(desc(AuditLog.created_at)).offset(offset).limit(limit).all()
        )
        return total, logs

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class AuditLogCreate(BaseModel):
    """创建审计日志请求"""

    action: str = Field(
        ...,
        max_length=50,
        description="操作类型: share, publish, revoke, delete, export",
    )
    target_type: str = Field(
        ...,
        max_length=50,
        description="目标类型: post, comment, assessment, collection",
    )
    target_id: Optional[int] = Field(None, description="目标对象ID")
    scope: str = Field(
        "public",
        max_length=20,
        description="范围: public, followers, specific_users, private",
    )
    detail: Optional[str] = Field(None, description="JSON格式详细信息")
    revokeable: bool = Field(True, description="是否可撤销")


class AuditLogResponse(BaseModel):
    """审计日志响应（不含ip_address — L3数据）"""

    id: int
    user_id: int
    action: str
    target_type: str
    target_id: Optional[int] = None
    scope: str
    detail: Optional[str] = None
    revokeable: bool
    revoked_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AuditLogRevokeRequest(BaseModel):
    """撤销审计日志请求"""

    confirm: bool = Field(..., description="确认撤销")


class AuditLogListResponse(BaseModel):
    """审计日志列表响应"""

    total: int
    items: List[AuditLogResponse]

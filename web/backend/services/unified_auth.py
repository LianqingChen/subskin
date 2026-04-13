"""
统一认证中间件
支持多种认证方式：JWT Bearer、微信、支付宝、手机号验证码
"""

from typing import Optional, Union
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from web.backend.database.database import get_db
from web.backend.database.models import User
from web.backend.services.auth import get_current_user as get_current_user_jwt

# HTTP Bearer 认证
security = HTTPBearer()


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """统一认证中间件 - 支持多种认证方式

    优先级：
    1. JWT Bearer Token
    2. 其他方式（预留扩展）
    """
    # JWT Bearer 认证
    if credentials and credentials.scheme == "Bearer":
        try:
            user = await get_current_user_jwt(credentials.credentials, db)
            return user
        except HTTPException:
            pass

    # 无有效认证
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="需要有效的认证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """获取当前激活用户（未激活则401）"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="用户账号已被停用"
        )
    return current_user


async def get_current_admin_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """获取当前管理员用户（非管理员则403）"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限"
        )
    return current_user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """可选认证中间件 - 未认证返回None而不是401

    适用于：游客可访问的资源，认证用户有额外功能
    """
    if credentials and credentials.scheme == "Bearer":
        try:
            user = await get_current_user_jwt(credentials.credentials, db)
            return user
        except HTTPException:
            pass

    return None

"""
JWT认证服务
支持访问令牌及刷新令牌
"""

import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, Optional, cast

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from web.backend.database.database import get_db
from web.backend.database.models import User, RefreshToken

SECRET_KEY = os.environ["SECRET_KEY"]  # 必须通过环境变量设置，不再提供默认值
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "10080"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
ADMIN_TOKEN_EXPIRE_DAYS = int(os.getenv("ADMIN_TOKEN_EXPIRE_DAYS", "365"))  # 管理员token几乎永不过期

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/user/login", auto_error=False)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(
    data: dict[str, Any], expires_delta: Optional[timedelta] = None,
    is_admin: bool = False,
) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    elif is_admin:
        # 管理员token使用极长过期时间（默认365天），确保不因闲置被踢出
        expire = datetime.now(timezone.utc) + timedelta(days=ADMIN_TOKEN_EXPIRE_DAYS)
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access", "is_admin": is_admin})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict[str, Any], db: Session, is_admin: bool = False) -> str:
    token = secrets.token_urlsafe(64)
    username = data.get("sub")
    if not isinstance(username, str):
        raise ValueError("Token subject is missing")
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise ValueError(f"User {username} not found")

    expire_days = ADMIN_TOKEN_EXPIRE_DAYS if is_admin else REFRESH_TOKEN_EXPIRE_DAYS
    expired_at = datetime.now(timezone.utc) + timedelta(days=expire_days)
    refresh_token = RefreshToken(token=token, user_id=user.id, expired_at=expired_at)
    db.add(refresh_token)
    db.commit()
    return token


def verify_refresh_token(token: str, db: Session) -> Optional[User]:
    now = datetime.now(timezone.utc)
    refresh_token = (
        db.query(RefreshToken)
        .filter(RefreshToken.token == token)
        .filter(RefreshToken.revoked == False)
        .filter(RefreshToken.expired_at > now)
        .first()
    )
    if not refresh_token:
        return None

    user = db.query(User).filter(User.id == refresh_token.user_id).first()
    return user


def revoke_refresh_token(token: str, db: Session) -> bool:
    refresh_token = db.query(RefreshToken).filter(RefreshToken.token == token).first()
    if refresh_token:
        db.query(RefreshToken).filter(RefreshToken.token == token).update(
            {"revoked": True}
        )
        db.commit()
        return True
    return False


def revoke_all_user_tokens(user_id: int, db: Session) -> int:
    now = datetime.now(timezone.utc)
    result = (
        db.query(RefreshToken)
        .filter(RefreshToken.user_id == user_id)
        .filter(RefreshToken.revoked == False)
        .filter(RefreshToken.expired_at > now)
        .update({"revoked": True})
    )
    db.commit()
    return result


async def authenticate_user(
    username: str, password: str, db: Session
) -> Optional[User]:
    # 支持 username / 手机号 / 邮箱 登录
    from sqlalchemy import or_
    user = (
        db.query(User)
        .filter(
            or_(
                User.username == username,
                User.phone == username,
                User.email == username,
            )
        )
        .first()
    )
    if not user:
        return None
    hashed_password = cast(Optional[str], cast(object, user.hashed_password))
    if not hashed_password:
        return None
    if not verify_password(password, hashed_password):
        return None
    return user


def get_user_from_access_token(token: str, db: Session) -> Optional[User]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        token_type = payload.get("type", "access")
        if not isinstance(username, str) or token_type != "access":
            return None
    except JWTError:
        return None

    return db.query(User).filter(User.username == username).first()


async def get_current_user(
    token: Annotated[Optional[str], Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if token is None:
        raise credentials_exception
    user = get_user_from_access_token(token, db)
    if user is None:
        raise credentials_exception
    return user


async def get_current_user_optional(
    token: Annotated[Optional[str], Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
):
    if token is None:
        return None

    try:
        return await get_current_user(token=token, db=db)
    except HTTPException:
        return None


async def get_required_user(
    token: Annotated[str, Depends(OAuth2PasswordBearer(tokenUrl="api/user/login"))],
    db: Annotated[Session, Depends(get_db)],
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    user = get_user_from_access_token(token, db)
    if user is None:
        raise credentials_exception
    return user


auth = get_required_user


def verify_token_ws(token: str):
    """从 WebSocket 查询参数验证 JWT token"""
    from web.backend.database.database import SessionLocal
    from web.backend.database.models import User as WsUser

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            return None
        db = SessionLocal()
        user = db.query(WsUser).filter(WsUser.id == int(user_id)).first()
        db.close()
        if user and user.is_active and user.user_status != "banned":
            return user
    except Exception:
        pass
    return None


def cleanup_expired_refresh_tokens():
    """Delete expired or revoked refresh tokens to prevent DB bloat."""
    import logging
    from web.backend.database.database import SessionLocal as _SL
    logger = logging.getLogger(__name__)
    db = _SL()
    try:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        deleted = (
            db.query(RefreshToken)
            .filter(
                (RefreshToken.expired_at < now) | (RefreshToken.revoked == True)
            )
            .delete(synchronize_session=False)
        )
        db.commit()
        if deleted > 0:
            logger.info("Cleaned up %d expired/revoked refresh tokens", deleted)
    except Exception as e:
        db.rollback()
        logger.error("Refresh token cleanup failed: %s", e)
    finally:
        db.close()

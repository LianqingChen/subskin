"""
第三方扫码登录API（微信、支付宝）
支持OAuth2.0流程、CSRF防护、状态轮询
"""

import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional, cast

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from web.backend.database.database import get_db
from web.backend.database.models import User as DBUser, OAuthState
from web.backend.models.user import Token, OAuthCallback, OAuthAuthUrl
from web.backend.services.wechat_auth import WechatAuthService
from web.backend.services.alipay_auth import AlipayAuthService
from web.backend.services.auth import create_access_token, create_refresh_token
from web.backend.api.user import _sync_legacy_user_fields
from web.backend.services.user_serializer import get_user_response as _get_user_response

logger = logging.getLogger(__name__)
router = APIRouter()

# status 轮询限速（2026-08-30 加固）：state 会出现在重定向 URL / 浏览器历史 /
# nginx 日志中，轮询端点必须防止被用来反复铸造 token。
_poll_buckets: dict = {}


def _poll_rate_limit(request: Request) -> None:
    from web.backend.utils.client_ip import get_real_client_ip

    ip = get_real_client_ip(request)
    now = time.time()
    window = 60
    limit = 30
    hits = [t for t in _poll_buckets.get(ip, []) if now - t < window]
    if len(hits) >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="请求过于频繁，请稍后再试",
        )
    hits.append(now)
    _poll_buckets[ip] = hits


def _consume_oauth_state(db: Session, oauth_state) -> Optional["DBUser"]:
    """按 state 换取用户并一次性消费。

    安全约束（2026-08-30 加固）：
    1. 过期校验 — expired_at 必须晚于当前时间；
    2. 一次性消费 — 签发成功后立即清空 user_id，同一 state 无法二次铸币；
    3. 调用方需先过 IP 限速。
    """
    from web.backend.database.models import OAuthState  # noqa: F401
    if oauth_state is None or not cast(bool, cast(object, oauth_state.used)):
        return None
    expired_at = cast(Optional[datetime], cast(object, oauth_state.expired_at))
    if expired_at is None or expired_at <= datetime.now(timezone.utc):
        return None
    oauth_user_id = cast(Optional[int], cast(object, oauth_state.user_id))
    if oauth_user_id is None:
        return None
    user = db.query(DBUser).filter(DBUser.id == oauth_user_id).first()
    if user is None:
        return None
    # 一次性消费：清空关联，后续轮询只能得到 pending
    oauth_state.user_id = None  # type: ignore[assignment]
    db.commit()
    return user


def _login_response(user: DBUser, db: Session) -> dict[str, Any]:
    _sync_legacy_user_fields(db, user)
    db.commit()
    db.refresh(user)
    access_token = create_access_token(
            data={"sub": user.username},
            token_version=int(getattr(user, "token_version", 0) or 0),
        )
    refresh_token = create_refresh_token(data={"sub": user.username}, db=db)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": _get_user_response(user, include_private=True, include_sensitive=True),
    }


@router.get("/wechat/auth-url", response_model=OAuthAuthUrl)
async def get_wechat_auth_url(db: Session = Depends(get_db)):
    service = WechatAuthService()
    state = service.create_auth_state(db)
    auth_url = service.get_auth_url(state)
    return {"auth_url": auth_url, "state": state}


@router.post("/wechat/callback", response_model=Token)
async def wechat_callback(data: OAuthCallback, db: Session = Depends(get_db)):
    service = WechatAuthService()

    oauth_state = service.validate_state(db, data.state)
    if not oauth_state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效或已过期的授权状态",
        )

    try:
        token_data = service.get_access_token(data.code)
        user_info = service.get_userinfo(
            access_token=token_data["access_token"],
            openid=token_data["openid"],
        )
        user = service.get_or_create_user(db, user_info)
        service.mark_state_used(db, data.state, cast(int, cast(object, user.id)))

        return _login_response(user, db)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("微信登录失败: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="登录服务暂时不可用，请稍后重试",
        )


@router.get("/wechat/status")
async def wechat_login_status(state: str, request: Request, db: Session = Depends(get_db)):
    _poll_rate_limit(request)
    oauth_state = db.query(OAuthState).filter(OAuthState.state == state).first()
    user = _consume_oauth_state(db, oauth_state)
    if user is not None:
        return {
            "status": "confirmed",
            "access_token": create_access_token(
                data={"sub": user.username},
                token_version=int(getattr(user, "token_version", 0) or 0),
            ),
            "refresh_token": create_refresh_token(data={"sub": user.username}, db=db),
            "token_type": "bearer",
        }
    return {"status": "pending"}


@router.get("/alipay/auth-url", response_model=OAuthAuthUrl)
async def get_alipay_auth_url(db: Session = Depends(get_db)):
    service = AlipayAuthService()
    state = service.create_auth_state(db)
    auth_url = service.get_auth_url(state)
    return {"auth_url": auth_url, "state": state}


@router.post("/alipay/callback", response_model=Token)
async def alipay_callback(data: OAuthCallback, db: Session = Depends(get_db)):
    service = AlipayAuthService()

    oauth_state = service.validate_state(db, data.state)
    if not oauth_state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效或已过期的授权状态",
        )

    try:
        token_data = service.get_access_token(data.code)
        access_token = token_data.get("access_token") or token_data.get(
            "alipay_system_oauth_token_response", {}
        ).get("access_token")
        if not access_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="支付宝授权失败：无法获取access_token",
            )

        user_info = service.get_user_info(access_token)
        user = service.get_or_create_user(db, user_info)
        service.mark_state_used(db, data.state, cast(int, cast(object, user.id)))

        return _login_response(user, db)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("支付宝登录失败: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="登录服务暂时不可用，请稍后重试",
        )


@router.get("/alipay/status")
async def alipay_login_status(state: str, request: Request, db: Session = Depends(get_db)):
    _poll_rate_limit(request)
    oauth_state = db.query(OAuthState).filter(OAuthState.state == state).first()
    user = _consume_oauth_state(db, oauth_state)
    if user is not None:
        return {
            "status": "confirmed",
            "access_token": create_access_token(
                data={"sub": user.username},
                token_version=int(getattr(user, "token_version", 0) or 0),
            ),
            "refresh_token": create_refresh_token(data={"sub": user.username}, db=db),
            "token_type": "bearer",
        }
    return {"status": "pending"}

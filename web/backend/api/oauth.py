"""
第三方扫码登录API（微信、支付宝）
支持OAuth2.0流程、CSRF防护、状态轮询
"""

import logging
from typing import Any, Optional, cast

from fastapi import APIRouter, Depends, HTTPException, status
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


def _login_response(user: DBUser, db: Session) -> dict[str, Any]:
    _sync_legacy_user_fields(db, user)
    db.commit()
    db.refresh(user)
    access_token = create_access_token(data={"sub": user.username})
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
async def wechat_login_status(state: str, db: Session = Depends(get_db)):
    oauth_state = db.query(OAuthState).filter(OAuthState.state == state).first()

    if oauth_state is not None and cast(bool, cast(object, oauth_state.used)):
        oauth_user_id = cast(Optional[int], cast(object, oauth_state.user_id))
        if oauth_user_id is not None:
            user = db.query(DBUser).filter(DBUser.id == oauth_user_id).first()
        else:
            user = None
        if user is not None:
            access_token = create_access_token(data={"sub": user.username})
            refresh_token = create_refresh_token(data={"sub": user.username}, db=db)
            return {
                "status": "confirmed",
                "access_token": access_token,
                "refresh_token": refresh_token,
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
async def alipay_login_status(state: str, db: Session = Depends(get_db)):
    oauth_state = db.query(OAuthState).filter(OAuthState.state == state).first()

    if oauth_state is not None and cast(bool, cast(object, oauth_state.used)):
        oauth_user_id = cast(Optional[int], cast(object, oauth_state.user_id))
        if oauth_user_id is not None:
            user = db.query(DBUser).filter(DBUser.id == oauth_user_id).first()
        else:
            user = None
        if user is not None:
            access_token = create_access_token(data={"sub": user.username})
            refresh_token = create_refresh_token(data={"sub": user.username}, db=db)
            return {
                "status": "confirmed",
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
            }

    return {"status": "pending"}

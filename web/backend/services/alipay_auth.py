"""
支付宝开放平台扫码登录服务
使用支付宝第三方授权流程
文档: https://opendocs.alipay.com/open/218/105325
"""

import os
import secrets
import logging
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, cast

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from web.backend.database.models import User, OAuthState
from web.backend.utils.uid import generate_uid
from web.backend.services.credential import bind_credential, find_user_by_credential

logger = logging.getLogger(__name__)

ALIPAY_AUTH_URL = "https://openauth.alipay.com/oauth2/publicAppAuthorize.htm"
ALIPAY_TOKEN_URL = "https://openapi.alipay.com/gateway.do"
ALIPAY_USER_URL = "https://openapi.alipay.com/gateway.do"

STATE_EXPIRE_MINUTES = 10


def _utcnow():
    return datetime.now(timezone.utc)


class AlipayAuthService:
    def __init__(self):
        self.app_id = os.getenv("ALIPAY_APP_ID", "")
        self.app_private_key = os.getenv("ALIPAY_PRIVATE_KEY", "")
        self.alipay_public_key = os.getenv("ALIPAY_PUBLIC_KEY", "")
        self.redirect_uri = os.getenv("ALIPAY_REDIRECT_URI", "")

    def _validate_config(self):
        if not all(
            [
                self.app_id,
                self.app_private_key,
                self.alipay_public_key,
                self.redirect_uri,
            ]
        ):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="支付宝登录服务未配置",
            )

    def _get_alipay_client(self):
        try:
            from alipay import AliPay  # pyright: ignore[reportMissingImports]

            alipay_private_key_string = self.app_private_key
            if not alipay_private_key_string.startswith("-----"):
                alipay_private_key_string = f"-----BEGIN RSA PRIVATE KEY-----\n{alipay_private_key_string}\n-----END RSA PRIVATE KEY-----"

            alipay_public_key_string = self.alipay_public_key
            if not alipay_public_key_string.startswith("-----"):
                alipay_public_key_string = f"-----BEGIN PUBLIC KEY-----\n{alipay_public_key_string}\n-----END PUBLIC KEY-----"

            return AliPay(
                appid=self.app_id,
                app_private_key_string=alipay_private_key_string,
                alipay_public_key_string=alipay_public_key_string,
                sign_type="RSA2",
                debug=False,
            )
        except ImportError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="支付宝SDK未安装，请运行: pip install python-alipay-sdk",
            )

    def create_auth_state(self, db: Session) -> str:
        state = secrets.token_urlsafe(32)
        expired_at = _utcnow() + timedelta(minutes=STATE_EXPIRE_MINUTES)
        oauth_state = OAuthState(state=state, provider="alipay", expired_at=expired_at)
        db.add(oauth_state)
        db.commit()
        return state

    def validate_state(self, db: Session, state: str) -> Optional[OAuthState]:
        now = _utcnow()
        oauth_state = (
            db.query(OAuthState)
            .filter(OAuthState.state == state)
            .filter(OAuthState.provider == "alipay")
            .filter(OAuthState.used == False)
            .filter(OAuthState.expired_at > now)
            .first()
        )
        return oauth_state

    def mark_state_used(self, db: Session, state: str, user_id: int):
        oauth_state = db.query(OAuthState).filter(OAuthState.state == state).first()
        if oauth_state is not None:
            setattr(oauth_state, "used", True)
            setattr(oauth_state, "user_id", user_id)
            db.commit()

    def get_auth_url(self, state: str) -> str:
        self._validate_config()
        params = {
            "app_id": self.app_id,
            "scope": "auth_user",
            "redirect_uri": self.redirect_uri,
            "state": state,
        }
        url = f"{ALIPAY_AUTH_URL}?{urllib.parse.urlencode(params)}"
        return url

    def get_access_token(self, code: str) -> Dict[str, Any]:
        alipay_client = self._get_alipay_client()
        result = alipay_client.api_alipay_system_oauth_auth_token(
            grant_type="authorization_code", code=code
        )

        if "error_response" in result:
            error = result["error_response"]
            logger.error(
                "支付宝获取token失败: %s - %s", error.get("code"), error.get("msg")
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"支付宝授权失败: {error.get('sub_msg', error.get('msg', '未知错误'))}",
            )

        return result

    def get_user_info(self, access_token: str) -> Dict[str, Any]:
        alipay_client = self._get_alipay_client()
        result = alipay_client.api_alipay_user_info_share(auth_token=access_token)

        if "error_response" in result:
            error = result["error_response"]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"获取支付宝用户信息失败: {error.get('sub_msg', '未知错误')}",
            )

        return result.get("alipay_user_info_share_response", result)

    def get_or_create_user(self, db: Session, user_info: Dict[str, Any]) -> User:
        alipay_user_id = cast(
            str, user_info.get("user_id") or user_info.get("alipay_user_id", "")
        )
        if not alipay_user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="无法获取支付宝用户ID",
            )

        user = find_user_by_credential(db, "alipay", alipay_user_id)

        if user is None:
            username = f"alipay_{alipay_user_id[:12]}"
            existing = db.query(User).filter(User.username == username).first()
            if existing:
                username = f"alipay_{secrets.token_hex(6)}"

            user = User(
                uid=generate_uid(alipay_user_id, db),
                username=username,
                alipay_id=alipay_user_id,
                hashed_password=None,
                is_active=True,
                is_admin=False,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            bind_credential(
                db,
                cast(int, cast(object, user.id)),
                "alipay",
                alipay_user_id,
                verified=True,
            )
            setattr(user, "alipay_id", alipay_user_id)
            db.commit()
            logger.info("支付宝新用户创建: %s", username)

        return user

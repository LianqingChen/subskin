"""
微信开放平台扫码登录服务
"""

import os
import secrets
import requests
from typing import Any, Dict, Optional, cast
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from web.backend.database.models import User, OAuthState
from web.backend.utils.uid import generate_uid
from web.backend.services.credential import bind_credential, find_user_by_credential


STATE_EXPIRE_MINUTES = 10


def _utcnow():
    return datetime.now(timezone.utc)


class WechatAuthService:
    """微信开放平台认证服务"""

    def __init__(self):
        self.app_id = os.getenv("WECHAT_APP_ID")
        self.app_secret = os.getenv("WECHAT_APP_SECRET")
        self.redirect_uri = os.getenv("WECHAT_REDIRECT_URI")
        self.base_url = "https://open.weixin.qq.com/connect/oauth2/authorize"
        self.access_token_url = "https://api.weixin.qq.com/sns/oauth2/access_token"
        self.userinfo_url = "https://api.weixin.qq.com/sns/userinfo"

    def get_auth_url(self, state: Optional[str] = None) -> str:
        """生成微信扫码登录URL"""
        if not all([self.app_id, self.redirect_uri]):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="微信开放平台配置缺失",
            )

        params = {
            "appid": self.app_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "snsapi_login",  # 静默授权
            "state": state or "subskin",
        }
        url = f"{self.base_url}?{self._build_query(params)}"
        return url

    def create_auth_state(self, db: Session) -> str:
        state = secrets.token_urlsafe(32)
        expired_at = _utcnow() + timedelta(minutes=STATE_EXPIRE_MINUTES)
        oauth_state = OAuthState(state=state, provider="wechat", expired_at=expired_at)
        db.add(oauth_state)
        db.commit()
        return state

    def validate_state(self, db: Session, state: str) -> Optional[OAuthState]:
        now = _utcnow()
        return (
            db.query(OAuthState)
            .filter(OAuthState.state == state)
            .filter(OAuthState.provider == "wechat")
            .filter(OAuthState.used == False)
            .filter(OAuthState.expired_at > now)
            .first()
        )

    def mark_state_used(self, db: Session, state: str, user_id: int):
        oauth_state = db.query(OAuthState).filter(OAuthState.state == state).first()
        if oauth_state is not None:
            setattr(oauth_state, "used", True)
            setattr(oauth_state, "user_id", user_id)
            db.commit()

    def get_access_token(self, code: str) -> Dict[str, Any]:
        """通过授权码获取access_token"""
        params = {
            "appid": self.app_id,
            "secret": self.app_secret,
            "code": code,
            "grant_type": "authorization_code",
        }

        response = requests.get(self.access_token_url, params=params)
        data = response.json()

        if "errcode" in data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"微信授权失败: {data['errmsg']}",
            )

        return data

    def get_userinfo(self, access_token: str, openid: str) -> Dict[str, Any]:
        """获取用户信息"""
        params = {"access_token": access_token, "openid": openid, "lang": "zh_CN"}

        response = requests.get(self.userinfo_url, params=params)
        data = response.json()

        if "errcode" in data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"获取微信用户信息失败: {data['errmsg']}",
            )

        return data

    def get_or_create_user(self, db: Session, wechat_userinfo: Dict[str, Any]) -> User:
        """根据微信用户信息获取或创建用户"""
        openid = cast(Optional[str], wechat_userinfo.get("openid"))
        unionid = cast(Optional[str], wechat_userinfo.get("unionid"))

        wechat_id = unionid if unionid else openid
        if not wechat_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="无法获取微信用户ID",
            )

        user = find_user_by_credential(db, "wechat", wechat_id)

        if user is None:
            username = f"wechat_{wechat_id[:10]}"
            if db.query(User).filter(User.username == username).first():
                username = f"wechat_{secrets.token_hex(6)}"

            user = User(
                uid=generate_uid(wechat_id, db),
                username=username,
                wechat_id=wechat_id,
                hashed_password=None,
                is_active=True,
                is_admin=False,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            bind_credential(
                db, cast(int, cast(object, user.id)), "wechat", wechat_id, verified=True
            )
            setattr(user, "wechat_id", wechat_id)
            db.commit()

        return user

    def _build_query(self, params: Dict[str, Any]) -> str:
        """构建查询字符串"""
        return "&".join([f"{k}={v}" for k, v in params.items()])

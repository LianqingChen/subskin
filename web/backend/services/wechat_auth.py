"""
微信开放平台扫码登录服务
"""

import os
import json
import requests
from typing import Optional, Dict
from datetime import datetime, timedelta
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from web.backend.database.models import User


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

    def get_access_token(self, code: str) -> Dict:
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

    def get_userinfo(self, access_token: str, openid: str) -> Dict:
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

    def get_or_create_user(self, db: Session, wechat_userinfo: Dict) -> User:
        """根据微信用户信息获取或创建用户"""
        openid = wechat_userinfo.get("openid")
        unionid = wechat_userinfo.get("unionid")  # 开放平台唯一标识

        wechat_id = unionid if unionid else openid

        user = db.query(User).filter(User.wechat_id == wechat_id).first()

        if not user:
            user = User(
                username=f"wechat_{wechat_id[:10]}",
                wechat_id=wechat_id,
                hashed_password="",  # 社交登录无需密码
                is_active=True,
                is_admin=False,
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        return user

    def _build_query(self, params: Dict) -> str:
        """构建查询字符串"""
        return "&".join([f"{k}={v}" for k, v in params.items()])

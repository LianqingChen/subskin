"""
支付宝开放平台扫码登录服务
"""

import os
import json
import hashlib
import base64
import requests
from typing import Optional, Dict
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from web.backend.database.models import User


class AlipayAuthService:
    """支付宝开放平台认证服务"""

    def __init__(self):
        self.app_id = os.getenv("ALIPAY_APP_ID")
        self.app_private_key = os.getenv("ALIPAY_PRIVATE_KEY")
        self.alipay_public_key = os.getenv("ALIPAY_PUBLIC_KEY")
        self.redirect_uri = os.getenv("ALIPAY_REDIRECT_URI")
        self.auth_url = "https://openauth.alipay.com/oauth2/publicAppAuthorize.htm"

    def get_auth_url(self, state: Optional[str] = None) -> str:
        """生成支付宝扫码登录URL"""
        if not all([self.app_id, self.redirect_uri]):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="支付宝开放平台配置缺失",
            )

        params = {
            "app_id": self.app_id,
            "redirect_uri": self.redirect_uri,
            "scope": "auth_base",  # 基础授权
            "state": state or "subskin",
        }
        url = f"{self.auth_url}?{self._build_query(params)}"
        return url

    def get_access_token(self, code: str) -> Dict:
        """通过授权码获取access_token"""
        token_url = "https://openapi.alipay.com/gateway.do"

        params = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
        }

        biz_content = json.dumps(params, ensure_ascii=False)

        # 构建请求参数
        request_params = {
            "app_id": self.app_id,
            "method": "charset=utf-8",
            "sign": self._generate_sign(biz_content),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "version": "1.0",
            "biz_content": biz_content,
        }

        response = requests.post(token_url, data=request_params)
        data = response.json()

        if "code" in data and data["code"] != "10000":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"支付宝授权失败: {data.get('msg', '未知错误')}",
            )

        return data

    def get_alipay_user_id(self, access_token: str) -> str:
        """获取支付宝用户唯一标识"""
        info_url = "https://openapi.alipay.com/gateway.do"

        biz_content = json.dumps({"auth_token": access_token}, ensure_ascii=False)

        request_params = {
            "app_id": self.app_id,
            "method": "alipay.user.info.share",
            "charset": "utf-8",
            "sign": self._generate_sign(biz_content),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "version": "1.0",
            "biz_content": biz_content,
        }

        response = requests.post(info_url, data=request_params)
        data = response.json()

        if "code" in data and data["code"] != "10000":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"获取支付宝用户信息失败: {data.get('msg', '未知错误')}",
            )

        # 从返回数据中提取alipay_user_id
        alipay_user_id = data.get("alipay_user_id")
        if not alipay_user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="无法获取支付宝用户ID"
            )

        return alipay_user_id

    def get_or_create_user(self, db: Session, alipay_user_id: str) -> User:
        """根据支付宝用户ID获取或创建用户"""
        user = db.query(User).filter(User.alipay_id == alipay_user_id).first()

        if not user:
            user = User(
                username=f"alipay_{alipay_user_id[:10]}",
                alipay_id=alipay_user_id,
                hashed_password="",  # 社交登录无需密码
                is_active=True,
                is_admin=False,
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        return user

    def _generate_sign(self, biz_content: str) -> str:
        """生成签名（RSA2）"""
        # TODO: 实现RSA2签名
        # 需要使用alipay-python-sdk官方SDK
        # 这里是简化版本
        import hashlib
        import base64

        rsa_private_key = self.app_private_key

        # 实际实现需要使用cryptography或pycryptodome库
        # 这里仅作为示例
        sign = hashlib.sha256(biz_content.encode()).hexdigest()

        return sign

    def _build_query(self, params: Dict) -> str:
        """构建查询字符串"""
        return "&".join([f"{k}={v}" for k, v in params.items()])

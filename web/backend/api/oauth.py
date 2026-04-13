"""
第三方扫码登录API（微信、支付宝）
"""

from typing import Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from web.backend.database.database import get_db
from web.backend.models.user import User, Token
from web.backend.services.wechat_auth import WechatAuthService
from web.backend.services.alipay_auth import AlipayAuthService
from web.backend.services.auth import create_access_token


router = APIRouter()


@router.get("/wechat/auth-url")
async def get_wechat_auth_url(state: Optional[str] = None):
    """获取微信扫码登录URL"""
    service = WechatAuthService()
    auth_url = service.get_auth_url(state)
    return {"auth_url": auth_url}


@router.post("/wechat/callback", response_model=Token)
async def wechat_callback(code: str, db: Session = Depends(get_db)):
    """微信授权回调 - 处理扫码登录"""
    service = WechatAuthService()

    try:
        # 获取access_token
        token_data = service.get_access_token(code)

        # 获取用户信息
        user_info = service.get_userinfo(
            access_token=token_data["access_token"], openid=token_data["openid"]
        )

        # 获取或创建用户
        user = service.get_or_create_user(db, user_info)

        # 生成JWT token
        access_token = create_access_token(data={"sub": user.username})

        return {"access_token": access_token, "token_type": "bearer"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"微信登录失败: {str(e)}",
        )


@router.get("/alipay/auth-url")
async def get_alipay_auth_url(state: Optional[str] = None):
    """获取支付宝扫码登录URL"""
    service = AlipayAuthService()
    auth_url = service.get_auth_url(state)
    return {"auth_url": auth_url}


@router.post("/alipay/callback", response_model=Token)
async def alipay_callback(code: str, db: Session = Depends(get_db)):
    """支付宝授权回调 - 处理扫码登录"""
    service = AlipayAuthService()

    try:
        # 获取access_token
        token_data = service.get_access_token(code)

        # 获取支付宝用户ID
        alipay_user_id = service.get_alipay_user_id(
            access_token=token_data["access_tokenization_code"]
        )

        # 获取或创建用户
        user = service.get_or_create_user(db, alipay_user_id)

        # 生成JWT token
        access_token = create_access_token(data={"sub": user.username})

        return {"access_token": access_token, "token_type": "bearer"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"支付宝登录失败: {str(e)}",
        )

"""
用户数据模型
"""

from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime


class UserBase(BaseModel):
    username: str
    email: Optional[str] = None
    phone: Optional[str] = Field(None, description="手机号码")
    wechat_id: Optional[str] = Field(None, description="微信开放平台ID")
    alipay_id: Optional[str] = Field(None, description="支付宝开放平台ID")


class UserCreateByPhone(BaseModel):
    phone: str = Field(description="手机号码")
    code: str = Field(description="验证码")
    password: Optional[str] = None


class PhoneLogin(BaseModel):
    phone: str = Field(description="手机号码")
    code: str = Field(description="验证码")


class UserCreate(UserBase):
    password: str


class User(UserBase):
    id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str

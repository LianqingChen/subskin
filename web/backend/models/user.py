"""
用户数据模型
"""

from typing import Optional
from pydantic import BaseModel, Field, EmailStr
from datetime import datetime


class UserBase(BaseModel):
    username: str
    email: Optional[str] = None
    phone: Optional[str] = None
    patient_relation: Optional[str] = None
    avatar_url: Optional[str] = None
    wechat_id: Optional[str] = None
    alipay_id: Optional[str] = None


class UserCreate(UserBase):
    password: str


class UserCreateByPhone(BaseModel):
    phone: str = Field(pattern=r"^1[3-9]\d{9}$")
    code: str = Field(min_length=6, max_length=6)
    password: Optional[str] = None


class PhoneLogin(BaseModel):
    phone: str = Field(pattern=r"^1[3-9]\d{9}$")
    code: str = Field(min_length=6, max_length=6)


class PhonePasswordLogin(BaseModel):
    phone: str = Field(pattern=r"^1[3-9]\d{9}$")
    password: str = Field(min_length=6, max_length=128)


class EmailLogin(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6)


class EmailRegister(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6)
    username: str = Field(default="", max_length=20)
    password: str = Field(min_length=6, max_length=128)


class SendSMSCode(BaseModel):
    phone: str = Field(pattern=r"^1[3-9]\d{9}$")


class SendEmailCode(BaseModel):
    email: EmailStr
    purpose: str = Field(default="login", pattern=r"^(login|register|reset|bind)$")


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class BindPhoneRequest(BaseModel):
    phone: str = Field(pattern=r"^1[3-9]\d{9}$")
    code: str = Field(min_length=6, max_length=6)


class BindEmailRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6)


class SetPasswordRequest(BaseModel):
    password: str = Field(min_length=6, max_length=128)


class ResetPasswordRequest(BaseModel):
    credential_id: str
    cred_type: str = Field(pattern=r"^(phone|email)$")
    code: str = Field(min_length=6, max_length=6)
    new_password: str = Field(min_length=6, max_length=128)


class EmailPasswordLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class CredentialResponse(BaseModel):
    id: int
    cred_type: str
    cred_id: str
    verified: bool
    last_used_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class UserProfileUpdate(BaseModel):
    username: Optional[str] = Field(default=None, min_length=2, max_length=20)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(default=None, pattern=r"^1[3-9]\d{9}$")
    patient_relation: Optional[str] = None


class OAuthCallback(BaseModel):
    code: str
    state: str


class OAuthAuthUrl(BaseModel):
    auth_url: str
    state: str


class User(UserBase):
    id: int
    uid: Optional[str] = None
    is_active: bool
    is_admin: bool = False
    created_at: datetime
    privacy_mode: bool = True
    phone_discoverable: bool = True

    class Config:
        from_attributes: bool = True


class Token(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    user: Optional[User] = None

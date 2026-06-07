"""
短信及邮箱验证码数据模型
"""

from typing import Optional
from pydantic import BaseModel, Field


class SendSMSCode(BaseModel):
    phone: str = Field(pattern=r"^1[3-9]\d{9}$")


class SMSCodeVerify(BaseModel):
    phone: str = Field(pattern=r"^1[3-9]\d{9}$")
    code: str = Field(min_length=6, max_length=6)


class SendEmailCode(BaseModel):
    email: str = Field(description="邮箱地址")
    purpose: str = Field(default="login", pattern=r"^(login|register|reset)$")

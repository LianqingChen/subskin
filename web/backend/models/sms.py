"""
短信验证码数据模型
"""

from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime


class SendSMSCode(BaseModel):
    phone: str = Field(description="手机号码")


class SMSCodeVerify(BaseModel):
    phone: str = Field(description="手机号码")
    code: str = Field(description="验证码")

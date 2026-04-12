"""
短信验证码服务
支持阿里云短信、腾讯云短信，或留作第三方服务接入
"""

import os
import random
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from web.backend.database.models import SMSCode


def generate_code() -> str:
    """生成6位数字验证码"""
    return "".join(random.choices("0123456789", k=6))


def create_sms_code(db: Session, phone: str, expire_minutes: int = 5) -> str:
    """创建验证码并保存到数据库"""
    # 使之前的验证码失效
    old_codes = (
        db.query(SMSCode)
        .filter(SMSCode.phone == phone)
        .filter(SMSCode.used == False)
        .all()
    )
    for code in old_codes:
        code.used = True
    db.commit()

    # 生成新验证码
    code = generate_code()
    expired_at = datetime.utcnow() + timedelta(minutes=expire_minutes)
    sms_code = SMSCode(phone=phone, code=code, expired_at=expired_at, used=False)
    db.add(sms_code)
    db.commit()
    return code


def verify_sms_code(db: Session, phone: str, code: str) -> bool:
    """验证验证码是否正确"""
    sms_code = (
        db.query(SMSCode)
        .filter(SMSCode.phone == phone)
        .filter(SMSCode.code == code)
        .filter(SMSCode.used == False)
        .filter(SMSCode.expired_at > datetime.utcnow())
        .first()
    )
    if not sms_code:
        return False
    # 标记为已使用
    sms_code.used = True
    db.commit()
    return True


def send_sms(phone: str, code: str) -> bool:
    """发送短信验证码
    这里需要对接第三方短信服务商
    当前环境下，开发模式直接打印验证码到日志
    """
    # 开发模式：记录验证码
    print(f"[SMS] 手机号 {phone} 的验证码是: {code}")

    # 对接阿里云短信示例：
    # import alibabacloud_dysmsapi20170525 from ...
    # 调用发送接口...

    # 对接腾讯云短信示例：
    # from qcloudsms_py import SmsSingleSender
    # ...

    # 实际生产环境需要配置环境变量：
    # SMS_PROVIDER=aliyun|tencent|log
    # SMS_ACCESS_KEY_ID=xxx
    # SMS_ACCESS_KEY_SECRET=xxx
    # SMS_SIGN_NAME=xxx
    # SMS_TEMPLATE_CODE=xxx

    sms_provider = os.getenv("SMS_PROVIDER", "log")
    if sms_provider == "log":
        # 开发模式，只打印不真实发送
        return True

    # TODO: 实现真实短信发送
    return True

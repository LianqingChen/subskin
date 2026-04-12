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


def check_sms_rate_limit(db: Session, phone: str) -> None:
    """检查短信发送频率限制
    1. 60秒冷却时间：同一手机号60秒内只能发送一次
    2. 24小时频率限制：同一手机号24小时内最多发送10次
    """
    from fastapi import HTTPException, status

    now = datetime.utcnow()

    # 检查60秒冷却时间
    last_sent = (
        db.query(SMSCode)
        .filter(SMSCode.phone == phone)
        .order_by(SMSCode.created_at.desc())
        .first()
    )

    if last_sent:
        time_since_last = now - last_sent.created_at
        if time_since_last.total_seconds() < 60:
            remaining = 60 - int(time_since_last.total_seconds())
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"请求过于频繁，请等待{remaining}秒后再试",
            )

    # 检查24小时内发送次数（最多10次）
    twenty_four_hours_ago = now - timedelta(hours=24)
    recent_count = (
        db.query(SMSCode)
        .filter(SMSCode.phone == phone)
        .filter(SMSCode.created_at >= twenty_four_hours_ago)
        .count()
    )

    if recent_count >= 10:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="今日短信发送次数已达上限（10次），请明天再试",
        )


def create_sms_code(db: Session, phone: str, expire_minutes: int = 5) -> str:
    """创建验证码并保存到数据库"""
    # 检查频率限制
    check_sms_rate_limit(db, phone)

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
    """验证验证码是否正确，包含暴力破解防护"""
    from fastapi import HTTPException, status
    import logging

    logger = logging.getLogger(__name__)

    sms_code = (
        db.query(SMSCode)
        .filter(SMSCode.phone == phone)
        .filter(SMSCode.code == code)
        .filter(SMSCode.used == False)
        .filter(SMSCode.expired_at > datetime.utcnow())
        .first()
    )

    if sms_code:
        # 检查是否已锁定
        if sms_code.locked:
            logger.warning(f"SMS验证码已被锁定，拒绝验证: phone={phone}")
            return False

        # 验证成功，标记为已使用
        sms_code.used = True
        db.commit()
        logger.info(
            f"SMS验证码验证成功: phone={phone}, attempt_count={sms_code.attempt_count}"
        )
        return True

    # 验证失败，更新尝试次数
    active_code = (
        db.query(SMSCode)
        .filter(SMSCode.phone == phone)
        .filter(SMSCode.used == False)
        .filter(SMSCode.expired_at > datetime.utcnow())
        .first()
    )

    if active_code:
        active_code.attempt_count = (active_code.attempt_count or 0) + 1

        # 超过5次尝试，锁定验证码
        if active_code.attempt_count >= 5:
            active_code.locked = True
            logger.warning(
                f"SMS验证码已锁定（尝试次数过多）: phone={phone}, attempts={active_code.attempt_count}"
            )

        db.commit()
        logger.warning(
            f"SMS验证码验证失败: phone={phone}, attempt={active_code.attempt_count}, locked={active_code.locked}"
        )

    return False


def send_sms(phone: str, code: str) -> bool:
    """发送短信验证码
    这里需要对接第三方短信服务商
    当前环境下，开发模式直接打印验证码到日志
    """
    # 开发模式：记录验证码
    print(f"[SMS] 手机号 {phone} 的验证码是: {code}")

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

    if sms_provider == "aliyun":
        return _send_sms_aliyun(phone, code)
    elif sms_provider == "tencent":
        return _send_sms_tencent(phone, code)
    else:
        print(f"[SMS] 未知的短信服务商: {sms_provider}")
        return False


def _send_sms_aliyun(phone: str, code: str) -> bool:
    """使用阿里云发送短信"""
    try:
        from alibabacloud_dysmsapi20170525.client import Client as DysmsClient
        from alibabacloud_tea_openapi import models as open_api_models
        from TeaCore import TeaCoreConfiguration

        access_key_id = os.getenv("SMS_ACCESS_KEY_ID")
        access_key_secret = os.getenv("SMS_ACCESS_KEY_SECRET")
        sign_name = os.getenv("SMS_SIGN_NAME", "SubSkin")
        template_code = os.getenv("SMS_TEMPLATE_CODE")

        if not all([access_key_id, access_key_secret, template_code]):
            print("[SMS] 阿里云配置缺失")
            return False

        config = TeaCoreConfiguration(
            access_key_id=access_key_id, access_key_secret=access_key_secret
        )

        client = DysmsClient(config)

        request = open_api_models.SendSmsRequest(
            phone_numbers=phone,
            sign_name=sign_name,
            template_code=template_code,
            template_param=f'{{"code":"{code}"}}',
        )

        response = client.send_sms(request)

        if response.body.code == "OK":
            print(f"[SMS] 阿里云发送成功: {phone}")
            return True
        else:
            print(
                f"[SMS] 阿里云发送失败: {response.body.code}, {response.body.message}"
            )
            return False

    except ImportError:
        print(
            "[SMS] 阿里云SDK未安装，请运行: pip install alibabacloud-dysmsapi20170525"
        )
        return False
    except Exception as e:
        print(f"[SMS] 阿里云发送异常: {str(e)}")
        return False


def _send_sms_tencent(phone: str, code: str) -> bool:
    """使用腾讯云发送短信"""
    try:
        from tencentcloud.common.profile.profile import Profile
        from tencentcloud.common.credential.secret_idCredential import (
            SecretIdCredential,
        )
        from tencentcloud.sms.v20210111 import sms_client, models

        secret_id = os.getenv("SMS_ACCESS_KEY_ID")
        secret_key = os.getenv("SMS_ACCESS_KEY_SECRET")
        app_id = os.getenv("TENCENT_SMS_APP_ID")
        sign_name = os.getenv("SMS_SIGN_NAME", "SubSkin")
        template_id = os.getenv("TENCENT_SMS_TEMPLATE_ID")

        if not all([secret_id, secret_key, app_id, template_id]):
            print("[SMS] 腾讯云配置缺失")
            return False

        cred = SecretIdCredential(secret_id, secret_key)
        profile = Profile(cred, "ap-guangzhou")
        client = sms_client.SmsClient(profile)

        request = models.SendSmsRequest(
            phone_number_set=[f"+86{phone}"],
            sms_sign_id=sign_name,
            template_id=template_id,
            template_param_set=[{"code": code}],
        )

        response = client.SendSms(request)

        if response.SendStatusSet[0].Code == "Ok":
            print(f"[SMS] 腾讯云发送成功: {phone}")
            return True
        else:
            print(
                f"[SMS] 腾讯云发送失败: {response.SendStatusSet[0].Code} - {response.SendStatusSet[0].Message}"
            )
            return False

    except ImportError:
        print("[SMS] 腾讯云SDK未安装，请运行: pip install tencentcloud-sdk-python")
        return False
    except Exception as e:
        print(f"[SMS] 腾讯云发送异常: {str(e)}")
        return False

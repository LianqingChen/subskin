"""
短信验证码服务
支持阿里云短信认证服务（SendSmsVerifyCode + CheckSmsVerifyCode）、阿里云短信、腾讯云短信及开发模式（仅日志打印）

短信认证服务（aliyun_auth）说明：
- 使用号码认证服务赠送的签名和模板，无需自审签名
- 发送验证码：SendSmsVerifyCode
- 云端核验：CheckSmsVerifyCode（VerifySmsVerifyCode 已废弃）
"""

import os
import secrets
import logging
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from web.backend.database.models import SMSCode

logger = logging.getLogger(__name__)


def _utcnow():
    return datetime.now(timezone.utc)


def generate_code() -> str:
    return "".join(secrets.choice("0123456789") for _ in range(6))


def check_sms_rate_limit(db: Session, phone: str) -> None:
    now = _utcnow()

    last_sent = (
        db.query(SMSCode)
        .filter(SMSCode.phone == phone)
        .order_by(SMSCode.created_at.desc())
        .first()
    )

    if last_sent:
        created_at = last_sent.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        elapsed = (now - created_at).total_seconds()
        if elapsed < 60:
            remaining = 60 - int(elapsed)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"请求过于频繁，请等待{remaining}秒后再试",
            )

    midnight = now - timedelta(hours=24)
    recent_count = (
        db.query(SMSCode)
        .filter(SMSCode.phone == phone)
        .filter(SMSCode.created_at >= midnight)
        .count()
    )

    if recent_count >= 10:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="今日短信发送次数已达上限（10次），请明天再试",
        )


def create_sms_code(db: Session, phone: str, expire_minutes: int = 5) -> str:
    check_sms_rate_limit(db, phone)

    old_codes = (
        db.query(SMSCode)
        .filter(SMSCode.phone == phone)
        .filter(SMSCode.used == False)
        .all()
    )
    for code in old_codes:
        code.used = True
    db.commit()

    code = generate_code()
    expired_at = _utcnow() + timedelta(minutes=expire_minutes)
    sms_code = SMSCode(phone=phone, code=code, expired_at=expired_at, used=False)
    db.add(sms_code)
    db.commit()
    return code


def verify_sms_code(db: Session, phone: str, code: str) -> bool:
    """验证短信验证码

    所有模式均使用本地数据库校验。
    aliyun_auth 模式使用阿里云号码认证服务发送验证码（SendSmsVerifyCode），
    但验证码由本地生成并存储，因此校验也在本地完成。
    CheckSmsVerifyCode 要求阿里云端生成验证码（##code## 占位符），
    与本地生成验证码的场景不兼容，故不使用云端核验。
    """
    return _verify_sms_code_local(db, phone, code)


def _verify_sms_code_local(db: Session, phone: str, code: str) -> bool:
    """本地数据库验证短信验证码"""
    now = _utcnow()

    sms_code = (
        db.query(SMSCode)
        .filter(SMSCode.phone == phone)
        .filter(SMSCode.code == code)
        .filter(SMSCode.used == False)
        .filter(SMSCode.expired_at > now)
        .first()
    )

    if sms_code:
        if sms_code.locked:
            logger.warning("SMS验证码已锁定，拒绝验证: phone=%s", phone)
            return False

        sms_code.used = True
        db.commit()
        logger.info(
            "SMS验证码验证成功: phone=%s, attempts=%d", phone, sms_code.attempt_count
        )
        return True

    active_code = (
        db.query(SMSCode)
        .filter(SMSCode.phone == phone)
        .filter(SMSCode.used == False)
        .filter(SMSCode.expired_at > now)
        .first()
    )

    if active_code:
        active_code.attempt_count = (active_code.attempt_count or 0) + 1
        if active_code.attempt_count >= 5:
            active_code.locked = True
            logger.warning(
                "SMS验证码已锁定: phone=%s, attempts=%d",
                phone,
                active_code.attempt_count,
            )
        db.commit()

    return False


def _mark_local_code_used(db: Session, phone: str) -> None:
    """云端核验通过后，标记本地验证码记录为已使用"""
    now = _utcnow()
    active_code = (
        db.query(SMSCode)
        .filter(SMSCode.phone == phone)
        .filter(SMSCode.used == False)
        .filter(SMSCode.expired_at > now)
        .first()
    )
    if active_code:
        active_code.used = True
        db.commit()


def _increment_local_attempt(db: Session, phone: str) -> None:
    """云端核验失败时，增加本地尝试计数"""
    now = _utcnow()
    active_code = (
        db.query(SMSCode)
        .filter(SMSCode.phone == phone)
        .filter(SMSCode.used == False)
        .filter(SMSCode.expired_at > now)
        .first()
    )
    if active_code:
        active_code.attempt_count = (active_code.attempt_count or 0) + 1
        if active_code.attempt_count >= 5:
            active_code.locked = True
            logger.warning(
                "云端核验多次失败，本地锁定: phone=%s, attempts=%d",
                phone,
                active_code.attempt_count,
            )
        db.commit()


def send_sms(phone: str, code: str) -> tuple[bool, str]:
    """发送短信验证码

    Returns:
        (success, code_or_empty): 成功时返回验证码，失败时返回空字符串。
        aliyun_auth 模式下由阿里云管理验证码生命周期，返回本地生成的验证码（用于日志）。
    """
    logger.info("[SMS] 手机号 %s 的验证码是: %s", phone, code)

    sms_provider = os.getenv("SMS_PROVIDER", "log")
    if sms_provider == "log":
        return True, code

    if sms_provider == "aliyun_auth":
        return _send_sms_aliyun_auth(phone, code)
    elif sms_provider == "aliyun":
        return _send_sms_aliyun(phone, code)
    elif sms_provider == "tencent":
        return _send_sms_tencent(phone, code)
    else:
        logger.warning("未知的短信服务商: %s", sms_provider)
        return False, ""


def _send_sms_aliyun_auth(phone: str, code: str) -> tuple[bool, str]:
    """阿里云短信认证服务（号码认证服务赠送签名和模板）

    无需自审签名，使用号码认证服务赠送的签名和模板发送验证码。
    验证码由阿里云端核验（CheckSmsVerifyCode），无需本地比对。
    """
    try:
        from alibabacloud_dypnsapi20170525.client import Client as DypnsClient
        from alibabacloud_dypnsapi20170525 import models as dypns_models
        from alibabacloud_tea_openapi import models as open_api_models

        access_key_id = os.getenv("SMS_ACCESS_KEY_ID")
        access_key_secret = os.getenv("SMS_ACCESS_KEY_SECRET")
        sign_name = os.getenv("SMS_SIGN_NAME", "")
        template_code = os.getenv("SMS_TEMPLATE_CODE", "")
        scheme_name = os.getenv("SMS_VERIFY_SCENE", "")

        if not all([access_key_id, access_key_secret, sign_name, template_code]):
            logger.error(
                "阿里云短信认证服务配置缺失: ACCESS_KEY=%s, SIGN_NAME=%s, TEMPLATE_CODE=%s",
                "已设置" if access_key_id else "缺失",
                "已设置" if sign_name else "缺失",
                "已设置" if template_code else "缺失",
            )
            return False, ""

        logger.info(
            "阿里云短信认证服务发送参数: phone=%s, sign_name=%s, template_code=%s",
            phone,
            sign_name,
            template_code,
        )

        config = open_api_models.Config(
            access_key_id=access_key_id,
            access_key_secret=access_key_secret,
        )
        config.endpoint = "dypnsapi.aliyuncs.com"

        client = DypnsClient(config)

        request = dypns_models.SendSmsVerifyCodeRequest(
            phone_number=phone,
            sign_name=sign_name,
            template_code=template_code,
            template_param=f'{{"code":"{code}","min":"5"}}',
            code_length=6,
            valid_time=300,
            interval=60,
            duplicate_policy=1,
            return_verify_code=False,
        )

        if scheme_name:
            request.scheme_name = scheme_name

        response = client.send_sms_verify_code(request)

        if response.body.code == "OK" and response.body.success:
            logger.info("阿里云短信认证服务发送成功: phone=%s", phone)
            return True, code
        else:
            logger.error(
                "阿里云短信认证服务发送失败: code=%s, message=%s",
                response.body.code,
                response.body.message,
            )
            return False, ""

    except ImportError:
        logger.error(
            "阿里云号码认证SDK未安装，请运行: pip install alibabacloud-dypnsapi20170525"
        )
        return False, ""
    except Exception as e:
        logger.error("阿里云短信认证服务发送异常: %s", str(e))
        return False, ""


def _send_sms_aliyun(phone: str, code: str) -> tuple[bool, str]:
    try:
        from alibabacloud_dysmsapi20170525.client import Client as DysmsClient
        from alibabacloud_dysmsapi20170525 import models as dysms_models
        from alibabacloud_tea_openapi import models as open_api_models

        access_key_id = os.getenv("SMS_ACCESS_KEY_ID")
        access_key_secret = os.getenv("SMS_ACCESS_KEY_SECRET")
        sign_name = os.getenv("SMS_SIGN_NAME", "SubSkin")
        template_code = os.getenv("SMS_TEMPLATE_CODE")

        if not all([access_key_id, access_key_secret, template_code]):
            logger.error("阿里云短信配置缺失")
            return False, ""

        logger.info(
            "阿里云短信发送参数: phone=%s, sign_name=%s, template_code=%s",
            phone,
            sign_name,
            template_code,
        )

        config = open_api_models.Config(
            access_key_id=access_key_id,
            access_key_secret=access_key_secret,
        )
        config.endpoint = "dysmsapi.aliyuncs.com"

        client = DysmsClient(config)

        request = dysms_models.SendSmsRequest(
            phone_numbers=phone,
            sign_name=sign_name,
            template_code=template_code,
            template_param=f'{{"code":"{code}"}}',
        )

        response = client.send_sms(request)

        if response.body.code == "OK":
            logger.info("阿里云短信发送成功: %s", phone)
            return True, code
        else:
            logger.error(
                "阿里云短信发送失败: %s, %s", response.body.code, response.body.message
            )
            return False, ""

    except ImportError:
        logger.error(
            "阿里云SDK未安装，请运行: pip install alibabacloud-dysmsapi20170525"
        )
        return False, ""
    except Exception as e:
        logger.error("阿里云短信发送异常: %s", str(e))
        return False, ""


def _send_sms_tencent(phone: str, code: str) -> tuple[bool, str]:
    try:
        from tencentcloud.common import credential
        from tencentcloud.common.profile.client_profile import ClientProfile
        from tencentcloud.common.profile.http_profile import HttpProfile
        from tencentcloud.sms.v20210111 import sms_client, models as sms_models

        secret_id = os.getenv("SMS_ACCESS_KEY_ID")
        secret_key = os.getenv("SMS_ACCESS_KEY_SECRET")
        app_id = os.getenv("TENCENT_SMS_APP_ID")
        sign_name = os.getenv("SMS_SIGN_NAME", "SubSkin")
        template_id = os.getenv("TENCENT_SMS_TEMPLATE_ID")

        if not all([secret_id, secret_key, app_id, template_id]):
            logger.error("腾讯云短信配置缺失")
            return False, ""

        cred = credential.Credential(secret_id, secret_key)
        http_profile = HttpProfile()
        client_profile = ClientProfile(httpProfile=http_profile)
        client = sms_client.SmsClient(cred, "ap-guangzhou", client_profile)

        request = sms_models.SendSmsRequest(
            SmsSdkAppId=app_id,
            SignName=sign_name,
            TemplateId=template_id,
            TemplateParamSet=[code],
            PhoneNumberSet=[f"+86{phone}"],
        )

        response = client.SendSms(request)

        status = response.SendStatusSet[0]
        if status.Code == "Ok":
            logger.info("腾讯云短信发送成功: %s", phone)
            return True, code
        else:
            logger.error("腾讯云短信发送失败: %s - %s", status.Code, status.Message)
            return False, ""

    except ImportError:
        logger.error("腾讯云SDK未安装，请运行: pip install tencentcloud-sdk-python")
        return False, ""
    except Exception as e:
        logger.error("腾讯云短信发送异常: %s", str(e))
        return False, ""

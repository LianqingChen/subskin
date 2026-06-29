"""
邮箱验证码服务
支持 SMTP 发送及开发模式（仅打印）
"""

import os
import secrets
import logging
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from web.backend.database.models import EmailVerificationCode

logger = logging.getLogger(__name__)


def _mask_email(email: str) -> str:
    """Mask an email for logging: li***@example.com."""
    if not email or "@" not in email:
        return "***"
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        masked_local = local[0] + "***" if local else "***"
    else:
        masked_local = local[:2] + "***"
    return f"{masked_local}@{domain}"


def _utcnow():
    return datetime.now(timezone.utc)


def generate_email_code() -> str:
    return "".join(secrets.choice("0123456789") for _ in range(6))


def check_email_rate_limit(db: Session, email: str) -> None:
    now = _utcnow()
    cooldown_seconds = 60
    daily_limit = 10

    last_sent = (
        db.query(EmailVerificationCode)
        .filter(EmailVerificationCode.email == email)
        .order_by(EmailVerificationCode.created_at.desc())
        .first()
    )

    if last_sent:
        elapsed = (
            now - last_sent.created_at.replace(tzinfo=timezone.utc)
        ).total_seconds()
        if elapsed < cooldown_seconds:
            remaining = cooldown_seconds - int(elapsed)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"请求过于频繁，请等待{remaining}秒后再试",
            )

    midnight = now - timedelta(hours=24)
    recent_count = (
        db.query(EmailVerificationCode)
        .filter(EmailVerificationCode.email == email)
        .filter(EmailVerificationCode.created_at >= midnight)
        .count()
    )

    if recent_count >= daily_limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="今日邮件发送次数已达上限，请明天再试",
        )


def create_email_code(
    db: Session, email: str, purpose: str = "login", expire_minutes: int = 10
) -> str:
    check_email_rate_limit(db, email)

    old_codes = (
        db.query(EmailVerificationCode)
        .filter(EmailVerificationCode.email == email)
        .filter(EmailVerificationCode.used == False)
        .all()
    )
    for code in old_codes:
        code.used = True
    db.commit()

    code = generate_email_code()
    expired_at = _utcnow() + timedelta(minutes=expire_minutes)
    record = EmailVerificationCode(
        email=email, code=code, purpose=purpose, expired_at=expired_at
    )
    db.add(record)
    db.commit()
    return code


def verify_email_code(
    db: Session, email: str, code: str, purpose: str = "login"
) -> bool:
    now = _utcnow()

    record = (
        db.query(EmailVerificationCode)
        .filter(EmailVerificationCode.email == email)
        .filter(EmailVerificationCode.code == code)
        .filter(EmailVerificationCode.purpose == purpose)
        .filter(EmailVerificationCode.used == False)
        .filter(EmailVerificationCode.expired_at > now)
        .first()
    )

    if record:
        if record.locked:
            logger.warning("邮箱验证码已锁定，拒绝验证: email=%s", _mask_email(email))
            return False

        record.used = True
        db.commit()
        logger.info("邮箱验证码验证成功: email=%s", _mask_email(email))
        return True

    active_code = (
        db.query(EmailVerificationCode)
        .filter(EmailVerificationCode.email == email)
        .filter(EmailVerificationCode.purpose == purpose)
        .filter(EmailVerificationCode.used == False)
        .filter(EmailVerificationCode.expired_at > now)
        .first()
    )

    if active_code:
        active_code.attempt_count = (active_code.attempt_count or 0) + 1
        if active_code.attempt_count >= 5:
            active_code.locked = True
            logger.warning(
                "邮箱验证码已锁定: email=%s, attempts=%d",
                _mask_email(email),
                active_code.attempt_count,
            )
        db.commit()

    return False


def send_email_code(to_email: str, code: str, purpose: str = "login") -> bool:
    email_provider = os.getenv("EMAIL_PROVIDER", "log")

    if email_provider == "log":
        logger.info("[EMAIL] %s 验证码(开发模式): %s (用途: %s)", _mask_email(to_email), code, purpose)
        return True

    if email_provider == "smtp":
        return _send_via_smtp(to_email, code, purpose)

    logger.warning("未知的邮件服务商: %s", email_provider)
    return False


def _send_via_smtp(to_email: str, code: str, purpose: str) -> bool:
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    smtp_host = os.getenv("SMTP_HOST", "smtp.qq.com")
    smtp_port = int(os.getenv("SMTP_PORT", "465"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    smtp_from = os.getenv("SMTP_FROM", smtp_user)

    if not all([smtp_user, smtp_password]):
        logger.error("SMTP 配置缺失")
        return False

    purpose_labels = {"login": "登录", "register": "注册", "reset": "重置密码"}
    purpose_label = purpose_labels.get(purpose, "验证")

    subject = f"SubSkin {purpose_label}验证码"
    html_body = f"""
    <div style="max-width:600px;margin:0 auto;font-family:sans-serif;">
        <div style="background:#10b981;padding:20px;text-align:center;border-radius:8px 8px 0 0;">
            <h1 style="color:#fff;margin:0;">SubSkin</h1>
        </div>
        <div style="padding:30px;background:#f9fafb;border-radius:0 0 8px 8px;">
            <p>您好，</p>
            <p>您的{purpose_label}验证码是：</p>
            <div style="font-size:32px;font-weight:bold;text-align:center;
                        color:#10b981;padding:16px;background:#ecfdf5;
                        border-radius:8px;letter-spacing:6px;">
                {code}
            </div>
            <p style="color:#9ca3af;font-size:14px;">验证码10分钟内有效，请勿泄露。</p>
            <p style="color:#9ca3af;font-size:12px;">如果您没有请求此验证码，请忽略此邮件。</p>
        </div>
        <div style="text-align:center;padding:16px;color:#9ca3af;font-size:12px;">
            SubSkin - 用AI缩短医学前沿与白友之间的知识鸿沟
        </div>
    </div>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = smtp_from
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port)
            server.starttls()

        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_from, [to_email], msg.as_string())
        server.quit()
        logger.info("邮件发送成功: %s", to_email)
        return True
    except Exception as e:
        logger.error("邮件发送失败: %s, 错误: %s", to_email, str(e))
        return False

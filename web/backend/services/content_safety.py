"""
内容安全检测服务 — 基于 LLM 的风控判定
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from openai import OpenAI
from sqlalchemy.orm import Session

from web.backend.database.database import get_db
from web.backend.utils.llm_config import get_llm_config
from web.backend.database.models import (
    ContentModeration,
    Post,
    PostComment,
    User,
    UserNotification,
    UserViolation,
    UserViolationLog,
)

logger = logging.getLogger(__name__)

RISK_CATEGORIES = [
    "涉政", "暴恐", "色情", "赌博", "诈骗", "毒品", "枪支",
    "自残教唆", "辱骂歧视", "人身攻击", "引流广告", "违反公序良俗",
]

SAFETY_PROMPT = """你是内容安全审核员。请判断以下用户发布的内容是否包含风险。

风险类别：涉政、暴恐、色情、赌博、诈骗、毒品、枪支、自残教唆、辱骂歧视、人身攻击、引流广告、违反公序良俗

风险等级：
- critical: 严重（涉政、暴恐、色情、违法犯罪）
- high: 高危（诈骗、毒品、枪支、自残教唆）
- medium: 中危（辱骂歧视、人身攻击、引流广告）
- low: 低危（轻微不当言论、疑似擦边）
- safe: 安全

返回JSON格式：
{"risk_level":"safe","risk_categories":[],"reason":"","confidence":0.0}

confidence范围 0.0~1.0，0.0表示完全安全，1.0表示确信违规。

待审核内容：
标题：{title}
正文：{content}"""


def check_content_safety(title: str, content: str) -> dict:
    config = get_llm_config()
    if not config or config.get("provider") == "none":
        logger.warning("No LLM API key configured, skipping content safety check")
        return {"risk_level": "safe", "risk_categories": [], "reason": "未配置LLM，跳过检测", "confidence": 0.0, "skipped": True}

    prompt = SAFETY_PROMPT.format(title=title[:200], content=content[:2000])

    try:
        client = OpenAI(api_key=config["api_key"], base_url=config["base_url"])
        response = client.chat.completions.create(
            model=config["chat_model"],
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=300,
        )
        raw = response.choices[0].message.content.strip()
        # Extract JSON from response (may be wrapped in markdown code block)
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        result = json.loads(raw)
        return {
            "risk_level": result.get("risk_level", "safe"),
            "risk_categories": result.get("risk_categories", []),
            "reason": result.get("reason", ""),
            "confidence": float(result.get("confidence", 0.0)),
        }
    except Exception as e:
        logger.error(f"Content safety check failed: {e}")
        return {"risk_level": "flagged", "risk_categories": ["检测异常"], "reason": f"内容安全检测服务异常，已标记待审: {e}", "confidence": 1.0}


def determine_auto_action(risk_level: str, confidence: float) -> str:
    if risk_level == "flagged":
        return "flagged"
    if risk_level == "critical" and confidence >= 0.6:
        return "blocked"
    if risk_level == "high" and confidence >= 0.6:
        return "blocked"
    if risk_level == "medium" and confidence >= 0.6:
        return "blocked"
    if risk_level == "low" and confidence >= 0.5:
        return "flagged"
    return "flagged"


def moderate_post(post_id: int):
    db_gen = get_db()
    db: Session = next(db_gen)
    try:
        post = db.query(Post).filter(Post.id == post_id).first()
        if not post:
            return

        title = post.title or ""
        content = post.content_text or post.content or ""

        result = check_content_safety(title, content)
        risk_level = result["risk_level"]

        if risk_level == "safe":
            return

        auto_action = determine_auto_action(risk_level, result["confidence"])

        moderation = ContentModeration(
            post_id=post_id,
            user_id=post.user_id,
            content_type="post",
            content_snapshot=f"{title}\n\n{content[:500]}",
            risk_level=risk_level,
            risk_categories=result["risk_categories"],
            auto_action=auto_action,
            ai_reason=result["reason"],
            ai_confidence=result["confidence"],
            status="pending",
        )
        db.add(moderation)

        if auto_action == "blocked":
            post.moderation_status = "blocked"
            _apply_auto_penalty(db, post.user_id, risk_level, moderation.id)

        db.commit()
    except Exception as e:
        logger.error(f"Moderate post {post_id} failed: {e}")
        db.rollback()
    finally:
        db_gen.close()


def moderate_profile_field(user_id: int, field_name: str, field_value: str):
    db_gen = get_db()
    db: Session = next(db_gen)
    try:
        result = check_content_safety(field_name, field_value)
        risk_level = result["risk_level"]

        if risk_level == "safe":
            return

        auto_action = determine_auto_action(risk_level, result["confidence"])

        moderation = ContentModeration(
            user_id=user_id,
            content_type="profile",
            content_snapshot=f"[{field_name}] {field_value[:200]}",
            risk_level=risk_level,
            risk_categories=result["risk_categories"],
            auto_action=auto_action,
            ai_reason=result["reason"],
            ai_confidence=result["confidence"],
            status="pending",
        )
        db.add(moderation)

        if auto_action == "blocked":
            user = db.query(User).filter(User.id == user_id).first()
            if user and field_name == "username":
                user.username = f"用户{user_id}"
            elif user and field_name in ("avatar", "avatar_url"):
                user.avatar_url = None

            _apply_auto_penalty(db, user_id, risk_level, moderation.id)

        db.commit()
    except Exception as e:
        logger.error(f"Moderate profile for user {user_id} failed: {e}")
        db.rollback()
    finally:
        db_gen.close()


def moderate_comment(comment_id: int, content: str, user_id: int):
    db_gen = get_db()
    db: Session = next(db_gen)
    try:
        result = check_content_safety("", content)
        risk_level = result["risk_level"]

        if risk_level == "safe":
            return

        auto_action = determine_auto_action(risk_level, result["confidence"])

        moderation = ContentModeration(
            user_id=user_id,
            content_type="comment",
            content_snapshot=content[:500],
            risk_level=risk_level,
            risk_categories=result["risk_categories"],
            auto_action=auto_action,
            ai_reason=result["reason"],
            ai_confidence=result["confidence"],
            status="pending",
        )
        db.add(moderation)

        if auto_action == "blocked":
            comment = db.query(PostComment).filter(PostComment.id == comment_id).first()
            if comment:
                comment.content = "[该评论因违规已被屏蔽]"
            _apply_auto_penalty(db, user_id, risk_level, moderation.id)

        db.commit()
    except Exception as e:
        logger.error(f"Moderate comment {comment_id} failed: {e}")
        db.rollback()
    finally:
        db_gen.close()


def _apply_auto_penalty(db: Session, user_id: int, risk_level: str, moderation_id: int):
    violation = db.query(UserViolation).filter(UserViolation.user_id == user_id).first()
    if not violation:
        violation = UserViolation(user_id=user_id)
        db.add(violation)
        db.flush()

    if risk_level == "critical":
        violation.critical_count += 1
        if violation.critical_count >= 1:
            _ban_user(db, user_id, "触发严重风控规则，自动封号", moderation_id)
            return
    elif risk_level == "high":
        violation.high_count += 1
        if violation.high_count >= 2:
            _mute_user(db, user_id, 720, "累计2次高危违规，禁言30天", moderation_id)
            return
        _mute_user(db, user_id, 168, "高危违规，禁言7天", moderation_id)
        return
    elif risk_level == "medium":
        violation.medium_count += 1
        if violation.medium_count >= 3:
            _mute_user(db, user_id, 168, "累计3次中危违规，禁言7天", moderation_id)
            return
        if violation.medium_count >= 2:
            _mute_user(db, user_id, 72, "累计2次中危违规，禁言3天", moderation_id)
            return
        _warn_user(db, user_id, "中危违规，已发警告", moderation_id)
    else:
        violation.low_count += 1
        _warn_user(db, user_id, "低危违规，已发警告", moderation_id)

    violation.violation_count = (
        violation.critical_count + violation.high_count
        + violation.medium_count + violation.low_count
    )
    _sync_user_status(db, user_id, violation)


def _warn_user(db: Session, user_id: int, reason: str, moderation_id: int):
    db.add(UserViolationLog(
        user_id=user_id, moderation_id=moderation_id,
        action="warn", reason=reason,
    ))
    _create_notification(db, user_id, "moderation_warning", "社区规范提醒", reason, moderation_id)
    _try_send_sms_with_cooldown(db, user_id, f"【SubSkin】您发布的内容因违反社区规范已收到警告，请遵守社区行为规范。详情请查看App内通知。")


def _mute_user(db: Session, user_id: int, hours: int, reason: str, moderation_id: int):
    violation = db.query(UserViolation).filter(UserViolation.user_id == user_id).first()
    if violation:
        violation.status = "muted"
        violation.muted_until = datetime.now(timezone.utc) + __import__("datetime").timedelta(hours=hours)
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        user.user_status = "muted"
        user.muted_until = violation.muted_until if violation else None
        user.violation_count = (user.violation_count or 0) + 1

    db.add(UserViolationLog(
        user_id=user_id, moderation_id=moderation_id,
        action="mute", duration_hours=hours, reason=reason,
    ))
    _create_notification(db, user_id, "mute", "账号禁言通知", f"您因违反社区规范已被禁言{hours}小时。原因：{reason}", moderation_id)
    _try_send_sms_with_cooldown(db, user_id, f"【SubSkin】您因违反社区规范已被禁言{hours}小时，详情请查看App内通知。")


def _ban_user(db: Session, user_id: int, reason: str, moderation_id: int):
    violation = db.query(UserViolation).filter(UserViolation.user_id == user_id).first()
    if violation:
        violation.status = "banned"
        violation.banned_at = datetime.now(timezone.utc)
        violation.ban_reason = reason
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        user.user_status = "banned"
        user.banned_at = datetime.now(timezone.utc)
        user.ban_reason = reason
        user.is_active = False
        user.violation_count = (user.violation_count or 0) + 1

    db.add(UserViolationLog(
        user_id=user_id, moderation_id=moderation_id,
        action="ban", reason=reason,
    ))
    _create_notification(db, user_id, "ban", "账号封禁通知", f"您因严重违反社区规范，账号已被永久封禁。原因：{reason}", moderation_id)
    _try_send_sms_with_cooldown(db, user_id, f"【SubSkin】您因严重违反社区规范，账号已被封禁。如有异议请邮件联系 lianqing_chan@126.com 申诉。")


def _sync_user_status(db: Session, user_id: int, violation: UserViolation):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return
    user.user_status = violation.status
    user.muted_until = violation.muted_until
    user.banned_at = violation.banned_at
    user.ban_reason = violation.ban_reason
    user.violation_count = violation.violation_count
    user.critical_count = violation.critical_count
    user.warning_count = violation.warning_count


def _create_notification(
    db: Session, user_id: int, ntype: str,
    title: str, content: str, related_id: Optional[int] = None,
):
    db.add(UserNotification(
        user_id=user_id, type=ntype, title=title,
        content=content, related_id=related_id,
    ))


def _try_send_sms_with_cooldown(db: Session, user_id: int, message: str, cooldown_hours: int = 1):
    """Send SMS with per-user cooldown to prevent abuse during batch violations."""
    one_hour_ago = datetime.now(timezone.utc).replace(microsecond=0) - __import__("datetime").timedelta(hours=cooldown_hours)
    recent_warn = (
        db.query(UserViolationLog)
        .filter(
            UserViolationLog.user_id == user_id,
            UserViolationLog.action.in_(["warn", "mute", "ban"]),
            UserViolationLog.created_at >= one_hour_ago,
        )
        .first()
    )
    if recent_warn:
        logger.info(f"SMS suppressed for user {user_id}: already notified within {cooldown_hours}h")
        return
    _try_send_sms(db, user_id, message)


def _try_send_sms(db: Session, user_id: int, message: str):
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.phone:
        return
    try:
        from web.backend.services.sms import send_sms
        send_sms(user.phone, message)
    except Exception as e:
        logger.error(f"SMS notification failed for user {user_id}: {e}")

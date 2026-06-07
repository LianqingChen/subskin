"""IM 消息风控服务"""

import json
import logging

from web.backend.database.database import get_db
from web.backend.database.models import (
    ImMessage,
    ImMessageModeration,
    UserViolation,
)
from web.backend.utils.llm_config import get_llm_config

logger = logging.getLogger(__name__)

SENSITIVE_WORDS = [
    "赌博", "博彩", "彩票", "六合彩", "时时彩",
    "毒品", "大麻", "海洛因", "冰毒", "摇头丸",
    "枪支", "手枪", "步枪", "弹药",
    "自残", "自杀", "割腕",
    "加微信", "加我微信", "加我VX",
]

IM_SAFETY_PROMPT = """你是医疗社区内容安全审核员。请判断以下私信内容是否违规。

风险类别：涉政、暴恐、色情、赌博、诈骗、毒品、枪支、自残教唆、辱骂歧视、人身攻击、引流广告、违反公序良俗

注意：这是白癜风患者社区，用户间可能讨论病情、交换治疗经验。正常的病情交流、医生推荐不属于"引流广告"。

返回JSON: {{"risk_level":"safe|low|medium|high|critical","risk_categories":[],"reason":"","confidence":0.0}}

待审核内容：
{content}"""


def check_im_message_safety(content: str) -> dict:
    for word in SENSITIVE_WORDS:
        if word in content:
            return {
                "risk_level": "high",
                "risk_categories": ["违规关键词"],
                "reason": f"包含敏感词: {word}",
                "confidence": 0.95,
            }

    config = get_llm_config()
    if not config or config.get("provider") == "none":
        return {
            "risk_level": "safe",
            "risk_categories": [],
            "reason": "",
            "confidence": 0.0,
        }

    try:
        from openai import OpenAI

        client = OpenAI(
            api_key=config["api_key"], base_url=config["base_url"]
        )
        response = client.chat.completions.create(
            model=config["chat_model"],
            messages=[
                {
                    "role": "user",
                    "content": IM_SAFETY_PROMPT.format(
                        content=content[:2000]
                    ),
                }
            ],
            temperature=0.1,
            max_tokens=300,
        )
        raw = response.choices[0].message.content.strip()
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        return json.loads(raw)
    except Exception as e:
        logger.error(f"IM safety check failed: {e}")
        return {
            "risk_level": "safe",
            "risk_categories": [],
            "reason": "",
            "confidence": 0.0,
        }


def moderate_im_message(message_id: int):
    db_gen = get_db()
    db = next(db_gen)
    try:
        msg = (
            db.query(ImMessage)
            .filter(ImMessage.id == message_id)
            .first()
        )
        if not msg or not msg.content:
            return

        result = check_im_message_safety(msg.content)
        if result["risk_level"] == "safe":
            return

        moderation = ImMessageModeration(
            message_id=message_id,
            sender_id=msg.sender_id,
            content_snapshot=msg.content[:500],
            risk_level=result["risk_level"],
            risk_categories=result.get("risk_categories", []),
            auto_action=(
                "blocked"
                if result["risk_level"] in ("critical", "high")
                else "flagged"
            ),
            ai_reason=result.get("reason", ""),
            ai_confidence=result.get("confidence", 0.0),
        )
        db.add(moderation)

        if result["risk_level"] in ("critical", "high"):
            msg.content = "[该消息因违规已被屏蔽]"
            violation = (
                db.query(UserViolation)
                .filter(UserViolation.user_id == msg.sender_id)
                .first()
            )
            if not violation:
                violation = UserViolation(user_id=msg.sender_id)
                db.add(violation)
                db.flush()
            if result["risk_level"] == "critical":
                violation.critical_count += 1
            else:
                violation.high_count += 1
            violation.violation_count = (
                violation.critical_count + violation.high_count
            )

        db.commit()
    except Exception as e:
        logger.error(f"IM message moderation failed: {e}")
        db.rollback()
    finally:
        db_gen.close()

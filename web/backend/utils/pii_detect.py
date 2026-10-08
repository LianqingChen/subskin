"""PII（个人身份信息）检测与脱敏（2026-08-30 隐私加固统一入口）。

用于用户公开发布场景（社区帖子、评论、分享到社区的报告等）：
- ``detect_pii``   返回命中的 PII 类型列表；
- ``redact_pii``   对文本中的手机号/邮箱/身份证/银行卡做掩码替换。

原则：公开内容命中 PII 时默认自动脱敏并提醒用户；
只有用户显式确认（confirm_pii）后才保留原文。
"""

import re
from typing import Dict, List, Tuple

# 手机号：1[3-9] 开头 11 位（前后不能是数字，避免误伤长数字串）
_PHONE_RE = re.compile(r"(?<!\d)(1[3-9]\d{9})(?!\d)")
# 邮箱
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# 身份证 18 位（含末位 X）
_ID_CARD_RE = re.compile(r"(?<!\d)(\d{17}[\dXx])(?!\d)")
# 银行卡：15-19 位连续数字（排除前面已是身份证/手机号场景的误报，见下方实现）
_BANK_CARD_RE = re.compile(r"(?<!\d)(\d{15,19})(?!\d)")

PII_LABELS: Dict[str, str] = {
    "phone": "手机号",
    "email": "邮箱",
    "id_card": "身份证号",
    "bank_card": "银行卡号",
}


def _mask_phone(m: re.Match) -> str:
    s = m.group(1)
    return s[:3] + "****" + s[-4:]


def _mask_email(m: re.Match) -> str:
    s = m.group(0)
    at = s.find("@")
    if at <= 1:
        return "*" + s[at:]
    return s[:1] + "***" + s[at:]


def _mask_id_card(m: re.Match) -> str:
    s = m.group(1)
    return s[:3] + "***********" + s[-2:]


def _mask_bank_card(m: re.Match) -> str:
    s = m.group(1)
    return "*" * (len(s) - 4) + s[-4:]


def detect_pii(text: str) -> List[str]:
    """检测文本中的 PII，返回命中的类型列表（去重，顺序固定）。"""
    if not text:
        return []
    hits: List[str] = []
    if _PHONE_RE.search(text):
        hits.append("phone")
    if _EMAIL_RE.search(text):
        hits.append("email")
    if _ID_CARD_RE.search(text):
        hits.append("id_card")
    # 银行卡检测放在身份证之后，且文本已含身份证/手机号命中时跳过长数字串，
    # 避免同一数字被重复计类
    if not hits and _BANK_CARD_RE.search(text):
        hits.append("bank_card")
    return hits


def pii_hit_labels(text: str) -> List[str]:
    """返回命中的 PII 中文标签列表（用于用户提示）。"""
    return [PII_LABELS[t] for t in detect_pii(text)]


def redact_pii(text: str) -> Tuple[str, List[str]]:
    """脱敏文本中的 PII，返回 (脱敏后文本, 命中类型列表)。"""
    if not text:
        return text, []
    hits = detect_pii(text)
    if not hits:
        return text, []
    result = _ID_CARD_RE.sub(_mask_id_card, text)
    result = _PHONE_RE.sub(_mask_phone, result)
    result = _EMAIL_RE.sub(_mask_email, result)
    if "bank_card" in hits:
        result = _BANK_CARD_RE.sub(_mask_bank_card, result)
    return result, hits

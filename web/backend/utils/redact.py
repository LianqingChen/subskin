"""
数据脱敏工具

按照 AGENTS.md 数据分级规范，对 L3（高敏感）数据进行脱敏处理：
- 手机号：保留前3后4，中间用 **** 填充 → 138****1234
- 邮箱：保留前2字符 + *** @ domain → li***@example.com
- 姓名：保留姓氏，其余用 * 替换 → 张*
- IP地址：仅保留前2组 → 192.168.*.*
"""

from typing import Optional


def mask_phone(phone: Optional[str]) -> Optional[str]:
    if not phone:
        return None
    phone = phone.strip()
    if len(phone) == 11 and phone.startswith("1"):
        return f"{phone[:3]}****{phone[7:]}"
    return f"{phone[:2]}****{phone[-2:]}" if len(phone) >= 4 else "****"


def mask_email(email: Optional[str]) -> Optional[str]:
    if not email:
        return None
    email = email.strip()
    if "@" not in email:
        return "***@***"
    local, domain = email.rsplit("@", 1)
    if len(local) <= 2:
        masked_local = local[0] + "***"
    else:
        masked_local = local[:2] + "***"
    return f"{masked_local}@{domain}"


def mask_name(name: Optional[str]) -> Optional[str]:
    if not name:
        return None
    name = name.strip()
    if len(name) <= 1:
        return name
    return f"{name[0]}{'*' * (len(name) - 1)}"


def mask_ip(ip: Optional[str]) -> Optional[str]:
    if not ip:
        return None
    parts = ip.strip().split(".")
    if len(parts) == 4:
        return f"{parts[0]}.{parts[1]}.*.*"
    return "***.***"


def looks_like_phone(value: Optional[str]) -> bool:
    """判断字符串是否为中国大陆手机号格式（1 开头的 11 位数字）。"""
    if not value:
        return False
    v = value.strip()
    return len(v) == 11 and v.startswith("1") and v.isdigit()


def safe_public_username(username: Optional[str], phone: Optional[str] = None) -> str:
    """返回可安全公开展示的昵称。

    历史注册逻辑曾把手机号直接设为 username，导致 L3 数据通过公开主页、
    评论作者等渠道泄露。此处做防御性脱敏：昵称与手机号一致或呈手机号格式
    时，统一展示为 138****1234 形式。
    """
    if not username:
        return "白友"
    if phone and username.strip() == phone.strip():
        return mask_phone(phone) or "白友"
    if looks_like_phone(username):
        return mask_phone(username.strip()) or "白友"
    return username

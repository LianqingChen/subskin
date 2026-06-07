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

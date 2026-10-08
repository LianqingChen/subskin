"""密码强度策略（2026-08-30 安全加固统一入口）。

所有设置/注册/重置密码的路径必须经过 ``validate_password_strength``。
登录路径不做强度校验（历史弱口令用户仍可登录，但改密时会被强制加强）。
"""

import re
from typing import Optional

MIN_LENGTH = 8

# 常见弱口令黑名单（小写比较）；命中直接拒绝
WEAK_PASSWORDS = {
    "12345678", "123456789", "1234567890", "password", "password1",
    "qwerty123", "11111111", "88888888", "66666666", "00000000",
    "abc12345", "abcd1234", "a1234567", "subskin123", "admin123",
    "iloveyou1", "sunshine1", "letmein123", "welcome123", "1qaz2wsx",
}


def validate_password_strength(password: str) -> Optional[str]:
    """校验密码强度；返回错误信息（不合规）或 None（合规）。"""
    if not isinstance(password, str) or len(password) < MIN_LENGTH:
        return f"密码至少需要 {MIN_LENGTH} 位字符"
    if len(password) > 128:
        return "密码过长（最多 128 位）"
    if password.isdigit():
        return "密码不能为纯数字"
    if password.lower() in WEAK_PASSWORDS:
        return "密码过于简单，请更换更复杂的密码"
    # 至少包含字母和数字（允许符号）
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        return "密码需同时包含字母和数字"
    return None

"""真实客户端 IP 解析。

应用经 nginx 反向代理部署，``request.client.host`` 恒为 127.0.0.1。
访客配额、IP 限速等场景必须解析代理头获取真实客户端 IP。

信任顺序（防伪造）：
1. ``X-Real-IP`` — 由我方 nginx 以 ``$remote_addr`` 覆盖写入，客户端无法伪造；
2. ``X-Forwarded-For`` **最后一个**合法地址 — nginx 以追加模式（``$proxy_add_x_forwarded_for``）
   写入，末位恒为真实连接 IP；取首值会被客户端自带的 XFF 头伪造，禁止；
3. 回退 socket 对端地址。
"""

import ipaddress
from typing import Optional

from fastapi import Request


def _first_valid_ip(raw: Optional[str]) -> Optional[str]:
    """从逗号分隔的 IP 列表中取第一个可解析的合法 IP。"""
    if not raw:
        return None
    for part in raw.split(","):
        candidate = part.strip()
        if not candidate:
            continue
        try:
            return str(ipaddress.ip_address(candidate))
        except ValueError:
            continue
    return None


def _last_valid_ip(raw: Optional[str]) -> Optional[str]:
    """从逗号分隔的 IP 列表中取最后一个可解析的合法 IP（nginx 追加的真实来源）。"""
    if not raw:
        return None
    for part in reversed(raw.split(",")):
        candidate = part.strip()
        if not candidate:
            continue
        try:
            return str(ipaddress.ip_address(candidate))
        except ValueError:
            continue
    return None


def get_real_client_ip(request: Request) -> str:
    """获取真实客户端 IP（nginx 反代感知），无法解析时回退 socket 对端。"""
    ip = _first_valid_ip(request.headers.get("x-real-ip"))
    if ip:
        return ip
    ip = _last_valid_ip(request.headers.get("x-forwarded-for"))
    if ip:
        return ip
    if request.client and request.client.host:
        return request.client.host
    return "unknown"

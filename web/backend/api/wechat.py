import hashlib
import os
import time
import secrets
from typing import Optional

import requests
from fastapi import APIRouter, Query, HTTPException, status
from pydantic import BaseModel

router = APIRouter()

_cached_ticket: Optional[str] = None
_ticket_expires_at: float = 0


class JSSDKConfig(BaseModel):
    appId: str
    timestamp: int
    nonceStr: str
    signature: str


def _get_access_token() -> str:
    app_id = os.getenv("WECHAT_APP_ID", "")
    app_secret = os.getenv("WECHAT_APP_SECRET", "")
    if not app_id or not app_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="微信配置缺失 (WECHAT_APP_ID / WECHAT_APP_SECRET)",
        )
    url = "https://api.weixin.qq.com/cgi-bin/token"
    resp = requests.get(url, params={
        "grant_type": "client_credential",
        "appid": app_id,
        "secret": app_secret,
    }, timeout=10)
    data = resp.json()
    if "access_token" not in data:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"获取微信access_token失败: {data.get('errmsg', 'unknown')}",
        )
    return data["access_token"]


def _get_jsapi_ticket() -> str:
    global _cached_ticket, _ticket_expires_at
    if _cached_ticket and time.time() < _ticket_expires_at:
        return _cached_ticket

    access_token = _get_access_token()
    url = "https://api.weixin.qq.com/cgi-bin/ticket/getticket"
    resp = requests.get(url, params={
        "access_token": access_token,
        "type": "jsapi",
    }, timeout=10)
    data = resp.json()
    if data.get("errcode") != 0:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"获取jsapi_ticket失败: {data.get('errmsg', 'unknown')}",
        )

    _cached_ticket = data["ticket"]
    _ticket_expires_at = time.time() + data.get("expires_in", 7200) - 300
    return _cached_ticket


def _sign(ticket: str, nonce_str: str, timestamp: int, url: str) -> str:
    raw = f"jsapi_ticket={ticket}&noncestr={nonce_str}&timestamp={timestamp}&url={url}"
    return hashlib.sha1(raw.encode()).hexdigest()


@router.get("/jssdk-config", response_model=JSSDKConfig)
async def get_jssdk_config(url: str = Query(..., description="当前页面完整URL")):
    app_id = os.getenv("WECHAT_APP_ID", "")
    if not app_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="WECHAT_APP_ID 未配置",
        )
    ticket = _get_jsapi_ticket()
    nonce_str = secrets.token_urlsafe(16)
    timestamp = int(time.time())
    signature = _sign(ticket, nonce_str, timestamp, url)
    return JSSDKConfig(
        appId=app_id,
        timestamp=timestamp,
        nonceStr=nonce_str,
        signature=signature,
    )

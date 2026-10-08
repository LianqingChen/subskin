"""集中式时间序列化工具。

后端数据库统一以 UTC 存储时间（models._utcnow = datetime.now(timezone.utc)，
SQLite DateTime 列读回时为 naive datetime）。若序列化输出不带时区后缀
（如 2026-08-04T13:37:14），前端 new Date() 会按浏览器本地时区解析，
导致全站时间出现 8 小时偏移。

因此所有对外序列化的 datetime 必须带 +00:00 后缀：
- ``iso_utc()``：手动序列化时使用（替代 ``dt.isoformat()``）；
- ``patch_datetime_serialization()``：app 启动时调用，集中覆盖
  FastAPI jsonable_encoder 与 Pydantic v2 response_model 两条序列化路径。

注意：date 类型（如日记 entry_date、VASI 日期）不受影响，仍输出 YYYY-MM-DD。
"""

import re
from datetime import date, datetime, timezone
from typing import Any, Optional, Union

# 无时区后缀的 ISO datetime 字符串（可能带小数秒）
_NAIVE_ISO_DATETIME_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?$"
)


def iso_utc(dt: Optional[Union[date, datetime]]) -> Optional[str]:
    """将 datetime 序列化为带 +00:00 后缀的 ISO 字符串。

    - None → None；
    - date（非 datetime）→ 原样 isoformat（YYYY-MM-DD）；
    - naive datetime → 按 UTC 对待，补 +00:00；
    - aware datetime → 换算为 UTC 后输出。
    """
    if dt is None:
        return None
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    return dt.isoformat()


def _ensure_utc_suffix(value: Any) -> Any:
    """递归扫描已序列化结构，为 naive ISO datetime 字符串补 +00:00。"""
    if isinstance(value, str):
        if _NAIVE_ISO_DATETIME_RE.match(value):
            return value + "+00:00"
        return value
    if isinstance(value, dict):
        return {k: _ensure_utc_suffix(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_ensure_utc_suffix(v) for v in value]
    if isinstance(value, tuple):
        return tuple(_ensure_utc_suffix(v) for v in value)
    return value


def _utc_isoformat(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


_PATCHED = False


def patch_datetime_serialization() -> None:
    """在 app 层集中为所有 datetime 序列化补 UTC 后缀（幂等）。

    覆盖两条路径：
    1. FastAPI ``jsonable_encoder``（返回 dict/手动构造响应的端点）；
    2. Pydantic v2 response_model 序列化（FastAPI ModelField.serialize）。
    """
    global _PATCHED
    if _PATCHED:
        return
    _PATCHED = True

    # 路径 1：jsonable_encoder 的精确类型编码表
    from fastapi import encoders as _fastapi_encoders

    _fastapi_encoders.ENCODERS_BY_TYPE[datetime] = _utc_isoformat

    # 路径 2：Pydantic v2 response_model（dump_python(mode="json") 对 naive
    # datetime 输出无后缀字符串），在序列化结果上补后缀
    try:
        from fastapi._compat.v2 import ModelField as _PydanticV2ModelField
    except Exception:  # pragma: no cover - fastapi 版本结构变化时降级
        return

    original_serialize = _PydanticV2ModelField.serialize

    def serialize_with_utc_suffix(self, value, **kwargs):
        result = original_serialize(self, value, **kwargs)
        return _ensure_utc_suffix(result)

    _PydanticV2ModelField.serialize = serialize_with_utc_suffix

"""简易令牌桶限速器 — 进程内存储，服务重启后清空。"""

import time
from collections import defaultdict
from typing import Optional

from fastapi import Request, HTTPException, status


class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._buckets: dict[str, list[float]] = defaultdict(list)

    def _clean(self, key: str) -> None:
        now = time.time()
        cutoff = now - self.window_seconds
        self._buckets[key] = [t for t in self._buckets[key] if t > cutoff]

    def is_allowed(self, key: str) -> bool:
        self._clean(key)
        return len(self._buckets[key]) < self.max_requests

    def hit(self, key: str) -> None:
        self._buckets[key].append(time.time())


# 社区读接口: 60次/分钟/IP
read_limiter = RateLimiter(max_requests=60, window_seconds=60)
# 社区写接口: 10次/分钟/用户 (or IP fallback)
write_limiter = RateLimiter(max_requests=10, window_seconds=60)


class ReadRateLimit:
    """FastAPI dependency: rate-limit by client IP."""

    async def __call__(self, request: Request) -> None:
        ip = request.client.host if request.client else "unknown"
        key = f"ip:{ip}"
        if not read_limiter.is_allowed(key):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="请求过于频繁，请稍后再试",
            )
        read_limiter.hit(key)


class WriteRateLimit:
    """FastAPI dependency: rate-limit by user ID, fallback to IP."""

    async def __call__(self, request: Request) -> None:
        # Try to get user_id from request state (set by auth middleware)
        user_id = getattr(request.state, "user_id", None)
        key = f"user:{user_id}" if user_id else f"ip:{request.client.host if request.client else 'unknown'}"
        if not write_limiter.is_allowed(key):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="操作过于频繁，请稍后再试",
            )
        write_limiter.hit(key)


async def limit_write_for_user(request: Request, user_id: Optional[int]) -> None:
    """Write rate limit with explicit user_id (use inside endpoint body)."""
    key = f"user:{user_id}" if user_id else f"ip:{request.client.host if request.client else 'unknown'}"
    if not write_limiter.is_allowed(key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="操作过于频繁，请稍后再试",
        )
    write_limiter.hit(key)

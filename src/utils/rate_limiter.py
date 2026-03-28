"""Thread-safe token bucket rate limiter utility."""

from __future__ import annotations

import time
from threading import Lock
from typing import Literal


class RateLimiter:
    """Rate limiter based on the token bucket algorithm.

    The limiter starts empty and refills tokens over time at the configured
    rate. Each call to :meth:`acquire` blocks until one token is available.

    Args:
        requests_per_second: Maximum number of requests allowed per second.

    Raises:
        ValueError: If ``requests_per_second`` is not positive.
    """

    def __init__(self, requests_per_second: float) -> None:
        if requests_per_second <= 0:
            raise ValueError("requests_per_second must be positive")

        self._rate = float(requests_per_second)
        self._capacity = float(requests_per_second)
        self._tokens = 0.0
        self._last_refill = time.monotonic()
        self._lock = Lock()

    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        if elapsed <= 0:
            return

        self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
        self._last_refill = now

    def acquire(self) -> None:
        """Block until a token is available and then consume it."""
        while True:
            wait_time = 0.0

            with self._lock:
                self._refill()
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return

                tokens_needed = 1.0 - self._tokens
                wait_time = tokens_needed / self._rate

            time.sleep(wait_time)

    def __enter__(self) -> RateLimiter:
        """Enter the context manager after acquiring one token."""
        self.acquire()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: object | None,
    ) -> Literal[False]:
        """Exit the context manager.

        Args:
            exc_type: Exception type, if raised inside the context.
            exc_value: Exception instance, if raised inside the context.
            traceback: Traceback, if an exception was raised.

        Returns:
            False to propagate any exception raised inside the context.
        """
        return False

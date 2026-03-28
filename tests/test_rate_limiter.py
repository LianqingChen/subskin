"""Tests for the rate limiter utility."""

from __future__ import annotations

import threading
import time

from src.utils.rate_limiter import RateLimiter


def test_rate_limiter_three_requests_per_second() -> None:
    """Three requests at 3 req/s should take about one second."""
    limiter = RateLimiter(3)

    start = time.monotonic()
    for _ in range(3):
        limiter.acquire()
    elapsed = time.monotonic() - start

    assert 0.9 <= elapsed <= 1.4


def test_rate_limiter_ten_requests_per_second() -> None:
    """Ten requests at 10 req/s should take about one second."""
    limiter = RateLimiter(10)

    start = time.monotonic()
    for _ in range(10):
        limiter.acquire()
    elapsed = time.monotonic() - start

    assert 0.9 <= elapsed <= 1.4


def test_rate_limiter_one_thousand_requests_per_second() -> None:
    """A burst at 1000 req/s should stay close to the expected duration."""
    limiter = RateLimiter(1000)

    start = time.monotonic()
    for _ in range(100):
        limiter.acquire()
    elapsed = time.monotonic() - start

    assert elapsed < 0.2


def test_rate_limiter_thread_safety() -> None:
    """Concurrent acquires should be safe and account for every request."""
    limiter = RateLimiter(1000)
    total_acquires = 200
    threads = 10
    acquires_per_thread = total_acquires // threads
    completed = 0
    completed_lock = threading.Lock()

    def worker() -> None:
        nonlocal completed
        for _ in range(acquires_per_thread):
            limiter.acquire()
            with completed_lock:
                completed += 1

    thread_list = [threading.Thread(target=worker) for _ in range(threads)]
    start = time.monotonic()
    for thread in thread_list:
        thread.start()
    for thread in thread_list:
        thread.join()
    elapsed = time.monotonic() - start

    assert completed == total_acquires
    assert elapsed < 0.5


def test_rate_limiter_context_manager() -> None:
    """The limiter should support use as a context manager."""
    limiter = RateLimiter(10)

    with limiter:
        acquired_inside_context = True

    assert acquired_inside_context is True

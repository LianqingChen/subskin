"""Tests for the SQLite-backed cache utility."""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

from src.utils.cache import Cache


def test_cache_hit_and_miss() -> None:
    """Cache should return stored values and None for missing keys."""
    cache = Cache()

    cache.set("key1", "value1", ttl=60)

    assert cache.get("key1") == "value1"
    assert cache.get("nonexistent") is None


def test_ttl_expiration() -> None:
    """Cache entries should expire after their TTL."""
    cache = Cache()

    cache.set("key1", "value1", ttl=1)
    time.sleep(2)

    assert cache.get("key1") is None


def test_cache_invalidation_delete_and_clear() -> None:
    """Cache delete and clear operations should invalidate entries."""
    cache = Cache()

    cache.set("key1", "value1", ttl=60)
    cache.set("key2", "value2", ttl=60)

    cache.delete("key1")
    assert cache.get("key1") is None
    assert cache.get("key2") == "value2"

    cache.clear()
    assert cache.get("key2") is None


def test_thread_safety() -> None:
    """Concurrent access should not corrupt cache state."""
    cache = Cache()
    start_event = threading.Event()

    def worker(index: int) -> tuple[str, str | None]:
        key = f"key-{index}"
        value = f"value-{index}"
        start_event.wait()
        cache.set(key, value, ttl=60)
        return key, cache.get(key)

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(worker, index) for index in range(20)]
        start_event.set()
        results = [future.result() for future in futures]

    assert all(value == f"value-{index}" for index, (_, value) in enumerate(results))
    for index in range(20):
        assert cache.get(f"key-{index}") == f"value-{index}"

"""SQLite-backed cache utility for API responses.

This module provides a lightweight, thread-safe cache with TTL support.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any


class Cache:
    """Thread-safe SQLite cache with TTL and invalidation.

    The cache stores JSON-serializable values in SQLite and automatically removes
    expired entries when they are accessed.
    """

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        """Initialize the cache.

        Args:
            db_path: SQLite database path. Defaults to an in-memory database.
        """
        self._db_path = str(db_path)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._initialize_schema()

    def _initialize_schema(self) -> None:
        """Create the cache table if it does not exist."""
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cache_entries (
                    cache_key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    ttl REAL,
                    expires_at REAL
                )
                """
            )

    def _now(self) -> float:
        """Return the current time as a UNIX timestamp."""
        return time.time()

    def _cleanup_expired_locked(self) -> None:
        """Remove expired entries.

        This method must be called while holding ``self._lock``.
        """
        current_time = self._now()
        with self._conn:
            self._conn.execute(
                "DELETE FROM cache_entries WHERE expires_at IS NOT NULL AND expires_at <= ?",
                (current_time,),
            )

    def set(self, key: str, value: Any, ttl: float | None) -> None:
        """Store a value in the cache.

        Args:
            key: Cache key.
            value: JSON-serializable value to store.
            ttl: Time-to-live in seconds. ``None`` means no expiration.
        """
        serialized_value = json.dumps(value)
        created_at = self._now()
        expires_at = created_at + ttl if ttl is not None else None

        with self._lock:
            self._cleanup_expired_locked()
            with self._conn:
                self._conn.execute(
                    """
                    INSERT INTO cache_entries (cache_key, value, created_at, ttl, expires_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(cache_key) DO UPDATE SET
                        value = excluded.value,
                        created_at = excluded.created_at,
                        ttl = excluded.ttl,
                        expires_at = excluded.expires_at
                    """,
                    (key, serialized_value, created_at, ttl, expires_at),
                )

    def get(self, key: str) -> Any | None:
        """Retrieve a cached value.

        Args:
            key: Cache key.

        Returns:
            The cached value, or ``None`` if the key is missing or expired.
        """
        with self._lock:
            self._cleanup_expired_locked()
            cursor = self._conn.execute(
                "SELECT value FROM cache_entries WHERE cache_key = ?",
                (key,),
            )
            row = cursor.fetchone()

            if row is None:
                return None

            return json.loads(row["value"])

    def delete(self, key: str) -> None:
        """Remove a cached value.

        Args:
            key: Cache key to remove.
        """
        with self._lock:
            with self._conn:
                self._conn.execute(
                    "DELETE FROM cache_entries WHERE cache_key = ?",
                    (key,),
                )

    def clear(self) -> None:
        """Remove all cached values."""
        with self._lock:
            with self._conn:
                self._conn.execute("DELETE FROM cache_entries")

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        with self._lock:
            self._conn.close()

    def __enter__(self) -> Cache:
        """Return the cache instance for context manager usage."""
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        """Close the cache when leaving a context manager."""
        self.close()

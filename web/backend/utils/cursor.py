"""Cursor-based pagination helpers.

Format: base64(timestamp_ms:post_id)
- timestamp_ms: UTC timestamp in milliseconds
- post_id: integer post ID

The cursor is opaque to the client — it's just passed back as the `after` parameter.
"""

import base64
import time
from datetime import datetime, timezone
from typing import Optional, Tuple


def encode_cursor(created_at: datetime, post_id: int) -> str:
    """Encode a post's created_at + id into an opaque cursor string."""
    ts_ms = int(created_at.replace(tzinfo=timezone.utc).timestamp() * 1000)
    raw = f"{ts_ms}:{post_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def decode_cursor(cursor: str) -> Optional[Tuple[datetime, int]]:
    """Decode a cursor string back to (created_at, post_id). Returns None if invalid."""
    try:
        # Add padding back
        padding = 4 - len(cursor) % 4
        if padding != 4:
            cursor += "=" * padding
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        ts_ms_str, post_id_str = raw.rsplit(":", 1)
        ts = datetime.fromtimestamp(int(ts_ms_str) / 1000, tz=timezone.utc)
        return ts, int(post_id_str)
    except Exception:
        return None


def encode_cursor_from_post(post) -> str:
    """Encode a cursor from a Post ORM object."""
    return encode_cursor(post.created_at, post.id)

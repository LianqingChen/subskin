import asyncio
import logging
import os
import time
from pathlib import Path
from typing import Optional


logger = logging.getLogger(__name__)

TEMP_UPLOAD_MAX_AGE_SECONDS = 24 * 60 * 60
TEMP_CLEANUP_INTERVAL_SECONDS = 60 * 60


def cleanup_temp_uploads(
    temp_dir: Optional[Path] = None,
    max_age_seconds: int = TEMP_UPLOAD_MAX_AGE_SECONDS,
) -> int:
    directory = temp_dir or Path("data/uploads/temp")
    if not directory.exists():
        return 0

    cutoff_timestamp = time.time() - max_age_seconds
    deleted_count = 0

    for path in directory.rglob("*"):
        if not path.is_file():
            continue

        try:
            modified_at = os.path.getmtime(path)
        except OSError:
            continue

        if modified_at >= cutoff_timestamp:
            continue

        try:
            path.unlink()
            deleted_count += 1
        except OSError:
            logger.warning("Failed to delete stale temp upload: %s", path)

    for path in sorted(directory.rglob("*"), reverse=True):
        if not path.is_dir():
            continue
        try:
            path.rmdir()
        except OSError:
            continue

    return deleted_count


async def run_temp_cleanup_loop(
    interval_seconds: int = TEMP_CLEANUP_INTERVAL_SECONDS,
) -> None:
    while True:
        deleted_count = cleanup_temp_uploads()
        if deleted_count:
            logger.info("Deleted %s stale temp uploads", deleted_count)
        try:
            await asyncio.sleep(interval_seconds)
        except asyncio.CancelledError:
            raise

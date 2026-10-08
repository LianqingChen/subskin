#!/usr/bin/env python
"""Daily online backup of the SubSkin SQLite database with fixed retention.

Uses the SQLite online backup API (via Python's sqlite3.Connection.backup),
which is safe to run against the live database while the backend holds it open
(handles WAL / concurrent writers and yields a consistent snapshot).

Backups are written to data/backups/subskin-<UTCstamp>.db and pruned so only
the most recent RETENTION_DAYS days are kept.
"""

from __future__ import annotations

import logging
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DB = REPO_ROOT / "data" / "subskin.db"
BACKUP_DIR = REPO_ROOT / "data" / "backups"
BACKUP_PREFIX = "subskin-"
BACKUP_SUFFIX = ".db"
RETENTION_DAYS = 7

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("db-backup")


def take_backup() -> Path:
    if not SRC_DB.exists():
        raise FileNotFoundError(f"source database not found: {SRC_DB}")

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    final_path = BACKUP_DIR / f"{BACKUP_PREFIX}{stamp}{BACKUP_SUFFIX}"
    tmp_path = final_path.with_suffix(f".db.partial")

    src = sqlite3.connect(str(SRC_DB))
    try:
        dst = sqlite3.connect(str(tmp_path))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()

    # Verify the snapshot is a valid database before promoting it.
    check = sqlite3.connect(str(tmp_path))
    try:
        result = check.execute("PRAGMA integrity_check").fetchone()[0]
        if result != "ok":
            raise RuntimeError(f"backup integrity check failed: {result}")
    finally:
        check.close()

    tmp_path.replace(final_path)
    return final_path


def prune_old_backups() -> int:
    cutoff = time.time() - RETENTION_DAYS * 24 * 3600
    removed = 0
    for path in sorted(BACKUP_DIR.glob(f"{BACKUP_PREFIX}*{BACKUP_SUFFIX}")):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
                removed += 1
                log.info("pruned old backup: %s", path.name)
        except FileNotFoundError:
            continue
    return removed


def main() -> int:
    try:
        backup_path = take_backup()
    except Exception:
        log.exception("database backup FAILED")
        return 1

    size_mb = backup_path.stat().st_size / (1024 * 1024)
    pruned = prune_old_backups()
    remaining = len(list(BACKUP_DIR.glob(f"{BACKUP_PREFIX}*{BACKUP_SUFFIX}")))
    log.info(
        "backup OK: %s (%.1f MB) | pruned %d | %d backups retained (<= %d days)",
        backup_path.name,
        size_mb,
        pruned,
        remaining,
        RETENTION_DAYS,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

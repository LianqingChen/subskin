#!/usr/bin/env python
"""Daily encrypted backup of the SubSkin SQLite database and patient uploads.

Uses the SQLite online backup API (via Python's sqlite3.Connection.backup),
which is safe to run against the live database while the backend holds it open
(handles WAL / concurrent writers and yields a consistent snapshot).

Outputs (data/backups, dir 0700, files 0600):
  subskin-<UTCstamp>.db.gz.gpg          keep newest DB_KEEP
  subskin-uploads-<UTCstamp>.tar.gpg    keep newest UPLOADS_KEEP

Encryption: gpg symmetric AES256 with the passphrase file KEY_FILE. Without that
key the backups cannot be restored, so a copy of it must be kept off this host.
"""

from __future__ import annotations

import base64
import gzip
import logging
import os
import re
import secrets
import shutil
import sqlite3
import subprocess
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DB = REPO_ROOT / "data" / "subskin.db"
UPLOADS_DIR = REPO_ROOT / "data" / "uploads"
BACKUP_DIR = REPO_ROOT / "data" / "backups"
KEY_FILE = Path("/root/.config/subskin/backup.key")
DB_KEEP = 7
UPLOADS_KEEP = 3

# Only timestamped files are rotated; hand-made snapshots like
# subskin-before-label-triage-20261024.db are never touched.
DB_BACKUP_RE = re.compile(r"^subskin-\d{8}-\d{6}\.db(\.gz\.gpg)?$")
UPLOADS_BACKUP_RE = re.compile(r"^subskin-uploads-\d{8}-\d{6}\.tar\.gpg$")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("db-backup")


def ensure_key() -> Path:
    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(KEY_FILE.parent, 0o700)
    if not KEY_FILE.exists():
        fd = os.open(str(KEY_FILE), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as fh:
            fh.write(base64.b64encode(secrets.token_bytes(48)).decode() + "\n")
        log.warning("generated new backup key at %s — copy it off this host", KEY_FILE)
    os.chmod(KEY_FILE, 0o600)
    return KEY_FILE


def prepare_dir() -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(BACKUP_DIR, 0o700)
    for path in BACKUP_DIR.iterdir():
        if path.is_file():
            os.chmod(path, 0o600)


def gpg_encrypt(src: Path, dst: Path, compress: bool) -> None:
    cmd = [
        "gpg", "--batch", "--yes", "--quiet",
        "--symmetric", "--cipher-algo", "AES256",
        "--passphrase-file", str(KEY_FILE),
        "--output", str(dst),
    ]
    if not compress:
        cmd += ["--compress-algo", "none"]
    subprocess.run(cmd + [str(src)], check=True)
    os.chmod(dst, 0o600)


def snapshot_db(tmp_path: Path) -> None:
    src = sqlite3.connect(str(SRC_DB))
    try:
        dst = sqlite3.connect(str(tmp_path))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    os.chmod(tmp_path, 0o600)

    check = sqlite3.connect(str(tmp_path))
    try:
        result = check.execute("PRAGMA integrity_check").fetchone()[0]
        if result != "ok":
            raise RuntimeError(f"backup integrity check failed: {result}")
    finally:
        check.close()


def take_db_backup(stamp: str) -> Path:
    if not SRC_DB.exists():
        raise FileNotFoundError(f"source database not found: {SRC_DB}")
    plain = BACKUP_DIR / f".subskin-{stamp}.db.partial"
    gz = BACKUP_DIR / f".subskin-{stamp}.db.gz.partial"
    final = BACKUP_DIR / f"subskin-{stamp}.db.gz.gpg"
    tmp_final = BACKUP_DIR / f".subskin-{stamp}.db.gz.gpg.partial"
    try:
        snapshot_db(plain)
        fd = os.open(str(gz), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with open(plain, "rb") as fin, os.fdopen(fd, "wb") as raw, gzip.GzipFile(
            fileobj=raw, mode="wb", compresslevel=6
        ) as fout:
            shutil.copyfileobj(fin, fout, 1024 * 1024)
        gpg_encrypt(gz, tmp_final, compress=False)
        tmp_final.replace(final)
    finally:
        for p in (plain, gz, tmp_final):
            if p.exists():
                p.unlink()
    return final


def take_uploads_backup(stamp: str) -> Path | None:
    if not UPLOADS_DIR.is_dir():
        log.warning("uploads dir missing, skipped: %s", UPLOADS_DIR)
        return None
    tar_path = BACKUP_DIR / f".subskin-uploads-{stamp}.tar.partial"
    final = BACKUP_DIR / f"subskin-uploads-{stamp}.tar.gpg"
    tmp_final = BACKUP_DIR / f".subskin-uploads-{stamp}.tar.gpg.partial"
    try:
        fd = os.open(str(tar_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as raw, tarfile.open(fileobj=raw, mode="w") as tar:
            tar.add(str(UPLOADS_DIR), arcname="uploads")
        # Photos are already compressed; skip gpg's zlib pass.
        gpg_encrypt(tar_path, tmp_final, compress=False)
        tmp_final.replace(final)
    finally:
        for p in (tar_path, tmp_final):
            if p.exists():
                p.unlink()
    return final


def prune(pattern: re.Pattern, keep: int) -> int:
    # Name stamps sort chronologically; plain and encrypted share one budget.
    matches = sorted(
        (p for p in BACKUP_DIR.iterdir() if p.is_file() and pattern.match(p.name)),
        key=lambda p: p.name.split(".")[0],
    )
    removed = 0
    for path in matches[: max(0, len(matches) - keep)]:
        path.unlink()
        removed += 1
        log.info("pruned old backup: %s", path.name)
    return removed


def mb(path: Path) -> float:
    return path.stat().st_size / (1024 * 1024)


def main() -> int:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    try:
        ensure_key()
        prepare_dir()
        db_path = take_db_backup(stamp)
    except Exception:
        log.exception("database backup FAILED")
        return 1
    log.info("db backup OK: %s (%.1f MB)", db_path.name, mb(db_path))

    status = 0
    try:
        up_path = take_uploads_backup(stamp)
        if up_path:
            log.info("uploads backup OK: %s (%.1f MB)", up_path.name, mb(up_path))
    except Exception:
        log.exception("uploads backup FAILED")
        status = 1

    pruned = prune(DB_BACKUP_RE, DB_KEEP) + prune(UPLOADS_BACKUP_RE, UPLOADS_KEEP)
    total = sum(p.stat().st_size for p in BACKUP_DIR.iterdir() if p.is_file())
    log.info("pruned %d | backup dir total %.1f MB", pruned, total / (1024 * 1024))
    return status


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python
"""Restore drill: prove the newest encrypted backups can actually be restored.

Decrypts the newest DB backup into a temp dir, runs PRAGMA integrity_check,
compares key table row counts against the live DB, and lists the newest uploads
archive. Exit code 0 = drill passed.
"""

from __future__ import annotations

import gzip
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LIVE_DB = REPO_ROOT / "data" / "subskin.db"
BACKUP_DIR = REPO_ROOT / "data" / "backups"
KEY_FILE = Path("/root/.config/subskin/backup.key")
TABLES = ("users", "posts", "diary_entries")


def decrypt(src: Path, dst: Path) -> None:
    subprocess.run(
        ["gpg", "--batch", "--yes", "--quiet", "--passphrase-file", str(KEY_FILE),
         "--output", str(dst), "--decrypt", str(src)],
        check=True,
    )


def counts(db: Path) -> dict:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return {t: conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in TABLES}
    finally:
        conn.close()


def newest(pattern: str) -> Path | None:
    files = sorted(BACKUP_DIR.glob(pattern), key=lambda p: p.name)
    return files[-1] if files else None


def main() -> int:
    ok = True
    db_bak = newest("subskin-[0-9]*-[0-9]*.db.gz.gpg")
    up_bak = newest("subskin-uploads-*.tar.gpg")
    if db_bak is None:
        print("FAIL: no encrypted DB backup found")
        return 1

    with tempfile.TemporaryDirectory(prefix="subskin-drill-") as tmp:
        tmpdir = Path(tmp)
        gz = tmpdir / "db.gz"
        db = tmpdir / "restored.db"
        decrypt(db_bak, gz)
        with gzip.open(gz, "rb") as fin, open(db, "wb") as fout:
            shutil.copyfileobj(fin, fout, 1024 * 1024)
        gz.unlink()

        conn = sqlite3.connect(str(db))
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        conn.close()
        print(f"db backup: {db_bak.name} -> integrity_check={integrity}")
        ok &= integrity == "ok"

        restored, live = counts(db), counts(LIVE_DB)
        for t in TABLES:
            flag = "ok" if 0 <= live[t] - restored[t] <= max(50, live[t] // 10) else "MISMATCH"
            print(f"  {t}: backup={restored[t]} live={live[t]} {flag}")
            ok &= flag == "ok"

        if up_bak is None:
            print("FAIL: no encrypted uploads backup found")
            ok = False
        else:
            tar_path = tmpdir / "uploads.tar"
            decrypt(up_bak, tar_path)
            with tarfile.open(tar_path) as tar:
                n_files = sum(1 for m in tar if m.isfile())
            live_files = sum(1 for p in (REPO_ROOT / "data" / "uploads").rglob("*") if p.is_file())
            print(f"uploads backup: {up_bak.name} -> {n_files} files (live {live_files})")
            ok &= n_files > 0

    print("DRILL PASSED" if ok else "DRILL FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

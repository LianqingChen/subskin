#!/usr/bin/env python
"""Migration: Add source_tier, authority_weight, pub_date to documents table.

Supports the data source authority tier system for RAG weighting.

Usage:
    python scripts/migration_add_source_tier.py
"""

import sqlite3
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv()

DB_URL = os.getenv("DATABASE_URL", "sqlite:///./web/backend/data/subskin.db")


def get_db_path(db_url):
    if db_url.startswith("sqlite:///"):
        rel_path = db_url.replace("sqlite:///", "")
        return str(PROJECT_ROOT / rel_path)
    return None


def migrate():
    db_path = get_db_path(DB_URL)
    if not db_path:
        print(f"Unsupported database: {DB_URL}")
        print("Migration only supports SQLite. For PostgreSQL, run manual ALTER TABLE.")
        return

    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}. Creating schema will include new columns.")
        return

    print(f"Migrating database: {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(documents)")
    columns = {row[1] for row in cursor.fetchall()}

    migrations = [
        ("source_tier", "TEXT DEFAULT 'C'"),
        ("authority_weight", "REAL DEFAULT 1.0"),
        ("pub_date", "TEXT"),
    ]

    for col_name, col_def in migrations:
        if col_name not in columns:
            sql = f"ALTER TABLE documents ADD COLUMN {col_name} {col_def}"
            cursor.execute(sql)
            print(f"  Added column: {col_name} {col_def}")
        else:
            print(f"  Column already exists: {col_name}")

    conn.commit()

    cursor.execute("PRAGMA table_info(documents)")
    print("\nDocuments table columns:")
    for row in cursor.fetchall():
        print(f"  {row[1]} ({row[2]})")

    conn.close()
    print("\nMigration complete.")


if __name__ == "__main__":
    migrate()

"""Add uid column to users table"""

import sqlite3
import os

DB_PATHS = [
    "/root/subskin/data/subskin.db",
    "/root/subskin/web/backend/data/subskin.db",
]


def migrate():
    for db_path in DB_PATHS:
        if not os.path.exists(db_path):
            print(f"Skipping {db_path} (not found)")
            continue

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        columns = [
            row[1] for row in cursor.execute("PRAGMA table_info(users)").fetchall()
        ]
        if "uid" in columns:
            print(f"uid column already exists in {db_path}")
            conn.close()
            continue

        cursor.execute("ALTER TABLE users ADD COLUMN uid VARCHAR")
        conn.commit()
        print(f"Added uid column to users in {db_path}")

        cursor.execute("SELECT id, phone, username, created_at FROM users")
        users = cursor.fetchall()

        from datetime import datetime, timezone

        for user_id, phone, username, created_at in users:
            identifier = phone or username or str(user_id)
            if identifier.isdigit() and len(identifier) >= 4:
                suffix = identifier[-4:]
            else:
                import hashlib

                suffix = hashlib.md5(identifier.encode()).hexdigest()[:4]

            if created_at:
                dt = (
                    datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                    if isinstance(created_at, str)
                    else created_at
                )
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                timestamp = dt.strftime("%Y%m%d%H%M")
                day_start = dt.replace(hour=0, minute=0, second=0, microsecond=0)
            else:
                timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
                day_start = datetime.now(timezone.utc).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )

            count_before = cursor.execute(
                "SELECT COUNT(*) FROM users WHERE created_at < ? AND created_at >= ?",
                (created_at, day_start.isoformat()),
            ).fetchone()[0]
            sequence = count_before + 1
            uid = f"SS-{suffix}-{timestamp}-{sequence:06d}"

            try:
                cursor.execute("UPDATE users SET uid = ? WHERE id = ?", (uid, user_id))
                print(f"  User {user_id}: uid = {uid}")
            except sqlite3.IntegrityError:
                sequence += 1
                uid = f"SS-{suffix}-{timestamp}-{sequence:06d}"
                cursor.execute("UPDATE users SET uid = ? WHERE id = ?", (uid, user_id))
                print(f"  User {user_id}: uid = {uid} (adjusted seq)")

        conn.commit()
        conn.close()
        print(f"Migration complete for {db_path}")


if __name__ == "__main__":
    migrate()

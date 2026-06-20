import sqlite3
import os

DB_PATHS = [
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data",
        "subskin.db",
    ),
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "web",
        "backend",
        "data",
        "subskin.db",
    ),
]


def main():
    for db_path in DB_PATHS:
        if not os.path.exists(db_path):
            print(f"Skipping non-existent: {db_path}")
            continue
        print(f"Migrating: {db_path}")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(conversations)")
        columns = [col[1] for col in cursor.fetchall()]
        if "is_deleted" not in columns:
            cursor.execute(
                "ALTER TABLE conversations ADD COLUMN is_deleted BOOLEAN DEFAULT 0"
            )
            print("  Added is_deleted column")
        else:
            print("  is_deleted column already exists")
        conn.commit()
        conn.close()


if __name__ == "__main__":
    main()

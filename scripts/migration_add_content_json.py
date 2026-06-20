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

        cursor.execute("PRAGMA table_info(posts)")
        columns = [col[1] for col in cursor.fetchall()]

        if "content_json" not in columns:
            cursor.execute("ALTER TABLE posts ADD COLUMN content_json TEXT")
            print("  Added content_json column")
        else:
            print("  content_json column already exists")

        if "content_text" not in columns:
            cursor.execute("ALTER TABLE posts ADD COLUMN content_text TEXT")
            print("  Added content_text column")
        else:
            print("  content_text column already exists")

        conn.commit()
        conn.close()


if __name__ == "__main__":
    main()

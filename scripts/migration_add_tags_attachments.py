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

TABLES_SQL = [
    """CREATE TABLE IF NOT EXISTS tags (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name VARCHAR NOT NULL UNIQUE,
        usage_count INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS post_tags (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id INTEGER NOT NULL REFERENCES posts(id),
        tag_id INTEGER NOT NULL REFERENCES tags(id),
        UNIQUE(post_id, tag_id)
    )""",
    """CREATE TABLE IF NOT EXISTS post_audios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id INTEGER NOT NULL REFERENCES posts(id),
        audio_url VARCHAR NOT NULL,
        duration INTEGER DEFAULT 0,
        file_size INTEGER DEFAULT 0,
        "order" INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS post_attachments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id INTEGER NOT NULL REFERENCES posts(id),
        file_url VARCHAR NOT NULL,
        file_name VARCHAR NOT NULL,
        file_size INTEGER DEFAULT 0,
        file_type VARCHAR DEFAULT '',
        "order" INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
]

INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS ix_tags_name ON tags(name)",
    "CREATE INDEX IF NOT EXISTS ix_post_tags_post_id ON post_tags(post_id)",
    "CREATE INDEX IF NOT EXISTS ix_post_tags_tag_id ON post_tags(tag_id)",
    "CREATE INDEX IF NOT EXISTS ix_post_audios_post_id ON post_audios(post_id)",
    "CREATE INDEX IF NOT EXISTS ix_post_attachments_post_id ON post_attachments(post_id)",
]


def main():
    for db_path in DB_PATHS:
        if not os.path.exists(db_path):
            print(f"Skipping non-existent: {db_path}")
            continue
        print(f"Migrating: {db_path}")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        for sql in TABLES_SQL:
            try:
                cursor.execute(sql)
                print(
                    f"  Created table: {sql.split('(')[0].split('EXISTS')[1].strip() if 'EXISTS' in sql else 'unknown'}"
                )
            except sqlite3.OperationalError as e:
                if "already exists" in str(e):
                    print(f"  Table already exists, skipping")
                else:
                    raise
        for sql in INDEXES_SQL:
            try:
                cursor.execute(sql)
            except sqlite3.OperationalError:
                pass
        conn.commit()
        conn.close()
    print("Migration complete!")


if __name__ == "__main__":
    main()

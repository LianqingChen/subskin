"""Add collections, bookmarks, and post versions tables."""

import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "subskin.db"


def migrate(db_path: str = str(DB_PATH)):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS collections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name VARCHAR NOT NULL,
            description TEXT,
            icon VARCHAR,
            is_public BOOLEAN DEFAULT 0,
            share_slug VARCHAR UNIQUE,
            sort_order INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS ix_collections_user_id ON collections(user_id)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS ix_collections_share_slug ON collections(share_slug)
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS collection_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            collection_id INTEGER NOT NULL,
            post_id INTEGER NOT NULL,
            sort_order INTEGER DEFAULT 0,
            note TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (collection_id) REFERENCES collections(id),
            FOREIGN KEY (post_id) REFERENCES posts(id),
            UNIQUE(collection_id, post_id)
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS ix_collection_items_collection_id ON collection_items(collection_id)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS ix_collection_items_post_id ON collection_items(post_id)
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS post_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            title VARCHAR NOT NULL,
            content TEXT NOT NULL,
            content_json TEXT,
            edit_summary VARCHAR,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (post_id) REFERENCES posts(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS ix_post_versions_post_id ON post_versions(post_id)
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bookmarks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            post_id INTEGER NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (post_id) REFERENCES posts(id),
            UNIQUE(user_id, post_id)
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS ix_bookmarks_user_id ON bookmarks(user_id)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS ix_bookmarks_post_id ON bookmarks(post_id)
    """)

    conn.commit()
    conn.close()
    print(
        f"Migration complete: collections, collection_items, post_versions, bookmarks tables created in {db_path}"
    )


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else str(DB_PATH)
    migrate(path)

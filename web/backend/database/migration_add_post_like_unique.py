"""Add a UNIQUE(post_id, user_id) constraint to post_likes.

Without this constraint, two concurrent ``toggle_like`` requests can both
INSERT, producing duplicate (post_id, user_id) rows that inflate like counts.
Bookmark and Follow already have analogous unique constraints; this brings
PostLike in line.

SQLite cannot add a constraint to an existing table directly, so this migration:
  1. Deduplicates any existing rows (keeps the earliest created_at per pair).
  2. Rebuilds the table with the constraint via the standard temp-table swap.

Idempotent: if the constraint already exists, the migration is a no-op.
"""

from pathlib import Path

from sqlalchemy import create_engine, inspect, text


DB_PATH = Path(__file__).resolve().parent.parent / "data" / "subskin.db"
ENGINE = create_engine(f"sqlite:///{DB_PATH}")


def _constraint_exists(conn) -> bool:
    """Check whether uq_post_like_post_user already exists on post_likes."""
    # SQLite stores unique constraints as auto-created unique indexes whose
    # name matches the constraint name.
    rows = conn.execute(text("PRAGMA index_list('post_likes')")).fetchall()
    for r in rows:
        # row: (seq, name, unique, origin, partial)
        if r[1] == "uq_post_like_post_user":
            return True
    return False


def migrate() -> None:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"数据库文件不存在: {DB_PATH}")

    with ENGINE.begin() as conn:
        if _constraint_exists(conn):
            print("ℹ️  uq_post_like_post_user already exists — skipping")
            return

        # 1. Deduplicate existing likes (keep earliest created_at per pair).
        conn.execute(text(
            "DELETE FROM post_likes WHERE id NOT IN ("
            "  SELECT MIN(id) FROM post_likes GROUP BY post_id, user_id"
            ")"
        ))

        # 2. Rebuild table with the unique constraint.
        conn.execute(text(
            "CREATE TABLE post_likes_new ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  post_id INTEGER NOT NULL REFERENCES posts(id),"
            "  user_id INTEGER NOT NULL REFERENCES users(id),"
            "  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,"
            "  CONSTRAINT uq_post_like_post_user UNIQUE (post_id, user_id)"
            ")"
        ))
        conn.execute(text(
            "INSERT INTO post_likes_new (id, post_id, user_id, created_at) "
            "SELECT id, post_id, user_id, created_at FROM post_likes"
        ))
        # Preserve indexes (SQLite drops them with the table).
        conn.execute(text("DROP TABLE post_likes"))
        conn.execute(text("ALTER TABLE post_likes_new RENAME TO post_likes"))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_post_likes_post_id ON post_likes (post_id)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_post_likes_user_id ON post_likes (user_id)"
        ))

    print("✅ post_likes unique constraint (uq_post_like_post_user) ensured")


if __name__ == "__main__":
    migrate()

"""Add analytics indexes to user_events table."""

from pathlib import Path

from sqlalchemy import create_engine, text


DB_PATH = Path(__file__).resolve().parent.parent / "data" / "subskin.db"
ENGINE = create_engine(f"sqlite:///{DB_PATH}")

INDEX_STATEMENTS = (
    "CREATE INDEX IF NOT EXISTS idx_events_created_type ON user_events(created_at, event_type)",
    "CREATE INDEX IF NOT EXISTS idx_events_created_type_path ON user_events(created_at, event_type, page_path)",
    "CREATE INDEX IF NOT EXISTS idx_events_created_uid ON user_events(created_at, uid)",
)


def migrate() -> None:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"数据库文件不存在: {DB_PATH}")

    with ENGINE.begin() as conn:
        for statement in INDEX_STATEMENTS:
            _ = conn.execute(text(statement))

    print("✅ user_events analytics indexes ensured")


if __name__ == "__main__":
    migrate()

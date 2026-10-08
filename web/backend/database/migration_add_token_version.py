"""Migration: add users.token_version column (additive, 2026-08-30 security hardening).

token_version 用于即时撤销 access token：
- create_access_token 埋入 tv claim
- get_user_from_access_token 校验 tv == User.token_version
- 改密 / 重置密码 / 登出全部设备 / 注销账户时 bump_token_version() 令所有存量 token 失效

用法: python -m web.backend.database.migration_add_token_version
"""

import logging
import sys

from sqlalchemy import inspect, text

from web.backend.database.database import engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def migrate() -> None:
    inspector = inspect(engine)
    columns = [c["name"] for c in inspector.get_columns("users")]
    if "token_version" in columns:
        logger.info("users.token_version already exists, skipping")
        return
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE users ADD COLUMN token_version INTEGER NOT NULL DEFAULT 0"))
    logger.info("Added users.token_version (default 0)")


if __name__ == "__main__":
    try:
        migrate()
    except Exception as exc:  # pragma: no cover
        logger.error("Migration failed: %s", exc)
        sys.exit(1)

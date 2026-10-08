"""
数据库连接配置
"""

import logging
import math
import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

logger = logging.getLogger(__name__)

# Use absolute path based on this file's location to avoid working-directory dependency
_BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent  # .../subskin/
DEFAULT_DB_PATH = str(_BASE_DIR / "data" / "subskin.db")

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}")

if "sqlite" in DATABASE_URL:
    # SQLite 使用 NullPool：按需开连接、用完即关。
    # 默认的 QueuePool(5+10) 在并发突发（社区页 20+ 张图片请求）下会耗尽，
    # 后续请求在 async 事件循环线程上同步等待 pool.get(30s)，
    # 直接冻结整个单 worker 服务（2026-08-04 全站挂起事故根因）。
    # SQLite 是文件库，开连接开销极小（<1ms），且不存在池可耗尽的问题。
    # timeout=15：写锁竞争时最多等 15s（默认 5s 太短易报 database is locked）。
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False, "timeout": 15},
        poolclass=NullPool,
    )

    # SQLite 默认不启用数学函数（无 pow），注册一个 Python 实现的 pow/exp，
    # 供热度排序的时间衰减公式（0.5^(age/7)）在 SQL 内直接计算。
    @event.listens_for(engine, "connect")
    def _register_sqlite_math(dbapi_conn, _record):
        try:
            dbapi_conn.create_function("pow", 2, lambda x, y: math.pow(x, y))
        except Exception as e:
            # 注册失败不阻断连接，但必须可诊断——否则热度排序会以
            # "no such function: pow" 500 的形式隐性复发（2026-08-24 事故）。
            logger.warning("SQLite pow UDF registration failed: %s", e)
else:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """获取数据库会话
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

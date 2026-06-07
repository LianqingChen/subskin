"""
数据库连接配置
"""

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Use absolute path based on this file's location to avoid working-directory dependency
_BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent  # .../subskin/
DEFAULT_DB_PATH = str(_BASE_DIR / "data" / "subskin.db")

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}")

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)
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

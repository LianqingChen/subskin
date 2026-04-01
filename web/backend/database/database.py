"""
数据库连接配置
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

import os

# 数据库URL，从环境变量读取，默认使用SQLite
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/subskin.db")

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

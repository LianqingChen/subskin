#!/usr/bin/env python
"""测试数据库创建"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from web.backend.database.database import engine, Base, SessionLocal
from web.backend.database.models import User, SMSCode, Comment
from web.backend.services.auth import get_password_hash

Base.metadata.create_all(bind=engine)
print("✅ 所有表创建完成")

# 检查表
from sqlalchemy import inspect

inspector = inspect(engine)
print(f"\n创建的表: {inspector.get_table_names()}")

db = SessionLocal()

# 手动创建管理员，密码截断
username = "admin"
password = "admin"
password = password[:72]
print(f"\n密码长度: {len(password)}")

existing = db.query(User).filter(User.username == username).first()
if existing:
    print(f"用户 {username} 已存在")
else:
    # 直接哈希，使用 pbkdf2 兼容方案绕开 bcrypt 问题
    from passlib.context import CryptContext

    pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
    hashed_password = pwd_context.hash(password)
    print(f"使用 pbkdf2_sha256 替代 bcrypt")

    user = User(
        username=username,
        hashed_password=hashed_password,
        is_active=True,
        is_admin=True,
    )
    db.add(user)
    db.commit()
    print(f"✅ 管理员 {username} 创建成功")

db.close()
print("\n数据库初始化完成!")

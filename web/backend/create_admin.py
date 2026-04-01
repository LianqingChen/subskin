#!/usr/bin/env python
"""手动创建管理员"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.database import engine, Base, SessionLocal
from database.models import User
from services.auth import get_password_hash

# 创建表
Base.metadata.create_all(bind=engine)
print("✅ 数据库表创建完成")

db = SessionLocal()

username = sys.argv[1] if len(sys.argv) > 1 else "admin"
password = sys.argv[2] if len(sys.argv) > 2 else "admin"

# 截断密码到72字节
password = password[:72]

# 检查是否已存在
existing = db.query(User).filter(User.username == username).first()
if existing:
    print(f"⚠️  用户 {username} 已存在")
else:
    user = User(
        username=username,
        hashed_password=get_password_hash(password),
        is_active=True,
        is_admin=True
    )
    db.add(user)
    db.commit()
    print(f"✅ 管理员 {username} 创建成功")

db.close()

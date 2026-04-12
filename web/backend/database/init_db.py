"""
初始化数据库
创建表结构并添加初始管理员账户
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

from web.backend.database.database import engine, Base
from web.backend.database.models import User
from web.backend.services.auth import get_password_hash


def init_db():
    """创建所有表"""
    Base.metadata.create_all(bind=engine)
    print("✅ 数据库表创建完成")


def create_admin(username: str, password: str, email: str = None):
    """创建管理员账户"""
    from web.backend.database.database import SessionLocal

    db = SessionLocal()

    # 检查是否已存在
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        print(f"⚠️  用户 {username} 已存在")
        return

    user = User(
        username=username,
        email=email,
        hashed_password=get_password_hash(password),
        is_active=True,
        is_admin=True,
    )
    db.add(user)
    db.commit()
    print(f"✅ 管理员账户 {username} 创建成功")

    db.close()


if __name__ == "__main__":
    init_db()
    # 创建默认管理员，可以通过环境变量覆盖
    admin_user = os.getenv("ADMIN_USER", "admin")
    admin_pass = os.getenv("ADMIN_PASS", "admin")
    admin_email = os.getenv("ADMIN_EMAIL", None)
    create_admin(admin_user, admin_pass, admin_email)

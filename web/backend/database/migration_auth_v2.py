"""
认证系统V2数据库迁移
- 邮箱验证码表
- OAuth状态表（CSRF防护）
- 刷新令牌表
- 用户表: hashed_password 改为可空
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

from web.backend.database.database import engine, Base, SessionLocal
from web.backend.database.models import (
    SMSCode,
    EmailVerificationCode,
    OAuthState,
    RefreshToken,
    GuestUsage,
    User,
)


def migrate():
    print("开始认证系统V2迁移...")

    # 创建新表
    Base.metadata.create_all(
        bind=engine,
        tables=[
            EmailVerificationCode.__table__,
            OAuthState.__table__,
            RefreshToken.__table__,
            GuestUsage.__table__,
        ],
    )
    print(
        "✅ 新表创建完成: email_verification_codes, oauth_states, refresh_tokens, guest_usages"
    )

    # 更新 users 表: hashed_password 改为可空
    db = SessionLocal()
    try:
        if "sqlite" in str(engine.url):
            db.execute("ALTER TABLE users ALTER COLUMN hashed_password DROP NOT NULL")
        else:
            db.execute("ALTER TABLE users ALTER COLUMN hashed_password DROP NOT NULL")
        db.commit()
        print("✅ users.hashed_password 已改为可空")
    except Exception as e:
        db.rollback()
        if "not null" in str(e).lower() or "already" in str(e).lower():
            print("ℹ️  hashed_password 已经是可空的，跳过")
        else:
            print(f"⚠️  修改hashed_password字段失败: {e}")
            print(
                "   请手动执行: ALTER TABLE users ALTER COLUMN hashed_password DROP NOT NULL"
            )
    finally:
        db.close()

    print("✅ 认证系统V2迁移完成")


if __name__ == "__main__":
    migrate()

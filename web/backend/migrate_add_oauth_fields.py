#!/usr/bin/env python
"""添加第三方登录字段到用户表（SQLite兼容版本）"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from database.database import engine

with engine.connect() as conn:
    # 添加 wechat_id 字段
    try:
        conn.execute(text("ALTER TABLE users ADD COLUMN wechat_id VARCHAR(255)"))
        conn.commit()
        print("✅ 添加 wechat_id 字段")
    except Exception as e:
        if "duplicate column name" in str(e).lower():
            print("ℹ️  wechat_id 字段已存在")
        else:
            print(f"⚠️  添加 wechat_id 字段失败: {e}")

    # 添加 alipay_id 字段
    try:
        conn.execute(text("ALTER TABLE users ADD COLUMN alipay_id VARCHAR(255)"))
        conn.commit()
        print("✅ 添加 alipay_id 字段")
    except Exception as e:
        if "duplicate column name" in str(e).lower():
            print("ℹ️  alipay_id 字段已存在")
        else:
            print(f"⚠️  添加 alipay_id 字段失败: {e}")

    # 创建 wechat_id 唯一索引（SQLite不支持ALTER TABLE ADD UNIQUE，使用索引替代）
    try:
        conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_wechat_id ON users(wechat_id)"
            )
        )
        conn.commit()
        print("✅ 创建 wechat_id 唯一索引")
    except Exception as e:
        if "duplicate index" in str(e).lower() or "already exists" in str(e).lower():
            print("ℹ️  wechat_id 唯一索引已存在")
        else:
            print(f"⚠️  创建 wechat_id 唯一索引失败: {e}")

    # 创建 alipay_id 唯一索引
    try:
        conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_alipay_id ON users(alipay_id)"
            )
        )
        conn.commit()
        print("✅ 创建 alipay_id 唯一索引")
    except Exception as e:
        if "duplicate index" in str(e).lower() or "already exists" in str(e).lower():
            print("ℹ️  alipay_id 唯一索引已存在")
        else:
            print(f"⚠️  创建 alipay_id 唯一索引失败: {e}")

print("✅ 用户表迁移完成")

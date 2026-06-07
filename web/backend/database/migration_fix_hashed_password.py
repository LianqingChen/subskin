"""
修复用户表 hashed_password 字段：允许 NULL，支持手机号/OAuth 登录
手机号登录和第三方登录（微信/支付宝）的用户不需要密码，hashed_password 应为 NULL
"""

import sqlite3
from pathlib import Path

db_path = Path(__file__).parent.parent / "data" / "subskin.db"

if not db_path.exists():
    print(f"数据库文件不存在: {db_path}")
    exit(1)

conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

# 检查当前 nullable 状态
cursor.execute("PRAGMA table_info(users)")
columns = {row[1]: row[3] for row in cursor.fetchall()}

changed = False

if "hashed_password" in columns and columns["hashed_password"] == 1:  # 1 = NOT NULL
    # SQLite 不支持 ALTER COLUMN，需要重建表
    print("修复 hashed_password 字段：NOT NULL → NULL ...")

    cursor.execute("""
        CREATE TABLE users_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username VARCHAR NOT NULL UNIQUE,
            email VARCHAR UNIQUE,
            phone VARCHAR UNIQUE,
            wechat_id VARCHAR UNIQUE,
            alipay_id VARCHAR UNIQUE,
            hashed_password VARCHAR,  -- 允许 NULL，手机号/OAuth 登录用户无密码
            is_active BOOLEAN DEFAULT 1,
            is_admin BOOLEAN DEFAULT 0,
            created_at DATETIME,
            updated_at DATETIME
        )
    """)

    cursor.execute("""
        INSERT INTO users_new (id, username, email, phone, wechat_id, alipay_id, hashed_password, is_active, is_admin, created_at, updated_at)
        SELECT id, username, email, phone, wechat_id, alipay_id, hashed_password, is_active, is_admin, created_at, updated_at
        FROM users
    """)

    cursor.execute("DROP TABLE users")
    cursor.execute("ALTER TABLE users_new RENAME TO users")

    # 重建索引
    cursor.execute("CREATE INDEX ix_users_username ON users (username)")
    cursor.execute("CREATE INDEX ix_users_email ON users (email)")
    cursor.execute("CREATE INDEX ix_users_phone ON users (phone)")
    cursor.execute("CREATE INDEX ix_users_wechat_id ON users (wechat_id)")
    cursor.execute("CREATE INDEX ix_users_alipay_id ON users (alipay_id)")

    changed = True
    print("  ✓ hashed_password 字段已修改为允许 NULL")
else:
    print("  hashed_password 字段已允许 NULL，无需修复")

conn.commit()
conn.close()

if changed:
    print("数据库迁移完成！")
else:
    print("无需修改。")

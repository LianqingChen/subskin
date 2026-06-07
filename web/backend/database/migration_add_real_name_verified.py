"""
数据库迁移脚本：添加 User.real_name_verified 字段
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "data", "subskin.db")


def run():
    if not os.path.exists(DB_PATH):
        print(f"数据库文件不存在: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(users)")
    columns = [row[1] for row in cursor.fetchall()]

    if "real_name_verified" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN real_name_verified BOOLEAN DEFAULT 0")
        print("Added column: real_name_verified")
    else:
        print("Column already exists: real_name_verified")

    conn.commit()
    conn.close()
    print("Migration complete")


if __name__ == "__main__":
    run()
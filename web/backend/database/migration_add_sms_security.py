"""
添加验证码暴力破解防护字段
添加 SMSCode.attempt_count 和 SMSCode.locked 字段
"""

import sqlite3
import os
from pathlib import Path

db_path = Path(__file__).parent.parent / "data" / "subskin.db"

if not db_path.exists():
    print(f"数据库文件不存在: {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 检查字段是否已存在
cursor.execute("PRAGMA table_info(sms_codes)")
columns = [row[1] for row in cursor.fetchall()]

if "attempt_count" not in columns:
    cursor.execute("ALTER TABLE sms_codes ADD COLUMN attempt_count INTEGER DEFAULT 0")
    print("✓ 已添加 attempt_count 字段")
else:
    print("  attempt_count 字段已存在，跳过")

if "locked" not in columns:
    cursor.execute("ALTER TABLE sms_codes ADD COLUMN locked BOOLEAN DEFAULT 0")
    print("✓ 已添加 locked 字段")
else:
    print("  locked 字段已存在，跳过")

conn.commit()
conn.close()
print("数据库迁移完成！")

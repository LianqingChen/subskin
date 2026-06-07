"""
数据库迁移脚本：添加 Post.draft_expires_at 字段

新增列:
- posts.draft_expires_at (草稿过期时间，仅 is_private=True 的帖子使用)
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

    cursor.execute("PRAGMA table_info(posts)")
    columns = [row[1] for row in cursor.fetchall()]

    if "draft_expires_at" not in columns:
        cursor.execute("ALTER TABLE posts ADD COLUMN draft_expires_at DATETIME")
        print("✅ posts.draft_expires_at 列已添加")

        from datetime import datetime, timedelta

        now = datetime.utcnow()
        expire_30d = now + timedelta(days=30)
        expire_str = expire_30d.strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute(
            "UPDATE posts SET draft_expires_at = ? WHERE is_private = 1 AND draft_expires_at IS NULL",
            (expire_str,),
        )
        updated = cursor.rowcount
        if updated:
            print(f"✅ 已为 {updated} 篇现有草稿设置30天过期时间")
    else:
        print("⏭️  posts.draft_expires_at 列已存在，跳过")

    conn.commit()
    conn.close()
    print("🎉 迁移完成")


if __name__ == "__main__":
    run()

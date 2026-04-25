"""
数据库迁移脚本：添加社交关系表和 Post.city 字段

新建表:
- user_follows (关注关系)
- user_blocks (拉黑关系)
- user_reports (举报记录)

新增列:
- posts.city (发布城市)
"""

import sqlite3
import os
import sys

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "data", "subskin.db")


def run():
    if not os.path.exists(DB_PATH):
        print(f"数据库文件不存在: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # user_follows 表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_follows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            followee_id INTEGER NOT NULL REFERENCES users(id),
            follower_id INTEGER NOT NULL REFERENCES users(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_user_follows_pair ON user_follows(followee_id, follower_id)"
    )
    print("✅ user_follows 表已就绪")

    # user_blocks 表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_blocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            blocker_id INTEGER NOT NULL REFERENCES users(id),
            blocked_id INTEGER NOT NULL REFERENCES users(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_user_blocks_pair ON user_blocks(blocker_id, blocked_id)"
    )
    print("✅ user_blocks 表已就绪")

    # user_reports 表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reporter_id INTEGER NOT NULL REFERENCES users(id),
            target_user_id INTEGER NOT NULL REFERENCES users(id),
            post_id INTEGER REFERENCES posts(id),
            reason TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("✅ user_reports 表已就绪")

    # posts.city 列
    cursor.execute("PRAGMA table_info(posts)")
    columns = [row[1] for row in cursor.fetchall()]
    if "city" not in columns:
        cursor.execute("ALTER TABLE posts ADD COLUMN city VARCHAR(100)")
        print("✅ posts.city 列已添加")
    else:
        print("⏭️  posts.city 列已存在，跳过")

    conn.commit()
    conn.close()
    print("🎉 迁移完成")


if __name__ == "__main__":
    run()

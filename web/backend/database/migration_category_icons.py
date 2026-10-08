"""一次性数据迁移：社区分类图标 emoji → RemixIcon 类。

init_db.py 的种子定义早已使用 RemixIcon 类（ri-book-3-line 等），
前端 PostCard 也按 :class 渲染，但存量生产数据仍是旧版 emoji，
导致分类按钮显示 emoji（违反 RemixIcon 规范）且 PostCard 图标失效。

幂等：按 name 匹配更新，可重复执行。
"""
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "subskin.db")

ICON_MAP = {
    "白白日记": "ri-book-3-line",
    "治疗分享": "ri-capsule-line",
    "心理支持": "ri-heart-2-line",
    "护肤经验": "ri-flask-line",
    "日常饮食": "ri-restaurant-line",
    "诊断咨询": "ri-microscope-line",
    "科普百科": "ri-newspaper-line",
    "其他": "ri-chat-3-line",
}


def main() -> None:
    db_path = os.path.normpath(DB_PATH)
    if not os.path.exists(db_path):
        raise SystemExit(f"DB not found: {db_path}")
    conn = sqlite3.connect(db_path)
    updated = 0
    for name, icon in ICON_MAP.items():
        cur = conn.execute(
            "UPDATE community_categories SET icon = ? WHERE name = ? AND icon != ?",
            (icon, name, icon),
        )
        updated += cur.rowcount
    conn.commit()
    rows = conn.execute(
        "SELECT name, icon FROM community_categories ORDER BY id"
    ).fetchall()
    conn.close()
    print(f"updated {updated} rows")
    for name, icon in rows:
        print(f"  {name}: {icon}")


if __name__ == "__main__":
    main()

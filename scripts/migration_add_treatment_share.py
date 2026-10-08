"""Migration: add posts.treatment_share_json column (SQLite ADD COLUMN only).

Stores the structured treatment-experience template JSON for community posts:
    {
        "method": str,              # 治疗方案
        "duration": str,            # 持续周期
        "effect_rating": int 1-5,   # 效果评价
        "cost_range": str,          # 费用区间
        "side_effects": [str],      # 副作用标签
        "vasi_assessment_ids": [int],   # 关联的 VASI 评估记录 ID（最多2个）
        "vasi_assessments": [dict],     # VASI 评估快照（日期/分数/部位）
    }

Safe to run multiple times — only adds the column if missing.
NOTE: This script is NOT executed automatically; run manually when deploying.
"""

import sqlite3
import os

DB_PATHS = [
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data",
        "subskin.db",
    ),
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "web",
        "backend",
        "data",
        "subskin.db",
    ),
]


def main():
    for db_path in DB_PATHS:
        if not os.path.exists(db_path):
            print(f"Skipping non-existent: {db_path}")
            continue
        print(f"Migrating: {db_path}")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(posts)")
        columns = [col[1] for col in cursor.fetchall()]

        if "treatment_share_json" not in columns:
            cursor.execute("ALTER TABLE posts ADD COLUMN treatment_share_json TEXT")
            print("  Added treatment_share_json column")
        else:
            print("  treatment_share_json column already exists")

        conn.commit()
        conn.close()


if __name__ == "__main__":
    main()

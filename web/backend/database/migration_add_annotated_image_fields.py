"""
添加图片打标模块新字段:
1. ImageLabel: annotated_image_path, annotated_image_url, annotated_layers_path
2. ImageLabelAnnotation: skin_mask_data
"""

import sqlite3
import os
from pathlib import Path

DB_CANDIDATES = [
    Path("/root/subskin/web/backend/data/subskin.db"),
    Path("/root/subskin/web/backend/database/data/subskin.db"),
    Path(__file__).parent.parent / "data" / "subskin.db",
    Path(__file__).parent / "data" / "subskin.db",
]

db_path = None
for candidate in DB_CANDIDATES:
    if candidate.exists():
        db_path = candidate
        break

if not db_path:
    # Try to find it by walking the web directory
    for root, dirs, files in os.walk(Path(__file__).parent.parent.parent):
        if "subskin.db" in files:
            db_path = Path(root) / "subskin.db"
            break

if not db_path or not db_path.exists():
    print(f"数据库文件未找到，尝试过的路径: {[str(c) for c in DB_CANDIDATES]}")
    exit(1)

print(f"使用数据库: {db_path}")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# ── ImageLabel 新增字段 ──
cursor.execute("PRAGMA table_info(image_labels)")
image_label_columns = [row[1] for row in cursor.fetchall()]

new_image_label_cols = [
    ("annotated_image_path", "VARCHAR"),
    ("annotated_image_url", "VARCHAR"),
    ("annotated_layers_path", "VARCHAR"),
]

for col_name, col_type in new_image_label_cols:
    if col_name not in image_label_columns:
        cursor.execute(f"ALTER TABLE image_labels ADD COLUMN {col_name} {col_type}")
        print(f"✓ image_labels.{col_name} 已添加")
    else:
        print(f"  image_labels.{col_name} 已存在，跳过")

# ── ImageLabelAnnotation 新增字段 ──
cursor.execute("PRAGMA table_info(image_label_annotations)")
anno_columns = [row[1] for row in cursor.fetchall()]

if "skin_mask_data" not in anno_columns:
    cursor.execute("ALTER TABLE image_label_annotations ADD COLUMN skin_mask_data TEXT")
    print("✓ image_label_annotations.skin_mask_data 已添加")
else:
    print("  image_label_annotations.skin_mask_data 已存在，跳过")

conn.commit()
conn.close()
print("数据库迁移完成！")

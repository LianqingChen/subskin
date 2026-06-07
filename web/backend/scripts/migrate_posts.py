"""Add missing columns to posts table and seed categories."""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'subskin.db')

def migrate_posts():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    expected_cols = [
        ('content_preview', 'TEXT'),
        ('post_type', "VARCHAR(20) DEFAULT 'text'"),
        ('video_url', 'VARCHAR'),
        ('video_thumbnail', 'VARCHAR'),
        ('read_count', 'INTEGER DEFAULT 0'),
        ('dwell_time', 'INTEGER DEFAULT 0'),
        ('is_private', 'BOOLEAN DEFAULT 0'),
        ('diary_date', 'DATE'),
        ('mood', 'VARCHAR'),
        ('is_anonymous', 'BOOLEAN DEFAULT 0'),
        ('city', 'VARCHAR(100)'),
    ]

    cursor.execute('PRAGMA table_info(posts)')
    existing = {c[1] for c in cursor.fetchall()}

    for col_name, col_type in expected_cols:
        if col_name not in existing:
            try:
                cursor.execute(f'ALTER TABLE posts ADD COLUMN {col_name} {col_type}')
                print(f'Added column: {col_name} ({col_type})')
            except Exception as e:
                print(f'Error adding {col_name}: {e}')
        else:
            print(f'Already exists: {col_name}')

    conn.commit()

    cursor.execute('PRAGMA table_info(posts)')
    print('\n=== Updated posts table columns ===')
    for c in cursor.fetchall():
        print(f'  {c[1]}: {c[2]}')

    conn.close()


def seed_categories():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    default_categories = [
        ('白白日记', '记录抗白路上的点点滴滴', '📝', 1),
        ('治疗交流', '分享治疗经验与心得', '💊', 2),
        ('日常生活', '生活中的趣事与感悟', '☀️', 3),
        ('互助问答', '提问与解答，病友互助', '🤝', 4),
        ('正能量', '鼓励与支持，一起加油', '💪', 5),
    ]

    for name, desc, icon, order in default_categories:
        cursor.execute(
            'SELECT id FROM community_categories WHERE name = ?',
            (name,)
        )
        if not cursor.fetchone():
            cursor.execute(
                'INSERT INTO community_categories (name, description, icon, "order", created_at) VALUES (?, ?, ?, ?, datetime("now"))',
                (name, desc, icon, order)
            )
            print(f'Seeded category: {name}')
        else:
            print(f'Category already exists: {name}')

    conn.commit()

    cursor.execute('SELECT id, name, icon FROM community_categories ORDER BY "order"')
    print('\n=== Categories ===')
    for row in cursor.fetchall():
        print(f'  {row[0]}: {row[1]} {row[2]}')

    conn.close()


if __name__ == '__main__':
    print('=== Migrating posts table ===')
    migrate_posts()
    print('\n=== Seeding categories ===')
    seed_categories()
    print('\nDone!')

"""
初始化数据库
创建表结构并添加初始管理员账户
"""

import sys
import os
from typing import Optional

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

from web.backend.database.database import engine, Base
from web.backend.database.models import User, CommunityCategory
from web.backend.models.vasi import VASIAssessment, ImageQualityTag, VasiFeedbackSignal, VasiTrainingSample, VasiModelVersion
from web.backend.models.image_label import ImageLabel, ImageLabelAnnotation, ImageLabelLog
from web.backend.services.auth import get_password_hash


def init_db():
    Base.metadata.create_all(bind=engine)
    print("✅ 数据库表创建完成")


def create_admin(username: str, password: str, email: Optional[str] = None):
    from web.backend.database.database import SessionLocal

    db = SessionLocal()

    existing = db.query(User).filter(User.username == username).first()
    if existing:
        print(f"⚠️  用户 {username} 已存在")
        return

    user = User(
        username=username,
        email=email,
        hashed_password=get_password_hash(password),
        is_active=True,
        is_admin=True,
    )
    db.add(user)
    db.commit()
    print(f"✅ 管理员账户 {username} 创建成功")

    db.close()


def seed_community_categories():
    from web.backend.database.database import SessionLocal

    db = SessionLocal()

    categories = [
        {
            "name": "白白日记",
            "description": "记录每一天的心情与变化",
            "icon": "ri-book-3-line",
            "order": 0,
        },
        {
            "name": "治疗分享",
            "description": "分享治疗经历、用药心得",
            "icon": "ri-capsule-line",
            "order": 1,
        },
        {
            "name": "心理支持",
            "description": "互相鼓励，交流心理调适方法",
            "icon": "ri-heart-2-line",
            "order": 2,
        },
        {
            "name": "护肤经验",
            "description": "日常护理、防晒保湿经验",
            "icon": "ri-flask-line",
            "order": 3,
        },
        {
            "name": "日常饮食",
            "description": "饮食禁忌、营养搭配建议",
            "icon": "ri-restaurant-line",
            "order": 4,
        },
        {
            "name": "诊断咨询",
            "description": "诊断过程、检查结果交流",
            "icon": "ri-microscope-line",
            "order": 5,
        },
        {
            "name": "科普百科",
            "description": "新药研发、临床试验动态",
            "icon": "ri-newspaper-line",
            "order": 1,
        },
        {"name": "其他", "description": "其他白癜风相关话题", "icon": "ri-chat-3-line", "order": 7},
    ]

    existing_count = db.query(CommunityCategory).count()
    if existing_count > 0:
        diary_cat = (
            db.query(CommunityCategory)
            .filter(CommunityCategory.name == "白白日记")
            .first()
        )
        if not diary_cat:
            diary_cat = CommunityCategory(
                name="白白日记",
                description="记录每一天的心情与变化",
                icon="ri-book-3-line",
                order=0,
            )
            db.add(diary_cat)
            db.commit()
            print("✅ 新增'白白日记'社区分类")
        else:
            print(f"⚠️  社区分类已存在 {existing_count} 个，跳过初始化")
        db.close()
        return

    for cat in categories:
        category = CommunityCategory(
            name=cat["name"],
            description=cat["description"],
            icon=cat["icon"],
            order=cat["order"],
        )
        db.add(category)

    db.commit()
    print(f"✅ 初始化 {len(categories)} 个社区分类")

    db.close()


if __name__ == "__main__":
    init_db()

    admin_user = os.getenv("ADMIN_USER", "admin")
    admin_pass = os.getenv("ADMIN_PASS", "admin")
    admin_email = os.getenv("ADMIN_EMAIL", None)
    create_admin(admin_user, admin_pass, admin_email)

    seed_community_categories()

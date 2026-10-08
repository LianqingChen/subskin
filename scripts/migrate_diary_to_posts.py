#!/usr/bin/env python3
"""把旧 DiaryEntry / DiaryImage 迁移为分享私密帖子（Post / PostImage）。

背景：日记功能合并到分享后，统一以 Post（is_private=True）作为病情日记。

特点：
- 幂等：用 DiaryEntry.post_id 标记已迁移，重复运行安全。
- 无损：保留 ai_summary / ai_extracted_json / 图片视觉分析结果。
- 从 /root/subskin 目录运行（后端工作目录）。

用法：
    cd /root/subskin && source web/backend/.env && python scripts/migrate_diary_to_posts.py
"""
import sys

sys.path.insert(0, "/root/subskin")

# 先确保表结构就绪（additive 迁移，幂等）
from web.backend.database.models import (
    ensure_diary_columns,
    ensure_post_columns,
    ensure_post_image_columns,
)

ensure_diary_columns()
ensure_post_columns()
ensure_post_image_columns()

from web.backend.database.database import SessionLocal
from web.backend.database.models import (
    CommunityCategory,
    DiaryEntry,
    DiaryImage,
    Post,
    PostImage,
)

# DiaryEntry.mood（good/bad/...） → Post.mood（emoji 字符串）
MOOD_MAP = {
    "good": "🎉好转",
    "bad": "😔低落",
    "anxious": "😔低落",
    "hopeful": "💪坚持中",
    "neutral": "🤔疑问",
}


def main():
    db = SessionLocal()
    try:
        cat = (
            db.query(CommunityCategory)
            .filter(CommunityCategory.name == "白白日记")
            .first()
        )
        if not cat:
            print("ERROR: 找不到「白白日记」分类，请先运行 init_db")
            return
        print(f"目标分类: 白白日记 (id={cat.id})")

        # 仅迁移尚未关联 Post 的日记（幂等）
        entries = db.query(DiaryEntry).filter(DiaryEntry.post_id.is_(None)).all()
        print(f"待迁移日记: {len(entries)} 条")

        migrated = 0
        images_migrated = 0
        for e in entries:
            mood = MOOD_MAP.get(e.mood)
            raw = e.raw_text or ""
            post = Post(
                user_id=e.user_id,
                title=(e.ai_summary or raw or "日记")[:50],
                content=raw or " ",
                content_text=raw,
                content_preview=raw[:100],
                post_type="text",
                category_id=cat.id,
                is_private=True,
                diary_date=e.entry_date,
                mood=mood,
                ai_summary=e.ai_summary,
                ai_extracted_json=e.ai_extracted_json,
            )
            db.add(post)
            db.flush()
            e.post_id = post.id  # 标记已迁移
            db.commit()
            migrated += 1

            imgs = (
                db.query(DiaryImage)
                .filter(DiaryImage.diary_entry_id == e.id)
                .order_by(DiaryImage.order_index.asc())
                .all()
            )
            for idx, im in enumerate(imgs):
                status = im.analysis_status or (
                    "light_done" if im.visual_analysis_json else "pending"
                )
                db.add(
                    PostImage(
                        post_id=post.id,
                        user_id=e.user_id,
                        image_url=im.image_url,
                        body_site=im.body_site,
                        capture_date=im.capture_date,
                        visual_analysis_json=im.visual_analysis_json,
                        analysis_status=status,
                        vasi_assessment_id=im.vasi_assessment_id,
                        order=idx,
                    )
                )
                images_migrated += 1
            db.commit()

        print(f"\n迁移完成: {migrated} 条日记 → 私密帖, {images_migrated} 张图片 → PostImage")

        # 校验
        total = (
            db.query(Post)
            .filter(Post.category_id == cat.id, Post.is_private.is_(True))
            .count()
        )
        total_images = db.query(PostImage).count()
        print(f"校验: 白白日记私密帖共 {total} 条 | PostImage 共 {total_images} 张")
    finally:
        db.close()


if __name__ == "__main__":
    main()

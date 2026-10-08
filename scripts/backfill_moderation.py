"""存量帖子内容补审 — 仅记录不处罚（修复审核管道历史瘫痪的遗留缺口）。

对 content_moderations 表尚无记录的帖子逐条调用安全检测：
- safe：不落行（与线上管道语义一致）
- 非 safe：写入 ContentModeration(status=pending)，但不改动帖子状态、不施加任何处罚
幂等：已有审核记录的帖子跳过。
"""

import sys
import time

sys.path.insert(0, "/root/subskin")

from sqlalchemy import func

from web.backend.database.database import SessionLocal
from web.backend.database.models import ContentModeration, Post
from web.backend.services.content_safety import check_content_safety, determine_auto_action


def main() -> None:
    db = SessionLocal()
    try:
        reviewed_ids = {
            row[0]
            for row in db.query(ContentModeration.post_id)
            .filter(ContentModeration.content_type == "post")
            .filter(ContentModeration.post_id.isnot(None))
            .all()
        }
        posts = db.query(Post).order_by(Post.id).all()
        todo = [p for p in posts if p.id not in reviewed_ids]
        print(f"[backfill] total posts={len(posts)}, already reviewed={len(reviewed_ids)}, todo={len(todo)}", flush=True)

        safe_count = 0
        risky_count = 0
        for idx, post in enumerate(todo, 1):
            title = post.title or ""
            content = post.content_text or post.content or ""
            try:
                result = check_content_safety(title, content)
            except Exception as exc:
                print(f"[backfill] {idx}/{len(todo)} post {post.id} ERROR: {exc}", flush=True)
                continue
            risk_level = result["risk_level"]
            if risk_level == "safe":
                safe_count += 1
                print(f"[backfill] {idx}/{len(todo)} post {post.id} safe", flush=True)
            else:
                auto_action = determine_auto_action(risk_level, result["confidence"])
                record = ContentModeration(
                    post_id=post.id,
                    user_id=post.user_id,
                    content_type="post",
                    content_snapshot=f"{title}\n\n{content[:500]}",
                    risk_level=risk_level,
                    risk_categories=result["risk_categories"],
                    auto_action=auto_action,
                    ai_reason=f"[存量补审·仅记录] {result['reason']}",
                    ai_confidence=result["confidence"],
                    status="pending",
                )
                db.add(record)
                db.commit()
                risky_count += 1
                print(
                    f"[backfill] {idx}/{len(todo)} post {post.id} risk={risk_level} action={auto_action} recorded (no penalty)",
                    flush=True,
                )
            time.sleep(0.3)

        print(f"[backfill] DONE safe={safe_count} risky_recorded={risky_count}", flush=True)
    finally:
        db.close()


if __name__ == "__main__":
    main()

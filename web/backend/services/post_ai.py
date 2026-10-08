"""
帖子 AI 增强服务（日记合并到分享后）

复用 diary_ai / diary_image 的核心 LLM 能力，把数据源/触发点切到 Post / PostImage：
- extract_post_structure: 从帖子正文提取心情/用药/睡眠等 → Post.ai_summary / ai_extracted_json
- analyze_post_images_async: 对帖子图片做轻量视觉分析 → PostImage.visual_analysis_json

与 diary_ai / diary_image 并存（迁移期保留 /diary 兼容），不修改原文件。
"""

import json
import logging
from datetime import date as date_type
from typing import List

logger = logging.getLogger(__name__)


def extract_post_structure(post_id: int) -> None:
    """从帖子正文提取结构化信息（后台线程运行）。

    复用 diary_ai._call_llm_extraction / _rule_based_extraction 核心，
    结果写入 Post.ai_summary / ai_extracted_json，并同步 TreatmentEvent。
    """
    from web.backend.database.database import SessionLocal
    from web.backend.database.models import Post

    db = SessionLocal()
    try:
        post = db.query(Post).filter(Post.id == post_id).first()
        if not post:
            return
        text = (post.content_text or post.content or "").strip()
        if not text:
            return

        # 2026-08-30 隐私加固：私密帖不外送第三方 LLM，降级为本地规则提取
        if getattr(post, "is_private", False):
            result = _rule_based_extraction(text)
            post.ai_summary = result.get("summary") or text[:30]
            post.ai_extracted_json = json.dumps(result, ensure_ascii=False)
            db.commit()
            _sync_treatment_events_for_post(db, post, result)
            logger.info("post_ai: private post %s uses local rule-based extraction", post_id)
            return

        from web.backend.services.diary_ai import (
            _call_llm_extraction,
            _rule_based_extraction,
        )

        result = _call_llm_extraction(text)
        if not result:
            result = _rule_based_extraction(text)
            logger.info("post_ai: rule-based extraction for post %s", post_id)

        post.ai_summary = result.get("summary") or text[:30]
        post.ai_extracted_json = json.dumps(result, ensure_ascii=False)
        db.commit()

        _sync_treatment_events_for_post(db, post, result)
        logger.info("post_ai: 提取完成 post %s", post_id)
    except Exception:
        logger.exception("post_ai: 提取失败 post %s", post_id)
        db.rollback()
    finally:
        db.close()


def _sync_treatment_events_for_post(db, post, result: dict) -> None:
    """将 AI 提取的用药/光疗同步到 TreatmentEvent（source=post_ai）。"""
    from web.backend.database.models import TreatmentEvent

    medication = result.get("medication_taken")
    raw_lower = ((post.content_text or post.content) or "").lower()
    event_date = post.diary_date or (post.created_at.date() if post.created_at else date_type.today())

    # 用药事件
    if medication:
        existing = (
            db.query(TreatmentEvent)
            .filter(
                TreatmentEvent.source == "post_ai",
                TreatmentEvent.source_ref_id == post.id,
                TreatmentEvent.event_type == "medication",
            )
            .first()
        )
        if existing:
            existing.title = medication
            existing.medication_name = medication
            existing.event_date = event_date
        else:
            db.add(
                TreatmentEvent(
                    user_id=post.user_id,
                    event_type="medication",
                    event_date=event_date,
                    title=medication,
                    medication_name=medication,
                    source="post_ai",
                    source_ref_id=post.id,
                )
            )

    # 光疗事件（关键词检测）
    if any(w in raw_lower for w in ["光疗", "照光", "308", "窄谱", "nb-uvb", "puva", "准分子"]):
        existing_photo = (
            db.query(TreatmentEvent)
            .filter(
                TreatmentEvent.source == "post_ai",
                TreatmentEvent.source_ref_id == post.id,
                TreatmentEvent.event_type == "phototherapy",
            )
            .first()
        )
        if not existing_photo:
            db.add(
                TreatmentEvent(
                    user_id=post.user_id,
                    event_type="phototherapy",
                    event_date=event_date,
                    title="光疗记录",
                    source="post_ai",
                    source_ref_id=post.id,
                )
            )

    db.commit()


def analyze_post_images_async(post_id: int) -> None:
    """后台线程：对帖子的所有 pending 图片做轻量视觉分析。

    复用 diary_image.analyze_light 核心视觉调用。
    """
    import threading

    from web.backend.database.database import SessionLocal

    def _run():
        from web.backend.database.models import PostImage

        db = SessionLocal()
        try:
            images = (
                db.query(PostImage)
                .filter(
                    PostImage.post_id == post_id,
                    PostImage.analysis_status.in_(["pending", "failed"]),
                )
                .order_by(PostImage.order.asc())
                .all()
            )
            if not images:
                return

            from web.backend.services.diary_image import analyze_light

            for img in images:
                img.analysis_status = "analyzing"
                db.commit()

                # 同部位历史图，供对比
                history_urls: List[str] = []
                if img.body_site and img.user_id:
                    hist = (
                        db.query(PostImage)
                        .filter(
                            PostImage.user_id == img.user_id,
                            PostImage.body_site == img.body_site,
                            PostImage.id != img.id,
                            PostImage.capture_date.isnot(None),
                        )
                        .order_by(PostImage.capture_date.desc())
                        .first()
                    )
                    if hist:
                        history_urls = [hist.image_url]

                result = analyze_light(img.image_url, img.body_site, history_urls)
                if result:
                    img.visual_analysis_json = json.dumps(result, ensure_ascii=False)
                    img.analysis_status = "light_done"
                else:
                    img.analysis_status = "failed"
                db.commit()

            logger.info("post_ai: 帖子 %s 的 %d 张图片分析完成", post_id, len(images))
        except Exception:
            logger.exception("post_ai: 图片分析异常 post %s", post_id)
            db.rollback()
        finally:
            db.close()

    t = threading.Thread(target=_run, daemon=True)
    t.start()

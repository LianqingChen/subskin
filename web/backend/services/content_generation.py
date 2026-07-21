"""
管理员内容生成服务

基于已收集资料（PubMed、CrossRef、CMA、基金会新闻等）自动生成社区帖子内容。
"""
import json
import logging
import os
import random
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from web.backend.database.database import SessionLocal
from web.backend.database.models import AdminGeneratedPost, CommunityCategory, Tag, User
from web.backend.services.community import CommunityService
from web.backend.utils.llm_config import get_llm_config

logger = logging.getLogger(__name__)

# 内容类型映射
CATEGORY_MAP = {
    "science": {
        "id": 1,  # 治疗分享
        "name": "治疗分享",
        "prompt_style": "科普",
        "mood_pool": ["💭求知", "📖学习", "🌱成长"],
    },
    "psychology": {
        "id": 2,  # 心理支持
        "name": "心理支持",
        "prompt_style": "心理辅导",
        "mood_pool": ["💪坚持中", "❤️温暖", "🌟希望"],
    },
    "news": {
        "id": 6,  # 科普百科
        "name": "科普百科",
        "prompt_style": "新闻",
        "mood_pool": ["📰关注", "🔬探索", "✨兴奋"],
    },
    "daily": {
        "id": 8,  # 白白日记
        "name": "白白日记",
        "prompt_style": "日记",
        "mood_pool": ["📚记录", "📸回忆", "🌙感想"],
    },
}

# 标签池
TAG_POOLS = {
    "science": ["白瘴风科普", "免疑治疗", "新药研究", "临床试验", "皮肤健康", "光疗", "激光治疗", "药物治疗"],
    "psychology": ["心理支持", "情绪管理", "自信心", "社交支持", "家庭关怀", "心理健康", "规避心理"],
    "news": ["最新动态", "行业资讯", "医学前沿", "科研突破", "药企动态", "基金会活动"],
    "daily": ["白白日记", "每日分享", "生活感悟", "经验交流", "日常护理"],
}

# 城市池
CITY_POOL = [
    "北京", "上海", "广州", "深圳", "杭州", "成都", "武汉", "南京",
    "重庆", "西安", "苏州", "郑州", "长春", "天津", "石家庄",
]

IMAGE_KEYWORDS = {
    "science": ["skin health", "dermatology treatment", "vitiligo research", "medical science"],
    "psychology": ["mental health support", "self care wellness", "hope and healing", "support group"],
    "news": ["medical breakthrough", "pharmaceutical research", "healthcare innovation", "clinical study"],
    "daily": ["daily life journal", "healthy lifestyle", "nature healing", "wellness journey"],
}


def _generate_image_urls(tags: List[str], category_key: str, count: int = 2) -> List[str]:
    from_kw = IMAGE_KEYWORDS.get(category_key, ["health wellness"])
    seed_words = tags[:3] + random.sample(from_kw, min(2, len(from_kw)))
    random.shuffle(seed_words)
    keyword = ",".join(seed_words[:3])
    encoded = urllib.parse.quote(keyword)
    return [
        f"https://source.unsplash.com/800x600/?{encoded}",
        f"https://source.unsplash.com/800x600/?{encoded}&sig={random.randint(1, 99999)}",
    ][:count]


def _get_llm_client():
    """获取 LLM 客户端"""
    import openai
    config = get_llm_config("content_safety")
    return openai.OpenAI(api_key=config["api_key"], base_url=config["base_url"])


def _read_latest_raw_data(max_items: int = 20) -> List[Dict[str, Any]]:
    """读取最新的原始采集数据"""
    data_dir = "/root/subskin/data/raw"
    if not os.path.exists(data_dir):
        return []

    items = []
    for fname in sorted(os.listdir(data_dir), reverse=True)[:5]:
        fpath = os.path.join(data_dir, fname)
        if not fpath.endswith(".json"):
            continue
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    items.extend(data[:max_items])
                elif isinstance(data, dict):
                    items.append(data)
        except Exception as e:
            logger.warning(f"Failed to read {fname}: {e}")

    return items[:max_items]


def _extract_source_info(item: Dict[str, Any]) -> Dict[str, Any]:
    """从原始数据中提取来源信息"""
    source = {}
    if "pmid" in item:
        source["type"] = "pubmed"
        source["title"] = item.get("title") or ""
        source["abstract"] = (item.get("abstract") or "")[:500]
        source["authors"] = item.get("authors") or []
        source["url"] = f"https://pubmed.ncbi.nlm.nih.gov/{item['pmid']}/"
        source["date"] = item.get("pubdate") or ""
    elif "doi" in item and "title" in item:
        source["type"] = "crossref"
        source["title"] = item.get("title") or ""
        source["abstract"] = (item.get("abstract") or "")[:500]
        source["url"] = f"https://doi.org/{item['doi']}"
        source["date"] = item.get("published") or ""
    elif "news_title" in item or ("title" in item and "source" in item):
        source["type"] = "foundation"
        source["title"] = item.get("title") or item.get("news_title") or ""
        source["abstract"] = (item.get("content") or item.get("summary") or "")[:500]
        source["url"] = item.get("url", "")
        source["date"] = item.get("date", "")
    else:
        source["type"] = "unknown"
        source["title"] = item.get("title", "")
        source["abstract"] = str(item)[:500]
    return source


def _build_generation_prompt(sources: List[Dict[str, Any]], style: str) -> str:
    """构建 LLM 生成提示词"""
    source_texts = []
    for i, src in enumerate(sources[:3], 1):
        source_texts.append(
            f"【来源 {i}】\n标题: {src['title']}\n"
            f"摘要: {src['abstract']}\n"
            f"链接: {src['url']}\n"
        )

    prompts = {
        "科普": f"""你是 SubSkin 白瘴风科普普及专家。请基于以下真实研究资料，生成一篇通俗易懂的科普普及文章。

要求：
1. 不能虚构信息，必须基于提供的研究资料
2. 用简单、温暖的语言告诉白瘴风患者
3. 标题要吸引人，不超过 20 个字
4. 内容 300-800 字，分段落
5. 末尾加上"编辑来源：基于 XXX 等研究"
6. 不要加加粗体字，不要 markdown 标题符号

参考资料：
{chr(10).join(source_texts)}

请返回 JSON 格式：
{{"title": "标题", "content": "正文", "summary": "摘要", "tags": ["标签1", "标签2"]}}
""",
        "心理辅导": f"""你是 SubSkin 心理辅导员。请基于以下真实资料，生成一篇心理支持文章，帮助白瘴风患者维护心理健康。

要求：
1. 不能虚构信息，必须基于提供的研究/资料
2. 用温暖、鼓励的语气，不要说教
3. 可以分享应对策略、情绪管理方法
4. 标题不超过 20 个字
5. 内容 300-800 字，分段落
6. 末尾加上"编辑来源：基于 XXX 等研究"
7. 不要加粗体字，不要 markdown 标题符号

参考资料：
{chr(10).join(source_texts)}

请返回 JSON 格式：
{{"title": "标题", "content": "正文", "summary": "摘要", "tags": ["标签1", "标签2"]}}
""",
        "新闻": f"""你是 SubSkin 资讯编辑。请基于以下最新资料，生成一篇简洁的行业/研究动态文章。

要求：
1. 不能虚构，严格基于提供的资料
2. 用简洁、专业的新闻语言
3. 标题不超过 20 个字
4. 内容 200-500 字
5. 末尾加上"来源：XXX"
6. 不要加粗体字，不要 markdown 标题符号

参考资料：
{chr(10).join(source_texts)}

请返回 JSON 格式：
{{"title": "标题", "content": "正文", "summary": "摘要", "tags": ["标签1", "标签2"]}}
""",
        "日记": f"""你是 SubSkin 社区达人。请基于以下资料，以第一人称写一篇生活日记式的分享。

要求：
1. 不能虚构，基于真实资料改写
2. 用真诚、贴心的口吻
3. 以"今天想分享..."或类似开头
4. 标题不超过 20 个字
5. 内容 300-600 字，分段落
6. 末尾加上"编辑来源：基于 XXX 等资料"
7. 不要加粗体字，不要 markdown 标题符号

参考资料：
{chr(10).join(source_texts)}

请返回 JSON 格式：
{{"title": "标题", "content": "正文", "summary": "摘要", "tags": ["标签1", "标签2"]}}
""",
    }

    return prompts.get(style, prompts["科普"])


def _generate_single_post(
    sources: List[Dict[str, Any]], style: str, category_key: str
) -> Optional[Dict[str, Any]]:
    """生成单篇内容"""
    try:
        client = _get_llm_client()
        config = get_llm_config("content_safety")
        prompt = _build_generation_prompt(sources, style)

        response = client.chat.completions.create(
            model=config.get("chat_model", "qwen-plus"),
            messages=[
                {
                    "role": "system",
                    "content": "你是 SubSkin 内容生成助手。严格基于提供的研究资料生成内容，不能虚构。只返回 JSON 格式。",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=2000,
            timeout=60,
        )

        raw = response.choices[0].message.content or ""
        # 提取 JSON
        import re
        json_match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not json_match:
            logger.warning("No JSON found in LLM response")
            return None

        result = json.loads(json_match.group())
        return {
            "title": result.get("title", "未命名文章"),
            "content": result.get("content", ""),
            "summary": result.get("summary", ""),
            "tags": result.get("tags", []),
            "sources": sources,
            "category_key": category_key,
        }
    except Exception as e:
        logger.error(f"Content generation failed: {e}")
        return None


def generate_daily_posts(count: int = 10, db: Optional[Session] = None) -> List[int]:
    """
每日自动生成内容

Args:
    count: 生成数量（默认 10篇）
    db: 数据库 session（可选）

Returns:
    生成的草稿 ID 列表
"""
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    created_ids = []
    try:
        raw_data = _read_latest_raw_data(max_items=30)
        if not raw_data:
            logger.warning("No raw data available for content generation")
            return []

        # 按类型分组
        sources_by_type: Dict[str, List[Dict]] = {
            "pubmed": [],
            "crossref": [],
            "foundation": [],
            "unknown": [],
        }
        for item in raw_data:
            info = _extract_source_info(item)
            sources_by_type[info["type"]].append(info)

        # 内容类型配置
        content_configs = [
            ("科普", "science", 4),      # 4 篇科普
            ("心理辅导", "psychology", 3),  # 3 篇心理
            ("新闻", "news", 2),          # 2 篇新闻
            ("日记", "daily", 1),          # 1 篇日记
        ]

        for style, cat_key, num in content_configs:
            # 选择来源
            all_sources = (
                sources_by_type["pubmed"]
                + sources_by_type["crossref"]
                + sources_by_type["foundation"]
            )
            if not all_sources:
                all_sources = sources_by_type["unknown"]

            for _ in range(num):
                # 随机选择 1-3 个来源
                selected = random.sample(all_sources, min(3, len(all_sources)))

                result = _generate_single_post(selected, style, cat_key)
                if not result:
                    continue

                category = CATEGORY_MAP[cat_key]
                tag_pool = TAG_POOLS[cat_key]

                # 合并生成的 tags 和默认 tags
                tags = list(set(result["tags"] + random.sample(tag_pool, min(2, len(tag_pool)))))
                tags = tags[:5]

                # 图片（占位，后续可以从图片库选择）
                images = _generate_image_urls(tags, cat_key, count=2)

                # 心情
                mood = random.choice(category["mood_pool"])

                # 城市
                city = random.choice(CITY_POOL)

                draft = AdminGeneratedPost(
                    title=result["title"],
                    content=result["content"],
                    content_preview=result["summary"][:100] if result["summary"] else result["content"][:100],
                    category_id=category["id"],
                    post_type="long",
                    images=json.dumps(images),
                    tag_names=json.dumps(tags),
                    city=city,
                    mood=mood,
                    source_type=selected[0]["type"],
                    source_refs=json.dumps([{"title": s["title"], "url": s["url"]} for s in selected]),
                    status="draft",
                    ai_confidence=0.85,
                    scheduled_at=datetime.utcnow() + timedelta(hours=random.randint(1, 24)),
                )
                db.add(draft)
                db.commit()
                db.refresh(draft)
                created_ids.append(draft.id)

        logger.info(f"Generated {len(created_ids)} daily posts")
        return created_ids

    except Exception as e:
        logger.error(f"Daily post generation failed: {e}")
        db.rollback()
        return []
    finally:
        if close_db:
            db.close()


def publish_post(draft_id: int, admin_user_id: int, db: Session) -> Optional[int]:
    """将草稿发布为社区帖子

Args:
    draft_id: 草稿 ID
    admin_user_id: 发布者（管理员）ID
    db: 数据库 session

Returns:
    发布后的帖子 ID
"""
    draft = db.query(AdminGeneratedPost).filter(AdminGeneratedPost.id == draft_id).first()
    if not draft:
        raise ValueError("草稿不存在")

    if draft.status == "published":
        raise ValueError("该草稿已发布")

    images = json.loads(draft.images) if draft.images else []
    tags = json.loads(draft.tag_names) if draft.tag_names else []

    service = CommunityService(db)
    post = service.create_post(
        user_id=admin_user_id,
        title=draft.title,
        content=draft.content,
        category_id=draft.category_id,
        content_json=draft.content_json,
        image_urls=images,
        tag_names=tags,
        is_private=False,
        mood=draft.mood,
        is_anonymous=False,
        post_type=draft.post_type,
        city=draft.city,
    )

    draft.status = "published"
    draft.published_post_id = post.id
    draft.published_at = datetime.utcnow()
    db.commit()

    logger.info(f"Published draft {draft_id} as post {post.id}")
    return post.id

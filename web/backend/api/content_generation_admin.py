"""
管理员内容生成 API

前缀 /api/admin/content
"""
import json
import logging
import re
import random
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from web.backend.database.database import get_db
from web.backend.database.models import AdminGeneratedPost, User
from web.backend.services.auth import get_current_user
from web.backend.services.content_generation import generate_daily_posts, publish_post

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/content", tags=["管理员-内容生成"])


class DraftListItem(BaseModel):
    id: int
    title: str
    content_preview: Optional[str] = None
    category_id: int
    category_name: Optional[str] = None
    post_type: str
    status: str
    city: Optional[str] = None
    mood: Optional[str] = None
    tag_names: List[str] = []
    images: List[str] = []
    source_type: Optional[str] = None
    ai_confidence: Optional[float] = None
    scheduled_at: Optional[str] = None
    published_at: Optional[str] = None
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


class DraftDetail(BaseModel):
    id: int
    title: str
    content: str
    content_json: Optional[str] = None
    content_preview: Optional[str] = None
    category_id: int
    category_name: Optional[str] = None
    post_type: str
    status: str
    city: Optional[str] = None
    mood: Optional[str] = None
    tag_names: List[str] = []
    images: List[str] = []
    source_type: Optional[str] = None
    source_refs: List[Dict[str, str]] = []
    ai_confidence: Optional[float] = None
    scheduled_at: Optional[str] = None
    published_post_id: Optional[int] = None
    published_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


class UpdateDraftRequest(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    content_json: Optional[str] = None
    category_id: Optional[int] = None
    tag_names: Optional[List[str]] = None
    images: Optional[List[str]] = None
    city: Optional[str] = None
    mood: Optional[str] = None
    status: Optional[str] = None


class GenerateResponse(BaseModel):
    status: str
    message: str
    created_count: int
    draft_ids: List[int]


class PublishResponse(BaseModel):
    status: str
    post_id: int


def _serialize_draft(draft: AdminGeneratedPost, detail: bool = False) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "id": draft.id,
        "title": draft.title,
        "content_preview": draft.content_preview,
        "category_id": draft.category_id,
        "category_name": draft.category.name if draft.category else None,
        "post_type": draft.post_type,
        "status": draft.status,
        "city": draft.city,
        "mood": draft.mood,
        "tag_names": json.loads(draft.tag_names) if draft.tag_names else [],
        "images": json.loads(draft.images) if draft.images else [],
        "source_type": draft.source_type,
        "ai_confidence": draft.ai_confidence,
        "scheduled_at": draft.scheduled_at.isoformat() if draft.scheduled_at else None,
        "published_at": draft.published_at.isoformat() if draft.published_at else None,
        "created_at": draft.created_at.isoformat() if draft.created_at else None,
    }
    if detail:
        data["content"] = draft.content
        data["content_json"] = draft.content_json
        data["source_refs"] = json.loads(draft.source_refs) if draft.source_refs else []
        data["published_post_id"] = draft.published_post_id
        data["updated_at"] = draft.updated_at.isoformat() if draft.updated_at else None
    return data


@router.get("/drafts", response_model=List[DraftListItem])
async def list_drafts(
    status: Optional[str] = None,
    category_id: Optional[int] = None,
    sort: str = "id_asc",
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    query = db.query(AdminGeneratedPost)
    if status:
        query = query.filter(AdminGeneratedPost.status == status)
    if category_id:
        query = query.filter(AdminGeneratedPost.category_id == category_id)

    total = query.count()
    sort_map = {
        "id_asc": AdminGeneratedPost.id.asc(),
        "id_desc": AdminGeneratedPost.id.desc(),
        "created_asc": AdminGeneratedPost.created_at.asc(),
        "created_desc": AdminGeneratedPost.created_at.desc(),
    }
    order = sort_map.get(sort, AdminGeneratedPost.id.asc())
    drafts = (
        query.order_by(order)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return [_serialize_draft(d) for d in drafts]


@router.get("/drafts/{draft_id}", response_model=DraftDetail)
async def get_draft(
    draft_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    draft = db.query(AdminGeneratedPost).filter(AdminGeneratedPost.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="草稿不存在")

    return _serialize_draft(draft, detail=True)


@router.put("/drafts/{draft_id}", response_model=DraftDetail)
async def update_draft(
    draft_id: int,
    req: UpdateDraftRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    draft = db.query(AdminGeneratedPost).filter(AdminGeneratedPost.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="草稿不存在")

    if draft.status == "published":
        raise HTTPException(status_code=400, detail="已发布的草稿不能修改")

    allowed = {
        "title", "content", "content_json", "category_id",
        "tag_names", "images", "city", "mood", "status",
    }
    for field in allowed:
        if getattr(req, field, None) is not None:
            if field in ("tag_names", "images"):
                value = json.dumps(getattr(req, field))
            else:
                value = getattr(req, field)
            setattr(draft, field, value)

    # Update preview
    if req.content:
        draft.content_preview = req.content[:100]

    draft.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(draft)
    return _serialize_draft(draft, detail=True)


@router.delete("/drafts/{draft_id}")
async def delete_draft(
    draft_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    draft = db.query(AdminGeneratedPost).filter(AdminGeneratedPost.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="草稿不存在")

    db.delete(draft)
    db.commit()
    return {"status": "ok"}


@router.post("/generate", response_model=GenerateResponse)
async def generate_content(
    count: int = 10,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    try:
        draft_ids = generate_daily_posts(count=count, db=db)
        return {
            "status": "ok",
            "message": f"成功生成 {len(draft_ids)} 篇内容",
            "created_count": len(draft_ids),
            "draft_ids": draft_ids,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成失败: {str(e)}")


@router.post("/drafts/{draft_id}/publish", response_model=PublishResponse)
async def publish_draft(
    draft_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    try:
        post_id = publish_post(draft_id, current_user.id, db)
        return {"status": "ok", "post_id": post_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"发布失败: {str(e)}")


class BatchIdsRequest(BaseModel):
    draft_ids: List[int] = Field(..., min_length=1, max_length=100)


@router.post("/drafts/batch-publish")
async def batch_publish(
    req: BatchIdsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    success = []
    failed = []
    for draft_id in req.draft_ids:
        try:
            post_id = publish_post(draft_id, current_user.id, db)
            success.append({"draft_id": draft_id, "post_id": post_id})
        except Exception as e:
            failed.append({"draft_id": draft_id, "error": str(e)})
    return {"success": success, "failed": failed, "total": len(req.draft_ids)}


@router.delete("/drafts/batch")
async def batch_delete(
    req: BatchIdsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    deleted = 0
    for draft_id in req.draft_ids:
        draft = db.query(AdminGeneratedPost).filter(AdminGeneratedPost.id == draft_id).first()
        if draft:
            if draft.status != "published":
                db.delete(draft)
                deleted += 1
    db.commit()
    return {"deleted": deleted, "total": len(req.draft_ids)}


class AiGenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=5, max_length=2000, description="管理员用自然语言描述的生成需求")
    auto_create: bool = Field(default=False, description="是否自动创建草稿")


class AiGenerateSource(BaseModel):
    title: str
    snippet: str
    url: Optional[str] = None
    source_type: str = "knowledge_base"


class AiGenerateResponse(BaseModel):
    title: str
    content: str
    summary: str
    tags: List[str]
    source_refs: List[Dict[str, str]]
    search_sources: List[AiGenerateSource]
    draft_id: Optional[int] = None


@router.post("/ai-generate", response_model=AiGenerateResponse)
async def ai_generate_content(
    req: AiGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    try:
        import openai
        from web.backend.services.rag import search_documents, _keyword_search
        from web.backend.services.content_generation import (
            _read_latest_raw_data,
            _extract_source_info,
            CATEGORY_MAP,
            TAG_POOLS,
            CITY_POOL,
        )
        from web.backend.utils.llm_config import get_llm_config

        config = get_llm_config()
        client = openai.OpenAI(api_key=config["api_key"], base_url=config["base_url"])
        model = config.get("chat_model", "qwen-plus")

        prompt = req.prompt

        # Step 1: Understand admin's intent
        intent_response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "你是内容策划助手。分析管理员的内容生成需求，提取：1) 主题关键词（用于搜索）2) 内容风格（科普/资讯/心理/日记）3) 目标分类（治疗分享/心理支持/科普百科/白白日记）4) 特别要求。返回JSON。",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=400,
            timeout=30,
        )
        intent_raw = intent_response.choices[0].message.content or "{}"
        intent_match = re.search(r"\{.*\}", intent_raw, re.DOTALL)
        intent = json.loads(intent_match.group()) if intent_match else {}
        keywords = intent.get("keywords", [prompt])
        style = intent.get("style", "科普")
        target_category = intent.get("category", "science")
        special_requests = intent.get("special_requests", "")

        # Step 2: Search knowledge base
        search_query = " ".join(keywords) if isinstance(keywords, list) else str(keywords)
        doc_results = search_documents(db, search_query, top_k=5)

        # Step 3: Search raw data
        raw_data = _read_latest_raw_data(max_items=20)
        raw_sources = []
        query_lower = search_query.lower()
        for item in raw_data:
            info = _extract_source_info(item)
            title_lower = (info.get("title", "") + info.get("abstract", "")).lower()
            if any(kw.lower() in title_lower for kw in ([search_query] if isinstance(search_query, str) else keywords)):
                raw_sources.append(info)

        # Step 4: Search encyclopedia
        en_sources = []
        try:
            from web.backend.database.models_encyclopedia import EncyclopediaArticle
            en_articles = (
                db.query(EncyclopediaArticle)
                .filter(EncyclopediaArticle.is_published == True)
                .all()
            )
            for article in en_articles:
                if any(kw.lower() in (article.title + article.summary).lower() for kw in ([search_query] if isinstance(search_query, str) else keywords)):
                    en_sources.append({
                        "title": article.title,
                        "snippet": (article.summary or article.content)[:300],
                        "url": f"/encyclopedia/{article.slug}",
                        "source_type": "encyclopedia",
                    })
        except Exception:
            pass

        # Step 5: Build search sources list
        search_sources = []
        for doc, score in doc_results:
            search_sources.append(AiGenerateSource(
                title=doc.title or "Untitled",
                snippet=(doc.content or "")[:300],
                url=doc.source_url,
                source_type="knowledge_base",
            ))
        for src in raw_sources[:3]:
            search_sources.append(AiGenerateSource(
                title=src.get("title", "Unknown"),
                snippet=src.get("abstract", "")[:300],
                url=src.get("url", ""),
                source_type="raw_data",
            ))
        for src in en_sources[:3]:
            search_sources.append(AiGenerateSource(
                title=src["title"],
                snippet=src["snippet"],
                url=src["url"],
                source_type=src["source_type"],
            ))

        # Step 6: Build generation prompt
        source_texts = []
        source_refs = []
        for s in search_sources:
            source_texts.append(f"【{s.source_type}】{s.title}\n{s.snippet}")
            if s.url:
                source_refs.append({"title": s.title, "url": s.url})

        style_prompts = {
            "科普": "基于以下真实研究资料生成一篇白癜风科普文章。不能虚构，所有信息必须来源于提供的资料。通俗易懂，面向患者。",
            "心理辅导": "基于以下资料生成一篇心理支持文章。温暖鼓励语气。面向白癜风患者。",
            "新闻": "基于以下资料生成一篇简洁的行业动态文章。专业准确。",
            "日记": "基于以下资料以第一人称生成一篇生活分享日记。真诚亲切。",
        }
        style_instruction = style_prompts.get(style, style_prompts["科普"])
        if special_requests:
            style_instruction += f"\n\n管理员特别要求：{special_requests}"

        gen_prompt = f"""{style_instruction}

要求：
1. 标题不超过20字，吸引人
2. 内容300-800字，分段落
3. 末尾标注来源
4. 不要markdown标题符号，不要加粗

参考资料：
{chr(10).join(source_texts[:6])}

请返回JSON：{{"title": "标题", "content": "正文", "summary": "一句话摘要", "tags": ["标签1", "标签2"]}}"""

        # Step 7: Generate content
        gen_response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "你是SubSkin内容生成助手。严格基于资料生成，不虚构。只返回JSON。",
                },
                {"role": "user", "content": gen_prompt},
            ],
            temperature=0.7,
            max_tokens=2000,
            timeout=60,
        )
        gen_raw = gen_response.choices[0].message.content or ""
        gen_match = re.search(r"\{.*\}", gen_raw, re.DOTALL)
        if not gen_match:
            raise HTTPException(status_code=500, detail="AI 生成失败：返回格式异常")
        result = json.loads(gen_match.group())

        title = result.get("title", "未命名")
        content_text = result.get("content", "")
        summary_text = result.get("summary", content_text[:100])
        tags = result.get("tags", [])

        # Auto-create draft if requested
        draft_id = None
        if req.auto_create:
            cat = CATEGORY_MAP.get(target_category, CATEGORY_MAP["science"])
            mood = random.choice(cat["mood_pool"])
            city = random.choice(CITY_POOL)
            tag_pool = TAG_POOLS.get(target_category, TAG_POOLS["science"])
            final_tags = list(set(tags + random.sample(tag_pool, min(2, len(tag_pool)))))[:5]
            draft = AdminGeneratedPost(
                title=title,
                content=content_text,
                content_preview=summary_text[:100],
                category_id=cat["id"],
                post_type="long",
                images=json.dumps([]),
                tag_names=json.dumps(final_tags),
                city=city,
                mood=mood,
                source_type="ai_dialog",
                source_refs=json.dumps(source_refs),
                status="draft",
                ai_confidence=0.85,
            )
            db.add(draft)
            db.commit()
            db.refresh(draft)
            draft_id = draft.id

        return AiGenerateResponse(
            title=title,
            content=content_text,
            summary=summary_text,
            tags=tags,
            source_refs=source_refs,
            search_sources=search_sources,
            draft_id=draft_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("AI generate failed")
        raise HTTPException(status_code=500, detail=f"AI 生成失败: {str(e)}")

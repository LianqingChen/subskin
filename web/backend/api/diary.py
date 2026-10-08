"""
AI病情日记 API
对话式记录 + AI结构化提取 + 日历视图 + 周报
"""
from web.backend.utils.timeutils import iso_utc

import asyncio
import json
import logging
from datetime import date, datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from web.backend.database.database import get_db
from web.backend.database.models import DiaryEntry, DiaryImage, TreatmentEvent, User
from web.backend.services.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Pydantic Models ──


class DiaryImageInput(BaseModel):
    """创建日记时附带的图片信息（前端先上传拿到 url 再提交）"""
    image_url: str = Field(..., description="图片URL（来自 /api/community/upload）")
    body_site: Optional[str] = Field(None, description="照片对应身体部位 key")
    capture_date: Optional[str] = Field(None, description="拍摄/记录日期 YYYY-MM-DD")


class DiaryCreateRequest(BaseModel):
    raw_text: str = Field(..., min_length=1, max_length=2000, description="日记内容")
    input_type: str = Field("text", description="输入类型: text/voice/quick")
    entry_date: Optional[str] = Field(None, description="日记日期 YYYY-MM-DD，默认今天")
    profile_id: Optional[int] = None
    vasi_assessment_id: Optional[int] = None
    images: Optional[List[DiaryImageInput]] = Field(None, description="附带图片列表")


class DiaryQuickRequest(BaseModel):
    """快捷记录 — 一键记录心情/用药"""
    mood: Optional[str] = Field(None, description="心情: good/neutral/bad/anxious/hopeful")
    medication_taken: Optional[str] = Field(None, description="用药记录")
    skin_condition: Optional[str] = Field(None, description="患处: stable/improving/spreading/new_spots")
    sleep_quality: Optional[str] = Field(None, description="睡眠: good/fair/poor")
    stress_level: Optional[int] = Field(None, ge=1, le=5, description="压力 1-5")
    note: Optional[str] = Field(None, max_length=500, description="补充说明")


class DiaryUpdateRequest(BaseModel):
    raw_text: Optional[str] = None
    mood: Optional[str] = None
    sleep_quality: Optional[str] = None
    diet_notes: Optional[str] = None
    medication_taken: Optional[str] = None
    stress_level: Optional[int] = None
    skin_condition: Optional[str] = None
    is_public: Optional[bool] = None


class DiaryImageResponse(BaseModel):
    id: int
    image_url: str
    body_site: Optional[str]
    capture_date: Optional[str]
    visual_analysis: Optional[dict]
    analysis_status: str
    vasi_assessment_id: Optional[int]
    order_index: int

    class Config:
        from_attributes = True


class DiaryResponse(BaseModel):
    id: int
    raw_text: str
    input_type: str
    mood: Optional[str]
    sleep_quality: Optional[str]
    diet_notes: Optional[str]
    medication_taken: Optional[str]
    stress_level: Optional[int]
    skin_condition: Optional[str]
    treatment_events_json: Optional[str]
    ai_summary: Optional[str]
    ai_extracted_json: Optional[str]
    vasi_assessment_id: Optional[int]
    is_public: bool
    post_id: Optional[int]
    entry_date: str
    created_at: str
    images_count: int = 0
    images: List[DiaryImageResponse] = []

    class Config:
        from_attributes = True


class DiaryListResponse(BaseModel):
    total: int
    items: List[DiaryResponse]


class CalendarDayData(BaseModel):
    date: str
    count: int
    moods: List[str]
    has_assessment: bool


class CalendarResponse(BaseModel):
    year: int
    month: int
    days: List[CalendarDayData]


class DailyMoodData(BaseModel):
    date: str
    moods: List[str]


class WeeklySummaryResponse(BaseModel):
    week_start: str
    week_end: str
    entry_count: int
    recorded_days: int
    mood_distribution: dict
    sleep_distribution: dict
    avg_stress_level: Optional[float]
    vasi_count: int
    daily_moods: List[DailyMoodData]
    ai_summary: Optional[str]
    insights: List[str]
    current_streak: int
    recorded_today: bool


# ── Helper ──


def _compute_streak(db: Session, user_id: int) -> tuple:
    """计算连续记录天数（streak）

    口径：从今天开始回溯；若今天未记录但昨天有记录，则从昨天开始回溯，
    即 streak 表示“截至最近一次记录日”的连续天数。
    返回 (streak, recorded_today)
    """
    today = date.today()
    rows = (
        db.query(DiaryEntry.entry_date)
        .filter(DiaryEntry.user_id == user_id)
        .distinct()
        .all()
    )
    recorded_dates = {d for (d,) in rows}
    recorded_today = today in recorded_dates
    check_date = today if recorded_today else today - timedelta(days=1)
    streak = 0
    while check_date in recorded_dates:
        streak += 1
        check_date -= timedelta(days=1)
    return streak, recorded_today


def _image_to_response(img: DiaryImage) -> DiaryImageResponse:
    visual = None
    if img.visual_analysis_json:
        try:
            visual = json.loads(img.visual_analysis_json)
        except Exception:
            visual = None
    return DiaryImageResponse(
        id=img.id,
        image_url=img.image_url,
        body_site=img.body_site,
        capture_date=iso_utc(img.capture_date) if img.capture_date else None,
        visual_analysis=visual,
        analysis_status=img.analysis_status or "pending",
        vasi_assessment_id=img.vasi_assessment_id,
        order_index=img.order_index or 0,
    )


def _entry_to_response(entry: DiaryEntry) -> DiaryResponse:
    images = getattr(entry, "diary_images", None) or []
    return DiaryResponse(
        id=entry.id,
        raw_text=entry.raw_text,
        input_type=entry.input_type or "text",
        mood=entry.mood,
        sleep_quality=entry.sleep_quality,
        diet_notes=entry.diet_notes,
        medication_taken=entry.medication_taken,
        stress_level=entry.stress_level,
        skin_condition=entry.skin_condition,
        treatment_events_json=entry.treatment_events_json,
        ai_summary=entry.ai_summary,
        ai_extracted_json=entry.ai_extracted_json,
        vasi_assessment_id=entry.vasi_assessment_id,
        is_public=entry.is_public or False,
        post_id=entry.post_id,
        entry_date=iso_utc(entry.entry_date) if entry.entry_date else "",
        created_at=iso_utc(entry.created_at) if entry.created_at else "",
        images_count=getattr(entry, "images_count", None) or len(images),
        images=[_image_to_response(im) for im in images],
    )


# ── CRUD Endpoints ──


@router.post("/entries", response_model=DiaryResponse)
async def create_diary_entry(
    req: DiaryCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建日记条目（触发AI结构化提取）"""
    entry_date = date.today()
    if req.entry_date:
        try:
            entry_date = date.fromisoformat(req.entry_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="日期格式错误，应为 YYYY-MM-DD")

    # 每日日记上限（防滥用）
    today_count = (
        db.query(func.count(DiaryEntry.id))
        .filter(
            DiaryEntry.user_id == current_user.id,
            DiaryEntry.entry_date == date.today(),
        )
        .scalar()
        or 0
    )
    if today_count >= 10:
        raise HTTPException(status_code=429, detail="今日日记已达上限（10条）")

    entry = DiaryEntry(
        user_id=current_user.id,
        profile_id=req.profile_id,
        raw_text=req.raw_text,
        input_type=req.input_type,
        entry_date=entry_date,
        vasi_assessment_id=req.vasi_assessment_id,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    # 创建附带的图片记录（图文日记）
    if req.images:
        body_sites = set()
        for idx, im in enumerate(req.images):
            cap_date = None
            if im.capture_date:
                try:
                    cap_date = date.fromisoformat(im.capture_date)
                except ValueError:
                    cap_date = None
            db.add(
                DiaryImage(
                    diary_entry_id=entry.id,
                    user_id=current_user.id,
                    image_url=im.image_url,
                    body_site=im.body_site,
                    capture_date=cap_date or entry_date,
                    order_index=idx,
                    analysis_status="pending",
                )
            )
            if im.body_site:
                body_sites.add(im.body_site)
        entry.images_count = len(req.images)
        if body_sites:
            entry.body_sites_json = json.dumps(list(body_sites), ensure_ascii=False)
        db.commit()
        db.refresh(entry)

        # 异步触发轻量视觉分析（不阻塞响应）
        try:
            from web.backend.services.diary_image import analyze_diary_images_async

            analyze_diary_images_async(entry.id)
        except Exception:
            logger.warning(
                "diary image analysis launch failed for entry %s",
                entry.id,
                exc_info=True,
            )

    # 异步触发AI提取（不阻塞响应）
    try:
        import threading
        from web.backend.services.diary_ai import extract_diary_structure
        t = threading.Thread(
            target=extract_diary_structure,
            args=(entry.id,),
            daemon=True,
        )
        t.start()
    except Exception:
        logger.warning("AI diary extraction launch failed for entry %s", entry.id, exc_info=True)

    return _entry_to_response(entry)


@router.get("/entries", response_model=DiaryListResponse)
async def list_diary_entries(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取日记列表"""
    query = (
        db.query(DiaryEntry)
        .options(joinedload(DiaryEntry.diary_images))
        .filter(DiaryEntry.user_id == current_user.id)
    )

    if start_date:
        try:
            query = query.filter(DiaryEntry.entry_date >= date.fromisoformat(start_date))
        except ValueError:
            pass
    if end_date:
        try:
            query = query.filter(DiaryEntry.entry_date <= date.fromisoformat(end_date))
        except ValueError:
            pass

    total = query.count()
    entries = (
        query.order_by(DiaryEntry.entry_date.desc(), DiaryEntry.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return DiaryListResponse(
        total=total,
        items=[_entry_to_response(e) for e in entries],
    )


@router.get("/entries/{entry_id}", response_model=DiaryResponse)
async def get_diary_entry(
    entry_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取单条日记"""
    entry = (
        db.query(DiaryEntry)
        .filter(DiaryEntry.id == entry_id, DiaryEntry.user_id == current_user.id)
        .first()
    )
    if not entry:
        raise HTTPException(status_code=404, detail="日记不存在")
    return _entry_to_response(entry)


@router.put("/entries/{entry_id}", response_model=DiaryResponse)
async def update_diary_entry(
    entry_id: int,
    req: DiaryUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新日记"""
    entry = (
        db.query(DiaryEntry)
        .filter(DiaryEntry.id == entry_id, DiaryEntry.user_id == current_user.id)
        .first()
    )
    if not entry:
        raise HTTPException(status_code=404, detail="日记不存在")

    update_data = req.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(entry, key, value)

    db.commit()
    db.refresh(entry)
    return _entry_to_response(entry)


@router.delete("/entries/{entry_id}")
async def delete_diary_entry(
    entry_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除日记"""
    entry = (
        db.query(DiaryEntry)
        .filter(DiaryEntry.id == entry_id, DiaryEntry.user_id == current_user.id)
        .first()
    )
    if not entry:
        raise HTTPException(status_code=404, detail="日记不存在")

    db.delete(entry)
    db.commit()
    return {"status": "ok", "deleted_id": entry_id}


# ── Quick Record ──


@router.post("/quick", response_model=DiaryResponse)
async def quick_record(
    req: DiaryQuickRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """快捷记录 — 一键记录心情/用药/睡眠"""
    # 构建raw_text
    parts = []
    if req.mood:
        mood_map = {"good": "😊", "neutral": "😐", "bad": "😢", "anxious": "😰", "hopeful": "🌟"}
        parts.append(f"心情：{mood_map.get(req.mood, req.mood)}")
    if req.medication_taken:
        parts.append(f"用药：{req.medication_taken}")
    if req.skin_condition:
        skin_map = {"stable": "稳定", "improving": "好转", "spreading": "扩散", "new_spots": "新发"}
        parts.append(f"患处：{skin_map.get(req.skin_condition, req.skin_condition)}")
    if req.sleep_quality:
        sleep_map = {"good": "良好", "fair": "一般", "poor": "较差"}
        parts.append(f"睡眠：{sleep_map.get(req.sleep_quality, req.sleep_quality)}")
    if req.stress_level:
        parts.append(f"压力：{req.stress_level}/5")
    if req.note:
        parts.append(f"备注：{req.note}")

    raw_text = " | ".join(parts) if parts else "快捷记录"

    entry = DiaryEntry(
        user_id=current_user.id,
        raw_text=raw_text,
        input_type="quick",
        mood=req.mood,
        medication_taken=req.medication_taken,
        skin_condition=req.skin_condition,
        sleep_quality=req.sleep_quality,
        stress_level=req.stress_level,
        entry_date=date.today(),
        ai_summary=raw_text,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return _entry_to_response(entry)


# ── Calendar View ──


@router.get("/calendar", response_model=CalendarResponse)
async def get_diary_calendar(
    year: int = Query(..., ge=2020, le=2030),
    month: int = Query(..., ge=1, le=12),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取日历视图数据"""
    first_day = date(year, month, 1)
    if month == 12:
        last_day = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = date(year, month + 1, 1) - timedelta(days=1)

    entries = (
        db.query(DiaryEntry)
        .filter(
            DiaryEntry.user_id == current_user.id,
            DiaryEntry.entry_date >= first_day,
            DiaryEntry.entry_date <= last_day,
        )
        .all()
    )

    # 按日期聚合
    day_map: dict = {}
    for e in entries:
        d = iso_utc(e.entry_date)
        if d not in day_map:
            day_map[d] = {"count": 0, "moods": [], "has_assessment": False}
        day_map[d]["count"] += 1
        if e.mood and e.mood not in day_map[d]["moods"]:
            day_map[d]["moods"].append(e.mood)
        if e.vasi_assessment_id:
            day_map[d]["has_assessment"] = True

    days = [
        CalendarDayData(
            date=d,
            count=data["count"],
            moods=data["moods"],
            has_assessment=data["has_assessment"],
        )
        for d, data in sorted(day_map.items())
    ]

    return CalendarResponse(year=year, month=month, days=days)


# ── Weekly Summary ──

# 周报LLM摘要内存缓存：key=(user_id, week_start, entry_count)，控制LLM调用成本
_weekly_llm_cache: dict = {}


def _get_weekly_ai_summary_llm(
    user_id: int, week_start: date, entry_count: int, entries_payload: List[dict]
) -> Optional[str]:
    """调用LLM生成周报总结（带缓存），失败返回None由调用方降级"""
    key = (user_id, iso_utc(week_start), entry_count)
    cached = _weekly_llm_cache.get(key)
    if cached:
        return cached
    try:
        from web.backend.services.diary_ai import generate_weekly_ai_summary

        summary = generate_weekly_ai_summary(entries_payload)
    except Exception:
        logger.warning("Weekly LLM summary failed", exc_info=True)
        summary = None
    if summary:
        if len(_weekly_llm_cache) > 500:
            _weekly_llm_cache.clear()
        _weekly_llm_cache[key] = summary
    return summary


@router.get("/summary/weekly", response_model=WeeklySummaryResponse)
async def get_weekly_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取本周AI摘要"""
    today = date.today()
    # 本周一
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    entries = (
        db.query(DiaryEntry)
        .filter(
            DiaryEntry.user_id == current_user.id,
            DiaryEntry.entry_date >= week_start,
            DiaryEntry.entry_date <= week_end,
        )
        .order_by(DiaryEntry.entry_date)
        .all()
    )

    # 心情/睡眠分布与每日心情
    mood_dist: dict = {}
    sleep_dist: dict = {}
    stress_levels: List[int] = []
    vasi_count = 0
    day_moods: dict = {}
    for e in entries:
        d = iso_utc(e.entry_date)
        if e.mood:
            mood_dist[e.mood] = mood_dist.get(e.mood, 0) + 1
            if e.mood not in day_moods.setdefault(d, []):
                day_moods[d].append(e.mood)
        if e.sleep_quality:
            sleep_dist[e.sleep_quality] = sleep_dist.get(e.sleep_quality, 0) + 1
        if e.stress_level:
            stress_levels.append(e.stress_level)
        if e.vasi_assessment_id:
            vasi_count += 1

    daily_moods = [
        DailyMoodData(
            date=(week_start + timedelta(days=i)).isoformat(),
            moods=day_moods.get((week_start + timedelta(days=i)).isoformat(), []),
        )
        for i in range(7)
    ]
    avg_stress = round(sum(stress_levels) / len(stress_levels), 1) if stress_levels else None

    # 生成简单洞察
    insights = []
    if len(entries) >= 5:
        insights.append(f"本周记录了{len(entries)}条日记，坚持得很好！")
    elif len(entries) >= 1:
        insights.append(f"本周记录了{len(entries)}条日记，继续保持~")
    else:
        insights.append("本周还没有记录，今天开始吧！")

    if mood_dist.get("bad", 0) + mood_dist.get("anxious", 0) > len(entries) * 0.5 and len(entries) > 2:
        insights.append("本周情绪偏低落，记得给自己一些放松时间 🤗")

    if avg_stress is not None and avg_stress >= 4:
        insights.append("本周压力水平偏高，试试深呼吸或散步放松一下 🧘")

    poor_sleep = sleep_dist.get("poor", 0)
    if poor_sleep > 0 and poor_sleep >= sum(sleep_dist.values()) * 0.5:
        insights.append("近期睡眠偏差，尽量保持规律作息 🌙")

    if vasi_count > 0:
        insights.append("本周完成了VASI患处评估，数据追踪很到位 📏")

    # AI摘要：LLM生成（仅当本周有≥1条日记时调用），失败降级为简单拼接
    ai_summary = None
    if entries:
        # 降级拼接：先去掉每条摘要末尾的句读，避免出现“。；”这类标点瑕疵
        summaries = [
            (e.ai_summary or "").strip().rstrip("。；;.！!？? ")
            for e in entries
            if e.ai_summary and e.ai_summary.strip()
        ]
        summaries = [s for s in summaries if s]
        fallback_summary = "；".join(summaries[:5]) if summaries else None

        entries_payload = [
            {
                "date": iso_utc(e.entry_date),
                "mood": e.mood,
                "sleep_quality": e.sleep_quality,
                "stress_level": e.stress_level,
                "skin_condition": e.skin_condition,
                "medication_taken": e.medication_taken,
                "summary": (e.ai_summary or e.raw_text or "")[:100],
            }
            for e in entries
        ]
        ai_summary = await asyncio.to_thread(
            _get_weekly_ai_summary_llm,
            current_user.id,
            week_start,
            len(entries),
            entries_payload,
        )
        if not ai_summary:
            ai_summary = fallback_summary

    streak, recorded_today = _compute_streak(db, current_user.id)

    return WeeklySummaryResponse(
        week_start=iso_utc(week_start),
        week_end=iso_utc(week_end),
        entry_count=len(entries),
        recorded_days=len({iso_utc(e.entry_date) for e in entries}),
        mood_distribution=mood_dist,
        sleep_distribution=sleep_dist,
        avg_stress_level=avg_stress,
        vasi_count=vasi_count,
        daily_moods=daily_moods,
        ai_summary=ai_summary,
        insights=insights,
        current_streak=streak,
        recorded_today=recorded_today,
    )


# ── Stats ──


@router.get("/stats")
async def get_diary_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取日记统计"""
    total = (
        db.query(func.count(DiaryEntry.id))
        .filter(DiaryEntry.user_id == current_user.id)
        .scalar()
        or 0
    )

    # 连续记录天数（今天未记录但昨天有记录时，从昨天起回溯）
    today = date.today()
    streak, recorded_today = _compute_streak(db, current_user.id)

    # 本周记录数
    week_start = today - timedelta(days=today.weekday())
    week_count = (
        db.query(func.count(DiaryEntry.id))
        .filter(
            DiaryEntry.user_id == current_user.id,
            DiaryEntry.entry_date >= week_start,
        )
        .scalar()
        or 0
    )

    return {
        "total_entries": total,
        "current_streak": streak,
        "recorded_today": recorded_today,
        "week_count": week_count,
    }


# ── 图片追加 ──


class AddImagesRequest(BaseModel):
    images: List[DiaryImageInput] = Field(..., min_length=1)


@router.post("/entries/{entry_id}/images", response_model=DiaryResponse)
async def add_diary_images(
    entry_id: int,
    req: AddImagesRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """为日记追加图片（并触发轻量视觉分析）"""
    entry = (
        db.query(DiaryEntry)
        .options(joinedload(DiaryEntry.diary_images))
        .filter(DiaryEntry.id == entry_id, DiaryEntry.user_id == current_user.id)
        .first()
    )
    if not entry:
        raise HTTPException(status_code=404, detail="日记不存在")

    existing_count = getattr(entry, "images_count", None) or 0
    body_sites = set()
    if entry.body_sites_json:
        try:
            body_sites = set(json.loads(entry.body_sites_json))
        except Exception:
            body_sites = set()

    for idx, im in enumerate(req.images):
        cap_date = None
        if im.capture_date:
            try:
                cap_date = date.fromisoformat(im.capture_date)
            except ValueError:
                cap_date = None
        db.add(
            DiaryImage(
                diary_entry_id=entry.id,
                user_id=current_user.id,
                image_url=im.image_url,
                body_site=im.body_site,
                capture_date=cap_date or entry.entry_date,
                order_index=existing_count + idx,
                analysis_status="pending",
            )
        )
        if im.body_site:
            body_sites.add(im.body_site)

    entry.images_count = existing_count + len(req.images)
    if body_sites:
        entry.body_sites_json = json.dumps(list(body_sites), ensure_ascii=False)
    db.commit()
    db.refresh(entry)

    try:
        from web.backend.services.diary_image import analyze_diary_images_async

        analyze_diary_images_async(entry.id)
    except Exception:
        logger.warning(
            "diary image analysis launch failed for entry %s", entry.id, exc_info=True
        )

    return _entry_to_response(entry)


# ── 深度白斑分析（VASI 分割管线）──


@router.post("/images/{image_id}/deep-analyze")
async def deep_analyze_diary_image(
    image_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """对日记图片触发深度白斑分析（VASI），返回关联的评估ID"""
    img = (
        db.query(DiaryImage)
        .filter(DiaryImage.id == image_id, DiaryImage.user_id == current_user.id)
        .first()
    )
    if not img:
        raise HTTPException(status_code=404, detail="图片不存在")
    if img.vasi_assessment_id:
        return {
            "status": "ok",
            "vasi_assessment_id": img.vasi_assessment_id,
            "message": "已分析过",
        }

    from web.backend.services.diary_image import _detect_mime, _load_image_bytes

    image_bytes = _load_image_bytes(img.image_url)
    if not image_bytes:
        raise HTTPException(status_code=400, detail="无法加载图片文件")

    body_site = img.body_site or "face"
    try:
        from web.backend.services.vasi import VASIService

        svc = VASIService(db)
        assessment = await svc.assess_vasi(
            user_id=current_user.id,
            image_file=image_bytes,
            body_site=body_site,
            image_type=_detect_mime(image_bytes),
            image_filename=f"diary_{img.id}.jpg",
            precision="quick",
        )
    except Exception as e:
        logger.warning("deep analyze failed for image %s: %s", image_id, e)
        raise HTTPException(status_code=500, detail=f"深度分析失败：{e}")

    img.vasi_assessment_id = assessment.id
    db.commit()
    return {"status": "ok", "vasi_assessment_id": assessment.id}

"""
白斑变化报告 API
对比报告生成 / 周报月报生成 / 报告列表 / 详情 / 公开分享 / 删除 / 发布到发现
"""
import asyncio
import json
import logging
import secrets
import threading
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from web.backend.database.database import SessionLocal, get_db
from web.backend.database.models import CommunityCategory, SkinReport, User
from web.backend.services.auth import get_current_user
from web.backend.services.skin_report import (
    BODY_SITE_LABELS,
    generate_comparison_report,
    generate_periodic_report,
    preview_periodic_reports,
    synthesize_reports,
)
from web.backend.utils.timeutils import iso_utc

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Pydantic 请求/响应 ──


class ManualAlignmentRequest(BaseModel):
    version: Literal["manual-similarity-v1"]
    reference_id: int = Field(..., gt=0, strict=True)
    moving_id: int = Field(..., gt=0, strict=True)
    scale: float = Field(1.0, ge=.25, le=4, allow_inf_nan=False, strict=True)
    rotation: float = Field(0.0, ge=-180, le=180, allow_inf_nan=False, strict=True)
    x: float = Field(0.0, ge=-1, le=1, allow_inf_nan=False, strict=True)
    y: float = Field(0.0, ge=-1, le=1, allow_inf_nan=False, strict=True)
    confirmed: Literal[True]


class ComparisonReportRequest(BaseModel):
    image_ids: Optional[List[int]] = Field(
        None, min_length=2, description="选中的日记图片ID（≥2），与 vasi_ids 二选一"
    )
    vasi_ids: Optional[List[int]] = Field(
        None, min_length=2, max_length=6, description="选中的 VASI 评估记录ID（≥2），与 image_ids 二选一"
    )
    body_site: Optional[str] = Field(None, description="聚焦部位，空则自动推断")
    profile_id: Optional[int] = None
    manual_alignment: Optional[ManualAlignmentRequest] = None


class ManualComparisonReportRequest(ComparisonReportRequest):
    manual_alignment: ManualAlignmentRequest


class ComparisonPhotoItem(BaseModel):
    image_url: str = Field(..., description="已上传图片 URL")
    body_site: Optional[str] = Field(None, description="身体部位英文 key（face/neck/…）")
    capture_date: Optional[str] = Field(None, description="拍摄日期 YYYY-MM-DD")


class ComparisonPhotosRequest(BaseModel):
    photos: List[ComparisonPhotoItem] = Field(..., min_length=1, max_length=20)


class UpdatePhotoMetaRequest(BaseModel):
    body_site: Optional[str] = Field(None, description="身体部位英文 key（face/neck/…），空=清除")
    capture_date: Optional[str] = Field(None, description="拍摄日期 YYYY-MM-DD，空=清除")


@router.patch("/photos/{image_id}")
async def update_photo_meta(
    image_id: int,
    req: UpdatePhotoMetaRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """编辑白斑照片的元数据（部位/拍摄日期），仅限照片所有者。"""
    from web.backend.database.models import PostImage

    img = (
        db.query(PostImage)
        .filter(PostImage.id == image_id, PostImage.user_id == current_user.id)
        .first()
    )
    if not img:
        raise HTTPException(status_code=404, detail="照片不存在")

    if req.body_site is not None:
        img.body_site = req.body_site.strip() or None
    if req.capture_date is not None:
        value = req.capture_date.strip()
        if not value:
            img.capture_date = None
        else:
            try:
                img.capture_date = date.fromisoformat(value)
            except ValueError:
                raise HTTPException(status_code=400, detail="拍摄日期格式应为 YYYY-MM-DD")
    db.commit()
    return {
        "status": "ok",
        "id": img.id,
        "body_site": img.body_site,
        "capture_date": img.capture_date.isoformat() if img.capture_date else None,
    }


class ReorderPhotosRequest(BaseModel):
    image_ids: List[int] = Field(..., min_length=1, max_length=100, description="按新顺序排列的照片ID")


@router.put("/photos/reorder")
async def reorder_photos(
    req: ReorderPhotosRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """调整白斑照片的展示顺序（order 字段作为同日期照片的排序依据）。"""
    from web.backend.database.models import PostImage

    ids = list(dict.fromkeys(req.image_ids))
    imgs = (
        db.query(PostImage)
        .filter(PostImage.id.in_(ids), PostImage.user_id == current_user.id)
        .all()
    )
    if len(imgs) != len(ids):
        raise HTTPException(status_code=400, detail="部分照片不存在或无权操作")
    by_id = {img.id: img for img in imgs}
    for idx, image_id in enumerate(ids):
        by_id[image_id].order = idx
    db.commit()
    return {"status": "ok"}


@router.delete("/photos/{image_id}")
async def delete_photo(
    image_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除白斑照片（仅限照片所有者；只删除记录，不删除磁盘文件）。"""
    from web.backend.database.models import PostImage

    img = (
        db.query(PostImage)
        .filter(PostImage.id == image_id, PostImage.user_id == current_user.id)
        .first()
    )
    if not img:
        raise HTTPException(status_code=404, detail="照片不存在")
    db.delete(img)
    db.commit()
    return {"status": "ok", "deleted_id": image_id}


class PeriodicReportRequest(BaseModel):
    period_type: str = Field(..., description="weekly / monthly")
    anchor_date: Optional[str] = Field(None, description="目标周期内任意日期 YYYY-MM-DD，默认今天")
    body_sites: Optional[List[str]] = Field(None, description="只包含指定部位，空=全部")
    profile_id: Optional[int] = None
    force: bool = Field(False, description="重新生成已存在的同周期报告")


class ShareToCommunityRequest(BaseModel):
    is_anonymous: bool = Field(False, description="是否匿名发布")
    # 2026-08-30 隐私加固：前端弹窗确认"将公开发布病情摘要"后置 True。
    # 不传不阻断（兼容旧客户端），但审计会记录确认状态。
    public_ack: bool = Field(False, description="用户已确认公开发布")


# ── Helpers ──


def _site_label(body_site: Optional[str]) -> str:
    if not body_site:
        return "全身概览"
    return BODY_SITE_LABELS.get(body_site, body_site)


def _safe_json(raw: Optional[str], default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


def _strip_private_metrics(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """公开访问时移除原始图片 URL（隐私保护）。"""
    metrics = dict(metrics)
    for key in ("first", "last"):
        p = metrics.get(key)
        if isinstance(p, dict) and "image_url" in p:
            metrics[key] = {kk: vv for kk, vv in p.items() if kk != "image_url"}
    sites = metrics.get("sites")
    if isinstance(sites, list):
        cleaned = []
        for s in sites:
            if isinstance(s, dict):
                s = {k: v for k, v in s.items() if k not in ("first_image_url", "last_image_url")}
            cleaned.append(s)
        metrics["sites"] = cleaned
    # 变化最大图对：去掉原始图片 URL
    mcp = metrics.get("max_change_pair")
    if isinstance(mcp, dict):
        cleaned_mcp = {k: v for k, v in mcp.items() if k not in ("first_image_url", "last_image_url")}
        for key in ("first", "last"):
            p = cleaned_mcp.get(key)
            if isinstance(p, dict) and "image_url" in p:
                cleaned_mcp[key] = {kk: vv for kk, vv in p.items() if kk != "image_url"}
        if isinstance(cleaned_mcp.get("align"), dict):
            cleaned_mcp["align"] = {
                k: v for k, v in cleaned_mcp["align"].items() if k not in ("aligned_after_url", "heatmap_url")
            }
        metrics["max_change_pair"] = cleaned_mcp
    # 首末图对配准产物：去掉配准图与热力图 URL（含用户照片，仅所有者可见）
    pa = metrics.get("pair_align")
    if isinstance(pa, dict):
        metrics["pair_align"] = {
            k: v for k, v in pa.items() if k not in ("aligned_after_url", "heatmap_url")
        }
    # 时间轴：去掉逐帧图片 URL 与合成图 URL（合成图含用户照片，仅所有者可见）
    frames = metrics.get("timeline_frames")
    if isinstance(frames, list):
        metrics["timeline_frames"] = [
            {kk: vv for kk, vv in f.items() if kk != "image_url"} if isinstance(f, dict) else f
            for f in frames
        ]
    for pair in [metrics.get("pair_metrics"), *[site.get("pair_metrics") for site in metrics.get("sites", []) if isinstance(site, dict)]]:
        if isinstance(pair, dict):
            pair.pop("photo_measurements", None)
            pair.pop("photo_measurements_as_of", None)
    metrics.pop("timeline_stack_url", None)
    return metrics


def _report_to_dict(report: SkinReport, include_private: bool = True) -> Dict[str, Any]:
    """将 SkinReport ORM 转为响应 dict。"""
    metrics = _safe_json(report.metrics_json, None) or {}
    from web.backend.services.report_measurements import safe_report_metrics
    metrics = safe_report_metrics(metrics)
    # 公开访问时移除原始图片 URL（隐私保护）
    if not include_private and isinstance(metrics, dict):
        metrics = _strip_private_metrics(metrics)

    d: Dict[str, Any] = {
        "id": report.id,
        "report_type": report.report_type,
        "title": report.title,
        "period_start": iso_utc(report.period_start) if report.period_start else None,
        "period_end": iso_utc(report.period_end) if report.period_end else None,
        "body_site": report.body_site,
        "body_site_label": _site_label(report.body_site),
        "narrative": report.narrative if metrics.get("measurement_version") != "legacy" else "历史报告采用旧测量方法，原始内容已保留。本页不将历史估算视为病情变化。",
        "metrics": metrics,
        "insights": _safe_json(report.insights_json, []) if metrics.get("measurement_version") != "legacy" else [],
        "recommendations": _safe_json(report.recommendations_json, []) if metrics.get("measurement_version") != "legacy" else [],
        "trend_chart": None,
        "status": report.status,
        "error_message": report.error_message,
        "is_public": report.is_public or False,
        "share_token": report.share_token,
        "created_at": iso_utc(report.created_at) if report.created_at else None,
        "generated_at": metrics.get("generated_at") if report.status == "completed" else None,
    }
    if include_private:
        d["source_data"] = _safe_json(report.source_data_json, None)
        d["post_id"] = report.post_id
        d["cover_composite_url"] = report.cover_composite_url
    else:
        d["has_cover"] = bool(report.cover_composite_url)
    return d


# ── 生成对比报告 ──


@router.get("/comparison-capabilities")
def comparison_capabilities():
    return {"manual_alignment": True, "same_site_comparison": True, "version": "manual-similarity-v1"}


@router.post("/comparison")
async def create_comparison_report(
    req: ComparisonReportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """生成白斑变化对比报告（基于选中的日记照片或历史 VASI 评估）。

    后台线程异步生成（含配对视觉识别 + 时间轴堆叠图，可能需要 1-2 分钟），
    立即返回 generating 状态的报告，前端在详情页轮询。
    """
    from web.backend.database.models import PostImage
    from web.backend.models.vasi import VASIAssessment

    if not req.image_ids and not req.vasi_ids:
        raise HTTPException(status_code=400, detail="请至少选择 2 张照片或 2 条评估记录")

    # 预校验（部位一致性由服务层二次校验）
    if req.image_ids:
        images = (
            db.query(PostImage)
            .filter(PostImage.id.in_(req.image_ids), PostImage.user_id == current_user.id)
            .all()
        )
        if len(images) < 2:
            raise HTTPException(status_code=400, detail="未能找到足够的有效照片（至少 2 张）")
    else:
        vasi_count = (
            db.query(VASIAssessment)
            .filter(VASIAssessment.id.in_(req.vasi_ids), VASIAssessment.user_id == current_user.id)
            .count()
        )
        if vasi_count < 2:
            raise HTTPException(status_code=400, detail="未能找到足够的有效评估记录（至少 2 条）")

    if req.manual_alignment is not None:
        if bool(req.image_ids) == bool(req.vasi_ids):
            raise HTTPException(status_code=400, detail="请选择一组照片或一组记录")
        selected = req.image_ids or req.vasi_ids or []
        settings = req.manual_alignment.model_dump()
        if len(selected) != 2 or len(set(selected)) != 2 or set(selected) != {settings["reference_id"], settings["moving_id"]}:
            raise HTTPException(status_code=400, detail="手动对齐仅支持当前选择的两张照片")
        from web.backend.services.comparison_alignment import validate_manual_comparison
        prefix = "pi" if req.image_ids else "va"
        validation_owner = current_user.id
        def validate_pair():
            validation_db = SessionLocal()
            try:
                validate_manual_comparison(validation_db, validation_owner,
                                           "%s:%s" % (prefix, selected[0]), "%s:%s" % (prefix, selected[1]), settings, req.body_site)
            finally:
                validation_db.close()
        try:
            await asyncio.to_thread(validate_pair)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception:
            logger.exception("Manual comparison validation failed")
            raise HTTPException(status_code=503, detail="照片暂时无法校验，请稍后重试")

    report = SkinReport(
        user_id=current_user.id,
        profile_id=req.profile_id,
        report_type="comparison",
        title="白斑对比报告 · 生成中…",
        status="generating",
        llm_module="skin_report",
        share_token=secrets.token_urlsafe(16),
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    report_id = report.id
    user_id = current_user.id

    def _run():
        thread_db = SessionLocal()
        try:
            row = thread_db.query(SkinReport).filter(SkinReport.id == report_id).first()
            if not row:
                return
            generate_comparison_report(
                thread_db,
                user_id,
                image_ids=req.image_ids,
                body_site=req.body_site,
                profile_id=req.profile_id,
                report_row=row,
                vasi_ids=req.vasi_ids,
                manual_alignment=req.manual_alignment.model_dump() if req.manual_alignment is not None else None,
            )
            # Completed reports remain in history; no inbox notification.
        except ValueError as e:
            thread_db.rollback()
            row = thread_db.query(SkinReport).filter(SkinReport.id == report_id).first()
            if row:
                row.status = "failed"
                row.error_message = str(e)
                thread_db.commit()
        except Exception:
            logger.exception("skin_report: 对比报告后台生成失败 report=%s", report_id)
            thread_db.rollback()
            try:
                row = thread_db.query(SkinReport).filter(SkinReport.id == report_id).first()
                if row:
                    row.status = "failed"
                    row.error_message = "生成失败，请稍后重试"
                    thread_db.commit()
            except Exception:
                pass
        finally:
            thread_db.close()

    threading.Thread(target=_run, daemon=True).start()
    return _report_to_dict(db.query(SkinReport).filter(SkinReport.id == report_id).first())


@router.post("/comparison/manual")
async def create_manual_comparison_report(
    req: ManualComparisonReportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return await create_comparison_report(req, current_user, db)


@router.post("/comparison-photos")
async def save_comparison_photos(
    req: ComparisonPhotosRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """保存白斑对比照片（存为私有日记帖），供对比报告直接选择，无需先发分享。"""
    from web.backend.database.models import PostImage
    from web.backend.services.community import CommunityService

    category = (
        db.query(CommunityCategory).filter(CommunityCategory.name == "白白日记").first()
        or db.query(CommunityCategory).first()
    )
    if not category:
        raise HTTPException(status_code=500, detail="社区分类缺失")

    svc = CommunityService(db)
    try:
        post = svc.create_post(
            user_id=current_user.id,
            title="白斑对比照片",
            content="（白斑对比照片）",
            category_id=category.id,
            image_metas=[
                {
                    "image_url": p.image_url,
                    "body_site": p.body_site,
                    "capture_date": p.capture_date,
                }
                for p in req.photos
            ],
            is_private=True,
            post_type="image",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    image_ids = [i for (i,) in db.query(PostImage.id).filter(PostImage.post_id == post.id).all()]
    return {"status": "ok", "post_id": post.id, "image_ids": image_ids}


class SynthesizeRequest(BaseModel):
    report_ids: List[int] = Field(..., min_length=2, max_length=6)


@router.post("/synthesize")
async def synthesize_history_reports(
    req: SynthesizeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """基于多份历史报告提炼对比，生成新的对比报告。"""
    try:
        report = await asyncio.to_thread(
            synthesize_reports, db, current_user.id, req.report_ids
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _report_to_dict(report)


# ── 周报 / 月报 ──


def _parse_anchor(raw: Optional[str]) -> Optional[date]:
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        raise HTTPException(status_code=400, detail="anchor_date 格式应为 YYYY-MM-DD")


@router.post("/periodic")
async def create_periodic_report(
    req: PeriodicReportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """生成白斑周报/月报（多部位聚合 + 配对识别 + 封面拼图）。

    后台线程异步生成（含多次视觉模型调用，可能需要 1-3 分钟），
    立即返回 generating 状态的报告，前端轮询详情接口。
    """
    if req.period_type not in ("weekly", "monthly"):
        raise HTTPException(status_code=400, detail="period_type 仅支持 weekly / monthly")
    anchor = _parse_anchor(req.anchor_date)

    from web.backend.services.skin_report import PERIOD_TYPE_NAMES, _period_window

    d_start, d_end = _period_window(req.period_type, anchor or date.today())
    period_name = PERIOD_TYPE_NAMES[req.period_type]

    # Keep one row per user/report-type/period. Reuse failed rows and in-flight
    # rows instead of spawning duplicate background jobs when users tap again.
    existing = (
        db.query(SkinReport)
        .filter(
            SkinReport.user_id == current_user.id,
            SkinReport.report_type == req.period_type,
            SkinReport.period_start == d_start,
        )
        .first()
    )
    if existing and existing.status == "generating":
        return _report_to_dict(existing)
    if existing and existing.status == "completed" and not req.force:
        return _report_to_dict(existing)

    if existing:
        report = existing
        report.profile_id = req.profile_id
        report.title = f"白斑{period_name} · 生成中…"
        report.period_end = d_end
        report.body_site = None
        report.status = "generating"
        report.error_message = None
    else:
        report = SkinReport(
            user_id=current_user.id,
            profile_id=req.profile_id,
            report_type=req.period_type,
            title=f"白斑{period_name} · 生成中…",
            period_start=d_start,
            period_end=d_end,
            body_site=None,
            status="generating",
            llm_module="skin_report",
            share_token=secrets.token_urlsafe(16),
        )
        db.add(report)
    db.commit()
    db.refresh(report)
    report_id = report.id
    user_id = current_user.id

    def _run():
        thread_db = SessionLocal()
        try:
            row = thread_db.query(SkinReport).filter(SkinReport.id == report_id).first()
            if not row:
                return
            generate_periodic_report(
                thread_db,
                user_id,
                req.period_type,
                anchor_date=anchor,
                body_sites=req.body_sites,
                profile_id=req.profile_id,
                force=req.force,
                report_row=row,
            )
            # Completed reports remain in history; no inbox notification.
        except ValueError as e:
            thread_db.rollback()
            row = thread_db.query(SkinReport).filter(SkinReport.id == report_id).first()
            if row:
                row.status = "failed"
                row.error_message = str(e)
                thread_db.commit()
        except Exception:
            logger.exception("skin_report: 周报/月报后台生成失败 report=%s", report_id)
            thread_db.rollback()
            try:
                row = thread_db.query(SkinReport).filter(SkinReport.id == report_id).first()
                if row:
                    row.status = "failed"
                    row.error_message = "生成失败，请稍后重试"
                    thread_db.commit()
            except Exception:
                pass
        finally:
            thread_db.close()

    threading.Thread(target=_run, daemon=True).start()
    return _report_to_dict(db.query(SkinReport).filter(SkinReport.id == report_id).first())


@router.get("/periodic/preview")
async def get_periodic_preview(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """周报/月报快捷生成入口的可用性预览（本周/上周/本月/上月）。"""
    return {"items": preview_periodic_reports(db, current_user.id)}


# ── 报告列表 ──


@router.get("/")
async def list_reports(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    report_type: Optional[str] = Query(None),
    body_site: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取我的报告列表。"""
    query = db.query(SkinReport).filter(SkinReport.user_id == current_user.id)
    if report_type:
        query = query.filter(SkinReport.report_type == report_type)
    if body_site:
        # 报告 body_site 存英文 key（如 left_arm），直接等值过滤
        query = query.filter(SkinReport.body_site == body_site)
    total = query.count()
    reports = (
        query.order_by(SkinReport.created_at.desc()).offset(offset).limit(limit).all()
    )
    # 列表只返回摘要字段
    items = []
    for r in reports:
        from web.backend.services.report_measurements import safe_report_metrics
        m = safe_report_metrics(_safe_json(r.metrics_json, {}) or {})
        exam = m.get("exam") or {}
        qa = m.get("qa") or {}
        mood = m.get("mood") or {}
        items.append(
            {
                "id": r.id,
                "report_type": r.report_type,
                "title": r.title,
                "period_start": iso_utc(r.period_start) if r.period_start else None,
                "period_end": iso_utc(r.period_end) if r.period_end else None,
                "body_site": r.body_site,
                "body_site_label": _site_label(r.body_site),
                "status": r.status,
                "is_public": r.is_public or False,
                "share_token": r.share_token,
                "created_at": iso_utc(r.created_at) if r.created_at else None,
                "generated_at": m.get("generated_at") if r.status == "completed" else None,
                # 列表预览：趋势 + 首末摘要
                "trend": m.get("trend"),
                "has_vasi": m.get("has_vasi"),
                "headline": m.get("headline"),
                "sites_summary": m.get("sites_summary"),
                "has_cover": bool(r.cover_composite_url),
                "cover_composite_url": r.cover_composite_url,
                # 综合健康报告摘要
                "exam_count": exam.get("report_count", 0),
                "exam_risk": exam.get("risk_label"),
                "qa_count": qa.get("question_count", 0),
                "mood_label": mood.get("mood_label"),
                "post_count": mood.get("post_count", 0),
            }
        )
    return {"total": total, "items": items}


# ── 报告详情 ──


@router.get("/{report_id}")
async def get_report(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取报告详情（仅所有者）。"""
    report = (
        db.query(SkinReport)
        .filter(SkinReport.id == report_id, SkinReport.user_id == current_user.id)
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
    from web.backend.services.report_quantification import supplement_report_quantification
    return supplement_report_quantification(db, current_user.id, _report_to_dict(report, include_private=True))


# ── 任意图对按需对比（报告页日期切换器）──

# 简单滑动窗口频控：VLM 调用有成本，防止前端异常轮询打爆
_PAIR_RATE: Dict[int, List[float]] = {}
_PAIR_RATE_WINDOW_SECONDS = 300.0
_PAIR_RATE_LIMIT = 20


def _pair_rate_ok(user_id: int) -> bool:
    import time

    now = time.time()
    bucket = [t for t in _PAIR_RATE.get(user_id, []) if now - t < _PAIR_RATE_WINDOW_SECONDS]
    if len(bucket) >= _PAIR_RATE_LIMIT:
        _PAIR_RATE[user_id] = bucket
        return False
    bucket.append(now)
    _PAIR_RATE[user_id] = bucket
    return True


def _resolve_frame_ref(db: Session, user_id: int, image_id: Optional[int]) -> Optional[str]:
    """旧报告未存 refs 时，按 image_id 反查照片引用（pi: / va:）。"""
    if image_id is None:
        return None
    from web.backend.database.models import PostImage

    if (
        db.query(PostImage.id)
        .filter(PostImage.id == image_id, PostImage.user_id == user_id)
        .first()
    ):
        return f"pi:{image_id}"
    from web.backend.models.vasi import VASIAssessment

    if (
        db.query(VASIAssessment.id)
        .filter(VASIAssessment.id == image_id, VASIAssessment.user_id == user_id)
        .first()
    ):
        return f"va:{image_id}"
    return None


def _lesion_mask_for_ref(db, ref: str):
    """照片引用 → 测评白斑掩膜（热力图用，复用测评分割产物）。"""
    from web.backend.services.skin_report import _lesion_mask_from_layer

    try:
        source, rid = ref.split(":")
        va = None
        if source == "va":
            from web.backend.models.vasi import VASIAssessment

            va = db.query(VASIAssessment).filter(VASIAssessment.id == int(rid)).first()
        else:
            from web.backend.database.models import PostImage
            from web.backend.models.vasi import VASIAssessment

            img = db.query(PostImage).filter(PostImage.id == int(rid)).first()
            if img and img.vasi_assessment_id:
                va = (
                    db.query(VASIAssessment)
                    .filter(VASIAssessment.id == img.vasi_assessment_id)
                    .first()
                )
        if not va:
            return None
        return _lesion_mask_from_layer(getattr(va, "user_lesion_layer", None)) or _lesion_mask_from_layer(
            getattr(va, "ai_lesion_layer", None)
        )
    except Exception:
        return None


def _pair_align_cached(db, user_id: int, ref_a: str, ref_b: str) -> Optional[Dict[str, Any]]:
    """图对配准产物（配准图 + 热力图），按 (user, ref_a, ref_b) 磁盘缓存。

    配准与掩膜差分为纯 CV（无 VLM 成本），缓存只为省重复计算。
    """
    import hashlib

    from web.backend.services.skin_report import _save_aligned_pair
    from web.backend.services.spot_compare import load_photo_ref, resolve_image_bytes

    key = hashlib.sha1(f"v2:{user_id}:{ref_a}:{ref_b}".encode()).hexdigest()[:16]
    cache_dir = Path("data/uploads/reports/pairs")
    cache_file = cache_dir / f"{key}.json"
    if cache_file.exists():
        try:
            data = json.loads(cache_file.read_text())
            if isinstance(data, dict) and data.get("v") == 2:
                return data
        except Exception:
            pass

    info_a = load_photo_ref(db, ref_a)
    info_b = load_photo_ref(db, ref_b)
    if not info_a or not info_b:
        return None
    if info_a["date"] > info_b["date"]:
        info_a, info_b = info_b, info_a
    bytes_a = resolve_image_bytes(info_a["image_url"], info_a.get("image_key"))
    bytes_b = resolve_image_bytes(info_b["image_url"], info_b.get("image_key"))
    if not bytes_a or not bytes_b:
        return None

    out = _save_aligned_pair(
        user_id,
        bytes_a,
        bytes_b,
        _lesion_mask_for_ref(db, info_a["ref"]),
        _lesion_mask_for_ref(db, info_b["ref"]),
    )
    if not out:
        return None
    out["v"] = 2
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(out, ensure_ascii=False))
    except Exception:
        pass
    return out


@router.get("/{report_id}/pair-compare")
async def pair_compare_report(
    report_id: int,
    index_a: int = Query(..., ge=0, description="较早照片在 timeline_frames 中的下标"),
    index_b: int = Query(..., ge=0, description="较晚照片在 timeline_frames 中的下标"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """按需对比报告内任选两张照片（日期切换器数据源）。

    配对识别复用 spot_compare 缓存（同一图对永不重复调用视觉模型），
    首次计算某图对需数秒到数十秒，前端展示加载态。
    """
    report = (
        db.query(SkinReport)
        .filter(SkinReport.id == report_id, SkinReport.user_id == current_user.id)
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
    metrics = _safe_json(report.metrics_json, None) or {}
    frames = metrics.get("timeline_frames") or []
    refs = metrics.get("refs") or []
    if len(frames) < 2:
        raise HTTPException(status_code=400, detail="该报告没有可对比的照片")
    if index_a == index_b or index_a >= len(frames) or index_b >= len(frames):
        raise HTTPException(status_code=400, detail="照片下标无效")
    if not _pair_rate_ok(current_user.id):
        raise HTTPException(status_code=429, detail="操作过于频繁，请稍后再试")

    def _ref(i: int) -> Optional[str]:
        if i < len(refs):
            return refs[i]
        frame = frames[i] if isinstance(frames[i], dict) else {}
        return _resolve_frame_ref(db, current_user.id, frame.get("image_id"))

    ref_a, ref_b = _ref(index_a), _ref(index_b)
    if not ref_a or not ref_b:
        raise HTTPException(status_code=404, detail="照片引用不存在")

    def _compute():
        # VLM 调用可能长达数十秒，放独立线程 + 独立 DB 会话，避免阻塞事件循环
        thread_db = SessionLocal()
        try:
            from web.backend.services.comparison_alignment import compare_report_pair
            return compare_report_pair(thread_db, current_user.id, ref_a, ref_b)
        finally:
            thread_db.close()

    try:
        pair, align = await asyncio.to_thread(_compute)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        logger.exception("Pair comparison failed")
        raise HTTPException(status_code=503, detail="照片暂时无法对比，请稍后重试")

    frame_a, frame_b = frames[index_a], frames[index_b]
    first, last = (
        (frame_a, frame_b)
        if str((frame_a or {}).get("date")) <= str((frame_b or {}).get("date"))
        else (frame_b, frame_a)
    )
    return {
        "first": first,
        "last": last,
        "pair_metrics": (pair or {}).get("merged"),
        "pair_align": align,
    }


# ── 公开访问（无需登录）──


@router.get("/shared/{token}")
async def get_shared_report(token: str, db: Session = Depends(get_db)):
    """公开访问报告（通过 share_token，脱敏：不含原始图片URL）。"""
    report = (
        db.query(SkinReport)
        .filter(SkinReport.share_token == token)
        .filter(SkinReport.is_public == True)  # noqa: E712
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在或已关闭分享")
    return _report_to_dict(report, include_private=False)


# ── 撤销分享（2026-08-30 加固：用户应有"关闭公开分享"的能力）──


@router.post("/{report_id}/unshare")
async def unshare_report(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """撤销报告的公开分享：shared 链接立即失效（原社区帖子保留，用户可另行删除）。"""
    report = (
        db.query(SkinReport)
        .filter(SkinReport.id == report_id, SkinReport.user_id == current_user.id)
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
    report.is_public = False
    # 轮换 share_token，让已流传的旧链接立即失效
    report.share_token = secrets.token_urlsafe(16)
    db.commit()
    try:
        from web.backend.services.audit import AuditLogService

        AuditLogService(db).create_log(
            user_id=current_user.id,
            action="skin_report.unshare",
            target_type="skin_report",
            target_id=report_id,
            scope="private",
            detail="{}",
        )
    except Exception:
        logger.warning("Audit log failed for unshare %s", report_id, exc_info=True)
    return {"status": "ok", "message": "已关闭公开分享"}


# ── 删除 ──


@router.delete("/{report_id}")
async def delete_report(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除报告（仅所有者）。"""
    report = (
        db.query(SkinReport)
        .filter(SkinReport.id == report_id, SkinReport.user_id == current_user.id)
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
    db.delete(report)
    db.commit()
    return {"status": "ok", "deleted_id": report_id}


# ── 发布到发现 ──


@router.post("/{report_id}/share-to-community")
async def share_to_community(
    report_id: int,
    req: ShareToCommunityRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """将报告发布到发现（创建「治疗分享」帖子，内嵌报告链接）。"""
    report = (
        db.query(SkinReport)
        .filter(SkinReport.id == report_id, SkinReport.user_id == current_user.id)
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
    if report.is_public and report.post_id:
        return {"status": "ok", "post_id": report.post_id, "message": "已分享过"}

    from web.backend.services.community import CommunityService

    category = (
        db.query(CommunityCategory).filter(CommunityCategory.name == "治疗分享").first()
    )
    if not category:
        raise HTTPException(status_code=500, detail="社区分类缺失")

    insights = _safe_json(report.insights_json, [])
    site_label = _site_label(report.body_site)
    share_url = f"/share/report/{report.share_token}"

    # 拼接帖子正文
    lines = [f"# {report.title}", ""]
    if report.narrative:
        lines.append(report.narrative)
        lines.append("")
    if insights:
        lines.append("**关键洞察：**")
        for ins in insights:
            lines.append(f"- {ins}")
        lines.append("")
    lines.append(f"> 📊 [查看完整白斑变化报告]({share_url})")
    lines.append("")
    lines.append("> ⚠️ 本文为个人病情记录分享，不构成医疗诊断建议。")
    content = "\n".join(lines)

    # 2026-08-30 隐私加固：报告标题/叙述可能包含用户手输的隐私信息，发布前自动脱敏
    from web.backend.utils.pii_detect import detect_pii, redact_pii

    if detect_pii(f"{report.title}\n{report.narrative or ''}"):
        title, _ = redact_pii(report.title)
        content, _ = redact_pii(content)
        logger.info("Share-to-community PII auto-redacted: report=%s", report_id)

    svc = CommunityService(db)
    post = svc.create_post(
        user_id=current_user.id,
        title=title,
        content=content,
        category_id=category.id,
        post_type="long",
        is_anonymous=req.is_anonymous,
        tag_names=["白斑报告", site_label],
    )

    report.is_public = True
    report.post_id = post.id
    db.commit()

    # 2026-08-30 加固：L3 病情数据公开动作必须留审计记录（原先绕过了 publish 审计）
    try:
        from web.backend.services.audit import AuditLogService

        AuditLogService(db).create_log(
            user_id=current_user.id,
            action="skin_report.share",
            target_type="skin_report",
            target_id=report_id,
            scope="public",
            detail=json.dumps(
                {"post_id": post.id, "public_ack": bool(req.public_ack)},
                ensure_ascii=False,
            ),
        )
    except Exception:
        logger.warning("Audit log failed for share-to-community %s", report_id, exc_info=True)

    return {
        "status": "ok",
        "post_id": post.id,
        "share_url": share_url,
        "message": "已发布到发现",
    }

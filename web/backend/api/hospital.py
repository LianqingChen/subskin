"""医评（/hospitals）API — 医院目录 + 病友公开评价/分享。

分层：本模块只做请求解析、鉴权、异常转换；业务逻辑在 services/hospital.py。
"""

import logging
import threading
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from sqlalchemy.orm import Session

from web.backend.app.middleware.rate_limit import ReadRateLimit, limit_write_for_user
from web.backend.database.database import get_db
from web.backend.database.models import User
from web.backend.exceptions import (
    HospitalNotFoundError,
    HospitalReviewNotFoundError,
    HospitalReviewRejectedError,
)
from web.backend.models.hospital import (
    HospitalCreate,
    HospitalListResponse,
    HospitalResponse,
    HospitalReviewAppealCreate,
    HospitalReviewAppealResponse,
    HospitalReviewCreate,
    HospitalReviewCreateResult,
    HospitalReviewHelpfulResponse,
    HospitalReviewImageUploadResponse,
    HospitalReviewListResponse,
    HospitalReviewReportCreate,
    HospitalReviewReportResponse,
    HospitalReviewResponse,
    HospitalRiskAdminResponse,
)
from web.backend.services.auth import auth, get_current_user_optional
from web.backend.services.hospital import (
    create_appeal,
    create_hospital,
    create_review,
    delete_review,
    get_hospital_response,
    hide_hospital,
    hide_review,
    list_admin_risk,
    list_hospitals,
    list_reviews,
    list_user_reviews,
    moderate_text_async,
    report_count,
    report_review,
    resolve_appeal,
    resolve_report,
    save_review_image,
    seed_official_hospitals,
    toggle_helpful,
)
from web.backend.services.admin_auth import get_admin_user
from web.backend.models.hospital_discovery import HospitalExperienceResponse
from web.backend.services.hospital_experience import experience_summary

logger = logging.getLogger(__name__)

router = APIRouter()

_read_limit = ReadRateLimit()


@router.get("", response_model=HospitalListResponse, dependencies=[Depends(_read_limit)])
def read_hospitals(
    province: Optional[str] = Query(None, max_length=50),
    city: Optional[str] = Query(None, max_length=50),
    q: Optional[str] = Query(None, max_length=100),
    db: Session = Depends(get_db),
):
    """医院目录（含官方收录与病友补充；病友补充条目 origin=community）。"""
    try:
        seed_official_hospitals(db)
    except Exception:
        # 目录种子失败不应让页面整体不可用 —— 仍返回库内既有数据
        logger.exception("seed_official_hospitals failed")
    items = list_hospitals(db, province=province, city=city, q=q)
    return HospitalListResponse(total=len(items), items=items)


@router.get("/reviews/mine", response_model=List[HospitalReviewResponse])
def read_my_reviews(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(auth),
    db: Session = Depends(get_db),
):
    """我的评价（含审核中/已屏蔽状态，仅本人可见）。"""
    return list_user_reviews(db, current_user.id, limit=limit, offset=offset)


@router.get("/experience-summary", response_model=HospitalExperienceResponse, dependencies=[Depends(_read_limit)])
def read_experience_summary(db: Session = Depends(get_db)):
    """Read-only experience statistics; no personal identifiers or clinical outcome scores."""
    return experience_summary(db)


@router.get("/reviews/feed", response_model=HospitalReviewListResponse, dependencies=[Depends(_read_limit)])
def read_review_feed(
    target: Optional[str] = Query(None, max_length=20),
    sort: str = Query("recent", max_length=20),
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """Cross-hospital feed using the same public serialization and moderation as hospital reviews."""
    try:
        total, items, summary = list_reviews(
            db, None, target=target, sort=sort, limit=limit, offset=offset,
            viewer_id=current_user.id if current_user else None,
        )
    except HospitalReviewRejectedError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return HospitalReviewListResponse(total=total, items=items, summary=summary)


@router.get("/{ident}", response_model=HospitalResponse, dependencies=[Depends(_read_limit)])
def read_hospital(ident: str, db: Session = Depends(get_db)):
    try:
        return get_hospital_response(db, ident)
    except HospitalNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{ident}/reviews", response_model=HospitalReviewListResponse, dependencies=[Depends(_read_limit)])
def read_hospital_reviews(
    ident: str,
    target: Optional[str] = Query(None, description="hospital/doctor/treatment/experience"),
    sort: str = Query("recent", description="recent=最新 / helpful=最有用"),
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """公开评价列表（只返回已通过审核且可见的评价）。"""
    try:
        hospital = get_hospital_response(db, ident)
    except HospitalNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    try:
        total, items, summary = list_reviews(
            db, hospital.id, target=target, limit=limit, offset=offset, sort=sort,
            viewer_id=current_user.id if current_user else None,
        )
    except HospitalReviewRejectedError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return HospitalReviewListResponse(total=total, items=items, summary=summary)


@router.post("", response_model=HospitalResponse, status_code=201)
async def submit_hospital(
    payload: HospitalCreate,
    request: Request,
    current_user: User = Depends(auth),
    db: Session = Depends(get_db),
):
    """病友补充医院/院区（省、市、区、详细地址）。立即可见并标注「病友补充·待核实」。"""
    await limit_write_for_user(request, current_user.id)
    _reject_inactive(current_user)
    try:
        return create_hospital(db, current_user.id, payload)
    except HospitalReviewRejectedError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("create hospital failed for user %s", current_user.id)
        raise HTTPException(status_code=500, detail="提交失败，请稍后重试")


@router.post("/{ident}/reviews", response_model=HospitalReviewCreateResult, status_code=201)
async def submit_review(
    ident: str,
    payload: HospitalReviewCreate,
    request: Request,
    current_user: User = Depends(auth),
    db: Session = Depends(get_db),
):
    """发布公开评价（医院 / 医生 / 治疗方案 / 治疗经历）。

    命中手机号等个人信息时自动脱敏；命中疗效夸大用语时标记待复核；
    LLM 内容安全审核在发布后异步执行，高危内容会自动下架。
    """
    await limit_write_for_user(request, current_user.id)
    _reject_inactive(current_user)
    try:
        review, pii_redacted, pii_types, claims, risk = create_review(
            db, current_user.id, ident, payload
        )
    except HospitalNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HospitalReviewRejectedError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("create hospital review failed for user %s", current_user.id)
        raise HTTPException(status_code=500, detail="发布失败，请稍后重试")

    try:
        threading.Thread(target=moderate_text_async, args=(review.id,), daemon=True).start()
    except Exception:
        logger.warning("Failed to start moderation thread for review %s", review.id, exc_info=True)

    risk_level = str(risk.get("level") or "safe")
    if pii_redacted:
        message = "已发布。检测到手机号/邮箱等个人信息，已自动脱敏后再公开。"
    elif risk_level == "blocked":
        message = "已发布，但这条评价含未证实的结论性指控，目前仅你自己可见；修改后可重新提交。"
    elif risk_level == "restricted":
        message = "已发布。这条评价涉及结论性表述，已进入人工复核，期间内容仍公开但排序靠后。"
    elif risk_level == "watch":
        message = "已发布。这条评价情绪化表述较多，我们先做一次复核，内容照常公开。"
    elif claims:
        message = "已发布。内容包含疗效保证类用语，已标记待复核，请注意个人经历不代表治疗效果。"
    else:
        message = "已发布，其他病友现在可以看到这条评价了。"
    return HospitalReviewCreateResult(
        review=review, pii_redacted=pii_redacted, pii_types=pii_types,
        claims_flagged=claims, message=message,
        risk_level=risk_level, risk_score=int(risk.get("score") or 0),
        risk_categories=[str(x) for x in (risk.get("categories") or [])],
        author_hints=[str(x) for x in (risk.get("hints") or [])],
        aggregate_pending=bool(risk.get("aggregate_pending")),
    )


@router.post("/reviews/images", response_model=HospitalReviewImageUploadResponse, status_code=201)
async def upload_review_image(
    request: Request,
    image: UploadFile = File(...),
    current_user: User = Depends(auth),
    db: Session = Depends(get_db),
):
    """上传评价凭证图（费用单/挂号单/处方/检查单）。禁止病情照片。"""
    await limit_write_for_user(request, current_user.id)
    _reject_inactive(current_user)
    try:
        content = await image.read()
    except Exception:
        logger.warning("read review image failed for user %s", current_user.id, exc_info=True)
        raise HTTPException(status_code=400, detail="图片读取失败，请重新选择")
    try:
        url = save_review_image(current_user.id, image.filename or "receipt.jpg", content)
    except HospitalReviewRejectedError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("save hospital review image failed for user %s", current_user.id)
        raise HTTPException(status_code=500, detail="上传失败，请稍后重试")
    return HospitalReviewImageUploadResponse(url=url)


@router.post("/reviews/{review_id}/helpful", response_model=HospitalReviewHelpfulResponse)
async def mark_review_helpful(
    review_id: int,
    current_user: User = Depends(auth),
    db: Session = Depends(get_db),
):
    """给病友评价点「有用」（再点一次取消）。"""
    try:
        count, is_helpful = toggle_helpful(db, current_user.id, review_id)
    except HospitalReviewNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HospitalReviewRejectedError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return HospitalReviewHelpfulResponse(review_id=review_id, helpful_count=count, is_helpful=is_helpful)


@router.delete("/reviews/{review_id}", status_code=204)
async def remove_review(
    review_id: int,
    current_user: User = Depends(auth),
    db: Session = Depends(get_db),
):
    """删除自己的评价（软删除，留审计记录）。"""
    try:
        delete_review(db, current_user.id, review_id)
    except HospitalReviewNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return None


@router.post("/reviews/{review_id}/report", response_model=HospitalReviewReportResponse, status_code=201)
async def report_hospital_review(
    review_id: int,
    payload: HospitalReviewReportCreate,
    request: Request,
    current_user: User = Depends(auth),
    db: Session = Depends(get_db),
):
    """举报一条评价（一人一次，幂等）。

    《网络信息内容生态治理规定》第 16 条要求显著位置提供便捷举报入口并反馈处理结果。
    """
    await limit_write_for_user(request, current_user.id)
    _reject_inactive(current_user)
    try:
        report, count = report_review(db, current_user.id, review_id, payload.reason_code, payload.detail)
    except HospitalReviewNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HospitalReviewRejectedError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("report review failed for user %s", current_user.id)
        raise HTTPException(status_code=500, detail="举报提交失败，请稍后重试")
    return HospitalReviewReportResponse(
        id=report.id, review_id=report.review_id, reason_code=report.reason_code,
        detail=report.detail, status=report.status, created_at=report.created_at,
        report_count=count,
    )


@router.get("/reviews/{review_id}/report-count")
def read_review_report_count(review_id: int, db: Session = Depends(get_db)):
    """公开的举报数量（不暴露举报人身份）。"""
    return {"review_id": review_id, "report_count": report_count(db, review_id)}


@router.post("/reviews/appeals", response_model=HospitalReviewAppealResponse, status_code=201)
async def submit_review_appeal(
    payload: HospitalReviewAppealCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    """提交评价申诉（被评价机构/医生，或认为评价被误判的作者）。

    公开可达、无需登录：机构申诉不应被登录门槛挡住。
    《民法典》第 1028 条：对失实内容应及时采取更正或删除等必要措施。
    """
    await limit_write_for_user(request, 0)
    try:
        return create_appeal(db, payload)
    except HospitalReviewNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HospitalReviewRejectedError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("submit review appeal failed")
        raise HTTPException(status_code=500, detail="申诉提交失败，请稍后重试")


# ── 管理端（仅管理员）：下架病友补充的医院或违规评价 ──

@router.post("/admin/{hospital_id}/visibility", response_model=HospitalResponse)
def admin_set_hospital_visibility(
    hospital_id: int,
    hidden: bool = Query(..., description="true=下架，false=恢复"),
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    try:
        hide_hospital(db, hospital_id, hidden)
        return get_hospital_response(db, str(hospital_id), include_hidden=True)
    except HospitalNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/admin/risk", response_model=HospitalRiskAdminResponse)
def admin_read_risk_board(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    only_pending: bool = Query(True),
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """管理后台医评风控看板：待处理举报/申诉、超时申诉、高冲突评价。"""
    return list_admin_risk(db, limit=limit, offset=offset, only_pending=only_pending)


@router.post("/admin/reports/{report_id}/resolve", status_code=204)
def admin_resolve_report(
    report_id: int,
    upheld: bool = Query(..., description="true=举报成立（下架评价），false=不成立"),
    note: Optional[str] = Query(None, max_length=200),
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    try:
        resolve_report(db, admin.id, report_id, upheld, note)
    except HospitalReviewRejectedError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return None


@router.post("/admin/appeals/{appeal_id}/resolve", response_model=HospitalReviewAppealResponse)
def admin_resolve_appeal(
    appeal_id: int,
    accepted: bool = Query(..., description="true=申诉成立"),
    action: str = Query("keep", description="keep/request_edit/hide/append_note"),
    resolution: Optional[str] = Query(None, max_length=300),
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    try:
        return resolve_appeal(db, admin.id, appeal_id, accepted, action, resolution)
    except HospitalReviewRejectedError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/admin/reviews/{review_id}/visibility", status_code=204)
def admin_set_review_visibility(
    review_id: int,
    hidden: bool = Query(..., description="true=下架，false=恢复"),
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    try:
        hide_review(db, review_id, hidden)
    except HospitalReviewNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return None


def _reject_inactive(user: User) -> None:
    from datetime import datetime as _dt, timezone as _tz

    if user.user_status == "banned":
        raise HTTPException(status_code=403, detail="账号已被封禁，无法发布内容")
    if user.user_status == "muted" and user.muted_until:
        muted_until = user.muted_until.replace(tzinfo=_tz.utc)
        if muted_until > _dt.now(_tz.utc):
            hours = int((muted_until - _dt.now(_tz.utc)).total_seconds() / 3600)
            raise HTTPException(status_code=403, detail=f"账号已被禁言，剩余{hours}小时")

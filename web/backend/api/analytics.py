from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from web.backend.database.database import get_db
from web.backend.database.models import User
from web.backend.services.analytics import AnalyticsService
from web.backend.services.auth import get_current_user

router = APIRouter()

ADMIN_PHONE_ALLOWLIST = {"15810004327", "17319030290", "15978713663", "18790010679"}


async def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
    is_admin = cast(bool, getattr(current_user, "is_admin", False))
    phone = getattr(current_user, "phone", None)
    if not is_admin and phone not in ADMIN_PHONE_ALLOWLIST:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    if not is_admin and phone in ADMIN_PHONE_ALLOWLIST:
        current_user.is_admin = True
        from web.backend.database.database import SessionLocal
        with SessionLocal() as db:
            db_user = db.query(User).filter(User.id == current_user.id).first()
            if db_user and not db_user.is_admin:
                db_user.is_admin = True
                db.commit()
        current_user.is_admin = True
    return current_user


@router.get("/overview")
async def overview(
    admin: User = Depends(get_admin_user), db: Session = Depends(get_db)
)-> dict[str, int]:
    _ = admin
    svc = AnalyticsService(db)
    return svc.get_overview()


@router.get("/trend")
async def trend(
    days: int = Query(30, ge=1, le=90),
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
)-> dict[str, Any]:
    _ = admin
    svc = AnalyticsService(db)
    return svc.get_trend(days)


@router.get("/page-views")
async def page_views(
    days: int = Query(7, ge=1, le=90),
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
)-> list[dict[str, Any]]:
    _ = admin
    svc = AnalyticsService(db)
    return svc.get_page_views(days)


@router.get("/funnel")
async def funnel(
    days: int = Query(30, ge=1, le=90),
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
)-> list[dict[str, Any]]:
    _ = admin
    svc = AnalyticsService(db)
    return svc.get_funnel(days)


@router.get("/feature-usage")
async def feature_usage(
    days: int = Query(7, ge=1, le=90),
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    _ = admin
    svc = AnalyticsService(db)
    return svc.get_feature_usage(days)


@router.get("/registration-trend")
async def registration_trend(
    days: int = Query(14, ge=1, le=90),
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    _ = admin
    svc = AnalyticsService(db)
    return svc.get_registration_trend(days)


@router.get("/user-journeys")
async def user_journeys(
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(50, ge=5, le=200),
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _ = admin
    svc = AnalyticsService(db)
    return svc.get_user_journeys(days, limit)

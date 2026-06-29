from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from web.backend.database.database import get_db
from web.backend.database.models import User
from web.backend.services.admin_auth import get_admin_user
from web.backend.services.analytics import AnalyticsService

router = APIRouter()


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

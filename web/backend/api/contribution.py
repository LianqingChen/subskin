"""Public anonymous statistics and strictly owner-scoped contribution APIs."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from web.backend.database.database import get_db
from web.backend.database.models import User
from web.backend.services import contribution as service
from web.backend.services.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


def no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


@router.get("/overview")
def overview(response: Response, db: Session = Depends(get_db)) -> dict:
    no_store(response)
    return service.overview(db)


@router.get("/distribution")
def distribution(response: Response, db: Session = Depends(get_db)) -> dict:
    no_store(response)
    return service.distribution(db)


@router.get("/me")
def me(
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    no_store(response)
    return service.my_summary(db, user.id)


@router.post("/me/sync")
def sync(
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    no_store(response)
    try:
        return {"added": service.sync_credits(db, user.id)}
    except Exception:
        db.rollback()
        logger.exception("Contribution credit reconciliation failed")
        raise HTTPException(status_code=500, detail="积分更新暂时不可用，请稍后重试")


@router.get("/me/events")
def events(
    response: Response,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    no_store(response)
    return service.my_events(db, user.id, offset, limit)

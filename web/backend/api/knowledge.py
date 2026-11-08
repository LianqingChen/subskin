"""同行·知识/前沿/科研：公开只读接口。

只返回已发布内容；管理员带 ``preview=1`` 可在主站预览未发布内容（附 status）。
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from web.backend.database.database import get_db
from web.backend.exceptions import KnowledgeError
from web.backend.services import knowledge as service
from web.backend.services.auth import get_current_user_optional
from web.backend.utils.knowledge_seed import topic_labels

router = APIRouter()


def _preview(flag: int, user) -> bool:
    return bool(flag) and bool(getattr(user, "is_admin", False))


def _cache(response: Response, preview: bool) -> None:
    # Published content is public; previews must never be cached by proxies.
    response.headers["Cache-Control"] = "no-store" if preview else "public, max-age=300"


def _raise(error: KnowledgeError) -> None:
    raise HTTPException(status_code=error.status_code, detail={"code": error.code, "message": error.message})


@router.get("/cards")
def cards(
    response: Response,
    topic: Optional[str] = Query(None, max_length=40),
    preview: int = Query(0),
    db: Session = Depends(get_db),
    user=Depends(get_current_user_optional),
) -> dict:
    show = _preview(preview, user)
    _cache(response, show)
    return service.list_cards(db, topic, show, topic_labels())


@router.get("/cards/{slug}")
def card(
    slug: str,
    response: Response,
    preview: int = Query(0),
    db: Session = Depends(get_db),
    user=Depends(get_current_user_optional),
) -> dict:
    show = _preview(preview, user)
    _cache(response, show)
    try:
        return service.get_card(db, slug[:80], show)
    except KnowledgeError as error:
        _raise(error)


@router.get("/pipeline")
def pipeline(
    response: Response,
    preview: int = Query(0),
    db: Session = Depends(get_db),
    user=Depends(get_current_user_optional),
) -> dict:
    show = _preview(preview, user)
    _cache(response, show)
    return service.list_pipeline(db, show)


@router.get("/digests")
def digests(
    response: Response,
    limit: int = Query(10, ge=1, le=30),
    preview: int = Query(0),
    db: Session = Depends(get_db),
    user=Depends(get_current_user_optional),
) -> dict:
    show = _preview(preview, user)
    _cache(response, show)
    return service.list_digests(db, show, limit)


@router.get("/entities/{key}/graph")
def entity_graph(
    key: str,
    response: Response,
    preview: int = Query(0),
    db: Session = Depends(get_db),
    user=Depends(get_current_user_optional),
) -> dict:
    show = _preview(preview, user)
    _cache(response, show)
    try:
        return service.entity_graph(db, key[:120], show)
    except KnowledgeError as error:
        _raise(error)


@router.get("/research")
def research(response: Response, db: Session = Depends(get_db)) -> dict:
    response.headers["Cache-Control"] = "no-store"
    return service.research_overview(db)

"""Administrator-only planning archive. Contents never become public assets."""
import logging
from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from web.backend.exceptions import PlanningDocumentError
from web.backend.services.admin_auth import get_admin_user
from web.backend.services.planning_archive import archive

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/planning", tags=["管理员-规划档案"],
                   dependencies=[Depends(get_admin_user)])


def run_read(response: Response, operation: Callable[..., dict], **kwargs: Any) -> dict:
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Vary"] = "Authorization"
    try:
        return operation(**kwargs)
    except PlanningDocumentError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc),
                            headers={"Cache-Control": "private, no-store"}) from exc
    except Exception as exc:
        logger.error("Planning archive read failed (%s)", type(exc).__name__)
        raise HTTPException(status_code=503, detail="规划档案暂时无法读取，请稍后重试",
                            headers={"Cache-Control": "private, no-store"}) from exc


@router.get("")
def list_documents(response: Response, q: str = Query("", max_length=200),
                   category: str = Query("", max_length=30), source: str = Query("", max_length=100),
                   month: str = Query("", max_length=7, pattern=r"^$|^20\d{2}-(0[1-9]|1[0-2])$"),
                   page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=50), refresh: bool = False) -> dict:
    return run_read(response, archive.list_documents, query=q, category=category, source=source,
                    month=month, page=page, page_size=page_size, refresh=refresh)


@router.get("/resolve")
def resolve_document(response: Response, path: str = Query(..., max_length=500)) -> dict:
    return run_read(response, archive.resolve_document, path=path)


@router.get("/document")
def get_document(response: Response, id: str = Query(..., pattern=r"^[a-f0-9]{64}$")) -> dict:
    return run_read(response, archive.get_document, identity=id)

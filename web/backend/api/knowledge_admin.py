"""管理后台·知识审核：列表、状态流转、审核记录、种子导入。"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from web.backend.database.database import get_db
from web.backend.database.models import User
from web.backend.exceptions import KnowledgeError
from web.backend.services import knowledge as service
from web.backend.services.admin_auth import get_admin_user
from web.backend.utils.knowledge_seed import read_seed

router = APIRouter(prefix="/api/admin/knowledge", tags=["管理员-知识审核"])


class TransitionBody(BaseModel):
    to: str = Field(..., max_length=20)
    note: str = Field("", max_length=1000)
    reviewer_label: str = Field("", max_length=100)


def _raise(error: KnowledgeError) -> None:
    raise HTTPException(status_code=error.status_code, detail={"code": error.code, "message": error.message})


@router.get("/{kind}")
def list_items(
    kind: str,
    status: Optional[str] = Query(None, max_length=20),
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
) -> dict:
    try:
        return service.admin_list(db, kind, status)
    except KnowledgeError as error:
        _raise(error)


@router.post("/{kind}/{item_id}/transition")
def transition(
    kind: str,
    item_id: int,
    body: TransitionBody,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
) -> dict:
    try:
        return service.transition(db, kind, item_id, body.to, admin.id, body.note, body.reviewer_label)
    except KnowledgeError as error:
        db.rollback()
        _raise(error)


@router.get("/{kind}/{item_id}/logs")
def logs(
    kind: str,
    item_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
) -> dict:
    try:
        return {"items": service.review_logs(db, kind, item_id)}
    except KnowledgeError as error:
        _raise(error)


@router.post("/seed/import")
def import_seed(db: Session = Depends(get_db), admin: User = Depends(get_admin_user)) -> dict:
    """Load web/shared/knowledge/seed.json. New rows are drafts; reviewed rows are never touched."""
    data = read_seed()
    if data is None:
        raise HTTPException(status_code=404, detail={"code": "NO_SEED", "message": "没有找到知识种子文件"})
    return {"version": data.get("version"), "stats": service.load_seed(db, data)}

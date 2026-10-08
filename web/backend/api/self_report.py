"""用户自报事实与微询问 API（图像数据库专项 SS-32/33；设计见研究文档 08）。

只返回/写入当前登录用户自己的数据；答案是用户自述（T1），不是临床标签。
"""
import logging
from datetime import datetime
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from web.backend.database.database import get_db
from web.backend.database.models import User as DBUser
from web.backend.services import self_report as svc
from web.backend.services.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


def _raise(err: svc.SelfReportError) -> None:
    status = 403 if err.code.startswith("FORBIDDEN") else 400
    raise HTTPException(status_code=status, detail={"code": err.code, "message": str(err)})


class NextRequest(BaseModel):
    trigger: str = Field(..., max_length=20)
    body_site: Optional[str] = Field(None, max_length=50)
    session_id: Optional[str] = Field(None, max_length=64)


class AnswerRequest(BaseModel):
    question_id: str = Field(..., max_length=8)
    answer: Any
    body_site: Optional[str] = Field(None, max_length=50)
    profile_id: Optional[int] = None
    session_id: Optional[str] = Field(None, max_length=64)
    source: str = Field("micro_ask", pattern="^(micro_ask|checklist)$")


class DismissRequest(BaseModel):
    question_id: str = Field(..., max_length=8)
    body_site: Optional[str] = Field(None, max_length=50)
    session_id: Optional[str] = Field(None, max_length=64)


class FactOut(BaseModel):
    question_id: str
    question_version: str
    body_site: Optional[str] = None
    answer: Any
    source: str
    answered_at: datetime


@router.post("/next")
def next_questions(
    data: NextRequest,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    try:
        qs = svc.next_questions(
            db, current_user.id, data.trigger, body_site=data.body_site, session_id=data.session_id
        )
    except svc.SelfReportError as err:
        _raise(err)
    return {"questions": qs}


@router.post("/answer", response_model=FactOut, status_code=201)
def answer(
    data: AnswerRequest,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    try:
        fact = svc.record_answer(
            db, current_user.id, data.question_id, data.answer, body_site=data.body_site,
            profile_id=data.profile_id, session_id=data.session_id, source=data.source,
        )
    except svc.SelfReportError as err:
        _raise(err)
    return next(
        f for f in svc.latest_facts(db, current_user.id)
        if f["question_id"] == fact.question_id and f["body_site"] == fact.body_site
    )


@router.post("/dismiss", status_code=204)
def dismiss(
    data: DismissRequest,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
):
    try:
        svc.dismiss(db, current_user.id, data.question_id, body_site=data.body_site, session_id=data.session_id)
    except svc.SelfReportError as err:
        _raise(err)


@router.get("/facts", response_model=List[FactOut])
def facts(db: Session = Depends(get_db), current_user: DBUser = Depends(get_current_user)):
    return svc.latest_facts(db, current_user.id)

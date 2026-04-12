"""
RAG 问答 API
基于知识库回答用户问题
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from web.backend.database.database import get_db
from web.backend.models.rag import QuestionRequest, QuestionResponse
from web.backend.services.rag import answer_question
from web.backend.services.auth import auth
from web.backend.database.models import User

router = APIRouter()


@router.post("/ask", response_model=QuestionResponse)
def ask_question(
    request: QuestionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(auth),
):
    """提问，基于知识库 RAG 回答
    需要登录
    """
    return answer_question(
        db=db,
        question=request.question,
        conversation_id=request.conversation_id,
        user_id=current_user.id,
    )


@router.post("/ask-public", response_model=QuestionResponse)
def ask_question_public(request: QuestionRequest, db: Session = Depends(get_db)):
    """公开提问（不需要登录，但不保存对话历史）"""
    return answer_question(
        db=db, question=request.question, conversation_id=None, user_id=None
    )

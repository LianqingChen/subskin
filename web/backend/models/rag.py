"""
RAG 问答数据模型
"""

from typing import Optional, List
from pydantic import BaseModel


class QuestionRequest(BaseModel):
    question: str
    conversation_id: Optional[str] = None


class Source(BaseModel):
    title: str
    url: str
    snippet: str


class QuestionResponse(BaseModel):
    answer: str
    sources: List[Source]

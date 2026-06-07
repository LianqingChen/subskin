"""RAG 问答数据模型。"""

from typing import Optional

from pydantic import BaseModel


class QuestionRequest(BaseModel):
    question: str
    conversation_id: Optional[str] = None
    mode: Optional[str] = None  # "knowledge" | "counseling"


class AttachmentInfo(BaseModel):
    temp_id: str
    temp_url: str
    mime_type: str
    size: int


class QuestionRequestWithAttachments(BaseModel):
    question: str
    conversation_id: Optional[str] = None
    attachment_ids: Optional[list[str]] = None
    mode: Optional[str] = None  # "knowledge" | "counseling"


class Source(BaseModel):
    title: str
    url: str
    snippet: str
    source_tier: str = "C"
    source_name: str = ""
    authority_weight: float = 1.0


class QuestionResponse(BaseModel):
    answer: str
    sources: list[Source]
    remaining_quota: Optional[int] = None
    is_guest: Optional[bool] = None


class TempUploadResponse(BaseModel):
    temp_url: str
    temp_id: str
    mime_type: str
    size: int


class ConfirmActionRequest(BaseModel):
    conversation_id: str
    card_type: str
    card_data: dict[str, object]
    action: str


class ConfirmActionResponse(BaseModel):
    success: bool
    message: str
    resource_id: Optional[int] = None

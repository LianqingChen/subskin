"""
模块提示词管理员 API

前缀 /api/admin/prompts — 用于管理后台编辑各业务模块的提示词模板，
持续迭代白斑识别 / 体检解读 / 报告叙事的准确度。
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from web.backend.database.database import get_db
from web.backend.database.models import LLMPrompt
from web.backend.services.auth import auth
from web.backend.services.llm_prompt_service import LLMPromptService
from web.backend.utils.timeutils import iso_utc

router = APIRouter(prefix="/api/admin/prompts", tags=["管理员-提示词"])


def _serialize_prompt(p: LLMPrompt) -> Dict[str, Any]:
    return {
        "id": p.id,
        "module_key": p.module_key,
        "prompt_key": p.prompt_key,
        "prompt_name": p.prompt_name,
        "prompt_text": p.prompt_text,
        "has_default": bool(p.default_text),
        "version": p.version,
        "is_active": p.is_active,
        "updated_by": p.updated_by,
        "created_at": iso_utc(p.created_at) if p.created_at else None,
        "updated_at": iso_utc(p.updated_at) if p.updated_at else None,
    }


class UpdatePromptRequest(BaseModel):
    prompt_text: str
    prompt_name: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("", response_model=List[Dict[str, Any]])
async def list_prompts(
    module_key: Optional[str] = None,
    current_user=Depends(auth),
    db: Session = Depends(get_db),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return [_serialize_prompt(p) for p in LLMPromptService.list_prompts(db, module_key)]


@router.get("/{module_key}/{prompt_key}", response_model=Dict[str, Any])
async def get_prompt(
    module_key: str,
    prompt_key: str,
    current_user=Depends(auth),
    db: Session = Depends(get_db),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    p = (
        db.query(LLMPrompt)
        .filter(
            LLMPrompt.module_key == module_key,
            LLMPrompt.prompt_key == prompt_key,
        )
        .first()
    )
    if not p:
        raise HTTPException(status_code=404, detail="提示词配置不存在")
    return _serialize_prompt(p)


@router.put("/{module_key}/{prompt_key}", response_model=Dict[str, Any])
async def upsert_prompt(
    module_key: str,
    prompt_key: str,
    req: UpdatePromptRequest,
    current_user=Depends(auth),
    db: Session = Depends(get_db),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    if not req.prompt_text or not req.prompt_text.strip():
        raise HTTPException(status_code=400, detail="提示词内容不能为空")

    p = LLMPromptService.upsert_prompt(
        db, module_key, prompt_key, req.prompt_text, updated_by=current_user.id
    )
    if not p:
        raise HTTPException(status_code=500, detail="保存失败，请稍后重试")
    if req.prompt_name is not None:
        p.prompt_name = req.prompt_name
    if req.is_active is not None:
        p.is_active = req.is_active
    db.commit()
    db.refresh(p)
    return _serialize_prompt(p)


@router.post("/{module_key}/{prompt_key}/reset", response_model=Dict[str, Any])
async def reset_prompt(
    module_key: str,
    prompt_key: str,
    current_user=Depends(auth),
    db: Session = Depends(get_db),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    p = LLMPromptService.reset_prompt(db, module_key, prompt_key)
    if not p:
        raise HTTPException(status_code=404, detail="该提示词无内置默认模板")
    return _serialize_prompt(p)

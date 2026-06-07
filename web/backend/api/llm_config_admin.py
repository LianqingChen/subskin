"""
LLM 模块配置管理员 API

前缀 /api/admin/llm
"""

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from web.backend.database.database import get_db
from web.backend.database.models import LLMModuleConfig
from web.backend.services.auth import auth
from web.backend.services.llm_config_service import (
    LLMConfigService,
    RECOMMENDED_PROVIDERS,
    decrypt_api_key,
)

router = APIRouter(prefix="/api/admin/llm", tags=["管理员-LLM配置"])


class ModuleConfigItem(BaseModel):
    id: int
    module_key: str
    module_name: str
    module_description: Optional[str] = None
    provider: str
    chat_model: Optional[str] = None
    vision_model: Optional[str] = None
    embedding_model: Optional[str] = None
    base_url: Optional[str] = None
    is_active: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


class ModuleConfigDetail(ModuleConfigItem):
    api_key: Optional[str] = None


class UpdateModuleConfigRequest(BaseModel):
    module_name: Optional[str] = None
    module_description: Optional[str] = None
    provider: Optional[str] = None
    chat_model: Optional[str] = None
    vision_model: Optional[str] = None
    embedding_model: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    is_active: Optional[bool] = None


class TestConfigRequest(BaseModel):
    provider: Optional[str] = None
    chat_model: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None


class TestConfigResponse(BaseModel):
    ok: bool
    model: Optional[str] = None
    provider: Optional[str] = None
    response: Optional[str] = None
    error: Optional[str] = None


class ProviderInfo(BaseModel):
    key: str
    name: str
    models: Dict[str, List[str]]
    base_url: str


class ProvidersResponse(BaseModel):
    providers: List[ProviderInfo]


def _serialize_module(module: LLMModuleConfig, with_api_key: bool = False) -> Dict[str, Any]:
    data = {
        "id": module.id,
        "module_key": module.module_key,
        "module_name": module.module_name,
        "module_description": module.module_description,
        "provider": module.provider,
        "chat_model": module.chat_model,
        "vision_model": module.vision_model,
        "embedding_model": module.embedding_model,
        "base_url": module.base_url,
        "is_active": module.is_active,
        "created_at": module.created_at.isoformat() if module.created_at else None,
        "updated_at": module.updated_at.isoformat() if module.updated_at else None,
    }
    if with_api_key:
        data["api_key"] = decrypt_api_key(module.api_key) or ""
    return data


@router.get("/modules", response_model=List[ModuleConfigItem])
async def list_modules(
    current_user=Depends(auth),
    db: Session = Depends(get_db),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    modules = LLMConfigService.get_all_modules(db)
    return [_serialize_module(m) for m in modules]


@router.get("/modules/{module_key}", response_model=ModuleConfigDetail)
async def get_module(
    module_key: str,
    current_user=Depends(auth),
    db: Session = Depends(get_db),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    module = LLMConfigService.get_module_by_key(db, module_key)
    if not module:
        raise HTTPException(status_code=404, detail="模块配置不存在")
    return _serialize_module(module, with_api_key=True)


@router.put("/modules/{module_key}", response_model=ModuleConfigDetail)
async def update_module(
    module_key: str,
    req: UpdateModuleConfigRequest,
    current_user=Depends(auth),
    db: Session = Depends(get_db),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    module = LLMConfigService.get_module_by_key(db, module_key)
    if not module:
        raise HTTPException(status_code=404, detail="模块配置不存在")

    update_data = req.model_dump(exclude_unset=True)
    updated = LLMConfigService.update_module(db, module_key, update_data)
    if not updated:
        raise HTTPException(status_code=500, detail="更新失败")
    return _serialize_module(updated, with_api_key=True)


@router.post("/modules/{module_key}/test", response_model=TestConfigResponse)
async def test_module_config(
    module_key: str,
    req: Optional[TestConfigRequest] = None,
    current_user=Depends(auth),
    db: Session = Depends(get_db),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    module = LLMConfigService.get_module_by_key(db, module_key)
    if not module:
        raise HTTPException(status_code=404, detail="模块配置不存在")

    override = None
    if req:
        override = req.model_dump(exclude_unset=True)
        if not any(override.values()):
            override = None

    result = LLMConfigService.test_config(module_key, config_override=override)
    return TestConfigResponse(**result)


@router.get("/providers", response_model=ProvidersResponse)
async def list_providers(
    current_user=Depends(auth),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    providers = []
    for key, info in RECOMMENDED_PROVIDERS.items():
        providers.append(
            ProviderInfo(
                key=key,
                name=info["name"],
                models=info.get("models", {}),
                base_url=info.get("base_url", ""),
            )
        )
    return ProvidersResponse(providers=providers)


class RefreshResponse(BaseModel):
    status: str
    updated_count: int


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_from_env(
    current_user=Depends(auth),
    db: Session = Depends(get_db),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    count = LLMConfigService.refresh_from_env(db)
    return RefreshResponse(status="ok", updated_count=count)


BACKUP_PATH = "/root/subskin/data/llm_config_backup.json"


class BackupResponse(BaseModel):
    status: str
    modules: List[Dict[str, Any]]
    backup_time: Optional[str] = None


@router.post("/backup", response_model=BackupResponse)
async def create_backup(
    current_user=Depends(auth),
    db: Session = Depends(get_db),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    modules = LLMConfigService.get_all_modules(db)
    backup_data = {
        "backup_time": datetime.now(timezone.utc).isoformat(),
        "modules": [_serialize_module(m, with_api_key=True) for m in modules],
    }

    os.makedirs(os.path.dirname(BACKUP_PATH), exist_ok=True)
    with open(BACKUP_PATH, "w", encoding="utf-8") as f:
        json.dump(backup_data, f, ensure_ascii=False, indent=2)

    return BackupResponse(
        status="ok",
        modules=backup_data["modules"],
        backup_time=backup_data["backup_time"],
    )


@router.get("/backup", response_model=BackupResponse)
async def get_backup(current_user=Depends(auth)):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    if not os.path.exists(BACKUP_PATH):
        return BackupResponse(status="not_found", modules=[], backup_time=None)

    with open(BACKUP_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    return BackupResponse(
        status="ok",
        modules=data.get("modules", []),
        backup_time=data.get("backup_time"),
    )


class RestoreResponse(BaseModel):
    status: str
    updated_count: int


@router.post("/backup/restore", response_model=RestoreResponse)
async def restore_backup(
    current_user=Depends(auth),
    db: Session = Depends(get_db),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    if not os.path.exists(BACKUP_PATH):
        raise HTTPException(status_code=404, detail="没有找到备份文件")

    with open(BACKUP_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    updated = []
    for mod_data in data.get("modules", []):
        module_key = mod_data.get("module_key")
        if not module_key:
            continue
        update_data = {k: v for k, v in mod_data.items() if k in (
            "provider", "chat_model", "vision_model", "embedding_model", "api_key", "base_url", "is_active"
        )}
        module = LLMConfigService.update_module(db, module_key, update_data)
        if module:
            updated.append({"module_key": module_key, "provider": mod_data.get("provider", ""), "chat_model": mod_data.get("chat_model", "")})

    return RestoreResponse(status="ok", updated_count=len(updated))


PRESET_CONFIGS = {
    "actual": {
        "name": "实际配置",
        "description": "当前线上生产环境配置",
        "icon": "ri-check-double-line",
        "provider": "dashscope",
        "chat_model": "qwen-plus",
        "vision_model": "qwen-vl-plus",
        "embedding_model": "text-embedding-v4",
    },
    "recommended": {
        "name": "推荐配置",
        "description": "基于模块功能需求与大模型能力推荐",
        "icon": "ri-star-line",
        "modules": {
            "rag": {"provider": "deepseek", "chat_model": "deepseek-v4-flash", "vision_model": "qwen-vl-plus", "embedding_model": "text-embedding-v4"},
            "vasi": {"provider": "dashscope", "chat_model": "qwen-vl-max", "vision_model": "qwen-vl-max", "embedding_model": "text-embedding-v4"},
            "medical_report": {"provider": "dashscope", "chat_model": "qwen-vl-max", "vision_model": "qwen-vl-max", "embedding_model": "text-embedding-v4"},
            "content_safety": {"provider": "dashscope", "chat_model": "qwen-turbo", "vision_model": "qwen-vl-plus", "embedding_model": "text-embedding-v3"},
            "im_moderation": {"provider": "dashscope", "chat_model": "qwen-turbo", "vision_model": "qwen-vl-plus", "embedding_model": "text-embedding-v3"},
            "summarizer": {"provider": "deepseek", "chat_model": "deepseek-v4-flash", "vision_model": "qwen-vl-plus", "embedding_model": "text-embedding-v4"},
            "translator": {"provider": "deepseek", "chat_model": "deepseek-v4-flash", "vision_model": "qwen-vl-plus", "embedding_model": "text-embedding-v4"},
            "briefing": {"provider": "deepseek", "chat_model": "deepseek-v4-flash", "vision_model": "qwen-vl-plus", "embedding_model": "text-embedding-v4"},
            "encyclopedia": {"provider": "deepseek", "chat_model": "deepseek-v4-flash", "vision_model": "qwen-vl-plus", "embedding_model": "text-embedding-v4"},
        },
    },
    "economy": {
        "name": "经济配置",
        "description": "最省钱方案，适合非关键任务",
        "icon": "ri-money-cny-circle-line",
        "modules": {
            "rag": {"provider": "dashscope", "chat_model": "qwen-turbo", "vision_model": "qwen-vl-plus", "embedding_model": "text-embedding-v3"},
            "vasi": {"provider": "dashscope", "chat_model": "qwen-vl-plus", "vision_model": "qwen-vl-plus", "embedding_model": "text-embedding-v3"},
            "medical_report": {"provider": "dashscope", "chat_model": "qwen-vl-plus", "vision_model": "qwen-vl-plus", "embedding_model": "text-embedding-v3"},
            "content_safety": {"provider": "dashscope", "chat_model": "qwen-turbo", "vision_model": "qwen-vl-plus", "embedding_model": "text-embedding-v3"},
            "im_moderation": {"provider": "dashscope", "chat_model": "qwen-turbo", "vision_model": "qwen-vl-plus", "embedding_model": "text-embedding-v3"},
            "summarizer": {"provider": "dashscope", "chat_model": "qwen-turbo", "vision_model": "qwen-vl-plus", "embedding_model": "text-embedding-v3"},
            "translator": {"provider": "dashscope", "chat_model": "qwen-turbo", "vision_model": "qwen-vl-plus", "embedding_model": "text-embedding-v3"},
            "briefing": {"provider": "dashscope", "chat_model": "qwen-turbo", "vision_model": "qwen-vl-plus", "embedding_model": "text-embedding-v3"},
            "encyclopedia": {"provider": "dashscope", "chat_model": "qwen-turbo", "vision_model": "qwen-vl-plus", "embedding_model": "text-embedding-v3"},
        },
    },
    "performance": {
        "name": "强劲配置",
        "description": "性能最强方案，适合关键任务",
        "icon": "ri-rocket-line",
        "modules": {
            "rag": {"provider": "deepseek", "chat_model": "deepseek-v4-pro", "vision_model": "qwen-vl-max", "embedding_model": "text-embedding-v4"},
            "vasi": {"provider": "dashscope", "chat_model": "qwen-vl-max", "vision_model": "qwen-vl-max", "embedding_model": "text-embedding-v4"},
            "medical_report": {"provider": "dashscope", "chat_model": "qwen-vl-max", "vision_model": "qwen-vl-max", "embedding_model": "text-embedding-v4"},
            "content_safety": {"provider": "deepseek", "chat_model": "deepseek-v4-pro", "vision_model": "qwen-vl-plus", "embedding_model": "text-embedding-v4"},
            "im_moderation": {"provider": "deepseek", "chat_model": "deepseek-v4-pro", "vision_model": "qwen-vl-plus", "embedding_model": "text-embedding-v4"},
            "summarizer": {"provider": "deepseek", "chat_model": "deepseek-v4-pro", "vision_model": "qwen-vl-max", "embedding_model": "text-embedding-v4"},
            "translator": {"provider": "deepseek", "chat_model": "deepseek-v4-pro", "vision_model": "qwen-vl-max", "embedding_model": "text-embedding-v4"},
            "briefing": {"provider": "deepseek", "chat_model": "deepseek-v4-pro", "vision_model": "qwen-vl-max", "embedding_model": "text-embedding-v4"},
            "encyclopedia": {"provider": "deepseek", "chat_model": "deepseek-v4-pro", "vision_model": "qwen-vl-max", "embedding_model": "text-embedding-v4"},
        },
    },
}


class PresetInfo(BaseModel):
    key: str
    name: str
    description: str
    icon: str


class ApplyPresetRequest(BaseModel):
    preset: str = Field(..., description="actual / recommended / economy / performance")


class ApplyPresetResponse(BaseModel):
    preset: str
    updated_count: int
    modules: List[Dict[str, Any]]


@router.get("/presets", response_model=List[PresetInfo])
async def list_presets(current_user=Depends(auth)):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return [
        PresetInfo(key=k, name=v["name"], description=v["description"], icon=v["icon"])
        for k, v in PRESET_CONFIGS.items()
    ]


@router.post("/presets/apply", response_model=ApplyPresetResponse)
async def apply_preset(
    req: ApplyPresetRequest,
    current_user=Depends(auth),
    db: Session = Depends(get_db),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    if req.preset not in PRESET_CONFIGS:
        raise HTTPException(status_code=400, detail=f"无效预设: {req.preset}")

    preset = PRESET_CONFIGS[req.preset]
    updated = []

    if "modules" in preset:
        for module_key, mod_config in preset["modules"].items():
            module = LLMConfigService.get_module_by_key(db, module_key)
            if module:
                LLMConfigService.update_module(db, module_key, mod_config)
                updated.append({"module_key": module_key, "provider": mod_config["provider"], "chat_model": mod_config["chat_model"]})
    else:
        modules = LLMConfigService.get_all_modules(db)
        for module in modules:
            config = {
                "provider": preset["provider"],
                "chat_model": preset["chat_model"],
                "vision_model": preset.get("vision_model"),
                "embedding_model": preset.get("embedding_model"),
            }
            LLMConfigService.update_module(db, module.module_key, config)
            updated.append({"module_key": module.module_key, "provider": preset["provider"], "chat_model": preset["chat_model"]})

    return ApplyPresetResponse(preset=req.preset, updated_count=len(updated), modules=updated)


class ApplyPresetModuleRequest(BaseModel):
    module_key: str = Field(..., description="Target module key")


@router.post("/presets/{preset_key}/apply-module", response_model=ApplyPresetResponse)
async def apply_preset_to_module(
    preset_key: str,
    req: ApplyPresetModuleRequest,
    current_user=Depends(auth),
    db: Session = Depends(get_db),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    if preset_key not in PRESET_CONFIGS:
        raise HTTPException(status_code=400, detail=f"无效预设: {preset_key}")

    preset = PRESET_CONFIGS[preset_key]
    module = LLMConfigService.get_module_by_key(db, req.module_key)
    if not module:
        raise HTTPException(status_code=404, detail="模块不存在")

    if "modules" in preset and req.module_key in preset["modules"]:
        mod_config = preset["modules"][req.module_key]
    else:
        mod_config = {
            "provider": preset.get("provider", module.provider),
            "chat_model": preset.get("chat_model", module.chat_model),
            "vision_model": preset.get("vision_model"),
            "embedding_model": preset.get("embedding_model"),
        }

    updated_module = LLMConfigService.update_module(db, req.module_key, mod_config)
    if not updated_module:
        raise HTTPException(status_code=500, detail="应用预设失败，请稍后重试")

    return ApplyPresetResponse(
        preset=preset_key,
        updated_count=1,
        modules=[{"module_key": req.module_key, "provider": mod_config.get("provider", ""), "chat_model": mod_config.get("chat_model", "")}],
    )


class PresetPreviewItem(BaseModel):
    module_key: str
    module_name: str
    current_provider: str
    current_chat_model: Optional[str] = None
    current_vision_model: Optional[str] = None
    current_embedding_model: Optional[str] = None
    new_provider: str
    new_chat_model: Optional[str] = None
    new_vision_model: Optional[str] = None
    new_embedding_model: Optional[str] = None
    changed: bool
    changed_fields: List[str] = []


class PresetPreviewResponse(BaseModel):
    preset_key: str
    preset_name: str
    preset_description: str
    items: List[PresetPreviewItem]
    change_count: int


@router.get("/presets/{preset_key}/preview", response_model=PresetPreviewResponse)
async def preview_preset(
    preset_key: str,
    current_user=Depends(auth),
    db: Session = Depends(get_db),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    if preset_key not in PRESET_CONFIGS:
        raise HTTPException(status_code=400, detail=f"无效预设: {preset_key}")

    preset = PRESET_CONFIGS[preset_key]
    modules = LLMConfigService.get_all_modules(db)
    items = []

    for module in modules:
        if "modules" in preset and module.module_key in preset["modules"]:
            mod_cfg = preset["modules"][module.module_key]
            new_provider = mod_cfg.get("provider", module.provider)
            new_chat = mod_cfg.get("chat_model", module.chat_model)
            new_vision = mod_cfg.get("vision_model", module.vision_model)
            new_embedding = mod_cfg.get("embedding_model", module.embedding_model)
        else:
            new_provider = preset.get("provider", module.provider)
            new_chat = preset.get("chat_model", module.chat_model)
            new_vision = preset.get("vision_model", module.vision_model)
            new_embedding = preset.get("embedding_model", module.embedding_model)

        changed_fields = []
        if module.provider != new_provider: changed_fields.append("provider")
        if (module.chat_model or "") != (new_chat or ""): changed_fields.append("chat_model")
        if (module.vision_model or "") != (new_vision or ""): changed_fields.append("vision_model")
        if (module.embedding_model or "") != (new_embedding or ""): changed_fields.append("embedding_model")

        items.append(PresetPreviewItem(
            module_key=module.module_key,
            module_name=module.module_name,
            current_provider=module.provider or "",
            current_chat_model=module.chat_model,
            current_vision_model=module.vision_model,
            current_embedding_model=module.embedding_model,
            new_provider=new_provider,
            new_chat_model=new_chat,
            new_vision_model=new_vision,
            new_embedding_model=new_embedding,
            changed=len(changed_fields) > 0,
            changed_fields=changed_fields,
        ))

    change_count = sum(1 for i in items if i.changed)
    return PresetPreviewResponse(
        preset_key=preset_key,
        preset_name=preset["name"],
        preset_description=preset["description"],
        items=items,
        change_count=change_count,
    )


class TestPresetModuleRequest(BaseModel):
    module_key: str


@router.post("/presets/{preset_key}/test-module")
async def test_preset_module(
    preset_key: str,
    req: TestPresetModuleRequest,
    current_user=Depends(auth),
    db: Session = Depends(get_db),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    if preset_key not in PRESET_CONFIGS:
        raise HTTPException(status_code=400, detail=f"无效预设: {preset_key}")

    preset = PRESET_CONFIGS[preset_key]
    module = LLMConfigService.get_module_by_key(db, req.module_key)
    if not module:
        raise HTTPException(status_code=404, detail="模块不存在")

    if "modules" in preset and req.module_key in preset["modules"]:
        mod_cfg = preset["modules"][req.module_key]
    else:
        mod_cfg = {
            "provider": preset.get("provider", module.provider),
            "chat_model": preset.get("chat_model", module.chat_model),
            "vision_model": preset.get("vision_model"),
            "embedding_model": preset.get("embedding_model"),
        }

    override = {
        "provider": mod_cfg.get("provider", module.provider),
        "chat_model": mod_cfg.get("chat_model", module.chat_model),
        "base_url": preset.get("base_url", module.base_url),
    }
    result = LLMConfigService.test_config(req.module_key, config_override=override)
    return TestConfigResponse(**result)

"""
LLM 模块配置服务层

支持按模块配置大模型供应商和模型，API Key 加密存储。
"""

import base64
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

from web.backend.database.database import SessionLocal
from web.backend.database.models import LLMModuleConfig

logger = logging.getLogger(__name__)

RECOMMENDED_PROVIDERS: Dict[str, Any] = {
    "dashscope": {
        "name": "百炼（阿里云）",
        "models": {
            "chat": ["qwen-plus", "qwen-max", "qwen-turbo", "qwen-plus-latest", "qwen-max-latest", "qwen-long"],
            "vision": ["qwen-vl-plus", "qwen-vl-max", "qwen-vl-max-latest"],
            "embedding": ["text-embedding-v4", "text-embedding-v3"],
        },
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    },
    "bailian_codingplan": {
        "name": "百炼 Coding Plan",
        "models": {
            "chat": ["qwen-plus", "qwen-max", "qwen-turbo", "qwen-plus-latest", "qwen-max-latest"],
            "vision": ["qwen-vl-plus", "qwen-vl-max"],
            "embedding": ["text-embedding-v4"],
        },
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    },
    "volcengine": {
        "name": "火山引擎",
        "models": {
            "chat": ["ep-20260414003938-k6r9g", "doubao-pro-32k", "doubao-pro-128k", "doubao-pro-256k", "doubao-lite-4k", "doubao-lite-32k", "doubao-lite-128k"],
            "vision": ["doubao-vision-pro-32k"],
            "embedding": ["ep-20260414011808-kwzm7", "text-embedding-3-small"],
        },
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
    },
    "volc_codingplan": {
        "name": "火山 Coding Plan",
        "models": {
            "chat": ["ep-20260414003938-k6r9g", "doubao-pro-32k", "doubao-lite-4k"],
            "vision": ["doubao-vision-pro-32k"],
            "embedding": ["ep-20260414011808-kwzm7", "text-embedding-3-small"],
        },
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
    },
    "deepseek": {
        "name": "DeepSeek",
        "models": {
            "chat": ["deepseek-v4-pro", "deepseek-v4-flash"],
            "vision": [],
            "embedding": [],
        },
        "base_url": "https://api.deepseek.com/v1",
    },
    "moonshot": {
        "name": "Kimi（月之暗面）",
        "models": {
            "chat": ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k", "kimi-latest", "kimi-thinking"],
            "vision": ["moonshot-v1-8k-vision-preview"],
            "embedding": [],
        },
        "base_url": "https://api.moonshot.cn/v1",
    },
    "minimax": {
        "name": "MiniMax",
        "models": {
            "chat": ["abab6.5s-chat", "abab6.5-chat", "abab7-chat-preview", "minimax-m1"],
            "vision": [],
            "embedding": ["embo-01"],
        },
        "base_url": "https://api.minimax.chat/v1",
    },
    "zhipuai": {
        "name": "智谱 AI (Z.ai)",
        "models": {
            "chat": ["glm-5.1", "glm-5", "glm-5-turbo", "glm-4.7", "glm-4.7-flash", "glm-4.7-flashx", "glm-4.6", "glm-4.5", "glm-4.5-air", "glm-4.5-flash", "glm-4-plus", "glm-4-flash"],
            "vision": ["glm-4.6v", "glm-4.5v", "glm-4v"],
            "embedding": ["embedding-3"],
        },
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
    },
    "deepseek": {
        "name": "DeepSeek",
        "models": {
            "chat": ["deepseek-v4-pro", "deepseek-v4-flash"],
            "vision": [],
            "embedding": [],
        },
        "base_url": "https://api.deepseek.com/v1",
    },
    "minimax": {
        "name": "MiniMax",
        "models": {
            "chat": ["MiniMax-M2.7", "MiniMax-M2.7-highspeed", "MiniMax-M2.5", "MiniMax-M2.5-highspeed", "MiniMax-M2.1", "MiniMax-M2.1-highspeed", "MiniMax-M2", "MiniMax-M1"],
            "vision": [],
            "embedding": ["embo-01"],
        },
        "base_url": "https://api.minimax.chat/v1",
    },
    "openai": {
        "name": "OpenAI",
        "models": {
            "chat": ["gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini", "o4-mini"],
            "vision": ["gpt-4o", "gpt-4o-mini"],
            "embedding": ["text-embedding-3-small", "text-embedding-3-large"],
        },
        "base_url": "https://api.openai.com/v1",
    },
    "anthropic": {
        "name": "Anthropic",
        "models": {
            "chat": ["claude-sonnet-4-20250514", "claude-3-5-sonnet-20241022", "claude-3-opus-20240229"],
            "vision": ["claude-sonnet-4-20250514", "claude-3-5-sonnet-20241022"],
        },
        "base_url": "https://api.anthropic.com/v1",
    },
}

DEFAULT_MODULES: List[Dict[str, Any]] = [
    {"module_key": "rag", "module_name": "RAG 智能问答", "module_description": "知识库 RAG 问答系统"},
    {"module_key": "vasi", "module_name": "VASI 白斑评估", "module_description": "VASI 白斑面积评估"},
    {"module_key": "medical_report", "module_name": "医疗报告解读", "module_description": "体检报告 AI 解读"},
    {"module_key": "content_safety", "module_name": "内容安全审核", "module_description": "社区内容安全风控"},
    {"module_key": "im_moderation", "module_name": "IM 消息审核", "module_description": "即时通讯消息风控"},
    {"module_key": "summarizer", "module_name": "文献摘要", "module_description": "医学论文摘要生成"},
    {"module_key": "translator", "module_name": "文献翻译", "module_description": "医学论文翻译"},
    {"module_key": "briefing", "module_name": "每日简报生成", "module_description": "每日研究动态简报"},
    {"module_key": "encyclopedia", "module_name": "百科知识库维护", "module_description": "小白百科知识库维护"},
]


def _get_fernet() -> Fernet:
    """获取加解密实例，密钥从环境变量获取或使用默认值。"""
    raw_key = os.getenv("LLM_CONFIG_ENCRYPTION_KEY", "subskin-llm-config-default-key-32b!")
    # Fernet 需要 32 字节的 base64 编码密钥
    key_bytes = raw_key.encode("utf-8")
    if len(key_bytes) < 32:
        key_bytes = key_bytes.ljust(32, b"\0")
    else:
        key_bytes = key_bytes[:32]
    fernet_key = base64.urlsafe_b64encode(key_bytes)
    return Fernet(fernet_key)


def encrypt_api_key(api_key: Optional[str]) -> Optional[str]:
    if not api_key:
        return None
    try:
        return _get_fernet().encrypt(api_key.encode("utf-8")).decode("utf-8")
    except Exception as e:
        logger.warning(f"API key encryption failed: {e}")
        return api_key


def decrypt_api_key(encrypted: Optional[str]) -> Optional[str]:
    if not encrypted:
        return None
    try:
        return _get_fernet().decrypt(encrypted.encode("utf-8")).decode("utf-8")
    except Exception:
        # 可能是明文存储的旧数据，直接返回
        return encrypted


class LLMConfigService:
    """LLM 模块配置服务"""

    @staticmethod
    def get_all_modules(db: Session) -> List[LLMModuleConfig]:
        return db.query(LLMModuleConfig).order_by(LLMModuleConfig.module_key).all()

    @staticmethod
    def get_module_by_key(db: Session, module_key: str) -> Optional[LLMModuleConfig]:
        return db.query(LLMModuleConfig).filter(LLMModuleConfig.module_key == module_key).first()

    @staticmethod
    def update_module(db: Session, module_key: str, data: Dict[str, Any]) -> Optional[LLMModuleConfig]:
        module = LLMConfigService.get_module_by_key(db, module_key)
        if not module:
            return None

        allowed_fields = {
            "module_name", "module_description", "provider", "chat_model",
            "vision_model", "embedding_model", "api_key", "base_url", "is_active",
        }
        for field in allowed_fields:
            if field in data:
                if field == "api_key" and data[field]:
                    value = encrypt_api_key(data[field])
                else:
                    value = data[field]
                setattr(module, field, value)

        module.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(module)
        return module

    @staticmethod
    def get_config_by_module(db: Session, module_key: str) -> Optional[Dict[str, Any]]:
        """获取指定模块的 LLM 配置，如果模块不存在或未激活返回 None。"""
        module = LLMConfigService.get_module_by_key(db, module_key)
        if not module or not module.is_active:
            return None

        provider_info = RECOMMENDED_PROVIDERS.get(module.provider, {})
        base_url = module.base_url or provider_info.get("base_url", "")

        result = {
            "api_key": decrypt_api_key(module.api_key) or "",
            "base_url": base_url,
            "chat_model": module.chat_model or "",
            "vision_model": module.vision_model or "",
            "embedding_model": module.embedding_model or "",
            "provider": module.provider,
            "embedding_dimensions": None,
        }
        if module.provider == "dashscope":
            result["embedding_dimensions"] = 1024
        return result

    @staticmethod
    def init_defaults(db: Optional[Session] = None) -> None:
        """根据现有 .env 配置初始化默认模块配置。"""
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True

        try:
            existing_keys = {m.module_key for m in db.query(LLMModuleConfig.module_key).all()}

            # 优先级：dashscope -> volcengine -> openai
            default_provider = "none"
            default_api_key = ""
            default_base_url = ""
            default_chat_model = ""
            default_vision_model = ""
            default_embedding_model = ""
            default_embedding_dimensions = None

            if os.getenv("DASHSCOPE_API_KEY"):
                default_provider = "dashscope"
                default_api_key = os.getenv("DASHSCOPE_API_KEY", "")
                default_base_url = os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
                default_chat_model = os.getenv("DASHSCOPE_CHAT_MODEL", "qwen-plus")
                default_vision_model = os.getenv("DASHSCOPE_VISION_MODEL", "qwen-vl-plus")
                default_embedding_model = os.getenv("DASHSCOPE_EMBEDDING_MODEL", "text-embedding-v4")
                default_embedding_dimensions = int(os.getenv("DASHSCOPE_EMBEDDING_DIMENSIONS", "1024"))
            elif os.getenv("VOLCENGINE_API_KEY"):
                default_provider = "volcengine"
                default_api_key = os.getenv("VOLCENGINE_API_KEY", "")
                default_base_url = os.getenv("VOLCENGINE_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
                default_chat_model = os.getenv("VOLCENGINE_CHAT_ENDPOINT", "doubao-4k")
                default_vision_model = os.getenv("VOLCENGINE_VISION_MODEL", "doubao-vision-pro-32k")
                default_embedding_model = os.getenv("VOLCENGINE_EMBEDDING_ENDPOINT", "text-embedding-3-small")
            elif os.getenv("OPENAI_API_KEY"):
                default_provider = "openai"
                default_api_key = os.getenv("OPENAI_API_KEY", "")
                default_base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
                default_chat_model = os.getenv("LLM_MODEL", "gpt-3.5-turbo")
                default_vision_model = os.getenv("OPENAI_VISION_MODEL", "gpt-4o")
                default_embedding_model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

            for mod in DEFAULT_MODULES:
                if mod["module_key"] in existing_keys:
                    continue

                config = LLMModuleConfig(
                    module_key=mod["module_key"],
                    module_name=mod["module_name"],
                    module_description=mod.get("module_description"),
                    provider=default_provider,
                    chat_model=default_chat_model,
                    vision_model=default_vision_model,
                    embedding_model=default_embedding_model,
                    api_key=encrypt_api_key(default_api_key) if default_api_key else None,
                    base_url=default_base_url,
                    is_active=True,
                )
                db.add(config)

            db.commit()
            logger.info("LLM module configs initialized from environment")
        except Exception as e:
            logger.error(f"Failed to initialize LLM module configs: {e}")
            db.rollback()
        finally:
            if close_db:
                db.close()

    @staticmethod
    def refresh_from_env(db: Optional[Session] = None) -> int:
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True

        updated = 0
        try:
            from web.backend.utils.llm_config import get_llm_config
            env_config = get_llm_config()

            modules = db.query(LLMModuleConfig).all()
            for module in modules:
                changed = False
                if env_config.get("provider") and module.provider != env_config["provider"]:
                    module.provider = env_config["provider"]
                    changed = True
                if env_config.get("chat_model") and module.chat_model != env_config["chat_model"]:
                    module.chat_model = env_config["chat_model"]
                    changed = True
                if env_config.get("vision_model") and module.vision_model != env_config.get("vision_model"):
                    module.vision_model = env_config["vision_model"]
                    changed = True
                if env_config.get("embedding_model") and module.embedding_model != env_config.get("embedding_model"):
                    module.embedding_model = env_config["embedding_model"]
                    changed = True
                if env_config.get("api_key"):
                    new_key = encrypt_api_key(env_config["api_key"])
                    if module.api_key != new_key:
                        module.api_key = new_key
                        changed = True
                if env_config.get("base_url") and module.base_url != env_config["base_url"]:
                    module.base_url = env_config["base_url"]
                    changed = True

                if changed:
                    module.updated_at = datetime.now(timezone.utc)
                    updated += 1

            if updated:
                db.commit()
                logger.info(f"Refreshed {updated} LLM module configs from environment")
        except Exception as e:
            logger.error(f"Failed to refresh LLM configs: {e}")
            db.rollback()
        finally:
            if close_db:
                db.close()

        return updated

    @staticmethod
    def test_config(module_key: str, config_override: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """测试指定模块的 LLM 配置是否可用。"""
        import openai

        db = SessionLocal()
        try:
            module = LLMConfigService.get_module_by_key(db, module_key)
            if not module:
                return {"ok": False, "error": f"模块 {module_key} 不存在"}

            if config_override:
                provider = config_override.get("provider", module.provider)
                api_key = config_override.get("api_key", decrypt_api_key(module.api_key))
                base_url = config_override.get("base_url", module.base_url)
                chat_model = config_override.get("chat_model", module.chat_model)
            else:
                provider = module.provider
                api_key = decrypt_api_key(module.api_key)
                base_url = module.base_url
                chat_model = module.chat_model

            if not api_key:
                return {"ok": False, "error": "API Key 未配置"}

            provider_info = RECOMMENDED_PROVIDERS.get(provider, {})
            base_url = base_url or provider_info.get("base_url", "")

            client = openai.OpenAI(api_key=api_key, base_url=base_url)
            response = client.chat.completions.create(
                model=chat_model or "gpt-3.5-turbo",
                messages=[{"role": "user", "content": "你好"}],
                max_tokens=5,
                timeout=15,
            )
            return {
                "ok": True,
                "model": chat_model,
                "provider": provider,
                "response": response.choices[0].message.content if response.choices else "",
            }
        except Exception as e:
            logger.warning(f"LLM config test failed for {module_key}: {e}")
            return {"ok": False, "error": str(e)}
        finally:
            db.close()

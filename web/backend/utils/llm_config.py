import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


def _get_env_config() -> dict:
    """从lLLM环境变量获取配置。"""
    if os.getenv("DASHSCOPE_API_KEY"):
        return {
            "api_key": os.getenv("DASHSCOPE_API_KEY"),
            "base_url": os.getenv(
                "DASHSCOPE_BASE_URL",
                "https://dashscope.aliyuncs.com/compatible-mode/v1",
            ),
            "chat_model": os.getenv("DASHSCOPE_CHAT_MODEL", "qwen-plus"),
            "vision_model": os.getenv("DASHSCOPE_VISION_MODEL", "qwen-vl-max"),
            "embedding_model": os.getenv(
                "DASHSCOPE_EMBEDDING_MODEL", "text-embedding-v4"
            ),
            "embedding_dimensions": int(
                os.getenv("DASHSCOPE_EMBEDDING_DIMENSIONS", "1024")
            ),
            "provider": "dashscope",
        }

    if os.getenv("VOLCENGINE_API_KEY"):
        return {
            "api_key": os.getenv("VOLCENGINE_API_KEY"),
            "base_url": os.getenv(
                "VOLCENGINE_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3"
            ),
            "chat_model": os.getenv("VOLCENGINE_CHAT_ENDPOINT", "ep-20260414003938-k6r9g"),
            "vision_model": os.getenv(
                "VOLCENGINE_VISION_MODEL", "doubao-vision-pro-32k"
            ),
            "embedding_model": os.getenv(
                "VOLCENGINE_EMBEDDING_ENDPOINT", "text-embedding-3-small"
            ),
            "embedding_dimensions": None,
            "provider": "volcengine",
        }

    if os.getenv("DEEPSEEK_API_KEY"):
        return {
            "api_key": os.getenv("DEEPSEEK_API_KEY"),
            "base_url": os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
            "chat_model": "deepseek-v4-flash",
            "vision_model": "",
            "embedding_model": "",
            "embedding_dimensions": None,
            "provider": "deepseek",
        }

    if os.getenv("MOONSHOT_API_KEY"):
        return {
            "api_key": os.getenv("MOONSHOT_API_KEY"),
            "base_url": os.getenv("MOONSHOT_BASE_URL", "https://api.moonshot.cn/v1"),
            "chat_model": "moonshot-v1-8k",
            "vision_model": "",
            "embedding_model": "",
            "embedding_dimensions": None,
            "provider": "moonshot",
        }

    if os.getenv("MINIMAX_API_KEY"):
        return {
            "api_key": os.getenv("MINIMAX_API_KEY"),
            "base_url": os.getenv("MINIMAX_BASE_URL", "https://api.minimax.chat/v1"),
            "chat_model": "MiniMax-M2.7",
            "vision_model": "",
            "embedding_model": "",
            "embedding_dimensions": None,
            "provider": "minimax",
        }

    if os.getenv("ZHIPU_API_KEY"):
        return {
            "api_key": os.getenv("ZHIPU_API_KEY"),
            "base_url": os.getenv("ZHIPU_BASE_URL", "https://open.bigmodel.cn/api/paas/v4"),
            "chat_model": "glm-4-flash",
            "vision_model": "glm-4v",
            "embedding_model": "embedding-3",
            "embedding_dimensions": None,
            "provider": "zhipuai",
        }

    if os.getenv("OPENAI_API_KEY"):
        return {
            "api_key": os.getenv("OPENAI_API_KEY"),
            "base_url": os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            "chat_model": os.getenv("LLM_MODEL", "gpt-3.5-turbo"),
            "vision_model": os.getenv("OPENAI_VISION_MODEL", "gpt-4o"),
            "embedding_model": os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
            "embedding_dimensions": None,
            "provider": "openai",
        }

    return {
        "api_key": "",
        "base_url": "https://api.openai.com/v1",
        "chat_model": "gpt-3.5-turbo",
        "vision_model": "qwen-vl-plus",
        "embedding_model": "text-embedding-3-small",
        "embedding_dimensions": None,
        "provider": "none",
    }


def get_llm_config(module: Optional[str] = None) -> dict:
    """获取 LLM 配置。

    Args:
        module: 可选的模块标识（如 rag、vasi 等）。
              如果提供，先尝试从数据库查询模块配置；
              如果没有找到有效配置，则回退到环境变量。
              如果未提供，行为与之前完全一致。
    """
    if module:
        try:
            from web.backend.database.database import SessionLocal
            from web.backend.services.llm_config_service import LLMConfigService

            db = SessionLocal()
            try:
                    config = LLMConfigService.get_config_by_module(db, module)
                    if config and config.get("api_key") and config.get("base_url"):
                        return config
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Failed to get module config for '{module}': {e}")

    return _get_env_config()


def get_ml_config() -> dict:
    """Get Volcano Engine ML Platform configuration for nnU-Net inference.

    Reads VOLC_ML_ENDPOINT and VOLC_ML_TOKEN from environment variables.

    Returns:
        dict with keys: endpoint, token, available
    """
    endpoint = os.getenv("VOLC_ML_ENDPOINT", "")
    token = os.getenv("VOLC_ML_TOKEN", "")
    return {
        "endpoint": endpoint,
        "token": token,
        "available": bool(endpoint and token),
    }

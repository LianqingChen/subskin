"""
API路由模块
"""

from . import (
    analytics,
    user,
    content,
    comment,
    comment_admin,
    rag,
    vasi,
    oauth,
    community,
    social,
    medical_report,
    audit,
    patient_profile,
    files,
    moderation,
    llm_config_admin,
    admin_general,
    content_generation_admin,
)
from .vasi import router as vasi_router

__all__ = [
    "user",
    "analytics",
    "content",
    "comment",
    "comment_admin",
    "rag",
    "vasi",
    "vasi_router",
    "oauth",
    "community",
    "social",
    "medical_report",
    "audit",
    "patient_profile",
    "files",
    "moderation",
    "llm_config_admin",
    "admin_general",
    "content_generation_admin",
]

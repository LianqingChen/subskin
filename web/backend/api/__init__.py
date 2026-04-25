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
]

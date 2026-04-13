"""
API路由模块
"""

from . import user, content, comment, comment_admin, rag, vasi, oauth
from .vasi import router as vasi_router

__all__ = [
    "user",
    "content",
    "comment",
    "comment_admin",
    "rag",
    "vasi",
    "vasi_router",
    "oauth",
]

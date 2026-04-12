"""
SubSkin Community Backend
社区网站后端 API 服务

提供用户认证、评论、内容管理等功能
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from web.backend.api import (
    user,
    content,
    comment,
    comment_admin,
    rag,
    vasi,
    vasi_router,
)
from web.backend.database.database import engine
from web.backend.database import models

models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="SubSkin Community API",
    description="SubSkin 社区网站后端 API",
    version="1.0.0",
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(user.router, prefix="/api/user", tags=["用户"])
app.include_router(content.router, prefix="/api/content", tags=["内容"])
app.include_router(comment.router, prefix="/api/comment", tags=["评论"])
app.include_router(
    comment_admin.router, prefix="/api/admin/comment", tags=["管理员-评论管理"]
)
app.include_router(rag.router, prefix="/api/rag", tags=["AI问答"])
app.include_router(vasi_router, prefix="/api/vasi", tags=["VASI评估"])


@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "service": "subskin-backend"}

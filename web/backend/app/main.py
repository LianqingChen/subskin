"""
SubSkin Community Backend
社区网站后端 API 服务

提供用户认证、评论、内容管理等功能
"""

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    _ = load_dotenv(env_path)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from web.backend.api import (
    analytics,
    user,
    content,
    comment,
    comment_admin,
    encyclopedia,
    events,
    rag,
    vasi_router,
    oauth,
    community,
    social,
    medical_report,
    audit,
    patient_profile,
    wechat,
)
from web.backend.api.files import router as files_router
from web.backend.database.database import Base, engine
from web.backend.database import models
from web.backend.services.temp_cleanup import (
    cleanup_temp_uploads,
    run_temp_cleanup_loop,
)

_ = models

Base.metadata.create_all(bind=engine)


def ensure_user_avatar_column() -> None:
    inspector = inspect(engine)
    try:
        columns = {column["name"] for column in inspector.get_columns("users")}
    except Exception:
        return

    if "avatar_url" in columns:
        return

    with engine.begin() as connection:
        _ = connection.execute(text("ALTER TABLE users ADD COLUMN avatar_url VARCHAR"))


ensure_user_avatar_column()


def ensure_medical_report_interpretation_column() -> None:
    inspector = inspect(engine)
    try:
        columns = {column["name"] for column in inspector.get_columns("medical_reports")}
    except Exception:
        return

    if "interpretation_json" in columns:
        return

    with engine.begin() as connection:
        _ = connection.execute(
            text("ALTER TABLE medical_reports ADD COLUMN interpretation_json JSON")
        )


ensure_medical_report_interpretation_column()
uploads_dir = Path("data/uploads")
uploads_dir.mkdir(parents=True, exist_ok=True)

DEFAULT_ALLOWED_ORIGINS = [
    "https://subskin.cn",
    "https://www.subskin.cn",
    "http://localhost:5173",
    "http://localhost:3000",
]


def get_allowed_origins() -> list[str]:
    raw_origins = os.getenv("ALLOWED_ORIGINS", "")
    if not raw_origins.strip():
        return DEFAULT_ALLOWED_ORIGINS

    origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
    return origins or DEFAULT_ALLOWED_ORIGINS


_temp_cleanup_task: Optional[asyncio.Task[None]] = None


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    global _temp_cleanup_task

    _ = app_instance
    _ = cleanup_temp_uploads()
    _temp_cleanup_task = asyncio.create_task(run_temp_cleanup_loop())
    try:
        yield
    finally:
        if _temp_cleanup_task is not None:
            _temp_cleanup_task.cancel()
            try:
                await _temp_cleanup_task
            except asyncio.CancelledError:
                pass
            _temp_cleanup_task = None


app = FastAPI(
    title="SubSkin Community API",
    description="SubSkin 社区网站后端 API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(analytics.router, prefix="/api/analytics", tags=["分析驾驶舱"])
app.include_router(user.router, prefix="/api/user", tags=["用户"])
app.include_router(user.profile_router, prefix="/api/users", tags=["用户"])
app.include_router(content.router, prefix="/api/content", tags=["内容"])
app.include_router(comment.router, prefix="/api/comment", tags=["评论"])
app.include_router(
    comment_admin.router, prefix="/api/admin/comment", tags=["管理员-评论管理"]
)
app.include_router(events.router, prefix="/api/events", tags=["事件追踪"])
app.include_router(rag.router, prefix="/api/rag", tags=["AI问答"])
app.include_router(vasi_router, prefix="/api/vasi", tags=["VASI评估"])
app.include_router(oauth.router, prefix="/api/oauth", tags=["第三方登录"])
app.include_router(community.router, prefix="/api/community", tags=["社区帖子"])
app.include_router(social.router, prefix="/api/community", tags=["社区社交"])
app.include_router(
    medical_report.router, prefix="/api/medical-reports", tags=["体检报告"]
)
app.include_router(files_router, prefix="/api/files", tags=["文件"])
app.include_router(audit.router, prefix="/api/audit", tags=["审计日志"])
app.include_router(patient_profile.router, prefix="/api", tags=["白友档案"])
app.include_router(wechat.router, prefix="/api/wechat", tags=["微信"])
app.include_router(encyclopedia.router, tags=["白白百科"])


@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "service": "subskin-backend"}

"""
Admin 综合 API
内容生成、网站运维
"""
from web.backend.utils.timeutils import iso_utc
import os
import subprocess
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from web.backend.database.database import get_db
from web.backend.database.models import User
from web.backend.services.admin_auth import get_admin_user

router = APIRouter(prefix="/api/admin", tags=["管理员-综合"])


# ── content generation ─────────────────────────────────────────────

@router.get("/content/briefings")
async def list_briefings(
    page: int = 1,
    page_size: int = 20,
    admin: User = Depends(get_admin_user),
):
    _ = admin
    import glob
    briefing_dir = "/root/subskin/data/briefings"
    if not os.path.exists(briefing_dir):
        return {"total": 0, "items": []}
    files = sorted(glob.glob(os.path.join(briefing_dir, "daily_*.md")), reverse=True)
    total = len(files)
    start = (page - 1) * page_size
    end = start + page_size
    items = []
    for f in files[start:end]:
        fname = os.path.basename(f)
        stat = os.stat(f)
        items.append({
            "id": fname,
            "date": fname.replace("daily_", "").replace(".md", ""),
            "title": fname,
            "status": "completed",
            "created_at": iso_utc(datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)),
            "size": stat.st_size,
        })
    return {"total": total, "items": items}


@router.post("/content/generate-briefing")
async def trigger_generate_briefing(
    admin: User = Depends(get_admin_user),
):
    _ = admin
    try:
        result = subprocess.run(
            ["python", "-m", "src.scheduler.briefing_generator"],
            cwd="/root/subskin",
            capture_output=True,
            text=True,
            timeout=120,
        )
        return {
            "status": "ok" if result.returncode == 0 else "error",
            "stdout": result.stdout[-2000:] if result.stdout else "",
            "stderr": result.stderr[-1000:] if result.stderr else "",
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ── website maintenance ─────────────────────────────────────────────
@router.get("/site/status")
def site_status(
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> Dict[str, object]:
    """Website database sizes; host monitoring lives in DSH Console."""
    from web.backend.services.site_maintenance import storage_status

    _ = admin
    bind = db.get_bind()
    database_path = bind.url.database if bind.dialect.name == "sqlite" else None
    return storage_status(database_path)


@router.post("/embed-batch")
def embed_batch(admin_user: User = Depends(get_admin_user), db: Session = Depends(get_db)) -> dict:
    """管理员手动触发增量向量化：对 embedding=NULL 的文档做批量向量化。"""
    try:
        from web.backend.services.rag import batch_embed_unembedded
        result = batch_embed_unembedded(db)
        return {"status": "ok", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail="向量化任务执行失败，请稍后重试")

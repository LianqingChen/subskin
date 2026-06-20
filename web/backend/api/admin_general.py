"""
Admin 综合 API
内容生成、系统监控
"""
import os
import subprocess
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from web.backend.database.database import get_db
from web.backend.database.models import User
from web.backend.services.auth import get_current_user

router = APIRouter(prefix="/api/admin", tags=["管理员-综合"])

ADMIN_PHONE_ALLOWLIST = {"15810004327", "17319030290", "15978713663", "18790010679"}


async def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
    is_admin = getattr(current_user, "is_admin", False)
    phone = getattr(current_user, "phone", None)
    if not is_admin and phone not in ADMIN_PHONE_ALLOWLIST:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    if not is_admin and phone in ADMIN_PHONE_ALLOWLIST:
        from web.backend.database.database import SessionLocal
        with SessionLocal() as db:
            db_user = db.query(User).filter(User.id == current_user.id).first()
            if db_user and not db_user.is_admin:
                db_user.is_admin = True
                db.commit()
        current_user.is_admin = True
    return current_user


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
            "created_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
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


# ── system monitor ──────────────────────────────────────────────────

@router.get("/system/resources")
async def system_resources(
    admin: User = Depends(get_admin_user),
):
    _ = admin
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.5)
        cpu_cores = psutil.cpu_count(logical=True)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        uptime_seconds = int(psutil.boot_time())
        db_path = "/root/subskin/data/subskin.db"
        db_size = os.path.getsize(db_path) if os.path.exists(db_path) else 0
        return {
            "cpu_percent": round(cpu, 1),
            "cpu_cores": cpu_cores,
            "uptime_seconds": uptime_seconds,
            "memory_percent": round(mem.percent, 1),
            "memory_used_mb": round(mem.used / 1024 / 1024, 1),
            "memory_total_mb": round(mem.total / 1024 / 1024, 1),
            "disk_percent": round(disk.percent, 1),
            "disk_used_gb": round(disk.used / 1024 / 1024 / 1024, 1),
            "disk_total_gb": round(disk.total / 1024 / 1024 / 1024, 1),
            "db_size_mb": round(db_size / 1024 / 1024, 1),
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/system/services")
async def system_services(
    admin: User = Depends(get_admin_user),
):
    _ = admin
    services = ["subskin-backend", "subskin-scheduler", "nginx"]
    result = []
    for svc in services:
        try:
            proc = subprocess.run(
                ["systemctl", "is-active", svc],
                capture_output=True,
                text=True,
                timeout=5,
            )
            active = proc.stdout.strip() == "active"
            result.append({
                "name": svc,
                "status": "running" if active else "stopped",
                "enabled": True,
            })
        except Exception:
            result.append({"name": svc, "status": "unknown", "enabled": False})
    return {"services": result}


@router.post("/system/services/{service_name}/action")
async def system_service_action(
    service_name: str,
    action: str = "restart",
    admin: User = Depends(get_admin_user),
):
    """控制服务：start / stop / restart"""
    _ = admin
    valid_actions = {"start", "stop", "restart"}
    allowed_services = {"subskin-backend", "subskin-scheduler", "nginx"}
    if action not in valid_actions:
        raise HTTPException(status_code=400, detail=f"无效操作，只支持: {', '.join(valid_actions)}")
    if service_name not in allowed_services:
        raise HTTPException(status_code=400, detail=f"不支持的服务，只允许: {', '.join(allowed_services)}")
    try:
        proc = subprocess.run(
            ["systemctl", action, service_name],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode == 0:
            return {"status": "ok", "action": action, "service": service_name}
        else:
            return {
                "status": "error",
                "action": action,
                "service": service_name,
                "stderr": proc.stderr.strip() if proc.stderr else "systemctl returned non-zero",
            }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="操作超时")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/system/logs")
async def system_logs(
    lines: int = 50,
    service: str = "subskin-backend",
    admin: User = Depends(get_admin_user),
):
    _ = admin
    try:
        if service == "file" and os.path.exists("/root/subskin/logs/subskin.log"):
            proc = subprocess.run(
                ["tail", "-n", str(lines), "/root/subskin/logs/subskin.log"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return {"service": service, "lines": proc.stdout.splitlines()}
        proc = subprocess.run(
            ["journalctl", "-u", service, "-n", str(lines), "--no-pager"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return {"service": service, "lines": proc.stdout.splitlines()}
    except Exception as e:
        return {"service": service, "error": str(e)}


@router.post("/embed-batch")
def embed_batch(admin_user: User = Depends(get_admin_user), db: Session = Depends(get_db)) -> dict:
    """管理员手动触发增量向量化：对 embedding=NULL 的文档做批量向量化。"""
    try:
        from web.backend.services.rag import batch_embed_unembedded
        result = batch_embed_unembedded(db)
        return {"status": "ok", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail="向量化任务执行失败，请稍后重试")

import json
import logging
import mimetypes
from pathlib import Path
from typing import List, Optional, Tuple, cast

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.orm import Session

from web.backend.database.database import get_db
from web.backend.database.models import MedicalReport, MedicalReportFile, User
from web.backend.services.auth import (
    auth,
    create_access_token,
    get_current_user_optional,
    get_user_from_access_token,
)
from web.backend.services.temp_cleanup import cleanup_temp_uploads


router = APIRouter()
logger = logging.getLogger(__name__)


def _uploads_dir() -> Path:
    return Path("data/uploads").resolve()


def _resolve_requested_file(file_path: str) -> Path:
    uploads_dir = _uploads_dir()
    requested_path = (uploads_dir / file_path).resolve()
    try:
        _ = requested_path.relative_to(uploads_dir)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该文件",
        ) from exc

    if not requested_path.exists() or not requested_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")

    return requested_path


def _authenticate_file_request(
    access_token: Optional[str],
    current_user: Optional[User],
    db: Session,
) -> User:
    if current_user is not None:
        return current_user

    if access_token:
        token_user = get_user_from_access_token(access_token, db)
        if token_user is not None:
            return token_user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _is_public_path(file_path: str) -> bool:
    return file_path.startswith("community/")


def _resolve_upload_path_from_url(file_url: str) -> Path:
    relative_path = file_url.removeprefix("/uploads/")
    return _resolve_requested_file(relative_path)


def _get_authorized_medical_report_file(
    db: Session,
    file_id: int,
    user: User,
) -> Tuple[MedicalReportFile, MedicalReport]:
    db_file = db.query(MedicalReportFile).filter(MedicalReportFile.id == file_id).first()
    if not db_file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")

    report = (
        db.query(MedicalReport)
        .filter(
            MedicalReport.id == db_file.report_id,
            MedicalReport.user_id == user.id,
        )
        .first()
    )
    if not report:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该文件")

    return db_file, report


def _guess_media_type(db_file: MedicalReportFile, requested_path: Path) -> str:
    file_type = cast(Optional[str], cast(object, db_file.file_type))
    if isinstance(file_type, str) and file_type:
        return file_type

    guessed_type, _ = mimetypes.guess_type(str(requested_path))
    return guessed_type or "application/octet-stream"


def _serve_authorized_report_file(
    file_id: int,
    user: User,
    db: Session,
    page: Optional[int] = None,
) -> FileResponse:
    db_file, _ = _get_authorized_medical_report_file(db=db, file_id=file_id, user=user)
    file_name = cast(str, cast(object, db_file.file_name))
    file_url = cast(str, cast(object, db_file.file_url))

    if page is not None:
        page_path = Path("data/uploads/pages") / str(file_id) / "page-{0}.png".format(page)
        if not page_path.exists() or not page_path.is_file():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")
        return FileResponse(page_path, media_type="image/png")

    requested_path = _resolve_upload_path_from_url(file_url)
    return FileResponse(
        requested_path,
        filename=file_name,
        media_type=_guess_media_type(db_file, requested_path),
    )


@router.get("/serve/{file_path:path}")
async def serve_file(
    file_path: str,
    access_token: Optional[str] = Query(default=None),
    page: Optional[int] = Query(default=None, ge=1),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    if file_path.isdigit():
        user = _authenticate_file_request(access_token, current_user, db)
        try:
            return _serve_authorized_report_file(
                file_id=int(file_path),
                user=user,
                db=db,
                page=page,
            )
        except HTTPException:
            raise
        except Exception as exc:
            logger.error("Serve medical report file failed: %s", str(exc), exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="服务暂时不可用，请稍后重试",
            )

    if not _is_public_path(file_path):
        _ = _authenticate_file_request(access_token, current_user, db)
    requested_path = _resolve_requested_file(file_path)
    # Force attachment for PDFs (browsers like WeChat can't render them inline);
    # images and other formats use their natural content-type for inline viewing.
    if requested_path.suffix.lower() == ".pdf":
        return FileResponse(
            requested_path,
            filename=requested_path.name,
            media_type="application/octet-stream",
        )
    return FileResponse(requested_path)


@router.delete("/cleanup-temp")
async def cleanup_temp_files(current_user: User = Depends(auth)):
    _ = current_user
    deleted_count = cleanup_temp_uploads()
    return {"deleted_count": deleted_count}


@router.get("/pages/{file_id}/{page_name}")
async def serve_page(
    file_id: int,
    page_name: str,
    access_token: Optional[str] = Query(default=None),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """Serve a pre-converted PDF page image for in-browser viewing."""
    user = _authenticate_file_request(access_token, current_user, db)
    _ = _get_authorized_medical_report_file(db=db, file_id=file_id, user=user)

    # Validate page_name to prevent path traversal
    if "/" in page_name or "\\" in page_name or ".." in page_name:
        raise HTTPException(status_code=404, detail="文件不存在")

    page_path = Path("data/uploads/pages") / str(file_id) / page_name
    if not page_path.exists() or not page_path.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")

    return FileResponse(page_path, media_type="image/png")


@router.get("/view/{file_id}")
async def view_file_as_html(
    file_id: int,
    access_token: Optional[str] = Query(default=None),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """Serve a self-contained HTML viewer for a file (PDF→pages, images direct).
    Works in all browsers including WeChat's built-in WebView."""
    user = _authenticate_file_request(access_token, current_user, db)
    db_file, _ = _get_authorized_medical_report_file(db=db, file_id=file_id, user=user)
    file_name = cast(str, cast(object, db_file.file_name))
    file_type = cast(Optional[str], cast(object, db_file.file_type))
    username = cast(str, cast(object, user.username))

    viewer_token = access_token
    if not viewer_token:
        viewer_token = create_access_token({"sub": username})

    page_dir = Path("data/uploads/pages") / str(file_id)
    page_urls: List[str] = []

    if page_dir.exists():
        import glob
        pages = sorted(glob.glob(str(page_dir / "page-*.png")))
        page_urls = [
            "/api/files/serve/{0}?page={1}".format(file_id, idx + 1)
            for idx, _ in enumerate(pages)
        ]

    # Build the token query fragment for image URLs inside the HTML
    token_q = "access_token={0}".format(viewer_token) if viewer_token else ""

    if page_urls:
        # PDF with pre-converted pages → paginated viewer
        template_path = Path(__file__).parent.parent / "services" / "viewer_template.html"
        html = template_path.read_text(encoding="utf-8")
        html = html.replace("__FILENAME__", file_name or "文件预览")
        html = html.replace("__PAGE_INFO__", f"共 {len(page_urls)} 页")
        html = html.replace("__PAGES__", json.dumps(page_urls))
        html = html.replace("__TOKEN__", viewer_token or "")
    elif isinstance(file_type, str) and file_type.startswith("image/"):
        # Single image → full-screen display
        img_url = "/api/files/serve/{0}".format(file_id)
        if token_q:
            img_url += f"?{token_q}"
        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{file_name}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html, body {{ width: 100%; height: 100%; background: #000; }}
.container {{ width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; }}
img {{ max-width: 100%; max-height: 100%; object-fit: contain; }}
.header {{ position: fixed; top: 0; left: 0; right: 0; padding: 12px 16px; background: rgba(0,0,0,0.5); z-index: 10; }}
.header button {{ background: none; border: none; color: #fff; font-size: 24px; cursor: pointer; }}
.filename {{ color: #ccc; font-size: 13px; margin-left: 8px; vertical-align: middle; }}
</style>
</head>
<body>
<div class="header">
  <button onclick="history.back()">&times;</button>
  <span class="filename">{file_name}</span>
</div>
<div class="container">
  <img src="{img_url}" alt="{file_name}" onclick="history.back()">
</div>
</body>
</html>"""
    else:
        # Unsupported format — offer download
        download_url = "/api/files/serve/{0}".format(file_id)
        if token_q:
            download_url += f"?{token_q}"
        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{file_name}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html, body {{ width: 100%; height: 100%; background: #f5f5f5; font-family: -apple-system, sans-serif; display: flex; align-items: center; justify-content: center; }}
.card {{ background: #fff; border-radius: 12px; padding: 32px; text-align: center; box-shadow: 0 2px 12px rgba(0,0,0,0.1); max-width: 320px; }}
.card h2 {{ font-size: 16px; color: #333; margin-bottom: 8px; }}
.card p {{ font-size: 13px; color: #888; margin-bottom: 20px; }}
.card a {{ display: inline-block; padding: 10px 24px; background: #22d3ee; color: #fff; border-radius: 8px; text-decoration: none; font-size: 14px; }}
</style>
</head>
<body>
<div class="card">
  <h2>{file_name}</h2>
  <p>此文件格式暂不支持在线预览<br>请下载后用对应应用打开</p>
  <a href="{download_url}">下载文件</a>
</div>
</body>
</html>"""

    return HTMLResponse(content=html)


@router.post("/upload/im-image")
async def upload_im_image(
    file: UploadFile = File(...),
    current_user: User = Depends(auth),
):
    import hashlib

    upload_dir = Path("data/uploads/im") / str(current_user.id)
    upload_dir.mkdir(parents=True, exist_ok=True)

    content = await file.read()
    file_hash = hashlib.sha256(content).hexdigest()[:16]
    ext = Path(file.filename or "image.jpg").suffix
    new_filename = f"{current_user.id}_{file_hash}{ext}"
    file_path = upload_dir / new_filename

    with open(file_path, "wb") as f:
        _ = f.write(content)

    return {
        "url": f"/uploads/im/{current_user.id}/{new_filename}",
        "filename": new_filename,
        "size": len(content),
    }

"""上传文件安全校验（2026-08-30 加固统一入口）。

Content-Type 可被客户端任意声明，不可作为安全依据；必须校验
扩展名白名单 + 文件魔数（magic bytes），防止上传 HTML/SVG 等
以同源内联渲染造成存储型 XSS。
"""

from pathlib import Path
from typing import Optional, Set

# 内联渲染安全的图片格式（SVG 因可携带脚本，明确排除）
ALLOWED_IMAGE_EXTS: Set[str] = {".jpg", ".jpeg", ".png", ".webp"}

_IMAGE_MAGIC = (
    (b"\xff\xd8\xff", ".jpg"),
    (b"\x89PNG\r\n\x1a\n", ".png"),
    (b"RIFF", ".webp"),  # RIFF....WEBP
)

_MAX_AVATAR_BYTES = 5 * 1024 * 1024
_MAX_IM_IMAGE_BYTES = 10 * 1024 * 1024


def detect_image_ext(content: bytes) -> Optional[str]:
    """按魔数识别图片真实格式，返回标准化扩展名；非白名单格式返回 None。"""
    if not content:
        return None
    for sig, ext in _IMAGE_MAGIC:
        if content.startswith(sig):
            if sig == b"RIFF":
                if len(content) >= 12 and content[8:12] == b"WEBP":
                    return ".webp"
                return None
            return ".jpg" if ext == ".jpg" else ext
    return None


def validate_image_upload(
    filename: str, content: bytes, max_bytes: int = _MAX_IM_IMAGE_BYTES
) -> str:
    """校验图片上传并返回安全的扩展名。

    校验项：非空、大小上限、扩展名白名单、魔数与扩展名一致。
    通过返回标准化扩展名（如 ``.jpg``）；不通过抛 ``ValueError``（API 层转 400）。
    """
    if not content:
        raise ValueError("上传文件不能为空")
    if len(content) > max_bytes:
        raise ValueError(f"图片过大，最大支持 {max_bytes // (1024 * 1024)}MB")
    declared_ext = (Path(filename).suffix or "").lower()
    if declared_ext == ".jpeg":
        declared_ext = ".jpg"
    if declared_ext not in ALLOWED_IMAGE_EXTS:
        raise ValueError(
            "不支持的图片格式，支持: " + ", ".join(sorted(ALLOWED_IMAGE_EXTS))
        )
    real_ext = detect_image_ext(content)
    if real_ext is None or real_ext != declared_ext:
        raise ValueError("图片内容与声明格式不符")
    return real_ext


def validate_avatar_upload(filename: str, content: bytes) -> str:
    """头像上传校验（5MB 上限）。"""
    return validate_image_upload(filename, content, max_bytes=_MAX_AVATAR_BYTES)

"""用户上传图片统一清洗：解码校验 → 按 EXIF 摆正 → 去除全部元数据 → 服务端定格式重编码。

患者照片的 EXIF 可能含 GPS 定位、拍摄设备与时间，属于不必要收集的个人信息，
落盘前必须剥离。扩展名只由解码出的真实格式决定，不信任客户端文件名或 Content-Type。
"""

import io
from typing import Tuple

from fastapi import UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError

UPLOAD_MAX_BYTES = 20 * 1024 * 1024
DEFAULT_MAX_SIDE = 4096
_MAX_PIXELS = 100_000_000
_ALLOWED_FORMATS = {"JPEG", "MPO", "PNG", "WEBP"}
_JPEG_QUALITY = 90
_READ_CHUNK = 1024 * 1024


async def read_upload_capped(upload: UploadFile, max_bytes: int = UPLOAD_MAX_BYTES) -> bytes:
    """分块读取上传文件，超过上限立即中止，避免把超大文件整个读进内存。"""
    declared = getattr(upload, "size", None)
    if declared is not None and declared > max_bytes:
        raise ValueError(f"文件过大，最大支持 {max_bytes // (1024 * 1024)}MB")
    buf = bytearray()
    while True:
        chunk = await upload.read(_READ_CHUNK)
        if not chunk:
            break
        buf.extend(chunk)
        if len(buf) > max_bytes:
            raise ValueError(f"文件过大，最大支持 {max_bytes // (1024 * 1024)}MB")
    return bytes(buf)


def _has_alpha(img: Image.Image) -> bool:
    if img.mode in ("RGBA", "LA", "PA"):
        return True
    return img.mode == "P" and "transparency" in img.info


def sanitize_image(content: bytes, max_side: int = DEFAULT_MAX_SIDE) -> Tuple[bytes, str]:
    """返回 (清洗后的字节, 扩展名 ".jpg"/".png")；不是可解码的 JPG/PNG/WebP 时抛 ValueError。"""
    if not content:
        raise ValueError("上传文件不能为空")
    try:
        with Image.open(io.BytesIO(content)) as probe:
            fmt = (probe.format or "").upper()
            width, height = probe.size
            probe.verify()
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError):
        raise ValueError("图片格式不支持或文件已损坏")
    if fmt not in _ALLOWED_FORMATS:
        raise ValueError("不支持的图片格式，请上传 JPG/PNG/WebP 图片")
    if width * height > _MAX_PIXELS:
        raise ValueError("图片分辨率过高，请压缩后再上传")

    try:
        with Image.open(io.BytesIO(content)) as img:
            img.load()
            icc_profile = img.info.get("icc_profile")
            normalized = ImageOps.exif_transpose(img)
    except (OSError, Image.DecompressionBombError):
        raise ValueError("图片格式不支持或文件已损坏")

    if max(normalized.size) > max_side:
        normalized.thumbnail((max_side, max_side), Image.LANCZOS)

    out = io.BytesIO()
    # 只写像素和 ICC 色彩配置（保证颜色测量一致），不带 exif/xmp/文本块。
    extra = {"icc_profile": icc_profile} if icc_profile else {}
    if _has_alpha(normalized):
        normalized.convert("RGBA").save(out, format="PNG", optimize=True, **extra)
        return out.getvalue(), ".png"
    normalized.convert("RGB").save(out, format="JPEG", quality=_JPEG_QUALITY, optimize=True, **extra)
    return out.getvalue(), ".jpg"


def mime_for_ext(ext: str) -> str:
    return "image/png" if ext == ".png" else "image/jpeg"

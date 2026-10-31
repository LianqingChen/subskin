"""上传图片清洗：GPS/EXIF 剥离、方向摆正、服务端定扩展名、尺寸上限。"""

import asyncio
import io

import pytest
from PIL import Image

from web.backend.utils.image_sanitize import read_upload_capped, sanitize_image

_GPS_IFD = 0x8825
_ORIENTATION = 0x0112


def _jpeg_with_exif(size=(40, 20), orientation=6) -> bytes:
    img = Image.new("RGB", size, (200, 120, 90))
    exif = Image.Exif()
    exif[_ORIENTATION] = orientation
    exif[0x010F] = "PhoneMaker"
    exif[_GPS_IFD] = {1: "N", 2: (39.0, 54.0, 27.0), 3: "E", 4: (116.0, 23.0, 17.0)}
    out = io.BytesIO()
    img.save(out, format="JPEG", exif=exif)
    return out.getvalue()


def test_gps_and_exif_removed_and_orientation_applied():
    raw = _jpeg_with_exif()
    with Image.open(io.BytesIO(raw)) as src:
        assert src.getexif().get_ifd(_GPS_IFD)

    cleaned, ext = sanitize_image(raw)

    assert ext == ".jpg"
    with Image.open(io.BytesIO(cleaned)) as out:
        assert out.size == (20, 40)  # orientation 6 = rotate 90°
        assert len(out.getexif()) == 0
        assert "exif" not in out.info


def test_alpha_png_stays_png_and_extension_ignores_client_name():
    img = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    cleaned, ext = sanitize_image(buf.getvalue())
    assert ext == ".png"
    with Image.open(io.BytesIO(cleaned)) as out:
        assert out.format == "PNG"


def test_opaque_webp_becomes_jpeg():
    buf = io.BytesIO()
    Image.new("RGB", (16, 16), (10, 20, 30)).save(buf, format="WEBP")
    _, ext = sanitize_image(buf.getvalue())
    assert ext == ".jpg"


def test_longest_side_capped():
    buf = io.BytesIO()
    Image.new("RGB", (3000, 1000)).save(buf, format="JPEG")
    cleaned, _ = sanitize_image(buf.getvalue(), max_side=1024)
    with Image.open(io.BytesIO(cleaned)) as out:
        assert max(out.size) == 1024


@pytest.mark.parametrize("payload", [b"", b"<svg onload=alert(1)>", b"\xff\xd8\xff" + b"0" * 50])
def test_non_images_rejected(payload):
    with pytest.raises(ValueError):
        sanitize_image(payload)


def test_gif_rejected():
    buf = io.BytesIO()
    Image.new("P", (4, 4)).save(buf, format="GIF")
    with pytest.raises(ValueError):
        sanitize_image(buf.getvalue())


class _FakeUpload:
    def __init__(self, data: bytes, size=None):
        self._stream = io.BytesIO(data)
        self.size = size

    async def read(self, n: int = -1) -> bytes:
        return self._stream.read(n)


def test_read_upload_capped_enforces_limit():
    assert asyncio.run(read_upload_capped(_FakeUpload(b"x" * 10), max_bytes=10)) == b"x" * 10
    with pytest.raises(ValueError):
        asyncio.run(read_upload_capped(_FakeUpload(b"x" * 11), max_bytes=10))
    with pytest.raises(ValueError):
        asyncio.run(read_upload_capped(_FakeUpload(b"", size=11), max_bytes=10))

"""Capture quality: only information loss is a hard retake."""

import io

import numpy as np
from PIL import Image
from web.backend.services.vasi_quality import vasi_quality_checker


def png(array: np.ndarray) -> bytes:
    stream = io.BytesIO()
    Image.fromarray(array).save(stream, format="PNG")
    return stream.getvalue()


def test_shadow_and_glare_do_not_force_retake():
    rng = np.random.default_rng(4)
    photo = np.clip(
        np.array([150, 110, 80]) + rng.integers(-6, 7, (140, 180, 3)), 0, 230
    ).astype(np.uint8)
    photo[:, :36] = (36, 32, 28)
    photo[12:36, 90:114] = 250
    report = vasi_quality_checker.check_all(png(photo))
    assert report.overall != "poor"
    assert report.suggestions != ["照片过曝、过暗或严重模糊，请重拍"]
    joined = " ".join(report.suggestions)
    assert "保持手机稳定" not in joined
    assert "拍照" not in joined


def test_washed_out_frame_is_a_short_retake():
    report = vasi_quality_checker.check_all(png(np.full((96, 96, 3), 255, np.uint8)))
    assert report.overall == "poor"
    assert report.suggestions == ["照片过曝、过暗或严重模糊，请重拍"]

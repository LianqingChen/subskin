"""逐像素精修（vasi_pixel_refine）单元测试。

覆盖设计文档 §4.1 验收点：
  - 矩形候选 → 精修后不再是轴对齐矩形；
  - lesion ⊆ skin 恒成立；
  - SAM 低分/低 IoU/面积比越界 → 正确降级并记录原因；
  - 超预算 → 剩余区域标 candidate-only 且不抛异常；
  - 开关关闭 → 返回 None（调用方保留候选图层）；
  - 纯 CV 降级路径可用。

全部为纯函数测试：SAM 与 CV 均被替换/合成，不触网、不落库。
"""

from __future__ import annotations

import io
import os

import numpy as np
import pytest
from PIL import Image

cv2 = pytest.importorskip("cv2")

from web.backend.services import vasi_pixel_refine as vpr  # noqa: E402
from web.backend.services.annotation_contract import encode_layer  # noqa: E402
from web.backend.services.assessment_measurement import decode_mask  # noqa: E402

H, W = 320, 320


def _synthetic_image(with_lesion: bool = True) -> bytes:
    """肤色底 + 中央浅色圆形病灶（合成图，非用户照片）。"""
    img = np.zeros((H, W, 3), dtype=np.uint8)
    img[:, :] = (65, 65, 65)
    img[16:304,16:304] = (205, 168, 140)
    if with_lesion:
        cv2.circle(img, (W // 2, H // 2), 60, (242, 232, 224), -1)
    img = cv2.GaussianBlur(img, (7, 7), 0)
    buffer = io.BytesIO()
    Image.fromarray(img).save(buffer, format="PNG")
    return buffer.getvalue()


def _rect_geometry() -> dict:
    """四个区域全用轴对齐矩形描述 —— 复刻用户看到的退化候选。"""
    return {
        "protocol": "skin-outline-v1",
        "status": "candidate",
        "skin_regions": [[[0.05, 0.05], [0.95, 0.05], [0.95, 0.95], [0.05, 0.95]]],
        "excluded_regions": [],
        "lesion_regions": [[[0.31, 0.31], [0.69, 0.31], [0.69, 0.69], [0.31, 0.69]]],
        "uncertain_regions": [],
    }


def _mask_data_url(circle: bool = True, radius: int = 60, score_mask=None) -> str:
    mask = np.zeros((H, W), dtype=bool)
    if circle:
        cv2.circle(mask.view(np.uint8).reshape(H, W), (W // 2, H // 2), radius, 1, -1)
    else:
        mask[100:220, 100:220] = True
    return encode_layer(mask, (0, 170, 100))


class _FakeSam:
    """可控的 SAM 替身：记录调用参数，返回预置掩膜与分数。"""

    def __init__(self, score: float = 0.95, radius: int = 60, circle: bool = True):
        self.score = score
        self.radius = radius
        self.circle = circle
        self.points_seen = []

    def prepare_image(self, cache_key, image_bytes):
        return {"width": W, "height": H, "cached": False}

    def predict_by_points(self, cache_key, points, multimask=True, box=None):
        self.points_seen.append(list(points))
        return {
            "mask_b64_png": _mask_data_url(self.circle, self.radius),
            "score": self.score,
            "area_pixels": int(np.pi * self.radius ** 2),
        }


def _install_sam(monkeypatch, fake: _FakeSam) -> None:
    monkeypatch.setattr(vpr.vasi_promptable, "prepare_image", fake.prepare_image)
    monkeypatch.setattr(vpr.vasi_promptable, "predict_by_points", fake.predict_by_points)


def _fill_ratio(mask):
    if mask is None or not mask.any():
        return 0.0
    ys, xs = np.where(mask)
    box = (ys.max() - ys.min() + 1) * (xs.max() - xs.min() + 1)
    return float(mask.sum()) / max(box, 1)


# ── 验收点 1：矩形候选 → 精修后不再是矩形 ──────────────────────────────


def test_rectangle_candidate_is_refined_to_non_rectangular(monkeypatch):
    _install_sam(monkeypatch, _FakeSam(score=0.95))
    out = vpr.refine_annotation_layers(_synthetic_image(), _rect_geometry())
    assert out is not None
    lesion = decode_mask(out["lesion_layer_data_url"])
    skin = decode_mask(out["skin_layer_data_url"])
    assert lesion is not None and lesion.any()
    # 修复前：矩形候选的外接框填充率恒为 1.00
    assert _fill_ratio(lesion) < 0.95, "白斑掩膜仍接近矩形，未贴合真实边缘"
    assert out["provenance"]["engine"]["lesion"] == ["sam"]
    assert out["provenance"]["status"] == "refined"
    # lesion ⊆ skin
    assert int((lesion & ~skin).sum()) == 0


# ── 验收点 2：lesion ⊆ skin ────────────────────────────────────────────


def test_lesion_never_exceeds_skin(monkeypatch):
    _install_sam(monkeypatch, _FakeSam(score=0.95, radius=140))  # 超出皮肤候选的巨掩膜
    geometry = _rect_geometry()
    geometry["skin_regions"] = [[[0.30, 0.30], [0.70, 0.30], [0.70, 0.70], [0.30, 0.70]]]
    out = vpr.refine_annotation_layers(_synthetic_image(), geometry)
    assert out is not None
    lesion = decode_mask(out["lesion_layer_data_url"])
    skin = decode_mask(out["skin_layer_data_url"])
    assert int((lesion & ~skin).sum()) == 0


# ── 验收点 3：低分 → 降级并记录原因 ────────────────────────────────────


def test_low_sam_score_degrades_with_reason(monkeypatch):
    _install_sam(monkeypatch, _FakeSam(score=0.10))
    out = vpr.refine_annotation_layers(_synthetic_image(), _rect_geometry())
    assert out is not None
    provenance = out["provenance"]
    assert "lesion:sam-low-score" in provenance["fallback_reasons"]
    assert "sam" not in provenance["engine"]["lesion"]


def test_area_ratio_out_of_range_degrades(monkeypatch):
    # 半径 138 的圆完全包住 122×122 的候选矩形：IoU≈0.25（过），面积比≈4.0（越界）
    _install_sam(monkeypatch, _FakeSam(score=0.95, radius=138))
    out = vpr.refine_annotation_layers(_synthetic_image(), _rect_geometry())
    reasons = out["provenance"]["fallback_reasons"]
    assert "lesion:sam-area-ratio" in reasons


# ── 验收点 4：超预算 → candidate-only 且不抛异常 ───────────────────────


def test_budget_exhausted_marks_candidate_only(monkeypatch):
    _install_sam(monkeypatch, _FakeSam(score=0.95))
    out = vpr.refine_annotation_layers(
        _synthetic_image(), _rect_geometry(), time_budget_s=0.0
    )
    assert out is not None
    provenance = out["provenance"]
    # 皮肤已被 CV 精修（recomputed 为真），白斑因超预算保持候选 → partial；
    # 若皮肤也未能精修则为 candidate-only。两者都不允许出现 "refined"。
    assert provenance["status"] in ("partial", "candidate-only")
    assert provenance["engine"]["lesion"] == ["unresolved"]
    assert "lesion:budget-exhausted" in provenance["fallback_reasons"]
    # 超预算区域保留在橙色待核对层，不能作为成功分割。
    lesion = decode_mask(out["lesion_layer_data_url"])
    uncertain = decode_mask(out["annotation"]["uncertain_layer_data_url"])
    assert lesion is not None and not lesion.any()
    assert uncertain is not None and uncertain.any()
    assert provenance["measurement_eligible"] is False


# ── 验收点 5：开关关闭 ─────────────────────────────────────────────────


def test_disabled_returns_none(monkeypatch):
    monkeypatch.setenv("VASI_PIXEL_REFINE", "0")
    assert vpr.is_enabled() is False
    assert vpr.refine_annotation_layers(_synthetic_image(), _rect_geometry()) is None


# ── 验收点 6：纯 CV 降级路径 ───────────────────────────────────────────


def test_cv_only_layers_are_consistent():
    out = vpr.cv_only_layers(_synthetic_image())
    assert out is not None
    skin = decode_mask(out["skin_layer_data_url"])
    lesion = decode_mask(out["lesion_layer_data_url"])
    assert skin is not None and skin.any()
    assert int((lesion & ~skin).sum()) == 0
    assert out["provenance"]["status"] == "cv-fallback"
    assert out["annotation"]["refine"]["measurement_eligible"] is False
    assert not lesion.any()
    assert decode_mask(out["annotation"]["uncertain_layer_data_url"]).any()


def test_cv_only_returns_none_on_undecodable_image():
    assert vpr.cv_only_layers(b"not-an-image") is None


# ── 辅助函数行为 ───────────────────────────────────────────────────────


def test_sam_points_add_only_outside_corners():
    circle = np.zeros((H, W), dtype=bool)
    cv2.circle(circle.view(np.uint8).reshape(H, W), (W // 2, H // 2), 60, 1, -1)
    points = vpr._sam_points(circle, W, H)
    assert points[0][2] == 1                      # 质心为前景
    assert sum(1 for p in points if p[2] == 0) == 4   # 圆形的四角在掩膜外
    rect = np.zeros((H, W), dtype=bool)
    rect[100:220, 100:220] = True
    rect_points = vpr._sam_points(rect, W, H)
    assert sum(1 for p in rect_points if p[2] == 0) >= 1
    assert all(not rect[round(y*H),round(x*W)] for x,y,label in rect_points if label == 0)


def test_components_sorted_by_area_and_filtered():
    mask = np.zeros((H, W), dtype=bool)
    mask[10:30, 10:30] = True          # 400 px
    mask[100:180, 100:180] = True      # 6400 px
    mask[300:302, 300:302] = True      # 4 px，应被最小面积过滤
    comps = vpr._components(mask)
    assert len(comps) == 2
    assert int(comps[0].sum()) > int(comps[1].sum())


def test_iou_bounds():
    a = np.zeros((10, 10), dtype=bool)
    b = np.zeros((10, 10), dtype=bool)
    a[0:5, 0:5] = True
    b[0:5, 0:5] = True
    assert vpr._iou(a, b) == pytest.approx(1.0)
    assert vpr._iou(a, np.zeros((10, 10), dtype=bool)) == 0.0


def test_colour_plausible_rejects_dark_or_high_chroma():
    assert vpr._colour_plausible({"available": 0.0}) is False  # 无参考色不能被当作通过
    assert vpr._colour_plausible({"available": 1.0, "lesion_L": 70, "skin_L": 60,
                                  "lesion_C": 10, "skin_C": 20}) is True
    assert vpr._colour_plausible({"available": 1.0, "lesion_L": 40, "skin_L": 60,
                                  "lesion_C": 10, "skin_C": 20}) is False
    assert vpr._colour_plausible({"available": 1.0, "lesion_L": 70, "skin_L": 60,
                                  "lesion_C": 40, "skin_C": 20}) is False

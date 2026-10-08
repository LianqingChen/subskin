"""边缘感知白斑分割（vasi_edge_segmentation）单元测试。

覆盖：
  - 局部参考能消除光照梯度（同一色块在左右两侧亮度不同时 ΔL ≈ 0）；
  - 合成白斑图上的范围/边缘精度（Dice）；
  - 边缘吸附把边界拉向真实色差脊线；
  - 连通域过滤剔除背景/高光伪阳性；
  - 多边形提取保留细节且坐标合法。
"""

from __future__ import annotations

import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")

from web.backend.services.vasi_edge_segmentation import (  # noqa: E402
    EdgeSegConfig,
    build_lesion_score,
    compute_gradient_magnitude,
    compute_local_reference,
    extract_precise_polygon,
    hysteresis_threshold,
    refine_mask_by_edges,
    segment_lesions_edge_aware,
    snap_mask_to_edges,
)


def _synthetic_skin(h=256, w=256) -> np.ndarray:
    """带横向光照梯度的健康皮肤（LAB 意义上的肤色渐变）。"""
    x = np.linspace(0.72, 1.28, w)[None, :]
    y = np.linspace(0.96, 1.04, h)[:, None]
    base = np.array([205.0, 165.0, 140.0])[None, None, :]
    img = base * (x * y)[:, :, None]
    return np.clip(img, 0, 255).astype(np.uint8)


def _add_lesion(img: np.ndarray, center, radius) -> np.ndarray:
    """在中心放一个低色素（更亮、低彩度）的圆形白斑。"""
    out = img.astype(np.float32)
    yy, xx = np.mgrid[0 : img.shape[0], 0 : img.shape[1]]
    m = (yy - center[0]) ** 2 + (xx - center[1]) ** 2 <= radius ** 2
    lesion_color = np.array([232.0, 226.0, 222.0])  # 几乎无色素
    out[m] = lesion_color
    return np.clip(out, 0, 255).astype(np.uint8)


def _dice(a: np.ndarray, b: np.ndarray) -> float:
    inter = float(np.logical_and(a, b).sum())
    denom = float(a.sum() + b.sum())
    return (2 * inter / denom) if denom else 1.0


# ── 局部参考 / 光照校正 ───────────────────────────────────────────────────


def test_local_reference_tracks_illumination_gradient():
    img = _synthetic_skin()
    region = np.ones(img.shape[:2], dtype=bool)
    score, parts = build_lesion_score(img, region)

    left = parts["delta_l"][:, :40]
    right = parts["delta_l"][:, -40:]
    # 光照从暗到亮差 ~55 灰阶；校正后两侧 ΔL 都应接近 0
    assert abs(float(left.mean())) < 8.0
    assert abs(float(right.mean())) < 8.0
    # 且左右差异被大幅压缩（原始亮度差 > 50）
    raw_gap = float(img[:, :40, 0].mean()) - float(img[:, -40:, 0].mean())
    assert abs(raw_gap) > 40
    ref_gap = abs(float(parts["l_ref"][:, :40].mean()) - float(parts["l_ref"][:, -40:].mean()))
    assert ref_gap > 30  # 参考本身跟着光照走
    assert abs(float(left.mean()) - float(right.mean())) < 8.0


def test_local_reference_handles_empty_region():
    img = _synthetic_skin(64, 64)
    empty = np.zeros(img.shape[:2], dtype=bool)
    ref = compute_local_reference(
        img[:, :, 0].astype(np.float32), empty, cells=8, win=3
    )
    assert ref.shape == img.shape[:2]
    assert np.isfinite(ref).all()


# ── 梯度 / 邻域色差 ────────────────────────────────────────────────────────


def test_gradient_peaks_at_lesion_boundary():
    img = _add_lesion(_synthetic_skin(), (128, 128), 40)
    grad = compute_gradient_magnitude(img)
    yy, xx = np.mgrid[0 : img.shape[0], 0 : img.shape[1]]
    r = np.sqrt((yy - 128.0) ** 2 + (xx - 128.0) ** 2)

    on_edge = grad[(r > 37) & (r < 43)].mean()
    inside = grad[r < 25].mean()
    outside = grad[(r > 55) & (r < 75)].mean()
    assert on_edge > 4 * max(inside, 1e-3)
    assert on_edge > 4 * max(outside, 1e-3)


# ── 端到端：范围与边缘 ────────────────────────────────────────────────────


@pytest.mark.parametrize("radius", [24, 40, 56])
def test_segment_lesion_area_and_edges(radius):
    base = _synthetic_skin()
    img = _add_lesion(base, (128, 128), radius)
    region = np.ones(img.shape[:2], dtype=bool)
    yy, xx = np.mgrid[0 : img.shape[0], 0 : img.shape[1]]
    truth = np.sqrt((yy - 128.0) ** 2 + (xx - 128.0) ** 2) <= radius

    res = segment_lesions_edge_aware(img, region)
    mask = res["lesion_mask"]
    assert mask.any(), "合成白斑应被检出"
    assert _dice(mask, truth) > 0.85

    # 边缘精度：检出的边界像素到真实圆周的平均距离应很小
    edge = mask & ~cv2.erode(mask.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    dist = np.abs(np.sqrt((yy - 128.0) ** 2 + (xx - 128.0) ** 2)[edge] - radius)
    assert float(dist.mean()) < 4.0


def test_no_false_positive_on_plain_skin():
    img = _synthetic_skin()
    region = np.ones(img.shape[:2], dtype=bool)
    res = segment_lesions_edge_aware(img, region)
    # 健康皮肤上不应报出大面积白斑
    assert res["lesion_mask"].sum() / region.sum() < 0.01


def test_background_rectangle_is_rejected():
    """图像角落的亮色背景块不应被判为白斑（外环缺少肤色证据）。

    模拟真实场景：分析区域被扩到整幅图（含背景），但肤色候选只在中心。
    """
    img = _synthetic_skin(320, 320)
    skin = np.zeros(img.shape[:2], dtype=bool)
    skin[40:280, 40:280] = True      # 中心皮肤
    img[~skin] = (60, 60, 60)        # 四周深色背景
    img[10:70, 10:70] = (240, 240, 236)  # 背景里的亮色块（桌面/纸张）
    region = np.ones(img.shape[:2], dtype=bool)  # 过度扩张的分析区域

    res = segment_lesions_edge_aware(img, region, skin_candidate=skin)
    assert res["lesion_mask"][10:70, 10:70].sum() == 0


# ── 边缘吸附 ──────────────────────────────────────────────────────────────


def test_snap_moves_boundary_toward_true_edge():
    base = _synthetic_skin()
    img = _add_lesion(base, (128, 128), 40)
    truth = np.zeros(img.shape[:2], dtype=bool)
    yy, xx = np.mgrid[0 : img.shape[0], 0 : img.shape[1]]
    truth[np.sqrt((yy - 128.0) ** 2 + (xx - 128.0) ** 2) <= 40] = True

    # 起始 mask 比真实白斑大 8px
    coarse = np.zeros_like(truth)
    coarse[np.sqrt((yy - 128.0) ** 2 + (xx - 128.0) ** 2) <= 48] = True
    before = _dice(coarse, truth)

    snapped = snap_mask_to_edges(img, coarse, radius=10)
    after = _dice(snapped, truth)
    assert after >= before, "边缘吸附不应让边界偏离真实色差脊线"
    assert after > 0.9


def test_refine_mask_by_edges_is_safe_on_empty():
    img = _synthetic_skin(64, 64)
    empty = np.zeros(img.shape[:2], dtype=bool)
    out = refine_mask_by_edges(img, empty)
    assert out.shape == empty.shape
    assert not out.any()


# ── 滞后阈值 ──────────────────────────────────────────────────────────────


def test_hysteresis_keeps_connected_region_only():
    score = np.zeros((60, 60), dtype=np.float32)
    score[10:20, 10:20] = 0.9        # 强核心 + 连通弱区
    score[10:20, 20:26] = 0.35
    score[40:45, 40:45] = 0.35       # 孤立的弱区（无核心）应被丢弃
    valid = np.ones((60, 60), dtype=bool)

    out = hysteresis_threshold(score, 0.6, 0.3, valid)
    assert out[12, 12] and out[12, 22]
    assert not out[42, 42]


# ── 多边形 ────────────────────────────────────────────────────────────────


def test_extract_precise_polygon_keeps_detail():
    mask = np.zeros((200, 200), dtype=bool)
    yy, xx = np.mgrid[0:200, 0:200]
    mask[np.sqrt((yy - 100.0) ** 2 + (xx - 100.0) ** 2) <= 60] = True

    pts = extract_precise_polygon(mask, max_points=180)
    assert pts is not None and len(pts) >= 12
    arr = np.array(pts)
    assert arr.min() >= 0.0 and arr.max() <= 1.0
    cx, cy = arr[:, 0].mean(), arr[:, 1].mean()
    assert abs(cx - 0.5) < 0.02 and abs(cy - 0.5) < 0.02


def test_extract_precise_polygon_returns_none_for_empty():
    assert extract_precise_polygon(np.zeros((20, 20), dtype=bool)) is None


# ── 工作分辨率 ────────────────────────────────────────────────────────────


def test_output_masks_match_input_shape():
    img = _add_lesion(_synthetic_skin(600, 800), (300, 400), 60)
    region = np.ones(img.shape[:2], dtype=bool)
    res = segment_lesions_edge_aware(img, region)
    assert res["lesion_mask"].shape == img.shape[:2]
    assert res["skin_region"].shape == img.shape[:2]
    assert res["score"].shape == img.shape[:2]


def test_small_image_not_rejected_by_area_ratio():
    """小图上按面积比例的相对阈值不应把全部候选拒之门外。"""
    img = _add_lesion(_synthetic_skin(120, 120), (60, 60), 22)
    region = np.ones(img.shape[:2], dtype=bool)
    res = segment_lesions_edge_aware(img, region, cfg=EdgeSegConfig())
    assert res["lesion_mask"].any()

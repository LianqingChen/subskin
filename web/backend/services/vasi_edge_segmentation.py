"""边缘感知 + 局部自适应的白斑（脱色素）分割。

设计动机（用户反馈：白斑面积识别不准，希望用「逐像素颜色 + 相邻像素颜色差异」
把白斑范围与边缘识别精准）：

原实现的两条根本缺陷：
  1. `detect_vitiligo_within_skin` 用**全图单一阈值**（median+offset / p75+5）。
     真实照片普遍存在侧向光照、阴影、反光，亮侧皮肤整体高于阈值 → 大面积误判。
  2. 完全未使用「相邻像素颜色差异」。白斑与正常皮肤的分界本质上是**局部色差
     脊线**，只有沿梯度找边界才能贴合真实边缘。

本模块的算法链路（纯 cv2/numpy，无新增依赖，O(n)）：

  ① 逐像素颜色：LAB 空间提取亮度 L 与色素强度 chroma=‖(a*,b*)‖。
  ② 局部光照校正：把图像切成 CELLS×CELLS 网格，用直方图精确求每个网格的
     分位数（L 取 p25 = 局部健康肤色，chroma 取 p75 = 局部本色皮肤），
     再做「取窗口内最暗邻域」的空间腐蚀 + 双线性上采样，得到**逐像素局部
     参考肤色**。ΔL = L − L_ref 消除光照梯度。
  ③ 相邻像素差异：对 L/a*/b* 做 Sobel，合成梯度幅值 = 邻域色差。
  ④ 白斑似然：局部更亮（ΔL↑）+ 局部更少色素（Δchroma↑）− 内部有强边缘
     （毛发/褶皱/反光/背景边界）。
  ⑤ 滞后双阈值：只保留与高置信核心连通的候选（Canny 思路），消除孤立噪点。
  ⑥ 分水岭边缘吸附：以颜色梯度为高程，用「白斑核心 / 健康皮肤核心」两个
     标记做分水岭，边界自动收敛到**色差最大处**；变更幅度被限制在
     ±snap_radius 内，保证稳定。
  ⑦ 连通域过滤：剔除过小、贴边背景、偏红（红疹/血管）、细长高光、
     边界对比度不足的伪阳性。

对外主要接口：
  - `segment_lesions_edge_aware(img_rgb, region=None)` → 完整结果（mask/region/stats）
  - `refine_mask_by_edges(img_rgb, mask, region=None)` → 对任意来源（SAM/U-Net/CV）
    的 mask 做边缘吸附精修，风格与结构保持向后兼容
  - `extract_precise_polygon(mask, ...)` → 亚像素平滑 + 保留细节的归一化多边形
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

try:
    import cv2

    _CV2_AVAILABLE = True
except ImportError:  # pragma: no cover - opencv is a hard dependency in practice
    _CV2_AVAILABLE = False
    logger.warning("opencv-python not available; edge-aware segmentation disabled")


# ── 工作分辨率 ──
# 4000×3000 的原图直接做形态学/滤波会带来 1-2s 的额外延迟。分割只需要
# 边界级别的几何精度，1280px 已足够，掩膜再按最近邻还原到原尺寸。
WORK_MAX_DIM = 1280

# ── 局部参考肤色网格 ──
CELLS = 48          # 网格分辨率（长边切 48 份）
LOCAL_WIN = 13      # 空间聚合窗口（单位：格）→ 约 27% 长边的邻域
L_PCT = 25.0        # 局部健康肤色亮度分位（保留给外部调参）
C_PCT = 75.0        # 局部本色皮肤色素分位


@dataclass
class EdgeSegConfig:
    """边缘感知分割参数（可被 vasi_param_optimizer 之类的外部流程覆盖）。"""

    local_win: int = LOCAL_WIN
    l_pct: float = L_PCT
    c_pct: float = C_PCT
    # 感知阈值：ΔL 需超过 dead_zone 才有意义（JND ≈ 1-2 L* 单位）。
    # 归一化刻意使用**固定尺度**而非按图自适应：真实白斑与健康皮肤的亮度差
    # 普遍在 8 L* 以上，用固定尺度才能保证同一用户不同次拍摄的阈值一致
    # （自适应 σ 会让同一白斑在不同照片上得到 2.7% vs 39% 的结论）。
    l_dead_zone: float = 4.0
    c_dead_zone: float = 2.0
    l_scale: float = 12.0
    c_scale: float = 8.0
    # mean-shift 带宽用的稳健噪声尺度上下限（同时用于诊断输出）
    sigma_floor_l: float = 3.5
    sigma_ceil_l: float = 10.0
    sigma_floor_c: float = 2.5
    sigma_ceil_c: float = 6.0
    # 似然权重
    w_l: float = 0.55
    w_c: float = 0.45
    w_texture: float = 0.18
    # 纹理惩罚尺度：局部平均梯度 / (gain × 区域中位梯度)
    texture_gain: float = 3.0
    # 滞后阈值
    hi_thresh: float = 0.55
    lo_thresh: float = 0.28
    # 边缘吸附
    snap_radius: int = 4
    # 连通域过滤
    min_area_ratio: float = 0.0015
    min_mean_score: float = 0.34
    max_border_contact: float = 0.30
    min_circularity: float = 0.08
    # 参考值安全夹取：只用很宽的全局分位夹取，避免阴影/大面积脱失把参考
    # 拉偏。上界必须足够宽（p95），否则强光照梯度下远端偏亮的健康皮肤
    # 会被误判成白斑。
    ref_global_lo_pct: float = 2.0
    ref_global_hi_pct: float = 95.0


# ── 基础颜色特征 ────────────────────────────────────────────────────────────


def to_lab_channels(img_rgb: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """返回 (L, chroma, A, B)，均为 float32；L/chroma 单位约 0-255。"""
    bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    L = lab[:, :, 0]
    A = lab[:, :, 1]
    B = lab[:, :, 2]
    chroma = np.sqrt((A - 128.0) ** 2 + (B - 128.0) ** 2)
    return L, chroma, A, B


def compute_gradient_magnitude(
    img_rgb: np.ndarray, blur_sigma: float = 1.0
) -> np.ndarray:
    """相邻像素颜色差异：LAB 三通道 Sobel 合成梯度幅值。

    亮度权重最高（人眼对亮度差异最敏感），a*/b* 各 0.7 —— 脱色素区域
    在彩度上的跳变同样是有效边界证据。
    """
    L, chroma, A, B = to_lab_channels(img_rgb)
    weights = (1.0, 0.8, 0.8)
    total = np.zeros(L.shape, dtype=np.float32)
    for ch, wt in zip((L, A, B), weights):
        if blur_sigma > 0:
            ch = cv2.GaussianBlur(ch, (0, 0), blur_sigma)
        gx = cv2.Sobel(ch, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(ch, cv2.CV_32F, 0, 1, ksize=3)
        total += wt * (gx * gx + gy * gy)
    del chroma
    return np.sqrt(total) / sum(weights)


# ── 局部参考（光照校正） ────────────────────────────────────────────────────


def _cell_percentile_map(
    channel: np.ndarray, valid: np.ndarray, cells: int, pct: float
) -> Tuple[np.ndarray, np.ndarray]:
    """把图像切成 cells×cells 网格，用直方图求每格在有效像素上的分位数。

    返回 (值图 ncy×ncx, 有效计数图 ncy×ncx)。全向量化，O(n)。
    """
    h, w = channel.shape
    cell_h = max(1, int(np.ceil(h / cells)))
    cell_w = max(1, int(np.ceil(w / cells)))
    ncy = max(1, int(np.ceil(h / cell_h)))
    ncx = max(1, int(np.ceil(w / cell_w)))

    q = np.clip(np.rint(channel), 0, 255).astype(np.int32)
    cy = np.clip(np.arange(h) // cell_h, 0, ncy - 1)
    cx = np.clip(np.arange(w) // cell_w, 0, ncx - 1)
    cell_id = (cy[:, None] * ncx + cx[None, :]).ravel()

    flat_valid = valid.ravel()
    idx = cell_id[flat_valid] * 256 + q.ravel()[flat_valid]
    hist = np.bincount(idx, minlength=ncy * ncx * 256).reshape(ncy, ncx, 256)
    counts = hist.sum(axis=2)
    cum = np.cumsum(hist, axis=2)

    # 目标序位（空网格 target=0 → argmax 返回 0，稍后由邻近网格填充）
    target = counts[:, :, None] * (pct / 100.0)
    values = np.argmax(cum >= target, axis=2).astype(np.float32)
    return values, counts


def _fill_empty_cells(values: np.ndarray, counts: np.ndarray) -> np.ndarray:
    """用邻域均值迭代填充空网格（无有效像素的区域）。"""
    out = values.copy()
    known = counts > 0
    if known.all():
        return out
    if not known.any():
        return out
    filled = known.copy()
    for _ in range(64):
        if filled.all():
            break
        num = cv2.boxFilter(
            np.where(filled, out, 0.0), -1, (3, 3), normalize=False
        )
        den = cv2.boxFilter(filled.astype(np.float32), -1, (3, 3), normalize=False)
        new = den > 0
        grow = new & (~filled)
        out[grow] = (num[grow] / den[grow]).astype(np.float32)
        filled |= grow
    if not filled.all():
        out[~filled] = float(np.median(out[filled]))
    return out


def compute_local_reference(
    channel: np.ndarray,
    valid: np.ndarray,
    cells: int = CELLS,
    pct: float = L_PCT,
    win: int = LOCAL_WIN,
    mode: str = "min",
) -> np.ndarray:
    """逐像素局部参考值（光照/肤色自适应）。

    Args:
        channel: float32 通道（0-255）。
        valid: bool 分析区域。
        pct: 网格内分位数。
        win: 空间聚合窗口（格）。
        mode: "min" 取窗口内最暗（用于健康肤色亮度参考）；
              "max" 取窗口内最亮（用于亮区分位，做归一化尺度）。

    Returns:
        与 channel 同尺寸的 float32 参考图。
    """
    if not _CV2_AVAILABLE or channel.size == 0 or not valid.any():
        return np.zeros_like(channel, dtype=np.float32)

    cell_vals, counts = _cell_percentile_map(channel, valid, cells, pct)
    cell_vals = _fill_empty_cells(cell_vals, counts)

    k = max(1, int(win) | 1)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k, k))
    if mode == "max":
        cell_ref = cv2.dilate(cell_vals, kernel)
    elif mode == "mean":
        cell_ref = cv2.blur(cell_vals, (k, k))
    else:
        cell_ref = cv2.erode(cell_vals, kernel)

    h, w = channel.shape
    ref = cv2.resize(cell_ref, (w, h), interpolation=cv2.INTER_LINEAR)
    # 网格边界会让参考出现块状台阶，轻度平滑使 ΔL 连续
    ref = cv2.GaussianBlur(ref, (0, 0), 1.5)
    return ref.astype(np.float32)


def _clamp_reference(
    ref: np.ndarray, channel: np.ndarray, valid: np.ndarray, cfg: EdgeSegConfig
) -> np.ndarray:
    """用全局分位数夹取参考值，避免阴影/大面积脱失把参考拉偏。"""
    if not valid.any():
        return ref
    vals = channel[valid]
    lo = float(np.percentile(vals, cfg.ref_global_lo_pct))
    hi = float(np.percentile(vals, cfg.ref_global_hi_pct))
    return np.clip(ref, lo, hi)


# ── 白斑似然图 ──────────────────────────────────────────────────────────────


def _median_reference(
    channel: np.ndarray,
    valid: np.ndarray,
    cells: int = CELLS,
    win: int = LOCAL_WIN,
) -> np.ndarray:
    """局部中位参考（网格直方图 p50 + 空间均值 + 双线性上采样）。"""
    return compute_local_reference(channel, valid, cells=cells, pct=50.0, win=win, mode="mean")


def _mode_reference(
    channel: np.ndarray,
    valid: np.ndarray,
    sigma: float,
    cells: int = CELLS,
    win: int = LOCAL_WIN,
    iters: int = 3,
    band_gain: float = 1.5,
) -> np.ndarray:
    """局部**众数**参考（mean-shift）。

    单纯用「比局部中位更暗的像素」再求中位（旧实现）会系统性收敛到局部 p25：
    即便全是健康皮肤，ΔL 也会有 ~12 L* 的偏移，导致大面积误判。
    这里用带宽 = band_gain × σ 的对称 mean-shift 迭代，收敛到局部分布的
    众数：均匀皮肤上就是肤色本身（Δ≈0），双峰（皮肤+白斑）时收敛到占多数
    的健康皮肤峰。
    """
    ref = _median_reference(channel, valid, cells=cells, win=win)
    band = max(3.0, band_gain * float(sigma))
    for _ in range(max(1, iters)):
        sel = valid & (np.abs(channel - ref) <= band)
        # 选区过小时保持上一轮参考，避免在纯白斑窗口内漂移
        enough = sel.sum() > max(64, int(0.005 * max(int(valid.sum()), 1)))
        if not enough:
            break
        ref = _median_reference(channel, sel, cells=cells, win=win)
    return ref


def build_lesion_score(
    img_rgb: np.ndarray,
    region: np.ndarray,
    cfg: Optional[EdgeSegConfig] = None,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """逐像素白斑似然（0-1），并返回中间证据图供调试/记录。

    流程：
      1) mean-shift 求解**局部众数**参考肤色（同时得到亮度 L_ref 与色素
         C_ref），消除侧向光照/阴影，且不被大面积白斑拉高；
      2) ΔL = L − L_ref、Δchroma = C_ref − C，用固定感知尺度归一化
         （跨照片/跨时间一致，便于趋势对比）；
      3) 减去局部纹理惩罚（内部有强边缘 → 毛发/褶皱/反光，不是白斑）。
    """
    cfg = cfg or EdgeSegConfig()
    L, chroma, _, _ = to_lab_channels(img_rgb)
    h, w = L.shape

    # ── 全局稳健噪声尺度（mean-shift 带宽用）──
    def _mad_sigma(values: np.ndarray, floor: float, ceil: float) -> float:
        if values.size < 64:
            return floor
        med = float(np.median(values))
        mad = float(np.median(np.abs(values - med)))
        return float(np.clip(1.4826 * mad, floor, ceil))

    sigma_l = _mad_sigma(L[region], cfg.sigma_floor_l, cfg.sigma_ceil_l)
    sigma_c = _mad_sigma(chroma[region], cfg.sigma_floor_c, cfg.sigma_ceil_c)

    # ── 局部众数参考（亮度 + 色素）──
    l_ref = _clamp_reference(
        _mode_reference(L, region, sigma_l, win=cfg.local_win), L, region, cfg
    )
    c_ref = _clamp_reference(
        _mode_reference(chroma, region, sigma_c, win=cfg.local_win), chroma, region, cfg
    )

    delta_l = L - l_ref
    delta_c = c_ref - chroma

    # ── 参考肤色可信度：参考本身过暗 = 毛发/深阴影，不是可判读的皮肤 ──
    ref_med = float(np.median(l_ref[region])) if region.any() else 0.0
    readable = region & (l_ref >= max(18.0, 0.45 * ref_med))
    if readable.sum() < max(64, 0.05 * max(int(region.sum()), 1)):
        readable = region

    # ── 感知归一化（固定尺度，保证跨照片/跨时间一致）──
    n_l = np.clip((delta_l - cfg.l_dead_zone) / cfg.l_scale, 0.0, 1.0)
    n_c = np.clip((delta_c - cfg.c_dead_zone) / cfg.c_scale, 0.0, 1.0)

    grad = compute_gradient_magnitude(img_rgb).astype(np.float32)
    # 局部平均梯度 = 纹理强度：白斑内部平滑，毛发/褶皱/反光/背景杂乱处高
    texture = cv2.blur(grad, (9, 9))
    t_med = float(np.median(texture[region])) if region.any() else float(np.median(texture))
    t_scale = max(t_med * cfg.texture_gain, 1e-3)
    n_t = np.clip(texture / t_scale, 0.0, 1.0)

    score = cfg.w_l * n_l + cfg.w_c * n_c - cfg.w_texture * n_t
    score = np.clip(score, 0.0, 1.0).astype(np.float32)
    score[~readable] = 0.0

    parts = {
        "delta_l": delta_l.astype(np.float32),
        "delta_c": delta_c.astype(np.float32),
        "gradient": grad,
        "texture": texture,
        "l_ref": l_ref,
        "c_ref": c_ref,
        "readable": readable,
        "n_l": n_l.astype(np.float32),
        "n_c": n_c.astype(np.float32),
        "n_t": n_t.astype(np.float32),
        "sigma_l": round(sigma_l, 2),
        "sigma_c": round(sigma_c, 2),
        "l_ref_median": round(ref_med, 1),
        "texture_scale": round(t_scale, 2),
        "size": (h, w),
    }
    return score, parts


def hysteresis_threshold(
    score: np.ndarray, hi: float, lo: float, valid: np.ndarray
) -> np.ndarray:
    """Canny 式双阈值：只保留与高置信核心连通的候选区域。"""
    if not _CV2_AVAILABLE:
        return score >= hi
    grow = (score >= lo) & valid
    if not grow.any():
        return np.zeros_like(grow)
    seeds = (score >= hi) & valid
    if not seeds.any():
        return np.zeros_like(grow)

    num, labels = cv2.connectedComponents(grow.astype(np.uint8), connectivity=8)
    keep = np.zeros(num, dtype=bool)
    seed_labels = np.unique(labels[seeds])
    keep[seed_labels[seed_labels > 0]] = True
    return keep[labels]


# ── 边缘吸附 ────────────────────────────────────────────────────────────────


def snap_mask_to_edges(
    img_rgb: np.ndarray,
    mask: np.ndarray,
    radius: int = 4,
    gradient: Optional[np.ndarray] = None,
) -> np.ndarray:
    """把 mask 边界吸附到颜色梯度脊线（分水岭），变更幅度限制在 ±radius。

    以「白斑核心 / 健康皮肤核心」为两个标记、颜色梯度为高程做分水岭，
    边界落在两核心之间的梯度脊线上 —— 即邻域色差最大处。
    """
    if not _CV2_AVAILABLE or not mask.any() or mask.all():
        return mask

    grad = gradient if gradient is not None else compute_gradient_magnitude(img_rgb)
    barrier = cv2.GaussianBlur(grad.astype(np.float32), (0, 0), 1.0)
    lo, hi = float(barrier.min()), float(np.percentile(barrier, 99.0))
    if hi <= lo:
        return mask
    barrier_u8 = np.clip((barrier - lo) / (hi - lo) * 255.0, 0, 255).astype(np.uint8)
    barrier_bgr = cv2.cvtColor(barrier_u8, cv2.COLOR_GRAY2BGR)

    k = max(1, int(radius) | 1)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    m8 = mask.astype(np.uint8)
    sure_fg = cv2.erode(m8, kernel).astype(bool)
    sure_bg = (cv2.erode(1 - m8, kernel)).astype(bool)
    if not sure_fg.any():
        sure_fg = m8.astype(bool)
    if not sure_bg.any():
        sure_bg = (1 - m8).astype(bool)

    markers = np.zeros(mask.shape, dtype=np.int32)
    markers[sure_bg] = 1
    markers[sure_fg] = 2
    try:
        cv2.watershed(barrier_bgr, markers)
    except cv2.error as e:  # pragma: no cover - defensive
        logger.debug("watershed failed: %s", e)
        return mask
    refined = markers == 2

    # 限制变更幅度：腐蚀核心必保留，膨胀外沿之外不采纳
    outer = cv2.dilate(m8, kernel).astype(bool)
    inner = cv2.erode(m8, kernel).astype(bool)
    refined = (refined & outer) | inner

    # 轻度平滑，去掉分水岭产生的单像素锯齿
    refined = _smooth_mask(refined)
    return refined


def _smooth_mask(mask: np.ndarray, close_size: int = 5, open_size: int = 3) -> np.ndarray:
    if not _CV2_AVAILABLE or not mask.any():
        return mask
    m = mask.astype(np.uint8) * 255
    m = cv2.medianBlur(m, 3)
    k_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (close_size, close_size))
    k_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (open_size, open_size))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, k_close)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, k_open)
    return m > 127


# ── 连通域过滤 ──────────────────────────────────────────────────────────────


def filter_lesion_components(
    mask: np.ndarray,
    score: np.ndarray,
    parts: Dict[str, Any],
    region: np.ndarray,
    cfg: Optional[EdgeSegConfig] = None,
    skin_candidate: Optional[np.ndarray] = None,
) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any]]:
    """剔除明显的伪阳性连通域。

    Returns:
        (kept, fallback, stats)
        kept     — 通过全部证据门槛的连通域；
        fallback — 仅因面积/形状门槛被否、但置信度很高（mean_score ≥ hi）的
                   连通域，供「严格过滤后为空」时兜底，避免整图空白。
    """
    cfg = cfg or EdgeSegConfig()
    empty = np.zeros_like(mask, dtype=bool)
    if not _CV2_AVAILABLE or not mask.any():
        return empty, empty, {"candidates": 0, "kept": 0, "rejected": {}}

    h, w = mask.shape
    delta_l = parts["delta_l"]
    delta_c = parts["delta_c"]
    grad = parts["gradient"]

    num, labels, stats, _ = cv2.connectedComponentsWithStats(
        mask.astype(np.uint8), connectivity=8
    )
    kept = np.zeros_like(mask)
    fallback = np.zeros_like(mask)
    rejected: Dict[str, int] = {}
    kept_count = 0
    fallback_count = 0

    border = np.zeros_like(mask)
    border[0, :] = border[-1, :] = True
    border[:, 0] = border[:, -1] = True

    # 邻域肤色证据：真实白斑的**边界四周**一定有皮肤，因此看连通域外环
    # 上的肤色比例（而不是整个连通域的面积占比 —— 大面积白斑的中心必然
    # 远离任何肤色像素）。
    ring_skin = None
    if skin_candidate is not None and skin_candidate.any():
        rk = max(3, int(0.01 * max(h, w)) | 1)
        ring_skin = cv2.dilate(
            skin_candidate.astype(np.uint8),
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (rk, rk)),
        ).astype(bool)

    for i in range(1, num):
        area = int(stats[i, cv2.CC_STAT_AREA])
        comp = labels == i
        mean_score = float(score[comp].mean())

        # 外环几乎没有肤色 = 背景/衣物/桌面上的亮块，直接否决
        if ring_skin is not None:
            comp_u8_early = comp.astype(np.uint8)
            ring = cv2.dilate(comp_u8_early, np.ones((5, 5), np.uint8)).astype(bool) & ~comp
            if ring.sum() > 0:
                skin_frac = float((ring & ring_skin).sum()) / float(ring.sum())
                if skin_frac < 0.35:
                    rejected["no_skin_neighbor"] = rejected.get("no_skin_neighbor", 0) + 1
                    continue

        # 面积过小：高置信小斑块仍进兜底集合
        if area < cfg.min_area_ratio * h * w:
            rejected["small"] = rejected.get("small", 0) + 1
            if mean_score >= cfg.hi_thresh and area >= max(16, int(0.0015 * h * w)):
                fallback |= comp
                fallback_count += 1
            continue

        if mean_score < cfg.min_mean_score:
            rejected["low_score"] = rejected.get("low_score", 0) + 1
            continue

        # 红疹/血管：彩度显著高于周围皮肤（Δchroma 明显为负）
        mean_delta_c = float(delta_c[comp].mean())
        if mean_delta_c < -4.0:
            rejected["high_chroma"] = rejected.get("high_chroma", 0) + 1
            continue

        # 细长高光/皮纹：面积小且低圆度
        contour_area = area
        comp_u8 = comp.astype(np.uint8)
        contours, _ = cv2.findContours(comp_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        perimeter = float(cv2.arcLength(contours[0], True)) if contours else 0.0
        circularity = (4.0 * np.pi * contour_area / (perimeter ** 2)) if perimeter > 0 else 0.0
        if circularity < cfg.min_circularity and area < 0.01 * h * w:
            rejected["thin"] = rejected.get("thin", 0) + 1
            if mean_score >= cfg.hi_thresh:
                fallback |= comp
                fallback_count += 1
            continue

        # 贴边背景：大面积贴住图像边框且置信度不高 → 多半是背景/衣物
        contact = float(np.logical_and(comp, border).sum()) / max(perimeter, 1.0)
        if contact > cfg.max_border_contact and mean_score < cfg.hi_thresh:
            rejected["border"] = rejected.get("border", 0) + 1
            continue

        # 内部梯度很高 → 纹理杂乱（毛发/布料），不是脱色素斑
        mean_grad_inside = float(grad[comp].mean())
        mean_grad_region = float(grad[region].mean()) if region.any() else mean_grad_inside
        if mean_grad_inside > 2.2 * max(mean_grad_region, 1e-3) and mean_score < cfg.hi_thresh:
            rejected["textured"] = rejected.get("textured", 0) + 1
            continue

        # 边界对比度：真实白斑与周围皮肤之间应有可测色差
        ring = cv2.dilate(comp_u8, np.ones((7, 7), np.uint8)).astype(bool) & ~comp
        if ring.any():
            edge_contrast = abs(float(delta_l[comp].mean() - delta_l[ring].mean()))
            if edge_contrast < 2.0:
                rejected["no_contrast"] = rejected.get("no_contrast", 0) + 1
                continue

        kept |= comp
        kept_count += 1

    return kept, fallback, {
        "candidates": num - 1,
        "kept": kept_count,
        "fallback": fallback_count,
        "rejected": rejected,
    }


# ── 分析区域（皮肤）精修 ────────────────────────────────────────────────────


def _boxes_intersect(a, b, margin: int = 0) -> bool:
    """两个 cv2 连通域 stats 行的包围框是否相交（可带外扩 margin）。"""
    ax1, ay1 = int(a[cv2.CC_STAT_LEFT]) - margin, int(a[cv2.CC_STAT_TOP]) - margin
    ax2 = ax1 + int(a[cv2.CC_STAT_WIDTH]) + 2 * margin
    ay2 = ay1 + int(a[cv2.CC_STAT_HEIGHT]) + 2 * margin
    bx1, by1 = int(b[cv2.CC_STAT_LEFT]), int(b[cv2.CC_STAT_TOP])
    bx2 = bx1 + int(b[cv2.CC_STAT_WIDTH])
    by2 = by1 + int(b[cv2.CC_STAT_HEIGHT])
    return not (ax2 < bx1 or bx2 < ax1 or ay2 < by1 or by2 < ay1)


def _border_color_reference(img_rgb: np.ndarray) -> np.ndarray:
    """图像外框（4% 边宽）的中位颜色，用于识别「贴边背景」连通域。"""
    h, w = img_rgb.shape[:2]
    bw = max(2, int(min(h, w) * 0.04))
    frame = np.concatenate([
        img_rgb[:bw, :, :].reshape(-1, 3),
        img_rgb[-bw:, :, :].reshape(-1, 3),
        img_rgb[:, :bw, :].reshape(-1, 3),
        img_rgb[:, -bw:, :].reshape(-1, 3),
    ])
    return np.median(frame, axis=0)


def refine_skin_region(
    img_rgb: np.ndarray,
    skin_mask: Optional[np.ndarray],
    lesion_mask: Optional[np.ndarray] = None,
    min_component_ratio: float = 0.02,
) -> np.ndarray:
    """把色彩候选皮肤收敛为「主体皮肤区域」。

    与旧的 `expand_skin_mask_to_include_vitiligo`（对最大轮廓做凸包）不同：
      1) 按长边比例做形态学开运算，切断皮肤与背景之间的细桥；
      2) 用**中心主体先验**挑选主体连通域（拍摄引导要求患处居中），
         并结合面积、贴边、颜色接近外框背景等证据；
      3) 填洞 + 有界膨胀（容纳白斑边缘），**绝不做凸包**。
    这样皮肤贴边时不会得到「整图」分母，面积分母不再失真。
    """
    h, w = img_rgb.shape[:2]
    if not _CV2_AVAILABLE:
        return skin_mask if skin_mask is not None else np.ones((h, w), dtype=bool)

    # 区域级几何只需工作分辨率：4000px 原图上做 1.2% 长边的开运算 + 连通域
    # 统计会带来秒级延迟。处理后再按最近邻还原到原尺寸。
    scale = min(1.0, WORK_MAX_DIM / max(h, w))
    if scale < 1.0:
        work = cv2.resize(
            img_rgb, (max(1, int(w * scale)), max(1, int(h * scale))),
            interpolation=cv2.INTER_AREA,
        )
        work_skin = (
            _resize_mask(skin_mask, (work.shape[0], work.shape[1]))
            if skin_mask is not None else None
        )
        work_lesion = (
            _resize_mask(lesion_mask, (work.shape[0], work.shape[1]))
            if lesion_mask is not None else None
        )
    else:
        work, work_skin, work_lesion = img_rgb, skin_mask, lesion_mask

    result = _refine_skin_region_impl(work, work_skin, work_lesion, min_component_ratio)
    if scale < 1.0:
        result = _resize_mask(result, (h, w))
    return result


def _refine_skin_region_impl(
    img_rgb: np.ndarray,
    skin_mask: Optional[np.ndarray],
    lesion_mask: Optional[np.ndarray],
    min_component_ratio: float,
) -> np.ndarray:
    """`refine_skin_region` 的实际实现（已在工作分辨率上）。"""
    h, w = img_rgb.shape[:2]
    if not _CV2_AVAILABLE:
        return skin_mask if skin_mask is not None else np.ones((h, w), dtype=bool)

    candidate = np.zeros((h, w), dtype=bool)
    if skin_mask is not None:
        candidate |= skin_mask.astype(bool)
    if lesion_mask is not None:
        candidate |= lesion_mask.astype(bool)
    if not candidate.any():
        return np.ones((h, w), dtype=bool)

    cand_u8 = candidate.astype(np.uint8)
    # 断桥：开运算核按长边比例（小图不至于被抹掉）。必须在连通域标注之前做，
    # 否则后续的闭运算会把刚切断的皮肤/背景细桥重新连上。
    open_k = max(3, int(0.012 * max(h, w)) | 1)
    cand_u8 = cv2.morphologyEx(
        cand_u8, cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (open_k, open_k)),
    )

    num, labels, stats, centroids = cv2.connectedComponentsWithStats(cand_u8, connectivity=8)
    if num <= 1:
        return np.ones((h, w), dtype=bool)

    total = float(h * w)
    diag = float(np.hypot(h, w))
    center = np.array([w / 2.0, h / 2.0])
    bg_ref = _border_color_reference(img_rgb)
    bg_lab = cv2.cvtColor(
        np.uint8([[bg_ref[::-1]]]), cv2.COLOR_BGR2LAB
    ).astype(np.float32)[0, 0]
    lab_img = cv2.cvtColor(
        cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR), cv2.COLOR_BGR2LAB
    ).astype(np.float32)

    def touches_border(i: int) -> bool:
        return bool(
            stats[i, cv2.CC_STAT_LEFT] <= 1
            or stats[i, cv2.CC_STAT_TOP] <= 1
            or stats[i, cv2.CC_STAT_LEFT] + stats[i, cv2.CC_STAT_WIDTH] >= w - 1
            or stats[i, cv2.CC_STAT_TOP] + stats[i, cv2.CC_STAT_HEIGHT] >= h - 1
        )

    def background_like(i: int) -> bool:
        comp = labels == i
        med = np.median(lab_img[comp], axis=0)
        dist = float(np.linalg.norm(med - bg_lab))
        return dist < 12.0

    # ── 主体连通域打分：面积 × 中心接近度 − 背景惩罚 ──
    best_idx, best_score = 1, -1.0
    for i in range(1, num):
        area = float(stats[i, cv2.CC_STAT_AREA])
        if area < 0.005 * total:
            continue
        dist = float(np.linalg.norm(centroids[i] - center)) / diag
        proximity = float(np.exp(-(dist / 0.40) ** 2))
        score = (area / total) * (0.35 + 0.65 * proximity)
        if touches_border(i) and background_like(i):
            score *= 0.15
        if score > best_score:
            best_score, best_idx = score, i

    keep = np.zeros((h, w), dtype=bool)
    for i in range(1, num):
        area = float(stats[i, cv2.CC_STAT_AREA])
        if i != best_idx:
            if area < min_component_ratio * total:
                continue
            # 只保留与主体包围框相交的连通域（同一次拍摄里的同一身体部位）。
            # 用包围框相交而非质心距离：颈/臂等与主体相连的区域得以保留，
            # 而远离主体的墙面/桌面/显示器被排除。
            if not _boxes_intersect(stats[i], stats[best_idx], margin=int(0.05 * max(h, w))):
                continue
            if background_like(i) and area < 0.4 * total:
                continue
        keep |= labels == i

    if not keep.any():
        keep = labels == best_idx

    # 填洞 + 有界膨胀（容纳白斑边缘），但绝不做凸包
    keep_u8 = keep.astype(np.uint8)
    ff = keep_u8.copy()
    mask2 = np.zeros((h + 2, w + 2), np.uint8)
    cv2.floodFill(ff, mask2, (0, 0), 1)
    holes = (ff == 0).astype(np.uint8)
    keep_u8 = np.clip(keep_u8 + holes, 0, 1)

    pad = max(3, int(0.012 * max(h, w)))
    keep_u8 = cv2.dilate(
        keep_u8, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (pad | 1, pad | 1))
    )
    allowed = cv2.dilate(
        cand_u8, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, ((pad * 4) | 1, (pad * 4) | 1))
    ).astype(bool)
    result = keep_u8.astype(bool) & allowed
    result = _smooth_mask(result, close_size=9, open_size=5)
    return result


# ── 顶层接口 ────────────────────────────────────────────────────────────────


def _resize_mask(mask: np.ndarray, shape: Tuple[int, int]) -> np.ndarray:
    if mask.shape[:2] == shape:
        return mask
    return (
        cv2.resize(mask.astype(np.uint8), (shape[1], shape[0]), interpolation=cv2.INTER_NEAREST)
        > 0
    )


def segment_lesions_edge_aware(
    img_rgb: np.ndarray,
    region: Optional[np.ndarray] = None,
    cfg: Optional[EdgeSegConfig] = None,
    skin_candidate: Optional[np.ndarray] = None,
) -> Dict[str, Any]:
    """边缘感知 + 局部自适应的白斑分割主入口。

    Args:
        img_rgb: (H, W, 3) uint8 RGB。内部会下采样到 WORK_MAX_DIM 处理，
                 返回的掩膜仍为原始尺寸。
        region: 可选的分析区域（皮肤）掩膜；None 时由 skin 检测自行推导。
        skin_candidate: 可选的**色彩肤色候选**掩膜（未填洞/未膨胀）。用于
                 「白斑必须紧邻肤色」的邻域证据校验；None 时自动计算。

    Returns:
        {
          "lesion_mask", "skin_region", "score", "stats", "source"
        }
    """
    cfg = cfg or EdgeSegConfig()
    h, w = img_rgb.shape[:2]
    out_empty = {
        "lesion_mask": np.zeros((h, w), dtype=bool),
        "skin_region": region if region is not None else np.zeros((h, w), dtype=bool),
        "score": np.zeros((h, w), dtype=np.float32),
        "stats": {"error": "unavailable"},
        "source": "edge-aware",
    }
    if not _CV2_AVAILABLE:
        return out_empty

    # 工作分辨率
    scale = min(1.0, WORK_MAX_DIM / max(h, w))
    if scale < 1.0:
        work = cv2.resize(img_rgb, (max(1, int(w * scale)), max(1, int(h * scale))),
                          interpolation=cv2.INTER_AREA)
    else:
        work = img_rgb
    wh, ww = work.shape[:2]

    if skin_candidate is None:
        from web.backend.services.vasi_skin_mask import build_skin_mask

        skin_candidate = build_skin_mask(work)
    if skin_candidate is not None:
        skin_candidate = _resize_mask(skin_candidate, (wh, ww))

    if region is None:
        region = refine_skin_region(work, skin_candidate, None)
    if region is None or not np.any(region):
        out_empty["stats"] = {"error": "no_region"}
        return out_empty
    region = _resize_mask(region, (wh, ww))

    score, parts = build_lesion_score(work, region, cfg)
    coarse = hysteresis_threshold(score, cfg.hi_thresh, cfg.lo_thresh, region)
    snapped = snap_mask_to_edges(work, coarse, cfg.snap_radius, gradient=parts["gradient"])
    filtered, fallback, comp_stats = filter_lesion_components(
        snapped, score, parts, region, cfg, skin_candidate=skin_candidate
    )
    if not filtered.any() and fallback.any():
        # 严格过滤为空时，用「仅因面积/形状被否但置信度很高」的兜底集合，
        # 避免整图空白；若连兜底都没有则返回空掩膜（比大面积误判更诚实，
        # 用户可在编辑器里手绘修正）。
        filtered = fallback
        comp_stats["used_fallback"] = True

    lesion = _resize_mask(filtered, (h, w))
    region_full = _resize_mask(region, (h, w))
    score_full = cv2.resize(score, (w, h), interpolation=cv2.INTER_LINEAR)

    stats: Dict[str, Any] = {
        "region_pixels": int(region_full.sum()),
        "region_ratio": round(float(region_full.sum()) / (h * w) * 100, 1),
        "lesion_pixels": int(lesion.sum()),
        "lesion_ratio_of_region": round(
            100.0 * float(lesion.sum()) / max(int(region_full.sum()), 1), 2
        ),
        "hi_thresh": cfg.hi_thresh,
        "lo_thresh": cfg.lo_thresh,
        "l_ref_median": parts["l_ref_median"],
        "sigma_l": parts["sigma_l"],
        "sigma_c": parts["sigma_c"],
        "texture_scale": parts["texture_scale"],
        "components": comp_stats,
    }
    return {
        "lesion_mask": lesion,
        "skin_region": region_full,
        "score": score_full,
        "stats": stats,
        "source": "edge-aware",
    }


def refine_mask_by_edges(
    img_rgb: np.ndarray,
    mask: np.ndarray,
    region: Optional[np.ndarray] = None,
    cfg: Optional[EdgeSegConfig] = None,
) -> np.ndarray:
    """对任意来源（U-Net / SAM / CV）的二值 mask 做边缘吸附精修。

    这是「无论用哪个模型得到初稿，边缘都贴合真实色差」的通用后处理：
      1) 用局部参考 + 梯度构建似然图与掩膜本身的一致性检查；
      2) 分水岭把边界吸附到颜色梯度脊线；
      3) 平滑去锯齿。
    """
    cfg = cfg or EdgeSegConfig()
    if not _CV2_AVAILABLE or mask is None or not mask.any():
        return mask
    h, w = img_rgb.shape[:2]
    if mask.shape[:2] != (h, w):
        mask = _resize_mask(mask, (h, w))

    scale = min(1.0, WORK_MAX_DIM / max(h, w))
    if scale < 1.0:
        work = cv2.resize(img_rgb, (max(1, int(w * scale)), max(1, int(h * scale))),
                          interpolation=cv2.INTER_AREA)
        work_mask = _resize_mask(mask, (work.shape[0], work.shape[1]))
    else:
        work, work_mask = img_rgb, mask

    grad = compute_gradient_magnitude(work)
    snapped = snap_mask_to_edges(work, work_mask, cfg.snap_radius, gradient=grad)
    if not snapped.any():
        snapped = work_mask
    return _resize_mask(snapped, (h, w))


def extract_precise_polygon(
    mask: np.ndarray,
    max_points: int = 180,
    epsilon_factor: float = 0.0018,
    smooth_sigma: float = 1.2,
) -> Optional[List[List[float]]]:
    """提取高精度归一化多边形：亚像素平滑 + 保留边界的轻度简化。

    与旧 `_mask_to_polygon`（epsilon=0.005、最多 40 点、只取最大轮廓）
    相比，顶点数上限提升到 180 且简化更轻，白斑边缘的不规则形态得以保留。
    """
    if not _CV2_AVAILABLE or mask is None or not mask.any():
        return None
    h, w = mask.shape
    m = (mask.astype(np.uint8)) * 255
    if smooth_sigma > 0:
        m = cv2.GaussianBlur(m, (0, 0), smooth_sigma)
        m = np.where(m > 127, 255, 0).astype(np.uint8)

    contours, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not contours:
        return None
    largest = max(contours, key=cv2.contourArea)
    if cv2.contourArea(largest) < 4:
        return None

    epsilon = max(0.8, epsilon_factor * cv2.arcLength(largest, True))
    approx = cv2.approxPolyDP(largest, epsilon, True)
    pts = approx[:, 0, :].astype(np.float64)
    if len(pts) < 3:
        pts = largest[:, 0, :].astype(np.float64)
    if len(pts) < 3:
        return None

    points = [[round(float(x) / w, 4), round(float(y) / h, 4)] for x, y in pts]
    if len(points) > max_points:
        step = len(points) / max_points
        points = [points[int(i * step)] for i in range(max_points)]
    return points

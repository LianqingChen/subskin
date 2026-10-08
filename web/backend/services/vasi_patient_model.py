"""患者级像素分类器（vasi_patient_model）。

依据 hermes_plan/VITILIGO_AUTO_SEGMENTATION_METHOD.md §4.4/§4.6/§5：

- 无监督冷启动：K-means(L*, 彩度C) + 合理性校验（白斑簇更亮且更低彩度），
  高光上限 L*>88，仅排确定非皮肤结构，连通域≥150px + 肤色邻域校验。
- 监督：随机森林，特征 [L*, a*, b*, C, y/EH, x/EW]，正负样本各≤4万，
  难负样本（眼球/毛发/衣物/背景）额外采样。
- 后处理：闭(5×5)→开(5×5)→发际线以上强开(11×11)→逆变换回原图→连通域≥300px。

模型持久化：data/vasi_models/{user_id}/{body_site}/model.joblib + meta.json。
患者模型是患者级隐私数据（L3）：只允许 owner 访问，不进日志、不进 Git。
Python 3.9 兼容；scikit-learn 缺失时所有函数返回 None（调用方降级）。
"""

import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

MODEL_ROOT = Path("data/vasi_models")

# 文档 §4.4 参数
_N_POS = 40000
_N_NEG = 40000
_PROB_THRESHOLD = 0.5
# 文档 §4.5/§4.6 参数
_CC_MIN_CANVAS = 150
_CC_MIN_ORIG = 300
_HIGHLIGHT_L = 88.0
_SKIN_NEIGHBOR_RADIUS = 25
_SKIN_NEIGHBOR_MIN = 0.15


def _cv_available() -> bool:
    try:
        import cv2  # noqa: F401
        return True
    except ImportError:
        return False


def _sk_available() -> bool:
    try:
        import sklearn  # noqa: F401
        return True
    except ImportError:
        return False


# ══════════════════════════════════════════════════════════════════════════════
# 无监督冷启动（文档 §4.6）
# ══════════════════════════════════════════════════════════════════════════════

def kmeans_cold_start(canvas_img: np.ndarray,
                      skin_mask: np.ndarray,
                      exclude_mask: Optional[np.ndarray] = None) -> Optional[Dict[str, Any]]:
    """K-means(L*, 彩度C) 冷启动白斑分割（零标注）。

    Args:
        canvas_img: 校准画布图 BGR uint8
        skin_mask: 皮肤区域掩膜（画布坐标）
        exclude_mask: 确定非皮肤结构（眼球/眉发/鼻孔/唇黏膜/发际线以上），可空

    Returns:
        {"mask": bool ndarray, "cluster_white": (L,C), "cluster_normal": (L,C),
         "sane": bool, "stats": {...}} 或 None
    """
    if not _sk_available() or not _cv_available():
        return None
    try:
        import cv2
        from sklearn.cluster import KMeans
    except Exception:
        return None
    if canvas_img is None or skin_mask is None:
        return None
    if canvas_img.shape[:2] != skin_mask.shape[:2]:
        return None
    import cv2
    lab = cv2.cvtColor(canvas_img, cv2.COLOR_BGR2LAB).astype(np.float32)
    L = lab[..., 0] * (100.0 / 255.0)
    C = np.hypot(lab[..., 1] - 128.0, lab[..., 2] - 128.0)

    region = skin_mask.astype(bool)
    if exclude_mask is not None and exclude_mask.shape == region.shape:
        region = region & (~exclude_mask.astype(bool))
    region = region & (L <= _HIGHLIGHT_L)  # 高光上限（文档 §4.6-4）
    ys, xs = np.where(region)
    if len(ys) < 500:
        return None

    X = np.column_stack([L[ys, xs], C[ys, xs]]).astype(np.float32)
    try:
        km = KMeans(n_clusters=2, n_init=4, random_state=0).fit(X)
    except Exception:
        return None
    centers = km.cluster_centers_
    # 白斑簇 = 更亮且更低彩度（文档 §4.6-3）
    if centers[0][0] > centers[1][0] and centers[0][1] < centers[1][1]:
        white_idx, normal_idx = 0, 1
    elif centers[1][0] > centers[0][0] and centers[1][1] < centers[0][1]:
        white_idx, normal_idx = 1, 0
    else:
        return None  # 彩度反转，结果作废

    mask = np.zeros_like(region, dtype=bool)
    mask[ys[km.labels_ == white_idx], xs[km.labels_ == white_idx]] = True

    # 形态学 + 连通域过滤（文档 §4.6-5/6）
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_CLOSE, k).astype(bool)
    mask = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_OPEN, k).astype(bool)
    mask = _filter_components(mask, _CC_MIN_CANVAS)
    if not mask.any():
        return None
    mask = _skin_neighbor_check(mask, skin_mask.astype(bool))

    white_center = centers[white_idx]
    normal_center = centers[normal_idx]
    sane = bool(white_center[0] > normal_center[0] and white_center[1] < normal_center[1])
    return {
        "mask": mask,
        "cluster_white": [float(white_center[0]), float(white_center[1])],
        "cluster_normal": [float(normal_center[0]), float(normal_center[1])],
        "sane": sane,
        "stats": {"pixels": int(mask.sum()), "skin_pixels": int(skin_mask.sum())},
    }


# ══════════════════════════════════════════════════════════════════════════════
# 监督随机森林（文档 §4.4）
# ══════════════════════════════════════════════════════════════════════════════

def _features(canvas_img: np.ndarray, ys: np.ndarray, xs: np.ndarray,
              EH: int, EW: int) -> np.ndarray:
    lab = _lab_of(canvas_img)
    L, a, b = lab[..., 0], lab[..., 1], lab[..., 2]
    C = np.hypot(a, b)
    return np.column_stack([
        L[ys, xs], a[ys, xs], b[ys, xs], C[ys, xs],
        ys.astype(np.float32) / float(EH),
        xs.astype(np.float32) / float(EW),
    ])


def _lab_of(bgr: np.ndarray) -> np.ndarray:
    import cv2
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    lab[..., 0] *= 100.0 / 255.0
    lab[..., 1] -= 128.0
    lab[..., 2] -= 128.0
    return lab


def _sample_indices(count: int, total: int, rng: np.random.RandomState) -> np.ndarray:
    if total <= count:
        return np.arange(total)
    return rng.choice(total, size=count, replace=False)


def train_rf(canvas_img: np.ndarray,
             lesion_mask: np.ndarray,
             validity: Optional[np.ndarray] = None,
             hard_negative_mask: Optional[np.ndarray] = None,
             ) -> Optional[Any]:
    """训练患者级随机森林像素分类器（文档 §4.4）。

    Args:
        canvas_img: 校准画布图 BGR uint8
        lesion_mask: 标注/伪标签白斑掩膜（画布坐标）
        validity: 有效像素掩膜（排除黑边）；None 时自动按 max(channel)>10
        hard_negative_mask: 易误检区（眼球/毛发/衣物/背景），额外采样为负例

    Returns:
        训练好的 sklearn RandomForestClassifier，失败返回 None
    """
    if not _sk_available():
        return None
    try:
        from sklearn.ensemble import RandomForestClassifier
    except Exception:
        return None
    if canvas_img is None or lesion_mask is None:
        return None
    h, w = canvas_img.shape[:2]
    if lesion_mask.shape[:2] != (h, w):
        return None
    if validity is None:
        validity = canvas_img.max(axis=2) > 10
    if validity.shape[:2] != (h, w):
        validity = np.ones((h, w), dtype=bool)

    lesion = lesion_mask.astype(bool)
    rng = np.random.RandomState(0)

    py, px = np.where(lesion & validity)
    ny, nx = np.where((~lesion) & validity)
    hard_y, hard_x = np.where(hard_negative_mask & (~lesion) & validity) \
        if hard_negative_mask is not None else (np.array([], dtype=int), np.array([], dtype=int))

    pos_idx = _sample_indices(_N_POS, len(py), rng)
    neg_idx = _sample_indices(_N_NEG, len(ny), rng)
    # 难负样本：最多占总负样本 25%
    hard_n = min(len(hard_y), int(_N_NEG * 0.25))
    hard_idx = _sample_indices(hard_n, len(hard_y), rng) if hard_n else np.array([], dtype=int)

    X_pos = _features(canvas_img, py[pos_idx], px[pos_idx], h, w)
    X_neg = _features(canvas_img, ny[neg_idx], nx[neg_idx], h, w)
    parts = [X_pos, X_neg]
    if len(hard_idx):
        parts.append(_features(canvas_img, hard_y[hard_idx], hard_x[hard_idx], h, w))
    X = np.vstack(parts)
    y = np.concatenate([
        np.ones(len(pos_idx)), np.zeros(len(neg_idx)),
        np.zeros(len(hard_idx)),
    ]).astype(np.int32)
    if len(y) < 100:
        return None

    try:
        clf = RandomForestClassifier(n_estimators=250, max_depth=18, n_jobs=-1,
                                     random_state=0).fit(X, y)
    except Exception as e:
        logger.warning("patient RF train failed: %s", e)
        return None
    return clf


def train_rf_from_samples(samples: List[Dict[str, Any]]) -> Optional[Any]:
    """合并多张照片样本训练患者级 RF（自循环训练入口）。

    Args:
        samples: iter_patient_samples() 的返回项列表，每项含
                 canvas_img/mask/validity

    Returns:
        训练好的分类器或 None
    """
    if not _sk_available():
        return None
    try:
        from sklearn.ensemble import RandomForestClassifier
    except Exception:
        return None
    if not samples:
        return None

    rng = np.random.RandomState(0)
    # 每张照片正负样本配额按样本数均分，保证各照片贡献均衡
    per_photo_pos = max(200, _N_POS // max(1, len(samples)))
    per_photo_neg = max(200, _N_NEG // max(1, len(samples)))

    X_parts: List[np.ndarray] = []
    y_parts: List[np.ndarray] = []
    for s in samples:
        canvas_img = s.get("canvas_img")
        mask = s.get("mask")
        validity = s.get("validity")
        if canvas_img is None or mask is None or not np.asarray(mask).any():
            continue
        h, w = canvas_img.shape[:2]
        if np.asarray(mask).shape[:2] != (h, w):
            continue
        if validity is None or np.asarray(validity).shape[:2] != (h, w):
            validity = canvas_img.max(axis=2) > 10
        lesion = np.asarray(mask).astype(bool)
        validity = np.asarray(validity).astype(bool)
        # 难负样本 = 画布内非皮肤背景（衣物/背景）
        hard = validity & (~lesion) & (~validity_skin_approx(canvas_img, validity))
        py, px = np.where(lesion & validity)
        ny, nx = np.where((~lesion) & validity)
        hy, hx = np.where(hard)
        if len(py) < 20:
            continue
        pos_idx = _sample_indices(per_photo_pos, len(py), rng)
        neg_idx = _sample_indices(per_photo_neg, len(ny), rng)
        hard_n = min(len(hy), int(per_photo_neg * 0.25))
        hard_idx = _sample_indices(hard_n, len(hy), rng) if hard_n else np.array([], dtype=int)

        X_parts.append(_features(canvas_img, py[pos_idx], px[pos_idx], h, w))
        y_parts.append(np.ones(len(pos_idx), dtype=np.int32))
        X_parts.append(_features(canvas_img, ny[neg_idx], nx[neg_idx], h, w))
        y_parts.append(np.zeros(len(neg_idx), dtype=np.int32))
        if len(hard_idx):
            X_parts.append(_features(canvas_img, hy[hard_idx], hx[hard_idx], h, w))
            y_parts.append(np.zeros(len(hard_idx), dtype=np.int32))

    if not X_parts:
        return None
    X = np.vstack(X_parts)
    y = np.concatenate(y_parts)
    if len(y) < 200:
        return None
    try:
        return RandomForestClassifier(n_estimators=250, max_depth=18, n_jobs=-1,
                                      random_state=0).fit(X, y)
    except Exception as e:
        logger.warning("train_rf_from_samples failed: %s", e)
        return None


def validity_skin_approx(canvas_img: np.ndarray, validity: np.ndarray) -> np.ndarray:
    """近似皮肤掩膜（用于难负样本选择）：HSV 肤色范围 ∩ 有效区。"""
    try:
        import cv2
    except ImportError:
        return validity
    hsv = cv2.cvtColor(canvas_img, cv2.COLOR_BGR2HSV)
    skin = cv2.inRange(hsv, (0, 20, 50), (25, 200, 255))
    skin2 = cv2.inRange(hsv, (160, 20, 50), (179, 200, 255))
    return ((cv2.bitwise_or(skin, skin2) > 0) & validity)


def predict_canvas(clf: Any, canvas_img: np.ndarray,
                   validity: Optional[np.ndarray] = None,
                   threshold: float = _PROB_THRESHOLD,
                   predict_region: Optional[np.ndarray] = None) -> Optional[np.ndarray]:
    """画布逐像素预测（文档 §4.4）。返回概率图 float32 或 None。

    Args:
        predict_region: 只预测该布尔区域（区域外概率=0）。用于大图性能优化
            （如原图恒等画布时仅预测皮肤区域）。
    """
    if clf is None or canvas_img is None:
        return None
    h, w = canvas_img.shape[:2]
    if validity is None:
        validity = canvas_img.max(axis=2) > 10
    try:
        region = validity.astype(bool)
        if predict_region is not None and predict_region.shape == region.shape:
            region = region & predict_region.astype(bool)
        ys, xs = np.where(region)
        if len(ys) == 0:
            return np.zeros((h, w), dtype=np.float32)
        X = _features(canvas_img, ys, xs, h, w)
        prob_flat = clf.predict_proba(X)[:, 1].astype(np.float32)
        prob = np.zeros((h, w), dtype=np.float32)
        prob[ys, xs] = prob_flat
    except Exception as e:
        logger.warning("patient RF predict failed: %s", e)
        return None
    prob[~validity.astype(bool)] = 0.0
    return prob


def postprocess_canvas(mask_canvas: np.ndarray,
                       top_hard_open_rows: int = 0) -> np.ndarray:
    """形态学后处理（文档 §4.5）。top_hard_open_rows：画布顶部强开运算行数。"""
    if mask_canvas is None or not mask_canvas.any():
        return np.zeros_like(mask_canvas) if mask_canvas is not None else np.zeros((1, 1), bool)
    import cv2
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    m = cv2.morphologyEx(mask_canvas.astype(np.uint8), cv2.MORPH_CLOSE, k)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, k)
    if top_hard_open_rows > 0:
        k11 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
        top = m[:top_hard_open_rows]
        if top.any():
            m[:top_hard_open_rows] = cv2.morphologyEx(top, cv2.MORPH_OPEN, k11)
    return m.astype(bool)


def _filter_components(mask: np.ndarray, min_area: int) -> np.ndarray:
    if not mask.any():
        return mask
    import cv2
    num, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)
    clean = np.zeros_like(mask)
    for i in range(1, num):
        if stats[i, cv2.CC_STAT_AREA] >= min_area:
            clean[labels == i] = True
    return clean


def _skin_neighbor_check(mask: np.ndarray, skin_mask: np.ndarray) -> np.ndarray:
    """肤色邻域校验：掩膜 25px 半径内肤色占比 ≥15% 才保留（文档 §4.5-5）。"""
    if not mask.any():
        return mask
    import cv2
    r = _SKIN_NEIGHBOR_RADIUS
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
    skin_blur = cv2.filter2D(skin_mask.astype(np.float32), -1,
                             kernel.astype(np.float32) / kernel.sum(), borderType=cv2.BORDER_CONSTANT)
    out = mask & (skin_blur >= _SKIN_NEIGHBOR_MIN)
    return _filter_components(out, _CC_MIN_CANVAS)


def canvas_mask_to_original(mask_canvas: np.ndarray,
                            transform: np.ndarray,
                            orig_shape: Tuple[int, int],
                            min_area: int = _CC_MIN_ORIG) -> np.ndarray:
    """画布掩膜逆变换回原图坐标 + 连通域过滤（文档 §4.5/§10-10）。"""
    if mask_canvas is None or not mask_canvas.any():
        return np.zeros(orig_shape, dtype=bool)
    import cv2
    h, w = orig_shape[:2]
    inv = np.linalg.inv(transform)
    warp = cv2.warpPerspective((mask_canvas.astype(np.uint8) * 255), inv, (w, h),
                               flags=cv2.INTER_NEAREST, borderValue=0)
    mask = (warp > 127)
    return _filter_components(mask, min_area)


# ══════════════════════════════════════════════════════════════════════════════
# 模型持久化与注册
# ══════════════════════════════════════════════════════════════════════════════

def _model_dir(user_id: int, body_site: str) -> Path:
    safe_site = "".join(ch if (ch.isalnum() or ch in "-_") else "_" for ch in (body_site or "site"))
    return MODEL_ROOT / str(int(user_id)) / safe_site


def save_model(user_id: int, body_site: str, clf: Any, meta: Dict[str, Any]) -> Optional[str]:
    """保存模型 + 元数据。返回模型路径或 None。"""
    if clf is None:
        return None
    try:
        import joblib
        d = _model_dir(user_id, body_site)
        d.mkdir(parents=True, exist_ok=True)
        ts = int(time.time())
        path = d / f"model_{ts}.joblib"
        joblib.dump(clf, str(path))
        meta_file = d / f"meta_{ts}.json"
        meta_file.write_text(json.dumps(meta, ensure_ascii=False, default=str), encoding="utf-8")
        # 记录活跃指针
        (d / "active.txt").write_text(path.name + "\n", encoding="utf-8")
        return str(path)
    except Exception as e:
        logger.warning("save patient model failed: %s", e)
        return None


def load_model(user_id: int, body_site: str) -> Optional[Any]:
    """加载该患者该部位当前活跃模型。"""
    try:
        d = _model_dir(user_id, body_site)
        active_f = d / "active.txt"
        if not active_f.exists():
            return None
        name = active_f.read_text(encoding="utf-8").strip()
        path = d / name
        if not path.exists():
            return None
        import joblib
        return joblib.load(str(path))
    except Exception as e:
        logger.info("load patient model failed (user=%s site=%s): %s", user_id, body_site, e)
        return None


def load_model_meta(user_id: int, body_site: str) -> Optional[Dict[str, Any]]:
    """加载活跃模型元数据。"""
    try:
        d = _model_dir(user_id, body_site)
        active_f = d / "active.txt"
        if not active_f.exists():
            return None
        name = active_f.read_text(encoding="utf-8").strip()
        meta_f = d / ("meta_" + name.replace("model_", "").replace(".joblib", ".json"))
        if not meta_f.exists():
            return None
        return json.loads(meta_f.read_text(encoding="utf-8"))
    except Exception:
        return None


def list_model_files(user_id: int, body_site: str) -> List[Path]:
    d = _model_dir(user_id, body_site)
    if not d.exists():
        return []
    return sorted(d.glob("model_*.joblib"))


def mask_hash(mask_bool: np.ndarray) -> str:
    """掩膜内容 hash（训练数据去重用）。"""
    return hashlib.md5(mask_bool.astype(np.uint8).tobytes()).hexdigest()[:16]

"""患者级时空对齐与色彩校准管线（vasi_canvas）。

依据 hermes_plan/VITILIGO_AUTO_SEGMENTATION_METHOD.md §3-§4：

阶段1 定位与对齐：MediaPipe 关键点（面部468点/手部21点/姿态33点）→
        相似变换到统一画布（面部 900×1600，扩展 +150/+250 覆盖发际线与颈部）。
阶段2 色彩校准：灰世界白平衡（原图计算增益）+ 本人正常皮肤参考 ROI 均值平移
        （自动选点，彩度自检 C>5），跨照片锚定同一 ref_mean_bgr。
输出：校准画布图 + 3×3 变换矩阵（逆变换回原图用）+ 校准参数 JSON。

所有关键点检测与校准失败均优雅降级为恒等对齐（原图即画布），不影响主链路。
Python 3.9 兼容。依赖（mediapipe/scipy）缺失时自动降级。
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# ── 画布模板（首张照片即对齐到该模板，后续照片对齐到同一模板） ──────────────
# 面部：900×1600，上方 +150 覆盖发际线、下方 +250 覆盖颈部（文档 §2.6/§4.3）
_FACE_CANVAS = {"width": 900, "height": 1600, "offset_y": 150, "ipd_px": 378.0}
_FACE_TARGET = [
    (261.0, 500.0),   # 左眼外角
    (639.0, 500.0),   # 右眼外角
    (450.0, 585.0),   # 鼻尖
    (338.0, 665.0),   # 左嘴角
    (562.0, 665.0),   # 右嘴角
]
# 手部：600×800，掌宽归一化 300px
_HAND_CANVAS = {"width": 600, "height": 800, "offset_y": 0, "ipd_px": 300.0}
_HAND_TARGET = [
    (300.0, 620.0),   # 腕
    (170.0, 400.0),   # 拇指 MCP
    (280.0, 290.0),   # 食指 MCP
    (345.0, 280.0),   # 中指 MCP
    (410.0, 290.0),   # 无名指 MCP
    (460.0, 340.0),   # 小指 MCP
]
# 躯干/四肢：800×1200，肩宽归一化 300px
_POSE_CANVAS = {"width": 800, "height": 1200, "offset_y": 0, "ipd_px": 300.0}
_POSE_TARGET = [
    (250.0, 400.0),   # 左肩
    (550.0, 400.0),   # 右肩
    (270.0, 800.0),   # 左髋
    (530.0, 800.0),   # 右髋
]

# 参考 ROI 候选块尺寸与彩度自检阈值（文档 §6.2：C 正常 8~30，<5 疑似白斑）
_ROI_BLOCK = 40
_ROI_C_MIN = 5.0
_ROI_C_MAX = 35.0
_MAX_SIDE_DETECT = 1024  # 关键点检测前最长边降采样

_MODEL_DIR = "data/models/mediapipe"

# MediaPipe 关键点索引
_FACE_IDX = [33, 263, 1, 61, 291]        # 左眼外角/右眼外角/鼻尖/左嘴角/右嘴角
_HAND_IDX = [0, 4, 5, 9, 13, 17]         # 腕/拇指尖/各指 MCP（实际用 0,5,9,13,17 + 4）
_POSE_IDX = [11, 12, 23, 24]             # 双肩 + 双髋


@dataclass
class CanvasResult:
    """对齐+校准画布结果。"""
    ok: bool = False
    aligned: bool = False                 # 是否真实做了相似变换对齐
    canvas_img: Optional[np.ndarray] = None   # 校准后画布图 BGR uint8
    canvas_warped: Optional[np.ndarray] = None  # 未校准 warp 图（用于有效像素掩膜）
    transform: Optional[np.ndarray] = None     # 3×3 原图→画布（含平移）
    keypoints: Optional[List[Tuple[float, float]]] = None  # 原图坐标关键点
    scale_baseline_px: Optional[float] = None  # 面积归一化基准（IPD/掌宽/肩宽）
    calibration: Dict[str, Any] = field(default_factory=dict)
    note: str = ""


# ══════════════════════════════════════════════════════════════════════════════
# 阶段1：关键点检测与相似变换
# ══════════════════════════════════════════════════════════════════════════════

def _site_kind(body_site: str) -> str:
    """把业务部位映射到检测器类别。"""
    s = (body_site or "").strip()
    if s in ("面部", "脸部", "face"):
        return "face"
    if s in ("手部", "左手", "右手", "手", "hand"):
        return "hand"
    if s in ("颈部", "躯干", "背部", "腹部", "胸部", "胳膊", "手臂", "腿部", "大腿", "小腿", "足部", "左脚", "右脚", "脚"):
        return "pose"
    return "pose"  # 其余部位默认尝试姿态


def _downscale_for_detect(img_bgr: np.ndarray) -> np.ndarray:
    h, w = img_bgr.shape[:2]
    m = max(h, w)
    if m <= _MAX_SIDE_DETECT:
        return img_bgr
    s = _MAX_SIDE_DETECT / m
    return np.ascontiguousarray(np.round(np.asarray(
        _cv_resize(img_bgr, (max(1, int(w * s)), max(1, int(h * s)))))).astype(np.uint8))


def _cv_resize(img, dsize):
    import cv2
    return cv2.resize(img, dsize, interpolation=cv2.INTER_LINEAR)


def _detect_face_pts(img_bgr: np.ndarray) -> Optional[List[Tuple[float, float]]]:
    """MediaPipe Face Landmarker 5 关键点（原图坐标）。"""
    try:
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision
        import os
        model_path = os.path.join(_MODEL_DIR, "face_landmarker.task")
        if not os.path.exists(model_path):
            return None
        options = vision.FaceLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=model_path),
            running_mode=vision.RunningMode.IMAGE,
            num_faces=1,
        )
        with vision.FaceLandmarker.create_from_options(options) as landmarker:
            rgb = mp.Image(image_format=mp.ImageFormat.SRGB, data=img_bgr[:, :, ::-1])
            res = landmarker.detect(rgb)
        if not res.face_landmarks:
            return None
        lm = res.face_landmarks[0]
        h, w = img_bgr.shape[:2]
        return [(float(lm[i].x) * w, float(lm[i].y) * h) for i in _FACE_IDX]
    except Exception as e:  # pragma: no cover - 依赖缺失/检测失败
        logger.info("face landmark detection unavailable: %s", e)
        return None


def _detect_hand_pts(img_bgr: np.ndarray) -> Optional[List[Tuple[float, float]]]:
    """MediaPipe Hand Landmarker（腕 + 各指 MCP，原图坐标）。"""
    try:
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision
        import os
        model_path = os.path.join(_MODEL_DIR, "hand_landmarker.task")
        if not os.path.exists(model_path):
            return None
        options = vision.HandLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=model_path),
            running_mode=vision.RunningMode.IMAGE,
            num_hands=1,
        )
        with vision.HandLandmarker.create_from_options(options) as landmarker:
            rgb = mp.Image(image_format=mp.ImageFormat.SRGB, data=img_bgr[:, :, ::-1])
            res = landmarker.detect(rgb)
        if not res.hand_landmarks:
            return None
        lm = res.hand_landmarks[0]
        h, w = img_bgr.shape[:2]
        # 腕 + 拇指/食指/中指/无名指/小指 MCP（顺序与 _HAND_TARGET 对齐）
        idx = [0, 5, 9, 13, 17, 20]
        return [(float(lm[i].x) * w, float(lm[i].y) * h) for i in idx]
    except Exception as e:  # pragma: no cover
        logger.info("hand landmark detection unavailable: %s", e)
        return None


def _detect_pose_pts(img_bgr: np.ndarray) -> Optional[List[Tuple[float, float]]]:
    """MediaPipe Pose Landmarker（双肩+双髋，原图坐标）。"""
    try:
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision
        import os
        model_path = os.path.join(_MODEL_DIR, "pose_landmarker_lite.task")
        if not os.path.exists(model_path):
            return None
        options = vision.PoseLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=model_path),
            running_mode=vision.RunningMode.IMAGE,
            num_poses=1,
        )
        with vision.PoseLandmarker.create_from_options(options) as landmarker:
            rgb = mp.Image(image_format=mp.ImageFormat.SRGB, data=img_bgr[:, :, ::-1])
            res = landmarker.detect(rgb)
        if not res.pose_landmarks:
            return None
        lm = res.pose_landmarks[0]
        h, w = img_bgr.shape[:2]
        pts = []
        for i in _POSE_IDX:
            p = lm[i]
            # 置信度阈值：不可见关节不参与
            if getattr(p, "visibility", 0.5) is not None and float(getattr(p, "visibility", 0.5)) < 0.5:
                return None
            pts.append((float(p.x) * w, float(p.y) * h))
        return pts
    except Exception as e:  # pragma: no cover
        logger.info("pose landmark detection unavailable: %s", e)
        return None


def detect_keypoints(image_bgr: np.ndarray, body_site: str) -> Tuple[Optional[List[Tuple[float, float]]], str]:
    """检测关键点。返回 (points, kind)。kind ∈ face/hand/pose/none。"""
    kind = _site_kind(body_site)
    small = _downscale_for_detect(image_bgr)
    if kind == "face":
        pts = _detect_face_pts(small)
        if pts:
            return pts, "face"
        # 面部检测失败尝试姿态（有的照片是半身照）
        pts = _detect_pose_pts(small)
        return (pts, "pose") if pts else (None, "none")
    if kind == "hand":
        pts = _detect_hand_pts(small)
        return (pts, "hand") if pts else (None, "none")
    pts = _detect_pose_pts(small)
    return (pts, "pose") if pts else (None, "none")


def _similarity_transform(src_pts: List[Tuple[float, float]],
                          dst_pts: List[Tuple[float, float]]) -> Optional[np.ndarray]:
    """最小二乘相似变换（4自由度：旋转/平移/均匀缩放）。返回 3×3。"""
    import cv2
    src = np.asarray(src_pts, dtype=np.float32).reshape(-1, 2)
    dst = np.asarray(dst_pts, dtype=np.float32).reshape(-1, 2)
    if len(src) < 3:
        return None
    m, inliers = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC,
                                             ransacReprojThreshold=3.0)
    if m is None:
        return None
    if inliers is not None and int(np.count_nonzero(inliers)) < 3:
        return None
    m3 = np.eye(3, dtype=np.float64)
    m3[:2, :] = m
    return m3


def _canvas_params(kind: str) -> Tuple[int, int, int, List[Tuple[float, float]], float]:
    if kind == "face":
        return (_FACE_CANVAS["width"], _FACE_CANVAS["height"], _FACE_CANVAS["offset_y"],
                _FACE_TARGET, _FACE_CANVAS["ipd_px"])
    if kind == "hand":
        return (_HAND_CANVAS["width"], _HAND_CANVAS["height"], _HAND_CANVAS["offset_y"],
                _HAND_TARGET, _HAND_CANVAS["ipd_px"])
    return (_POSE_CANVAS["width"], _POSE_CANVAS["height"], _POSE_CANVAS["offset_y"],
            _POSE_TARGET, _POSE_CANVAS["ipd_px"])


# ══════════════════════════════════════════════════════════════════════════════
# 阶段2：色彩校准
# ══════════════════════════════════════════════════════════════════════════════

def _gray_world_gains(orig_bgr: np.ndarray) -> np.ndarray:
    """在原图上计算灰世界逐通道增益（文档 §4.2 步骤1）。"""
    flat = orig_bgr.astype(np.float64).reshape(-1, 3)
    means = flat.mean(axis=0)
    eps = 1e-6
    overall = float(means.mean())
    gains = np.array([overall / (means[0] + eps), overall / (means[1] + eps),
                      overall / (means[2] + eps)], dtype=np.float32)
    # 增益钳制，防极端色偏图被拉爆
    gains = np.clip(gains, 0.6, 1.7)
    return gains


def _roi_block_stats(canvas_bgr: np.ndarray, y: int, x: int, block: int) -> Optional[Dict[str, float]]:
    """一个 ROI 块的 BGR 均值 + Lab 均值 + 彩度中位。"""
    h, w = canvas_bgr.shape[:2]
    if y < 0 or x < 0 or y + block > h or x + block > w:
        return None
    block_img = canvas_bgr[y:y + block, x:x + block]
    if block_img.size == 0:
        return None
    import cv2
    lab = cv2.cvtColor(block_img, cv2.COLOR_BGR2LAB).astype(np.float32)
    L = lab[..., 0].mean()
    a = lab[..., 1].mean() - 128.0
    b = lab[..., 2].mean() - 128.0
    C = float(np.median(np.hypot(lab[..., 1] - 128.0, lab[..., 2] - 128.0)))
    return {"mean_bgr": block_img.reshape(-1, 3).mean(axis=0),
            "L": float(L), "a": float(a), "b": float(b), "C": C}


def auto_select_roi(canvas_bgr: np.ndarray,
                    skin_mask: Optional[np.ndarray],
                    lesion_mask: Optional[np.ndarray],
                    block: int = _ROI_BLOCK,
                    step: int = 20) -> Optional[Dict[str, Any]]:
    """自动选本人正常皮肤参考 ROI（文档 §6.2）。

    条件：块内皮肤覆盖率≥70%、不含病灶、彩度 C∈[5,35]。
    优先选择离病灶近的块（同一照片内光照最一致），其次任意合格块。
    返回 {"y":..., "x":..., "mean_bgr":..., "L":..., "a":..., "b":..., "C":...}
    """
    h, w = canvas_bgr.shape[:2]
    if skin_mask is None:
        return None
    if skin_mask.shape[:2] != (h, w):
        return None
    lesion = lesion_mask if (lesion_mask is not None and lesion_mask.shape[:2] == (h, w)) \
        else np.zeros((h, w), dtype=bool)

    # 病灶几何中心（用于"近病灶优先"）
    ys, xs = np.where(lesion)
    near_candidates: List[Dict[str, Any]] = []
    far_candidates: List[Dict[str, Any]] = []
    if len(ys):
        cy, cx = float(ys.mean()), float(xs.mean())
    else:
        cy, cx = h / 2.0, w / 2.0

    for y in range(0, h - block + 1, step):
        for x in range(0, w - block + 1, step):
            skin_cov = float(skin_mask[y:y + block, x:x + block].mean())
            if skin_cov < 0.7:
                continue
            if lesion[y:y + block, x:x + block].any():
                continue
            stats = _roi_block_stats(canvas_bgr, y, x, block)
            if stats is None:
                continue
            if not (_ROI_C_MIN <= stats["C"] <= _ROI_C_MAX):
                continue
            cand = {"y": y, "x": x, "block": block, **stats,
                    "dist": float(np.hypot(y + block / 2 - cy, x + block / 2 - cx))}
            if cand["dist"] <= max(h, w) * 0.35:
                near_candidates.append(cand)
            else:
                far_candidates.append(cand)

    pool = near_candidates or far_candidates
    if not pool:
        return None
    # 彩度最接近健康肤色中段(C≈15)者优先
    pool.sort(key=lambda c: abs(c["C"] - 15.0))
    best = pool[0]
    for key in ("y", "x", "block", "dist"):
        best[key] = int(best[key]) if isinstance(best[key], (int, float)) and key != "dist" else best[key]
    return best


def calibrate_canvas(canvas_warped: np.ndarray,
                     orig_bgr: np.ndarray,
                     skin_mask: Optional[np.ndarray],
                     lesion_mask: Optional[np.ndarray],
                     anchor_ref_mean: Optional[np.ndarray] = None) -> Tuple[np.ndarray, Dict[str, Any]]:
    """灰世界 + 参考ROI 均值平移（文档 §4.2）。

    Args:
        canvas_warped: warp 后的画布图（未校准）
        orig_bgr: 原图（灰世界增益在此计算，文档 §4.3：不在扩展图上重算）
        skin_mask/lesion_mask: 画布坐标皮肤/病灶掩膜（病灶用于避开 ROI）
        anchor_ref_mean: 该患者该部位的历史参考均值（跨照片锚定）；None 时以本图为准

    Returns:
        (calibrated_canvas, calibration_dict)
    """
    gains = _gray_world_gains(orig_bgr)
    img = np.clip(canvas_warped.astype(np.float32) * gains, 0, 255)
    roi = auto_select_roi(img.astype(np.uint8), skin_mask, lesion_mask)
    ref_mean = None
    if roi is not None:
        cur = np.asarray(roi["mean_bgr"], dtype=np.float32)
        if anchor_ref_mean is not None:
            ref = np.asarray(anchor_ref_mean, dtype=np.float32)
            img = np.clip(img + (ref - cur), 0, 255)
            ref_mean = ref
        else:
            ref_mean = cur  # 首张照片：锚定自身
    img = img.astype(np.uint8)
    cal = {
        "wb_gains": [float(g) for g in gains],
        "ref_mean_bgr": [float(v) for v in ref_mean] if ref_mean is not None else None,
        "roi": {"y": roi["y"], "x": roi["x"], "block": roi["block"]} if roi else None,
        "roi_c": roi["C"] if roi else None,
        "roi_l": roi["L"] if roi else None,
        "roi_ok": roi is not None and (_ROI_C_MIN <= roi["C"] <= _ROI_C_MAX),
    }
    return img, cal


# ══════════════════════════════════════════════════════════════════════════════
# 主入口
# ══════════════════════════════════════════════════════════════════════════════

def align_and_calibrate(image_bytes: bytes,
                        body_site: str,
                        anchor: Optional[Dict[str, Any]] = None,
                        skin_mask: Optional[np.ndarray] = None,
                        lesion_mask: Optional[np.ndarray] = None,
                        ) -> CanvasResult:
    """主入口：原图 → 对齐 → 校准 → 统一画布。

    Args:
        image_bytes: 原图字节
        body_site: 评估部位
        anchor: 患者级锚点（patient_align_states.calibration_json 等），
                None 时以本图为锚（首张照片）
        skin_mask/lesion_mask: 画布坐标的皮肤/病灶掩膜（用于参考ROI避让与几何约束）。
                病灶掩膜可以由 VLM/SAM 先在原图坐标给出，随后 warp 到画布。

    Returns:
        CanvasResult（ok=False 时 canvas_img=None，调用方降级）
    """
    result = CanvasResult()
    try:
        import cv2
    except ImportError:
        result.note = "opencv unavailable"
        return result
    try:
        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        orig = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if orig is None:
            result.note = "image decode failed"
            return result
    except Exception as e:
        result.note = f"image decode failed: {e}"
        return result

    # ── 关键点检测 ──
    pts, kind = detect_keypoints(orig, body_site)
    if pts is None:
        # 恒等对齐：原图即画布（不重采样到模板，避免无谓失真）
        result.aligned = False
        result.canvas_warped = orig
        result.transform = np.eye(3, dtype=np.float64)
        result.keypoints = None
        result.scale_baseline_px = None
        cal_img, cal = calibrate_canvas(orig, orig, skin_mask, lesion_mask,
                                        np.asarray(anchor["ref_mean_bgr"], dtype=np.float32)
                                        if anchor and anchor.get("ref_mean_bgr") else None)
        result.canvas_img = cal_img
        result.calibration = cal
        result.ok = True
        result.note = "identity alignment (no keypoints)"
        return result

    EW, EH, OFF_Y, target, ipd_px = _canvas_params(kind)
    src = np.asarray(pts, dtype=np.float32)
    dst = np.asarray(target, dtype=np.float32)
    # 点数对齐：取两者交集数量
    n = min(len(src), len(dst))
    M = _similarity_transform([(float(p[0]), float(p[1])) for p in src[:n]],
                              [(float(p[0]), float(p[1])) for p in dst[:n]])
    if M is None:
        result.note = "similarity transform failed"
        return result

    T = np.array([[1, 0, 0], [0, 1, OFF_Y], [0, 0, 1]], dtype=np.float64)
    TM = T @ M
    try:
        warped = cv2.warpPerspective(orig, TM, (EW, EH), flags=cv2.INTER_LINEAR,
                                     borderValue=(0, 0, 0))
    except Exception as e:
        result.note = f"warp failed: {e}"
        return result

    # 皮肤/病灶掩膜（原图坐标）→ 画布坐标
    skin_c = None
    lesion_c = None
    if skin_mask is not None and skin_mask.shape[:2] == orig.shape[:2]:
        skin_c = (cv2.warpPerspective(skin_mask.astype(np.uint8) * 255, TM, (EW, EH),
                                      flags=cv2.INTER_NEAREST) > 127)
    if lesion_mask is not None and lesion_mask.shape[:2] == orig.shape[:2]:
        lesion_c = (cv2.warpPerspective(lesion_mask.astype(np.uint8) * 255, TM, (EW, EH),
                                        flags=cv2.INTER_NEAREST) > 127)

    anchor_ref = None
    if anchor and anchor.get("ref_mean_bgr"):
        anchor_ref = np.asarray(anchor["ref_mean_bgr"], dtype=np.float32)
    cal_img, cal = calibrate_canvas(warped, orig, skin_c, lesion_c, anchor_ref)
    cal["kind"] = kind
    cal["ipd_px"] = ipd_px

    result.ok = True
    result.aligned = True
    result.canvas_warped = warped
    result.canvas_img = cal_img
    result.transform = TM
    result.keypoints = [(float(p[0]), float(p[1])) for p in pts]
    result.scale_baseline_px = ipd_px
    result.calibration = cal
    result.note = f"aligned via {kind}"
    return result


def canvas_validity_mask(canvas_warped: np.ndarray) -> np.ndarray:
    """有效像素掩膜：排除 warp 黑边（文档 §4.3）。"""
    if canvas_warped is None:
        return np.zeros((1, 1), dtype=bool)
    return canvas_warped.max(axis=2) > 10


def lab_of(bgr: np.ndarray) -> np.ndarray:
    """BGR → Lab（L×100/255，a/b 减 128），文档 §5.2。"""
    import cv2
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    lab[..., 0] *= 100.0 / 255.0
    lab[..., 1] -= 128.0
    lab[..., 2] -= 128.0
    return lab


def canvas_snapshot(result: CanvasResult) -> Dict[str, Any]:
    """CanvasResult → 可持久化快照（评估上存 canvas_json）。

    快照必须支持确定性重建（rebuild_calibrated_canvas），供对比/追踪/训练复用。
    恒等对齐（无关键点）时 transform 记 None，画布=原图，由重建函数按原图尺寸处理。
    """
    aligned = bool(result.aligned)
    canvas_params = None
    if result.calibration.get("kind"):
        EW, EH, OFF_Y, target, ipd_px = _canvas_params(result.calibration["kind"])
        canvas_params = {"width": EW, "height": EH, "offset_y": OFF_Y, "ipd_px": ipd_px}
    elif result.canvas_warped is not None:
        h, w = result.canvas_warped.shape[:2]
        canvas_params = {"width": w, "height": h, "offset_y": 0, "ipd_px": None}
    return {
        "aligned": aligned,
        "kind": result.calibration.get("kind") or "identity",
        "transform": result.transform.tolist()
        if (result.transform is not None and aligned) else None,
        "canvas": canvas_params,
        "calibration": {
            "wb_gains": result.calibration.get("wb_gains"),
            "ref_mean_bgr": result.calibration.get("ref_mean_bgr"),
            "roi": result.calibration.get("roi"),
            "roi_c": result.calibration.get("roi_c"),
            "roi_ok": result.calibration.get("roi_ok"),
        },
        "scale_baseline_px": result.scale_baseline_px,
        "note": result.note,
    }


def rebuild_calibrated_canvas(orig_bgr: np.ndarray,
                              snapshot: Dict[str, Any]) -> Optional[np.ndarray]:
    """由 canvas_json 快照确定性重建校准画布图。

    变换矩阵 + wb_gains + 参考ROI坐标全部来自快照，因此与评测时逐像素一致。
    """
    try:
        import cv2
    except ImportError:
        return None
    if not snapshot or snapshot.get("transform") is None:
        # 恒等对齐快照：无法确定原校准图尺寸（原图即画布），直接按原图重建校准
        gains = np.asarray(snapshot["calibration"]["wb_gains"], dtype=np.float32)
        img = np.clip(orig_bgr.astype(np.float32) * gains, 0, 255).astype(np.uint8)
        if snapshot["calibration"].get("ref_mean_bgr") and snapshot["calibration"].get("roi"):
            roi = snapshot["calibration"]["roi"]
            block = roi.get("block", _ROI_BLOCK)
            y, x = roi["y"], roi["x"]
            h, w = img.shape[:2]
            if y + block <= h and x + block <= w:
                cur = img[y:y + block, x:x + block].reshape(-1, 3).mean(0)
                ref = np.asarray(snapshot["calibration"]["ref_mean_bgr"], dtype=np.float32)
                img = np.clip(img.astype(np.float32) + (ref - cur), 0, 255).astype(np.uint8)
        return img
    M = np.asarray(snapshot["transform"], dtype=np.float64)
    cw, ch = snapshot["canvas"]["width"], snapshot["canvas"]["height"]
    try:
        warped = cv2.warpPerspective(orig_bgr, M, (cw, ch), flags=cv2.INTER_LINEAR,
                                     borderValue=(0, 0, 0))
    except Exception:
        return None
    gains = np.asarray(snapshot["calibration"]["wb_gains"], dtype=np.float32)
    img = np.clip(warped.astype(np.float32) * gains, 0, 255)
    if snapshot["calibration"].get("ref_mean_bgr") and snapshot["calibration"].get("roi"):
        roi = snapshot["calibration"]["roi"]
        block = roi.get("block", _ROI_BLOCK)
        y, x = roi["y"], roi["x"]
        h, w = img.shape[:2]
        if y + block <= h and x + block <= w:
            cur = img[y:y + block, x:x + block].reshape(-1, 3).mean(0)
            ref = np.asarray(snapshot["calibration"]["ref_mean_bgr"], dtype=np.float32)
            img = np.clip(img + (ref - cur), 0, 255)
    return img.astype(np.uint8)


def warp_mask_orig_to_canvas(mask_orig: np.ndarray,
                             snapshot: Dict[str, Any]) -> Optional[np.ndarray]:
    """原图坐标布尔掩膜 → 画布坐标。恒等对齐快照直接返回原掩膜。"""
    try:
        import cv2
    except ImportError:
        return None
    if snapshot is None or snapshot.get("transform") is None:
        return mask_orig.astype(bool)
    M = np.asarray(snapshot["transform"], dtype=np.float64)
    cw, ch = snapshot["canvas"]["width"], snapshot["canvas"]["height"]
    warped = cv2.warpPerspective((mask_orig.astype(np.uint8) * 255), M, (cw, ch),
                                 flags=cv2.INTER_NEAREST, borderValue=0)
    return warped > 127

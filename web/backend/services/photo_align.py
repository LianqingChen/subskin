"""白斑照片像素级配准与变化热力图 — 对比报告核心可视化基元。

最佳实践参考（2026-08 调研）：
- Miiskin：叠影（半透明覆盖）对比，帮助用户对齐并直观看到变化；
- JuxtaposeJS：拖拽滑块前后对比；
- OpenCV 社区/显微镜配准案例：ORB 特征匹配 + RANSAC 单应性配准后再差分。

流程（v2 — 白斑掩膜差分，替代旧版纯灰度差分）：
1. ORB 特征匹配 + RANSAC 单应性，把「之后」照片配准到「之前」照片的几何
   （视角/距离/轻微旋转），使滑块与叠影对比真正对得上；
2. 皮肤掩膜：用全站唯一的 vasi_skin_mask 分别提取两图皮肤区域，取配准后
   交集——衣物/背景/参考卡永远不参与变化判定（旧版把变暗的衣服标成
   「复色」的根源就是没有皮肤约束）；
3. 白斑掩膜：优先使用外部传入的测评分割层（VASI 评估的 AI/用户修正掩膜），
   否则用 vasi_skin_mask.detect_vitiligo_within_skin 在皮肤区内做相对亮度检测；
4. 掩膜差分分类：复色（原白斑→正常肤色，绿）/ 扩大或新发（红），叠加在原图上；
5. 双重门禁：配准质量（匹配点/内点/形变）+ 光线/皮肤区域门槛，
   任一不满足则不出热力图，只如实返回原因——不精确就不展示。

诚实降级原则：配准不达标绝不硬对齐，避免错位图误导用户。
"""

import io
import logging
import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

_MODEL_DIR = "data/models/mediapipe"

_MAX_SIDE = 900
_MIN_GOOD_MATCHES = 10
_MIN_INLIERS = 8
_MIN_SCALE = 0.5
_MAX_SCALE = 2.0
_OVERLAY_ALPHA = 0.5
# 光线门禁：任一图灰度均值低于该值（夜间/严重欠曝）不出热力图
_MIN_BRIGHTNESS = 55
# 皮肤交集占画面最小比例，低于该值说明可见皮肤过少，差分不可靠
_MIN_SKIN_RATIO = 0.03
# 变化类像素（复色+扩大）占分析区最小比例，低于该值视为无明显变化
_MIN_CHANGE_RATIO = 0.002
# 变化类像素的连通域最小面积（防噪点）
_MIN_COMPONENT_AREA = 40

# BGR 叠加色：绿=复色，红=扩大/新发
_COLOR_REPIG = (110, 200, 60)
_COLOR_EXPAND = (70, 70, 235)


def _load_rgb(image_bytes: bytes):
    """解码并降采样（最长边 900），失败返回 None。"""
    try:
        import cv2
        import numpy as np
    except ImportError:
        return None
    try:
        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return None
        h, w = img.shape[:2]
        m = max(h, w)
        if m > _MAX_SIDE:
            s = _MAX_SIDE / m
            img = cv2.resize(img, (max(1, int(w * s)), max(1, int(h * s))))
        return img
    except Exception:
        return None


def _skin_mask_of(img_bgr) -> Optional[np.ndarray]:
    """全站统一皮肤掩膜（vasi_skin_mask），输入 BGR，输出 bool 或 None。"""
    try:
        from web.backend.services import vasi_skin_mask

        rgb = img_bgr[:, :, ::-1]
        return vasi_skin_mask.build_skin_mask(rgb)
    except Exception:
        logger.warning("photo_align: 皮肤掩膜不可用，回退内置 HSV 掩膜", exc_info=True)
        return None


def _drop_huge_components(mask: np.ndarray, analysis_px: int) -> np.ndarray:
    """去掉面积超过分析区 35% 的连通域——单个如此巨大的"白斑"几乎必然是
    衣物/背景误检，不是病灶。"""
    import cv2

    if not mask.any():
        return mask
    out = np.zeros_like(mask, dtype=np.uint8)
    num, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), 8)
    cap = analysis_px * 0.35
    for i in range(1, num):
        if stats[i, cv2.CC_STAT_AREA] <= cap:
            out[labels == i] = 1
    return out.astype(bool)


def _enclosed_holes(skin: np.ndarray) -> np.ndarray:
    """被皮肤完全包围的非皮肤空洞（即白斑内部）→ 整块纳入分析区。

    与图像边界连通的非皮肤区域（衣物/背景/大面积头发）不纳入——
    这是"只认皮肤内白斑"的精确实现。
    """
    import cv2

    inv = (~skin).astype(np.uint8)
    num, labels = cv2.connectedComponents(inv, connectivity=8)
    if num <= 1:
        return np.zeros(skin.shape, dtype=bool)
    border_ids = set(
        np.unique(
            np.concatenate([labels[0, :], labels[-1, :], labels[:, 0], labels[:, -1]])
        ).tolist()
    )
    out = np.zeros(skin.shape, dtype=bool)
    for i in range(1, num):
        if i in border_ids:
            continue
        out |= labels == i
    return out


def _fallback_skin_mask(img_bgr) -> np.ndarray:
    """vasi_skin_mask 不可用时的兜底 HSV∪YCrCb 皮肤掩膜。"""
    import cv2

    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    ycrcb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2YCrCb)
    m1 = cv2.inRange(hsv, (0, 20, 50), (25, 200, 255))
    m2 = cv2.inRange(hsv, (160, 20, 50), (179, 200, 255))
    m3 = cv2.inRange(ycrcb, (0, 133, 77), (255, 180, 130))
    return (cv2.bitwise_or(cv2.bitwise_or(m1, m2), m3) > 0)


def _detect_lesion(img_bgr, region: np.ndarray) -> Optional[np.ndarray]:
    """皮肤区域内白斑检测（相对亮度法，与测评同源）。"""
    try:
        from web.backend.services.vasi_skin_mask import detect_vitiligo_within_skin

        mask, _stats = detect_vitiligo_within_skin(img_bgr[:, :, ::-1], region)
        return mask
    except Exception:
        logger.warning("photo_align: 白斑检测失败", exc_info=True)
        return None


def _fit_mask(mask: Optional[np.ndarray], shape: Tuple[int, int]) -> Optional[np.ndarray]:
    """把外部掩膜缩放到工作分辨率（bool）。"""
    import cv2

    if mask is None:
        return None
    m = np.asarray(mask)
    if m.ndim != 2 or m.size == 0:
        return None
    if m.shape[:2] != shape[:2]:
        m = cv2.resize(
            (m > 0).astype(np.uint8), (shape[1], shape[0]), interpolation=cv2.INTER_NEAREST
        )
    return m > 0


def _clean_small_components(mask: np.ndarray, min_area: int) -> np.ndarray:
    import cv2

    out = np.zeros_like(mask, dtype=np.uint8)
    num, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), 8)
    for i in range(1, num):
        if stats[i, cv2.CC_STAT_AREA] >= min_area:
            out[labels == i] = 1
    return out.astype(bool)


def _fail(note: str, inliers=None, scale=None) -> Dict[str, Any]:
    return {"aligned": False, "inlier_count": inliers, "scale": scale, "warped": None, "heatmap": None, "note": note}


def align_and_diff(
    image_bytes_a: bytes,
    image_bytes_b: bytes,
    lesion_mask_a: Optional[np.ndarray] = None,
    lesion_mask_b: Optional[np.ndarray] = None,
) -> Dict[str, Any]:
    """配准「之后」(B) 到「之前」(A) 并生成白斑变化热力图。

    Args:
        image_bytes_a: 较早照片原始字节
        image_bytes_b: 较晚照片原始字节
        lesion_mask_a: A 图白斑掩膜（原图分辨率 bool，可来自测评分割层），可空
        lesion_mask_b: B 图白斑掩膜，可空

    Returns:
        {
          "aligned": bool,
          "inlier_count": Optional[int],
          "scale": Optional[float],          # 配准尺度（B→A）
          "warped": PIL.Image | None,        # B 配准到 A 画布后的展示图（空白区用 A 补齐）
          "heatmap": PIL.Image | None,       # 变化热力图（绿=复色，红=扩大/新发），仅门禁全过时返回
          "classes": dict | None,            # {"repigmented_px", "expanded_px", "analysis_px"}
          "note": Optional[str],             # 失败原因/未出图原因
        }
    """
    try:
        import cv2
    except ImportError:
        return _fail("图像配准组件不可用")

    a = _load_rgb(image_bytes_a)
    b = _load_rgb(image_bytes_b)
    if a is None or b is None:
        return _fail("照片无法解码")

    try:
        ga = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY)
        gb = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY)

        orb = cv2.ORB_create(nfeatures=3000)
        ka, da = orb.detectAndCompute(ga, None)
        kb, db = orb.detectAndCompute(gb, None)
        if da is None or db is None or len(ka) < 8 or len(kb) < 8:
            return _fail("照片纹理特征不足")

        bf = cv2.BFMatcher(cv2.NORM_HAMMING)
        knn = bf.knnMatch(da, db, k=2)
        good = [m for m, n in knn if m.distance < 0.75 * n.distance]
        if len(good) < _MIN_GOOD_MATCHES:
            return _fail("两图共同特征点过少，无法对齐")

        src = np.float32([kb[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
        dst = np.float32([ka[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
        homography, mask = cv2.findHomography(src, dst, cv2.RANSAC, 5.0, maxIters=3000)
        if homography is None:
            return _fail("无法估计两图的几何关系")

        inliers = int(np.count_nonzero(mask)) if mask is not None else 0
        if inliers < _MIN_INLIERS:
            return _fail("两图对齐点过少（拍摄角度差异可能较大）", inliers=inliers)

        sx = abs(float(homography[0, 0]))
        sy = abs(float(homography[1, 1]))
        scale = round((sx + sy) / 2, 3)
        if sx < _MIN_SCALE or sx > _MAX_SCALE or sy < _MIN_SCALE or sy > _MAX_SCALE:
            return _fail("两图拍摄距离/角度差异过大，放弃像素对齐", inliers=inliers, scale=scale)

        h, w = a.shape[:2]
        warped = cv2.warpPerspective(b, homography, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        valid = cv2.warpPerspective(np.ones_like(gb, dtype=np.float32), homography, (w, h)) > 0.5

        # 展示图：有效区域显示配准后的 B，空白区域用 A 补齐（画面完整）
        display = a.copy()
        display[valid] = warped[valid]

        warped_pil = _to_pil(display)

        # ── 变化热力图：皮肤掩膜交集 + 白斑掩膜差分 ──
        heatmap_pil, classes, heat_note = _build_lesion_diff_heatmap(
            a, warped, valid, lesion_mask_a, lesion_mask_b
        )

        return {
            "aligned": True,
            "inlier_count": inliers,
            "scale": scale,
            "warped": warped_pil,
            "heatmap": heatmap_pil,
            "classes": classes,
            "note": heat_note,
        }
    except Exception:
        logger.warning("photo_align: 配准失败", exc_info=True)
        return _fail("配准过程中出现异常，未做像素对齐")


def _to_pil(img_bgr):
    from PIL import Image

    import cv2

    return Image.fromarray(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))


def _build_lesion_diff_heatmap(
    a_bgr,
    warped_bgr,
    valid: np.ndarray,
    lesion_mask_a: Optional[np.ndarray],
    lesion_mask_b: Optional[np.ndarray],
):
    """皮肤掩膜交集内的白斑掩膜差分。返回 (heatmap|None, classes|None, note)。"""
    import cv2

    h, w = a_bgr.shape[:2]
    total = h * w

    # 光线门禁：夜间/欠曝照片不做差分（亮度差主要来自光线而非病情）
    ga = cv2.cvtColor(a_bgr, cv2.COLOR_BGR2GRAY)
    gw = cv2.cvtColor(warped_bgr, cv2.COLOR_BGR2GRAY)
    mean_a = float(ga[valid].mean()) if valid.any() else float(ga.mean())
    mean_b = float(gw[valid].mean()) if valid.any() else float(gw.mean())
    if mean_a < _MIN_BRIGHTNESS or mean_b < _MIN_BRIGHTNESS:
        return None, None, "照片光线不足，无法生成可靠热力图（请在自然光下拍摄）"

    skin_a = _skin_mask_of(a_bgr)
    skin_b = _skin_mask_of(warped_bgr)
    if skin_a is None:
        skin_a = _fallback_skin_mask(a_bgr)
    if skin_b is None:
        skin_b = _fallback_skin_mask(warped_bgr)

    core = skin_a & skin_b & valid
    if int(np.count_nonzero(core)) < total * _MIN_SKIN_RATIO:
        return None, None, "两图可见皮肤区域过少或不重叠，无法生成可靠热力图"

    # 分析区 = 真实皮肤的窄邻域带 ∪ 被皮肤完全包围的空洞（白斑内部）。
    # 衣服/头发/背景要么不在带内、要么与图像边界连通被排除——从源头抗误检。
    band = max(12, int(max(h, w) * 0.035))
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (band * 2 + 1, band * 2 + 1))
    zone_a = cv2.dilate(skin_a.astype(np.uint8), k).astype(bool) | _enclosed_holes(skin_a)
    zone_b = cv2.dilate(skin_b.astype(np.uint8), k).astype(bool) | _enclosed_holes(skin_b)
    analysis = zone_a & zone_b & valid
    analysis_px = int(np.count_nonzero(analysis))
    if analysis_px < total * _MIN_SKIN_RATIO:
        return None, None, "两图可见皮肤区域过少或不重叠，无法生成可靠热力图"

    # 白斑掩膜：优先外部传入（测评分割层），否则皮肤区内相对亮度检测
    lesion_a = _fit_mask(lesion_mask_a, (h, w))
    if lesion_a is None:
        lesion_a = _detect_lesion(a_bgr, analysis)
    else:
        lesion_a = lesion_a & analysis
    lesion_b_warped = _fit_mask(lesion_mask_b, (h, w))
    if lesion_b_warped is None:
        lesion_b_warped = _detect_lesion(warped_bgr, analysis)
    else:
        lesion_b_warped = lesion_b_warped & analysis
    if lesion_a is None or lesion_b_warped is None:
        return None, None, "白斑区域识别失败，无法生成可靠热力图"
    # CV 回退路径：去掉疑似衣物/背景的巨大误检连通域（测评分割层已人工校验，不裁）
    if lesion_mask_a is None:
        lesion_a = _drop_huge_components(lesion_a, analysis_px)
    if lesion_mask_b is None:
        lesion_b_warped = _drop_huge_components(lesion_b_warped, analysis_px)

    # 分类：复色 = 原白斑现已恢复正常肤色；扩大 = 新增/扩大的白斑区域
    repig = lesion_a & ~lesion_b_warped
    expand = lesion_b_warped & ~lesion_a
    repig = _clean_small_components(repig, _MIN_COMPONENT_AREA)
    expand = _clean_small_components(expand, _MIN_COMPONENT_AREA)

    repig_px = int(np.count_nonzero(repig))
    expand_px = int(np.count_nonzero(expand))
    classes = {"repigmented_px": repig_px, "expanded_px": expand_px, "analysis_px": analysis_px}

    if (repig_px + expand_px) < analysis_px * _MIN_CHANGE_RATIO:
        return None, classes, "未检测到白斑区域的明显变化"
    # 方向一致性门禁：复色与扩大双向都显著时，差异更像配准残差/拍摄条件噪声
    # （真实复色应绿≫红，真实扩大应红≫绿），不出图以免误导。
    if min(repig_px, expand_px) > analysis_px * 0.01:
        return None, classes, "两图差异信号分散，更像拍摄角度/光线差异所致，无法生成可靠的变化热力图"

    # 轻微膨胀+羽化，让叠加区域边界更柔和可读
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    repig_s = cv2.dilate(repig.astype(np.uint8), kernel, iterations=1).astype(bool)
    expand_s = cv2.dilate(expand.astype(np.uint8), kernel, iterations=1).astype(bool)

    overlay = a_bgr.copy().astype(np.float32)
    if repig_px:
        sel = repig_s & analysis
        overlay[sel] = overlay[sel] * (1 - _OVERLAY_ALPHA) + np.array(_COLOR_REPIG, dtype=np.float32) * _OVERLAY_ALPHA
    if expand_px:
        sel = expand_s & analysis & ~repig_s
        overlay[sel] = overlay[sel] * (1 - _OVERLAY_ALPHA) + np.array(_COLOR_EXPAND, dtype=np.float32) * _OVERLAY_ALPHA

    return _to_pil(overlay.astype(np.uint8)), classes, None


# ══════════════════════════════════════════════════════════════════════════════
# 面部对齐参数（瞳距归一化）— 供前端滑块对比使用
# ══════════════════════════════════════════════════════════════════════════════

_DETECT_MAX_SIDE = 1024  # 关键点检测前最长边降采样


def _detect_eyes(image_bytes: bytes) -> Optional[Tuple[Tuple[float, float], Tuple[float, float], int, int]]:
    """检测双眼中心（内外眼角中点），返回 (left, right, orig_w, orig_h) 或 None。

    - 坐标按 EXIF 转正后的「视觉方向」原图像素坐标（与浏览器 createImageBitmap 一致）；
    - 检测前最长边降采样到 1024，坐标还原到原图。
    """
    try:
        import os

        import mediapipe as mp
        import numpy as np
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision
        from PIL import Image, ImageOps

        model_path = os.path.join(_MODEL_DIR, "face_landmarker.task")
        if not os.path.exists(model_path):
            return None

        pil = Image.open(io.BytesIO(image_bytes))
        pil = ImageOps.exif_transpose(pil).convert("RGB")
        orig_w, orig_h = pil.size
        arr = np.asarray(pil)

        scale = 1.0
        m = max(orig_w, orig_h)
        if m > _DETECT_MAX_SIDE:
            scale = _DETECT_MAX_SIDE / m
            pil = pil.resize((max(1, int(orig_w * scale)), max(1, int(orig_h * scale))))
            arr = np.asarray(pil)

        options = vision.FaceLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=model_path),
            running_mode=vision.RunningMode.IMAGE,
            num_faces=1,
        )
        with vision.FaceLandmarker.create_from_options(options) as landmarker:
            rgb = mp.Image(image_format=mp.ImageFormat.SRGB, data=arr)
            res = landmarker.detect(rgb)
        if not res.face_landmarks:
            return None
        lm = res.face_landmarks[0]
        dh, dw = arr.shape[:2]

        def eye_center(a: int, b: int) -> Tuple[float, float]:
            ax = float(lm[a].x) * dw
            ay = float(lm[a].y) * dh
            bx = float(lm[b].x) * dw
            by = float(lm[b].y) * dh
            return ((ax + bx) / 2, (ay + by) / 2)

        # 左眼（外角33/内角133）、右眼（外角263/内角362）
        left = eye_center(33, 133)
        right = eye_center(362, 263)
        k = 1.0 / scale
        return ((left[0] * k, left[1] * k), (right[0] * k, right[1] * k), orig_w, orig_h)
    except Exception:
        logger.info("photo_align: 眼部关键点检测不可用", exc_info=True)
        return None


def _detect_hand_anchor(image_bytes: bytes) -> Optional[Tuple[Tuple[float, float], Tuple[float, float], int, int]]:
    """检测手掌宽度锚点（食指 MCP 5 / 小指 MCP 17），返回 (a, b, orig_w, orig_h) 或 None。"""
    try:
        import os

        import mediapipe as mp
        import numpy as np
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision
        from PIL import Image, ImageOps

        model_path = os.path.join(_MODEL_DIR, "hand_landmarker.task")
        if not os.path.exists(model_path):
            return None

        pil = Image.open(io.BytesIO(image_bytes))
        pil = ImageOps.exif_transpose(pil).convert("RGB")
        orig_w, orig_h = pil.size
        arr = np.asarray(pil)
        scale = 1.0
        m = max(orig_w, orig_h)
        if m > _DETECT_MAX_SIDE:
            scale = _DETECT_MAX_SIDE / m
            pil = pil.resize((max(1, int(orig_w * scale)), max(1, int(orig_h * scale))))
            arr = np.asarray(pil)

        options = vision.HandLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=model_path),
            running_mode=vision.RunningMode.IMAGE,
            num_hands=1,
        )
        with vision.HandLandmarker.create_from_options(options) as landmarker:
            rgb = mp.Image(image_format=mp.ImageFormat.SRGB, data=arr)
            res = landmarker.detect(rgb)
        if not res.hand_landmarks:
            return None
        lm = res.hand_landmarks[0]
        dh, dw = arr.shape[:2]

        def pt(i: int) -> Tuple[float, float]:
            return (float(lm[i].x) * dw, float(lm[i].y) * dh)

        a, b = pt(5), pt(17)
        k = 1.0 / scale
        return ((a[0] * k, a[1] * k), (b[0] * k, b[1] * k), orig_w, orig_h)
    except Exception:
        logger.info("photo_align: 手部锚点检测不可用", exc_info=True)
        return None


def _detect_pose_anchor(image_bytes: bytes) -> Optional[Tuple[Tuple[float, float], Tuple[float, float], int, int]]:
    """检测肩部锚点（左肩 11 / 右肩 12），返回 (a, b, orig_w, orig_h) 或 None。"""
    try:
        import os

        import mediapipe as mp
        import numpy as np
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision
        from PIL import Image, ImageOps

        model_path = os.path.join(_MODEL_DIR, "pose_landmarker_lite.task")
        if not os.path.exists(model_path):
            return None

        pil = Image.open(io.BytesIO(image_bytes))
        pil = ImageOps.exif_transpose(pil).convert("RGB")
        orig_w, orig_h = pil.size
        arr = np.asarray(pil)
        scale = 1.0
        m = max(orig_w, orig_h)
        if m > _DETECT_MAX_SIDE:
            scale = _DETECT_MAX_SIDE / m
            pil = pil.resize((max(1, int(orig_w * scale)), max(1, int(orig_h * scale))))
            arr = np.asarray(pil)

        options = vision.PoseLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=model_path),
            running_mode=vision.RunningMode.IMAGE,
            num_poses=1,
        )
        with vision.PoseLandmarker.create_from_options(options) as landmarker:
            rgb = mp.Image(image_format=mp.ImageFormat.SRGB, data=arr)
            res = landmarker.detect(rgb)
        if not res.pose_landmarks:
            return None
        lm = res.pose_landmarks[0]
        dh, dw = arr.shape[:2]

        def pt(i: int) -> Tuple[float, float]:
            p = lm[i]
            if getattr(p, "visibility", 0.5) is not None and float(getattr(p, "visibility", 0.5)) < 0.5:
                raise ValueError("关节不可见")
            return (float(p.x) * dw, float(p.y) * dh)

        a, b = pt(11), pt(12)
        k = 1.0 / scale
        return ((a[0] * k, a[1] * k), (b[0] * k, b[1] * k), orig_w, orig_h)
    except Exception:
        logger.info("photo_align: 姿态锚点检测不可用", exc_info=True)
        return None


def _site_kind(body_site: str) -> str:
    """把业务部位映射到锚点类别。"""
    s = (body_site or "").strip()
    if s in ("面部", "脸部", "face"):
        return "face"
    if s in ("手部", "左手", "右手", "手", "hand"):
        return "hand"
    return "pose"


_ANCHOR_DETECTORS = {
    "face": _detect_eyes,
    "hand": _detect_hand_anchor,
    "pose": _detect_pose_anchor,
}


def compute_align_params(
    image_bytes_list: List[bytes],
    body_site: Optional[str] = None,
) -> Dict[str, Any]:
    """计算多张照片的对齐参数：按部位锚点归一化缩放 + 锚点同点同角度。

    锚点按部位自动选择：
    - face：双眼中心（瞳距）；
    - hand：食指/小指 MCP（掌宽）；
    - pose：双肩（肩宽）——躯干/背部/四肢等部位；
    body_site 指定时优先用对应锚点，检测失败自动回退其余类别；
    参考 = 第一张检测成功的照片，仅对齐与参考同类别的照片。

    返回：
      ok=False 时至少两张照片未检测到同类锚点；
      ok=True 时携带 canvas（参考图尺寸与锚点）与每张照片的
      {anchor_a, anchor_b, anchor_mid, anchor_dist, scale, rotate_deg, kind, width, height}。
    """
    if body_site:
        preferred = _site_kind(body_site)
        order = [preferred] + [k for k in ("face", "hand", "pose") if k != preferred]
    else:
        order = ["face", "hand", "pose"]

    detections = []
    for b in image_bytes_list:
        hit = None
        for kind in order:
            r = _ANCHOR_DETECTORS[kind](b)
            if r:
                hit = (kind, r[0], r[1], r[2], r[3])
                break
        detections.append(hit)

    found_idx = [i for i, d in enumerate(detections) if d]
    if len(found_idx) < 2:
        return {
            "ok": False,
            "note": "至少两张照片需检测到同一部位特征，未自动对齐",
            "items": [{"index": i, "found": bool(detections[i])} for i in range(len(image_bytes_list))],
        }

    ref_i = found_idx[0]
    ref_kind, a0, b0, w0, h0 = detections[ref_i]  # type: ignore[misc]
    dist0 = math.hypot(b0[0] - a0[0], b0[1] - a0[1])
    ang0 = math.atan2(b0[1] - a0[1], b0[0] - a0[0])
    mid0 = ((a0[0] + b0[0]) / 2, (a0[1] + b0[1]) / 2)

    items: List[Dict[str, Any]] = []
    for i, d in enumerate(detections):
        if not d or d[0] != ref_kind:
            items.append({"index": i, "found": False})
            continue
        _, a, b, w, h = d
        dist = math.hypot(b[0] - a[0], b[1] - a[1])
        ang = math.atan2(b[1] - a[1], b[0] - a[0])
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        items.append({
            "index": i,
            "found": True,
            "kind": ref_kind,
            "anchor_a": [round(a[0], 2), round(a[1], 2)],
            "anchor_b": [round(b[0], 2), round(b[1], 2)],
            "anchor_mid": [round(mid[0], 2), round(mid[1], 2)],
            "anchor_dist": round(dist, 2),
            "scale": round(dist0 / dist, 6),
            "rotate_deg": round(math.degrees(ang0 - ang), 4),
            "width": w,
            "height": h,
        })

    return {
        "ok": True,
        "ref_index": ref_i,
        "kind": ref_kind,
        "canvas": {
            "width": w0,
            "height": h0,
            "anchor_mid": [round(mid0[0], 2), round(mid0[1], 2)],
            "angle_deg": round(math.degrees(ang0), 4),
            "anchor_dist": round(dist0, 2),
        },
        "items": items,
    }

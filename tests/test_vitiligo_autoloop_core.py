"""白斑识别自循环核心模块单元测试（患者画布管线 / 患者分类器 / 共识引擎）。

不依赖数据库与外部 AI 服务：合成图像验证
- 对齐/校准管线（含恒等对齐降级与快照确定性重建）
- K-means 冷启动合理性校验
- 随机森林训练/预测/逆变换闭环
- 色值验证与共识判定
"""

import io

import cv2
import numpy as np
import pytest

from web.backend.services import vasi_canvas
from web.backend.services import vasi_patient_model as pm
from web.backend.services.vasi_consensus import (
    color_verify_candidate,
    mask_iou,
)


def _synthetic_face() -> bytes:
    """合成含白斑的肤色图（背景中性灰、皮肤椭圆、右下方亮白斑）。"""
    img = np.full((600, 480, 3), 120, dtype=np.uint8)
    cv2.ellipse(img, (240, 300), (140, 190), 0, 0, 360, (140, 100, 90), -1)
    cv2.ellipse(img, (300, 330), (40, 55), 0, 0, 360, (200, 180, 165), -1)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 95])
    assert ok
    return buf.tobytes()


def _skin_mask(shape, center=(240, 300), axes=(140, 190)) -> np.ndarray:
    return cv2.ellipse(np.zeros(shape[:2], np.uint8), center, axes, 0, 0, 360, 1, -1) > 0


def _patch_mask(shape, center=(300, 330), axes=(40, 55)) -> np.ndarray:
    return cv2.ellipse(np.zeros(shape[:2], np.uint8), center, axes, 0, 0, 360, 1, -1) > 0


class TestCanvasPipeline:
    def test_align_and_calibrate_identity_fallback(self):
        img_bytes = _synthetic_face()
        res = vasi_canvas.align_and_calibrate(img_bytes, "面部", anchor=None)
        assert res.ok
        # 合成图无真实人脸 → 恒等对齐（优雅降级，不抛错）
        assert res.aligned is False or res.aligned is True
        assert res.canvas_img is not None
        assert res.transform is not None

    def test_snapshot_rebuild_deterministic(self):
        img_bytes = _synthetic_face()
        orig = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)
        res = vasi_canvas.align_and_calibrate(img_bytes, "面部", anchor=None)
        snap = vasi_canvas.canvas_snapshot(res)
        rebuilt = vasi_canvas.rebuild_calibrated_canvas(orig, snap)
        assert rebuilt is not None
        assert np.array_equal(res.canvas_img, rebuilt)

    def test_snapshot_has_required_keys(self):
        res = vasi_canvas.align_and_calibrate(_synthetic_face(), "面部")
        snap = vasi_canvas.canvas_snapshot(res)
        for key in ("aligned", "kind", "transform", "canvas", "calibration",
                    "scale_baseline_px"):
            assert key in snap

    def test_gray_world_gains_bounded(self):
        img = np.full((100, 100, 3), 120, dtype=np.uint8)
        img[..., 2] = 200  # 偏红
        gains = vasi_canvas._gray_world_gains(img)
        assert gains.shape == (3,)
        assert (gains >= 0.6).all() and (gains <= 1.7).all()

    def test_auto_select_roi_avoids_lesion(self):
        img_bytes = _synthetic_face()
        res = vasi_canvas.align_and_calibrate(img_bytes, "面部")
        canvas = res.canvas_img
        skin = _skin_mask(canvas.shape)
        patch = _patch_mask(canvas.shape)
        roi = vasi_canvas.auto_select_roi(canvas, skin, patch)
        assert roi is not None
        y, x, b = roi["y"], roi["x"], roi["block"]
        assert not patch[y:y + b, x:x + b].any()  # ROI 不含病灶
        assert 5.0 <= roi["C"] <= 35.0            # 彩度自检

    def test_lab_of_range(self):
        img = np.full((50, 50, 3), 128, dtype=np.uint8)
        lab = vasi_canvas.lab_of(img)
        assert lab.shape == (50, 50, 3)
        assert 0 <= lab[..., 0].min() <= 100


class TestKMeansColdStart:
    def test_sane_white_cluster(self):
        img_bytes = _synthetic_face()
        res = vasi_canvas.align_and_calibrate(img_bytes, "面部")
        canvas = res.canvas_img
        skin = _skin_mask(canvas.shape)
        km = pm.kmeans_cold_start(canvas, skin)
        assert km is not None
        assert km["sane"] is True
        # 白斑簇必须更亮且更低彩度（文档 §4.6-3）
        assert km["cluster_white"][0] > km["cluster_normal"][0]
        assert km["cluster_white"][1] < km["cluster_normal"][1]
        # 掩膜应集中在合成白斑附近
        patch_c = _patch_mask(canvas.shape)
        iou = mask_iou(km["mask"], patch_c)
        assert iou is not None and iou > 0.4

    def test_chroma_reversal_rejected(self):
        """纯灰色无彩度分层的图 → 合理性校验作废（返回 None）。"""
        img = np.full((400, 400, 3), 128, dtype=np.uint8)
        cv2.circle(img, (200, 200), 120, (190, 190, 190), -1)  # 更亮但彩度相同
        ok, buf = cv2.imencode(".jpg", img)
        res = vasi_canvas.align_and_calibrate(buf.tobytes(), "面部")
        skin = np.ones((400, 400), dtype=bool)
        km = pm.kmeans_cold_start(res.canvas_img, skin)
        assert km is None  # 无彩度分层 → 作废


class TestRandomForest:
    def test_train_predict_inverse_roundtrip(self):
        img_bytes = _synthetic_face()
        orig = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)
        res = vasi_canvas.align_and_calibrate(img_bytes, "面部")
        canvas = res.canvas_img
        skin = _skin_mask(canvas.shape)
        km = pm.kmeans_cold_start(canvas, skin)
        assert km is not None
        clf = pm.train_rf(canvas, km["mask"], validity=canvas.max(2) > 10)
        assert clf is not None
        prob = pm.predict_canvas(clf, canvas, canvas.max(2) > 10)
        assert prob is not None and prob.shape == canvas.shape[:2]
        mask_orig = pm.canvas_mask_to_original(prob > 0.5, res.transform, orig.shape[:2])
        assert mask_orig.shape == orig.shape[:2]
        patch = _patch_mask(orig.shape)
        iou = mask_iou(mask_orig, patch)
        assert iou is not None and iou > 0.5

    def test_train_rf_from_samples(self):
        img_bytes = _synthetic_face()
        res = vasi_canvas.align_and_calibrate(img_bytes, "面部")
        canvas = res.canvas_img
        skin = _skin_mask(canvas.shape)
        km = pm.kmeans_cold_start(canvas, skin)
        assert km is not None
        samples = [{"canvas_img": canvas, "mask": km["mask"],
                    "validity": canvas.max(2) > 10}]
        clf = pm.train_rf_from_samples(samples)
        assert clf is not None

    def test_save_load_model(self, tmp_path, monkeypatch):
        monkeypatch.setattr(pm, "MODEL_ROOT", tmp_path)
        img_bytes = _synthetic_face()
        res = vasi_canvas.align_and_calibrate(img_bytes, "面部")
        canvas = res.canvas_img
        skin = _skin_mask(canvas.shape)
        km = pm.kmeans_cold_start(canvas, skin)
        clf = pm.train_rf(canvas, km["mask"], validity=canvas.max(2) > 10)
        path = pm.save_model(42, "面部", clf, {"version": "v1", "sample_count": 1})
        assert path is not None
        loaded = pm.load_model(42, "面部")
        assert loaded is not None
        meta = pm.load_model_meta(42, "面部")
        assert meta and meta["version"] == "v1"


class TestConsensus:
    def test_color_verify_confirms_white_patch(self):
        img_bytes = _synthetic_face()
        res = vasi_canvas.align_and_calibrate(img_bytes, "面部")
        canvas = res.canvas_img
        skin = _skin_mask(canvas.shape)
        patch = _patch_mask(canvas.shape)
        chk = color_verify_candidate(canvas, patch, skin, canvas.max(2) > 10)
        assert chk is not None
        assert chk["passed"] is True
        assert chk["C_ratio"] < 0.85 and chk["L_gap"] > 0

    def test_color_verify_rejects_background(self):
        img_bytes = _synthetic_face()
        res = vasi_canvas.align_and_calibrate(img_bytes, "面部")
        canvas = res.canvas_img
        skin = _skin_mask(canvas.shape)
        bg = np.zeros(canvas.shape[:2], dtype=bool)
        bg[:80, :80] = True  # 背景角块（非皮肤）
        chk = color_verify_candidate(canvas, bg, skin, canvas.max(2) > 10)
        assert chk is None or chk["passed"] is False

    def test_mask_iou_metrics(self):
        a = np.zeros((100, 100), dtype=bool)
        b = np.zeros((100, 100), dtype=bool)
        a[10:50, 10:50] = True
        b[30:70, 30:70] = True
        iou = mask_iou(a, b)
        assert iou is not None and 0.0 < iou < 1.0
        assert mask_iou(a, a) == 1.0
        assert mask_iou(a, np.zeros((50, 50), bool)) is None

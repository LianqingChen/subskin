"""
VASI RL 策略优化器 — Contextual Bandit 驱动的自我进化

Phase L2: 不使用 GPU，通过轻量图片特征 + 2层 MLP 策略网络，
从用户修正数据中学习最优 pipeline 参数组合。

Architecture:
  ImageFeatureExtractor (PIL + numpy, <50ms)
      ↓ 16D feature vector
  ContextualBanditPolicy (2-layer MLP, 1345 params)
      ↓ predicted Dice score
  OnlineLearner (gradient descent from user corrections)
      ↓ improved policy

设计原则:
  - 零 GPU 依赖: 纯 numpy 前向/反向传播
  - 推理耗时 <1ms: 1345个参数，24D 输入
  - 持续在线学习: 每10次用户修正触发一次学习
  - 参数持久化: JSON 文件存储，重启不丢失
"""

import json
import logging
import os
import hashlib
import math
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from io import BytesIO

import numpy as np

logger = logging.getLogger(__name__)

# ── State file path ────────────────────────────────────────────────
STATE_DIR = "/root/subskin/data/rl_state"
STATE_FILE = os.path.join(STATE_DIR, "vasi_policy.json")
BUFFER_FILE = os.path.join(STATE_DIR, "vasi_training_buffer.jsonl")


# ═══════════════════════════════════════════════════════════════════
# Image Feature Extractor
# ═══════════════════════════════════════════════════════════════════

class ImageFeatureExtractor:
    """提取轻量级图片特征用于 RL 策略网络

    无需 GPU — 基于 PIL + numpy 的统计特征:
      - LAB 色彩空间直方图 (8D): 肤色分布 + 白斑对比度
      - 边缘密度 (2D): 白斑边界清晰度
      - 纹理均匀性 (3D): 白斑内部一致性
      - 几何特征 (3D): 斑块大小、位置、分散度
    """

    def __init__(self, target_dim: int = 16):
        self.target_dim = target_dim

    def extract(self, image_bytes: bytes) -> Optional[np.ndarray]:
        """从图片二进制数据提取特征向量

        Returns:
            np.ndarray shape (16,) or None on failure
        """
        try:
            from PIL import Image, ImageFilter, ImageStat
        except ImportError:
            logger.warning("PIL not available for feature extraction")
            return None

        try:
            img = Image.open(BytesIO(image_bytes)).convert("RGB")
            w, h = img.size

            # Resize for consistent feature extraction (max 512px)
            max_dim = max(w, h)
            if max_dim > 512:
                scale = 512.0 / max_dim
                img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

            features = []

            # ── LAB Color Features (8D) ────────────────────────────
            lab_img = img.convert("LAB" if hasattr(Image, 'LAB') else "RGB")
            try:
                # Use numpy for LAB conversion
                rgb_arr = np.array(img, dtype=np.float32) / 255.0
                lab_arr = self._rgb_to_lab(rgb_arr)
            except Exception:
                # Fallback to simple RGB histograms
                lab_arr = np.array(img, dtype=np.float32) / 255.0

            # L* channel statistics
            l_channel = lab_arr[:, :, 0]
            features.append(float(np.mean(l_channel)))  # mean brightness
            features.append(float(np.std(l_channel)))    # brightness variance
            features.append(float(np.percentile(l_channel, 10)))  # dark areas
            features.append(float(np.percentile(l_channel, 90)))  # bright areas (lesion)

            # a* / b* or R/G/B channel stats
            if lab_arr.shape[2] >= 3:
                a_channel = lab_arr[:, :, 1]
                b_channel = lab_arr[:, :, 2]
                features.append(float(np.mean(a_channel)))  # redness
                features.append(float(np.std(a_channel)))
                features.append(float(np.mean(b_channel)))  # yellowness
                features.append(float(np.std(b_channel)))
            else:
                features.extend([0.0, 0.0, 0.0, 0.0])

            # ── Edge Density (2D) ──────────────────────────────────
            gray = np.array(img.convert("L"), dtype=np.float32)
            # Simple Sobel-like edge detection
            gx = np.zeros_like(gray)
            gy = np.zeros_like(gray)
            gx[:, 1:-1] = gray[:, 2:] - gray[:, :-2]
            gy[1:-1, :] = gray[2:, :] - gray[:-2, :]
            edge_mag = np.sqrt(gx**2 + gy**2)
            features.append(float(np.mean(edge_mag)))     # mean edge strength
            features.append(float(np.percentile(edge_mag, 95)))  # strong edge density

            # ── Texture Uniformity (3D) ────────────────────────────
            # Local variance as texture measure
            local_var = np.zeros_like(gray)
            patch = 5
            for i in range(patch, gray.shape[0] - patch):
                for j in range(patch, gray.shape[1] - patch):
                    local_var[i, j] = np.var(gray[i-patch:i+patch+1, j-patch:j+patch+1])
            features.append(float(np.mean(local_var)))    # mean texture roughness
            features.append(float(np.std(local_var)))     # texture variation
            features.append(float(np.percentile(local_var, 90)))  # high-texture areas

            # ── Geometric Features (3D) ────────────────────────────
            aspect_ratio = max(w, h) / (min(w, h) + 1)
            features.append(math.log(aspect_ratio + 1))   # aspect ratio
            features.append(math.log(w * h) / 15.0)        # image area (log scale)
            # Blur estimate (Laplacian variance)
            laplacian = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float32)
            lap_h, lap_w = gray.shape
            lap_var = 0.0
            if lap_h >= 3 and lap_w >= 3:
                conv = np.zeros_like(gray)
                for i in range(1, lap_h - 1):
                    for j in range(1, lap_w - 1):
                        conv[i, j] = np.sum(gray[i-1:i+2, j-1:j+2] * laplacian)
                lap_var = float(np.var(conv))
            features.append(min(lap_var / 500.0, 1.0))    # normalized blur score

            # Pad/truncate to target_dim
            features = features[:self.target_dim]
            while len(features) < self.target_dim:
                features.append(0.0)

            arr = np.array(features, dtype=np.float32)
            # Normalize to [0, 1] range per feature
            arr = np.clip(arr, -3.0, 3.0) / 3.0
            arr = (arr + 1.0) / 2.0  # shift to [0, 1]

            return arr

        except Exception as e:
            logger.warning("Feature extraction failed: %s", e)
            return None

    @staticmethod
    def _rgb_to_lab(rgb: np.ndarray) -> np.ndarray:
        """RGB to CIELAB conversion (simplified for feature extraction)"""
        # Linearize
        rgb = np.clip(rgb, 0.001, 1.0)
        # RGB to XYZ (sRGB D65)
        mask = rgb > 0.04045
        rgb_lin = np.where(mask, ((rgb + 0.055) / 1.055) ** 2.4, rgb / 12.92)
        xyz = np.zeros_like(rgb)
        xyz[:, :, 0] = 0.4124 * rgb_lin[:, :, 0] + 0.3576 * rgb_lin[:, :, 1] + 0.1805 * rgb_lin[:, :, 2]
        xyz[:, :, 1] = 0.2126 * rgb_lin[:, :, 0] + 0.7152 * rgb_lin[:, :, 1] + 0.0722 * rgb_lin[:, :, 2]
        xyz[:, :, 2] = 0.0193 * rgb_lin[:, :, 0] + 0.1192 * rgb_lin[:, :, 1] + 0.9505 * rgb_lin[:, :, 2]
        # XYZ to Lab
        xn, yn, zn = 0.95047, 1.0, 1.08883
        f = np.where(xyz > 0.008856, xyz ** (1.0 / 3.0), 7.787 * xyz + 16.0 / 116.0)
        fx, fy, fz = f[:, :, 0], f[:, :, 1], f[:, :, 2]
        lab = np.zeros_like(xyz)
        lab[:, :, 0] = 116.0 * fy - 16.0
        lab[:, :, 1] = 500.0 * (fx - fy)
        lab[:, :, 2] = 200.0 * (fy - fz)
        return lab / 100.0  # normalize to ~[-1, 1] range


# ═══════════════════════════════════════════════════════════════════
# Standard Pipeline Parameters
# ═══════════════════════════════════════════════════════════════════

PIPELINE_PARAM_SPEC = {
    # SAM segmentation params
    "pred_iou_thresh":         {"min": 0.70, "max": 0.95, "default": 0.88},
    "stability_score_thresh":  {"min": 0.70, "max": 0.95, "default": 0.88},
    "points_per_side":         {"min": 16,   "max": 64,   "default": 32},
    # Color-based detection params
    "color_threshold":         {"min": 0.05, "max": 0.30, "default": 0.15},
    # Preprocessing params
    "blur_kernel":             {"min": 3,    "max": 15,   "default": 5},
    "morph_close_size":        {"min": 3,    "max": 11,   "default": 5},
    # Postprocessing params
    "min_lesion_area_ratio":   {"min": 0.001, "max": 0.05, "default": 0.005},
    "skin_expand_px":          {"min": 0,    "max": 20,   "default": 10},
}

PARAM_NAMES = list(PIPELINE_PARAM_SPEC.keys())
N_PARAMS = len(PARAM_NAMES)

def normalize_params(params: Dict[str, float]) -> np.ndarray:
    """Normalize pipeline params to [0, 1] range"""
    arr = np.zeros(N_PARAMS, dtype=np.float32)
    for i, name in enumerate(PARAM_NAMES):
        spec = PIPELINE_PARAM_SPEC[name]
        val = params.get(name, spec["default"])
        arr[i] = (val - spec["min"]) / (spec["max"] - spec["min"])
    return arr

def denormalize_params(norm_vec: np.ndarray) -> Dict[str, float]:
    """Denormalize [0,1] vector back to param space"""
    params = {}
    for i, name in enumerate(PARAM_NAMES):
        spec = PIPELINE_PARAM_SPEC[name]
        val = norm_vec[i] * (spec["max"] - spec["min"]) + spec["min"]
        # Round discrete params
        if name in ("points_per_side", "blur_kernel", "morph_close_size", "skin_expand_px"):
            val = round(val)
        params[name] = val
    return params

def get_default_params() -> Dict[str, float]:
    return {name: spec["default"] for name, spec in PIPELINE_PARAM_SPEC.items()}


# ═══════════════════════════════════════════════════════════════════
# Contextual Bandit Policy Network
# ═══════════════════════════════════════════════════════════════════

class ContextualBanditPolicy:
    """2-layer MLP 策略网络 — 纯 NumPy 实现

    Architecture:
        Input: 16 (image features) + 8 (pipeline params) = 24
        Hidden1: 32 neurons, tanh
        Hidden2: 16 neurons, tanh
        Output: 1, sigmoid → predicted Dice score

    Total: 1,345 parameters — 推理 <0.1ms on CPU
    """

    def __init__(self, feature_dim: int = 16, param_dim: int = N_PARAMS):
        self.f_dim = feature_dim
        self.p_dim = param_dim
        self.input_dim = feature_dim + param_dim
        self.h1_dim = 32
        self.h2_dim = 16
        self.output_dim = 1

        # He initialization
        rng = np.random.RandomState(42)
        self.W1 = rng.randn(self.input_dim, self.h1_dim) * np.sqrt(2.0 / self.input_dim)
        self.b1 = np.zeros(self.h1_dim)
        self.W2 = rng.randn(self.h1_dim, self.h2_dim) * np.sqrt(2.0 / self.h1_dim)
        self.b2 = np.zeros(self.h2_dim)
        self.W3 = rng.randn(self.h2_dim, self.output_dim) * np.sqrt(2.0 / self.h2_dim)
        self.b3 = np.zeros(self.output_dim)

        # Training metadata
        self.total_updates = 0
        self.cumulative_loss = 0.0
        self.last_updated = None

    def forward(self, features: np.ndarray, params: np.ndarray) -> Tuple[float, List[np.ndarray]]:
        """前向传播 — 预测 Dice score

        Returns:
            (predicted_dice, cache_for_backward)
        """
        x = np.concatenate([features, params])  # (24,)

        z1 = np.dot(x, self.W1) + self.b1       # (32,)
        a1 = np.tanh(z1)

        z2 = np.dot(a1, self.W2) + self.b2       # (16,)
        a2 = np.tanh(z2)

        z3 = np.dot(a2, self.W3) + self.b3       # (1,)
        y = 1.0 / (1.0 + np.exp(-z3[0]))         # sigmoid

        cache = [x, z1, a1, z2, a2, z3, y]
        return float(np.clip(y, 0.001, 0.999)), cache

    def predict(self, features: np.ndarray, params: np.ndarray) -> float:
        """Quick inference without caching (for production use)"""
        pred, _ = self.forward(features, params)
        return pred

    def backward(
        self, cache: List[np.ndarray], actual_dice: float, learning_rate: float = 1e-3
    ) -> float:
        """单样本反向传播 — MSE loss"""
        x, z1, a1, z2, a2, z3, y = cache

        # MSE gradient at output
        dy = -2.0 * (actual_dice - y) * y * (1.0 - y)  # scalar

        # Layer 3
        dW3 = np.outer(a2, dy)
        db3 = np.array([dy])

        # Layer 2
        da2 = dy * self.W3.flatten()
        dz2 = da2 * (1.0 - a2**2)
        dW2 = np.outer(a1, dz2)
        db2 = dz2.copy()

        # Layer 1
        da1 = np.dot(self.W2, dz2)
        dz1 = da1 * (1.0 - a1**2)
        dW1 = np.outer(x, dz1)
        db1 = dz1.copy()

        # Gradient descent
        self.W1 -= learning_rate * dW1
        self.b1 -= learning_rate * db1
        self.W2 -= learning_rate * dW2
        self.b2 -= learning_rate * db2
        self.W3 -= learning_rate * dW3
        self.b3 -= learning_rate * db3

        self.total_updates += 1
        loss = (actual_dice - y) ** 2
        self.cumulative_loss += loss
        return float(loss)

    def optimize_params(
        self, features: np.ndarray, n_trials: int = 20, exploration_std: float = 0.05
    ) -> Tuple[Dict[str, float], float]:
        """搜索最优 pipeline 参数: 从默认参数出发，用贪心+探索逼近最优

        Args:
            features: image feature vector
            n_trials: 尝试次数
            exploration_std: 探索噪声标准差

        Returns:
            (best_params_dict, predicted_dice)
        """
        best_params = get_default_params()
        best_norm = normalize_params(best_params)
        best_score = self.predict(features, best_norm)

        rng = np.random.RandomState()

        for _ in range(n_trials):
            # Add Gaussian noise for exploration
            noise = rng.randn(N_PARAMS) * exploration_std
            candidate = np.clip(best_norm + noise, 0.0, 1.0)
            score = self.predict(features, candidate)

            if score > best_score:
                best_score = score
                best_norm = candidate

        return denormalize_params(best_norm), best_score

    def save(self, filepath: str = STATE_FILE) -> None:
        """Save policy weights to JSON"""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        state = {
            "W1": self.W1.tolist(),
            "b1": self.b1.tolist(),
            "W2": self.W2.tolist(),
            "b2": self.b2.tolist(),
            "W3": self.W3.tolist(),
            "b3": self.b3.tolist(),
            "total_updates": self.total_updates,
            "cumulative_loss": self.cumulative_loss,
            "last_updated": datetime.utcnow().isoformat(),
            "architecture": {
                "input_dim": self.input_dim,
                "h1_dim": self.h1_dim,
                "h2_dim": self.h2_dim,
                "output_dim": self.output_dim,
            },
        }
        with open(filepath, "w") as f:
            json.dump(state, f)
        logger.info(
            "Policy saved: %d updates, avg_loss=%.6f",
            self.total_updates,
            self.cumulative_loss / max(self.total_updates, 1),
        )

    @classmethod
    def load(cls, filepath: str = STATE_FILE) -> "ContextualBanditPolicy":
        """Load policy weights from JSON, or initialize fresh"""
        policy = cls()
        if not os.path.exists(filepath):
            logger.info("No saved policy found, initializing fresh")
            return policy

        try:
            with open(filepath) as f:
                state = json.load(f)

            policy.W1 = np.array(state["W1"], dtype=np.float32)
            policy.b1 = np.array(state["b1"], dtype=np.float32)
            policy.W2 = np.array(state["W2"], dtype=np.float32)
            policy.b2 = np.array(state["b2"], dtype=np.float32)
            policy.W3 = np.array(state["W3"], dtype=np.float32)
            policy.b3 = np.array(state["b3"], dtype=np.float32)
            policy.total_updates = state.get("total_updates", 0)
            policy.cumulative_loss = state.get("cumulative_loss", 0.0)
            policy.last_updated = state.get("last_updated")

            logger.info(
                "Policy loaded: %d updates, avg_loss=%.6f",
                policy.total_updates,
                policy.cumulative_loss / max(policy.total_updates, 1),
            )
            return policy

        except Exception as e:
            logger.warning("Failed to load policy: %s, reinitializing", e)
            return cls()


# ═══════════════════════════════════════════════════════════════════
# Online Learner — 从用户修正中持续学习
# ═══════════════════════════════════════════════════════════════════

class OnlineLearner:
    """在线学习器 — 累积用户修正数据并定期更新策略网络

    工作流:
      1. record_correction() — 记录每次用户修正
      2. 每 N 条累积自动触发 train_batch()
      3. 模型权重持久化到磁盘
    """

    def __init__(
        self,
        policy: ContextualBanditPolicy,
        extractor: ImageFeatureExtractor,
        buffer_max_size: int = 1000,
        train_every_n: int = 10,
        learning_rate: float = 1e-3,
    ):
        self.policy = policy
        self.extractor = extractor
        self.buffer_max_size = buffer_max_size
        self.train_every_n = train_every_n
        self.learning_rate = learning_rate

        # Training buffer: [(features_vec, params_vec, actual_dice), ...]
        self.buffer: List[Tuple[np.ndarray, np.ndarray, float]] = []
        self.corrections_since_train = 0

        # Load buffer from disk
        self._load_buffer()

    def record_correction(
        self,
        image_bytes: bytes,
        pipeline_params: Optional[Dict[str, float]],
        actual_dice: float,
    ) -> bool:
        """记录一次用户修正（图片 → 参数 → Dice score）

        Args:
            image_bytes: 原始图片二进制
            pipeline_params: 本次评估使用的 pipeline 参数
            actual_dice: 用户修正后的真实 Dice score

        Returns:
            True 如果触发了训练
        """
        features = self.extractor.extract(image_bytes)
        if features is None:
            return False

        params = normalize_params(pipeline_params or get_default_params())

        # Add to buffer
        self.buffer.append((features, params, actual_dice))
        if len(self.buffer) > self.buffer_max_size:
            self.buffer.pop(0)

        self.corrections_since_train += 1

        # Trigger training?
        if self.corrections_since_train >= self.train_every_n and len(self.buffer) >= 5:
            self.train_batch()
            self.corrections_since_train = 0
            self._save_buffer()
            self.policy.save()
            return True

        return False

    def train_batch(self, epochs: int = 3) -> float:
        """Batch training on all buffered samples

        Returns:
            Average loss over the epoch
        """
        if not self.buffer:
            return 0.0

        total_loss = 0.0
        n = len(self.buffer)

        for _ in range(epochs):
            epoch_loss = 0.0
            # Shuffle buffer
            indices = list(range(n))
            np.random.shuffle(indices)

            for idx in indices:
                features, params, actual_dice = self.buffer[idx]
                _, cache = self.policy.forward(features, params)
                loss = self.policy.backward(cache, actual_dice, self.learning_rate)
                epoch_loss += loss

            total_loss += epoch_loss / n

        avg_loss = total_loss / epochs
        logger.info(
            "Online training: %d samples, avg_loss=%.6f, total_updates=%d",
            n, avg_loss, self.policy.total_updates,
        )
        return avg_loss

    def suggest_params(
        self, image_bytes: bytes, n_trials: int = 20
    ) -> Tuple[Dict[str, float], float]:
        """根据图片特征推荐最优 pipeline 参数

        Args:
            image_bytes: 图片二进制
            n_trials: 优化尝试次数

        Returns:
            (params_dict, predicted_dice_score)
        """
        features = self.extractor.extract(image_bytes)
        if features is None:
            return get_default_params(), 0.5

        return self.policy.optimize_params(features, n_trials=n_trials)

    def _save_buffer(self) -> None:
        """Persist training buffer to disk"""
        os.makedirs(STATE_DIR, exist_ok=True)
        try:
            with open(BUFFER_FILE, "w") as f:
                for features, params, actual_dice in self.buffer:
                    record = {
                        "features": features.tolist(),
                        "params": params.tolist(),
                        "actual_dice": actual_dice,
                    }
                    f.write(json.dumps(record) + "\n")
        except Exception as e:
            logger.warning("Failed to save buffer: %s", e)

    def _load_buffer(self) -> None:
        """Load training buffer from disk"""
        if not os.path.exists(BUFFER_FILE):
            return
        try:
            with open(BUFFER_FILE) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                        features = np.array(rec["features"], dtype=np.float32)
                        params = np.array(rec["params"], dtype=np.float32)
                        actual_dice = float(rec["actual_dice"])
                        self.buffer.append((features, params, actual_dice))
                    except (json.JSONDecodeError, KeyError):
                        continue
            # Trim to max size
            if len(self.buffer) > self.buffer_max_size:
                self.buffer = self.buffer[-self.buffer_max_size:]
            logger.info("Loaded %d training samples from buffer", len(self.buffer))
        except Exception as e:
            logger.warning("Failed to load buffer: %s", e)


# ═══════════════════════════════════════════════════════════════════
# Singleton accessor
# ═══════════════════════════════════════════════════════════════════

_learner: Optional[OnlineLearner] = None


def get_rl_learner() -> OnlineLearner:
    """获取全局 OnlineLearner 单例（懒加载）"""
    global _learner
    if _learner is None:
        policy = ContextualBanditPolicy.load()
        extractor = ImageFeatureExtractor()
        _learner = OnlineLearner(
            policy=policy,
            extractor=extractor,
            buffer_max_size=1000,
            train_every_n=10,
            learning_rate=1e-3,
        )
        logger.info("RL Learner initialized: %d historical updates", policy.total_updates)
    return _learner


def reset_rl_learner() -> None:
    """重置 RL 学习器（测试/调试用）"""
    global _learner
    _learner = None
    logger.info("RL learner reset")

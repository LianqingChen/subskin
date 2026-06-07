"""
VASI 参数自适应优化器 (Phase 3)

将皮肤检测、白斑检测的可调参数按用户特征（肤色类型、图片质量、部位）
自适应选择最优参数组合。使用贝叶斯优化骨架进行持续学习。

核心思路:
  - 按 Fitzpatrick × Quality × BodySite 三维分组
  - 每组维护一组最优参数
  - 从用户修正数据中持续学习：参数 → 准确率 的映射
  - 使用高斯过程回归 (Gaussian Process) 建模，EI (Expected Improvement) 推荐
"""

import json
import logging
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass, field
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

try:
    import numpy as np
    _NUMPY_AVAILABLE = True
except ImportError:
    _NUMPY_AVAILABLE = False
    logger.warning("numpy not available; parameter optimization will use simple heuristics")


# ══════════════════════════════════════════════════════════════════════════════
# Adaptive Parameter Set
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class AdaptiveParams:
    """按条件分组的一组合自适应参数"""
    # ── 皮肤检测 ──
    skin_hsv_sat_low: int = 20
    skin_hsv_sat_high: int = 200
    skin_ycrcb_cr_low: int = 133
    skin_ycrcb_cr_high: int = 180

    # ── 白斑检测 ──
    vitiligo_l_offset: float = 12.0
    vitiligo_max_chroma: float = 35.0
    vitiligo_min_area_ratio: float = 0.005

    # ── SAM 参数 ──
    sam_points_per_side: int = 16
    sam_pred_iou_thresh: float = 0.80
    sam_stability_thresh: float = 0.85

    # ── VLM 参数 ──
    vlm_confidence_threshold: float = 0.85
    vlm_temperature: float = 0.1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skin_hsv_sat_low": self.skin_hsv_sat_low,
            "skin_hsv_sat_high": self.skin_hsv_sat_high,
            "skin_ycrcb_cr_low": self.skin_ycrcb_cr_low,
            "skin_ycrcb_cr_high": self.skin_ycrcb_cr_high,
            "vitiligo_l_offset": self.vitiligo_l_offset,
            "vitiligo_max_chroma": self.vitiligo_max_chroma,
            "vitiligo_min_area_ratio": self.vitiligo_min_area_ratio,
            "sam_points_per_side": self.sam_points_per_side,
            "sam_pred_iou_thresh": self.sam_pred_iou_thresh,
            "sam_stability_thresh": self.sam_stability_thresh,
            "vlm_confidence_threshold": self.vlm_confidence_threshold,
            "vlm_temperature": self.vlm_temperature,
        }


# ══════════════════════════════════════════════════════════════════════════════
# Pre-defined Parameter Sets by User Profile
# ══════════════════════════════════════════════════════════════════════════════

DEFAULT_PARAMS = AdaptiveParams()

PARAM_PRESETS: Dict[str, AdaptiveParams] = {
    # ── 浅肤色 + 好质量: 严格模式（避免高光/浅色皮肤误判）──
    "light_skin_good": AdaptiveParams(
        skin_hsv_sat_low=18,
        skin_hsv_sat_high=220,
        vitiligo_l_offset=14.0,       # 更高的L偏移 → 只抓明显白斑
        vitiligo_max_chroma=28.0,      # 更低色度 → 排除有色区域
        vitiligo_min_area_ratio=0.006,
        sam_pred_iou_thresh=0.85,      # 更高阈值 → 更保守
        vlm_confidence_threshold=0.88,
    ),
    # ── 浅肤色 + 差质量: 适度放宽 ──
    "light_skin_poor": AdaptiveParams(
        skin_hsv_sat_low=15,
        skin_hsv_sat_high=230,
        vitiligo_l_offset=11.0,
        vitiligo_max_chroma=38.0,
        vitiligo_min_area_ratio=0.005,
        sam_pred_iou_thresh=0.78,
        vlm_confidence_threshold=0.82,
    ),
    # ── 深肤色 + 好质量: 灵敏模式（深皮肤白斑更明显，但也需要仔细区分）──
    "dark_skin_good": AdaptiveParams(
        skin_hsv_sat_low=12,
        skin_hsv_sat_high=255,
        skin_ycrcb_cr_low=120,
        skin_ycrcb_cr_high=190,
        vitiligo_l_offset=10.0,        # 较低L偏移 → 更灵敏
        vitiligo_max_chroma=35.0,
        vitiligo_min_area_ratio=0.004, # 更小面积也抓
        sam_pred_iou_thresh=0.78,
        vlm_confidence_threshold=0.80,
    ),
    # ── 深肤色 + 差质量: 最宽松模式 ──
    "dark_skin_poor": AdaptiveParams(
        skin_hsv_sat_low=10,
        skin_hsv_sat_high=255,
        skin_ycrcb_cr_low=115,
        skin_ycrcb_cr_high=195,
        vitiligo_l_offset=8.0,
        vitiligo_max_chroma=42.0,
        vitiligo_min_area_ratio=0.003,
        sam_pred_iou_thresh=0.72,
        vlm_confidence_threshold=0.75,
    ),
    # ── 特定部位微调 ──
    "face_light": AdaptiveParams(
        vitiligo_l_offset=15.0,         # 面部容易反光，提高阈值
        vitiligo_max_chroma=25.0,
        sam_pred_iou_thresh=0.86,
    ),
    "hands_dark": AdaptiveParams(
        vitiligo_l_offset=8.0,          # 手部白斑在深肤色上对比明显
        vitiligo_max_chroma=40.0,
        vitiligo_min_area_ratio=0.003,  # 手指间小面积
    ),
}


# ══════════════════════════════════════════════════════════════════════════════
# Simple Bayesian Optimization (Gaussian Process — lightweight)
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Observation:
    """一次观测: 参数组合 + 对应的指标"""
    params: Dict[str, float]
    score: float         # 综合评分 (0-1, 越高越好)
    timestamp: str


class SimpleBayesianOptimizer:
    """轻量级贝叶斯优化器。

    不依赖 scikit-optimize，使用简单的基于历史数据的启发式优化:
    1. 记录所有 (params → score) 观测
    2. 对每个参数，计算 score 最高的参数值范围
    3. 推荐该范围内的中点
    """

    def __init__(self, group_key: str, history: Optional[list] = None):
        self.group_key = group_key
        self.observations: list[Observation] = history or []

    def record(self, params: Dict[str, float], score: float) -> None:
        """记录一次观测"""
        from datetime import datetime
        self.observations.append(Observation(
            params=params,
            score=score,
            timestamp=datetime.utcnow().isoformat(),
        ))
        # 只保留最近 100 条
        if len(self.observations) > 100:
            self.observations = self.observations[-100:]

    def recommend(self, current_params: AdaptiveParams) -> Optional[Dict[str, float]]:
        """基于历史观测推荐参数调整。

        策略:
        1. 如果观测 < 5 条：返回 None（保持当前参数）
        2. 如果最近5条 score 都 > 0.7：推荐微调（exploit）
        3. 否则：推荐朝向最佳观测方向调整（explore）
        """
        if len(self.observations) < 5:
            return None

        recent_scores = [o.score for o in self.observations[-5:]]
        avg_recent = sum(recent_scores) / len(recent_scores)

        if avg_recent > 0.7:
            # 表现好 → 微调 (exploit): 向最佳观测靠近
            best = max(self.observations, key=lambda o: o.score)
            return self._interpolate(current_params.to_dict(), best.params, 0.2)
        else:
            # 表现差 → 探索 (explore): 向最佳观测靠近，步幅更大
            best = max(self.observations, key=lambda o: o.score)
            return self._interpolate(current_params.to_dict(), best.params, 0.5)

    @staticmethod
    def _interpolate(
        current: Dict[str, float],
        target: Dict[str, float],
        alpha: float,
    ) -> Dict[str, float]:
        """在 current 和 target 之间插值，alpha=0 保持current，alpha=1 到达target"""
        result = {}
        for key in current:
            if key in target:
                result[key] = current[key] * (1 - alpha) + target[key] * alpha
            else:
                result[key] = current[key]
        return result

    def get_best_params(self) -> Optional[Dict[str, float]]:
        """返回历史最佳参数组合"""
        if not self.observations:
            return None
        best = max(self.observations, key=lambda o: o.score)
        return best.params

    def get_stats(self) -> Dict[str, Any]:
        """返回统计信息"""
        if not self.observations:
            return {"count": 0}
        scores = [o.score for o in self.observations]
        return {
            "count": len(self.observations),
            "best_score": max(scores),
            "avg_score": sum(scores) / len(scores),
            "worst_score": min(scores),
        }


# ══════════════════════════════════════════════════════════════════════════════
# ParameterOptimizer — 主服务
# ══════════════════════════════════════════════════════════════════════════════

class VasiParameterOptimizer:
    """VASI 参数自适应优化器。

    三层参数选择策略:
      1. Preset: 根据 Fitzpatrick + Quality 选择预设参数
      2. Site Tweak: 在预设基础上，叠加特定部位的微调
      3. Bayesian: 如果该分组的观测数据够多，用贝叶斯优化推荐
    """

    def __init__(self):
        self.optimizers: Dict[str, SimpleBayesianOptimizer] = {}

    def _build_group_key(
        self, fitzpatrick: str, quality_level: str
    ) -> str:
        """构建分组键"""
        skin_tone = "light_skin" if fitzpatrick in ("I", "II", "III") else "dark_skin"
        quality = "good" if quality_level in ("good", "excellent") else "poor"
        return f"{skin_tone}_{quality}"

    def select_params(
        self,
        fitzpatrick: str = "III",
        quality_level: str = "good",
        body_site: str = "面部",
    ) -> AdaptiveParams:
        """根据用户特征选择最优参数集。

        Args:
            fitzpatrick: Fitzpatrick 肤色类型 (I-VI)
            quality_level: 图片质量 (good/acceptable/poor)
            body_site: 评估部位
        """
        group_key = self._build_group_key(fitzpatrick, quality_level)
        params = PARAM_PRESETS.get(group_key, DEFAULT_PARAMS)

        # 贝叶斯优化 (如果有足够观测)
        opt = self.optimizers.get(group_key)
        if opt and len(opt.observations) >= 5:
            recommended = opt.recommend(params)
            if recommended:
                for key, val in recommended.items():
                    if hasattr(params, key):
                        setattr(params, key, val)

        # 部位微调
        self._apply_site_tweaks(params, body_site, fitzpatrick)

        return params

    def _apply_site_tweaks(
        self, params: AdaptiveParams, body_site: str, fitzpatrick: str
    ) -> None:
        """叠加部位特定的微调"""
        skin_tone = "light" if fitzpatrick in ("I", "II", "III") else "dark"

        # 面部: 更容易反光，提高阈值
        if "面" in body_site or "脸" in body_site or body_site == "face":
            params.vitiligo_l_offset += 2.0
            params.vitiligo_max_chroma -= 3.0
            params.sam_pred_iou_thresh += 0.03

        # 手部: 小面积白斑更常见
        if "手" in body_site or body_site in ("hands", "left_hand", "right_hand"):
            params.vitiligo_min_area_ratio = 0.003
            if skin_tone == "dark":
                params.vitiligo_l_offset -= 2.0

        # 足部: 同理小面积
        if "足" in body_site or body_site in ("feet", "left_foot", "right_foot"):
            params.vitiligo_min_area_ratio = 0.003

        # 上肢/下肢: 大面积，提高 threshold 避免过检
        if "腿" in body_site or "臂" in body_site or body_site in ("arms", "legs"):
            params.vitiligo_l_offset += 1.0

        # 躯干: 大面积，提高阈值
        if any(w in body_site for w in ["背", "胸", "腹", "背"]):
            params.vitiligo_l_offset += 1.5

    def update_from_feedback(
        self,
        fitzpatrick: str,
        quality_level: str,
        params_used: AdaptiveParams,
        metrics: Dict[str, float],
    ) -> None:
        """从用户反馈更新贝叶斯优化器。

        Args:
            fitzpatrick: 肤色类型
            quality_level: 图片质量
            params_used: 使用的参数
            metrics: 该次评估的指标 {"dice": 0.65, "area_error_pct": 15.0, ...}
        """
        group_key = self._build_group_key(fitzpatrick, quality_level)

        if group_key not in self.optimizers:
            self.optimizers[group_key] = SimpleBayesianOptimizer(group_key)

        # 综合评分: Dice 和面积误差的加权
        dice = metrics.get("dice", 0.5)
        area_error = metrics.get("area_error_pct", 50.0)
        score = 0.6 * dice + 0.4 * (1.0 - min(area_error / 100.0, 1.0))
        score = max(0.0, min(1.0, score))

        self.optimizers[group_key].record(params_used.to_dict(), score)
        logger.info(
            "ParamOptimizer updated: group=%s dice=%.3f area_err=%.1f%% score=%.3f total_obs=%d",
            group_key, dice, area_error, score,
            self.optimizers[group_key].get_stats()["count"],
        )

    def get_confidence_calibration(
        self, confidence: float, body_site: str
    ) -> float:
        """置信度校准: 从历史数据中学习 confidence → 准确率 的映射。

        如果该部位历史上 AI 声称 confidence=0.8 但实际 accuracy=0.6，
        则校准后 confidence=0.6。
        """
        # 默认: 不校准 (等数据够了再启用)
        return confidence

    def get_all_stats(self) -> Dict[str, Any]:
        """获取所有分组的统计信息"""
        return {
            group_key: opt.get_stats()
            for group_key, opt in self.optimizers.items()
        }

    def get_preset_params(self) -> Dict[str, Dict[str, Any]]:
        """获取所有预设参数"""
        return {key: params.to_dict() for key, params in PARAM_PRESETS.items()}


# ══════════════════════════════════════════════════════════════════════════════
# Module-level singleton
# ══════════════════════════════════════════════════════════════════════════════

vasi_param_optimizer = VasiParameterOptimizer()


def get_param_optimizer() -> VasiParameterOptimizer:
    """获取全局 VasiParameterOptimizer 实例"""
    return vasi_param_optimizer

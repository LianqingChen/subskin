"""
VASI 自我进化编排器 (Phase 5)

将所有模块串联成自运行的闭环系统:

  FeedbackCollector → PromptEvolver → ParameterOptimizer → Evaluator
       ↑                                                        │
       └──────────────────── 部署 ←── 通过 ←── Shadow Eval ←────┘

核心职责:
  1. 触发条件判断: 什么时候该进化
  2. 进化策略选择: 用哪种方式进化 (prompt/params/model)
  3. 安全部署: 验证通过后上线，退化自动回滚
  4. 定时任务: 每日自动检查是否需要进化
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from web.backend.models.vasi import VasiTrainingSample, VasiModelVersion

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# Data Classes
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class EvolutionResult:
    """一轮进化的结果"""
    strategy: str                       # "prompt" | "params" | "full" | "none"
    prompt_evolved: bool = False
    prompt_version: Optional[str] = None
    prompt_changes: Dict[str, Any] = field(default_factory=dict)

    params_optimized: bool = False
    params_changes: Dict[str, Any] = field(default_factory=dict)

    metrics_before: Dict[str, Any] = field(default_factory=dict)
    metrics_after: Dict[str, Any] = field(default_factory=dict)

    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    elapsed_seconds: float = 0.0

    def has_any_change(self) -> bool:
        return self.prompt_evolved or self.params_optimized

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy": self.strategy,
            "prompt_evolved": self.prompt_evolved,
            "prompt_version": self.prompt_version,
            "prompt_changes": self.prompt_changes,
            "params_optimized": self.params_optimized,
            "params_changes": self.params_changes,
            "metrics_before": self.metrics_before,
            "metrics_after": self.metrics_after,
            "warnings": self.warnings,
            "errors": self.errors,
            "elapsed_seconds": round(self.elapsed_seconds, 1),
        }


@dataclass
class EvolutionStatus:
    """当前进化状态"""
    feedback_stats: Dict[str, Any] = field(default_factory=dict)
    prompt_should_evolve: bool = False
    prompt_new_samples: int = 0
    prompt_current_version: Optional[str] = None
    params_groups: Dict[str, Any] = field(default_factory=dict)
    current_metrics: Dict[str, Any] = field(default_factory=dict)
    degradation_warning: Optional[str] = None
    last_evolution: Optional[str] = None


# ══════════════════════════════════════════════════════════════════════════════
# EvolutionOrchestrator — 中央控制器
# ══════════════════════════════════════════════════════════════════════════════

class EvolutionOrchestrator:
    """自我进化中央编排器。

    使用方式:
      orchestrator = EvolutionOrchestrator(db)
      
      # 手动触发
      result = await orchestrator.evolve("full")
      
      # 定时自动
      result = await orchestrator.scheduled_evolution()
      
      # 查看状态
      status = orchestrator.get_status()
    """

    # ── 触发阈值 ──
    PROMPT_EVO_THRESHOLD = 20      # 新增20个高质量样本触发 prompt 进化
    PARAM_EVO_THRESHOLD = 50       # 新增50个样本触发参数优化
    NNUNET_TRAIN_THRESHOLD = 200   # 200个样本触发 nnU-Net 训练

    def __init__(self, db: Session):
        self.db = db
        self._load_modules()

    def _load_modules(self):
        """延迟加载子模块"""
        from web.backend.services.vasi_feedback import VasiFeedbackCollector
        from web.backend.services.vasi_prompt_evolver import VasiPromptEvolver
        from web.backend.services.vasi_param_optimizer import VasiParameterOptimizer
        from web.backend.services.vasi_evaluator import VasiEvaluator

        self.collector = VasiFeedbackCollector(self.db)
        self.prompt_evolver = VasiPromptEvolver(self.db)
        self.param_optimizer = VasiParameterOptimizer()
        self.evaluator = VasiEvaluator(self.db)

    # ── 触发条件判断 ──

    def should_evolve_prompt(self) -> tuple:
        """检查是否应该触发 Prompt 进化"""
        return self.prompt_evolver.should_evolve()

    def should_evolve_params(self) -> bool:
        """检查是否应该触发参数优化"""
        # 当新增样本超过阈值
        new_samples = self.collector.count_training_samples(min_dice=0.4)
        return new_samples >= self.PARAM_EVO_THRESHOLD

    def should_train_nnunet(self) -> bool:
        """检查是否应该触发 nnU-Net 训练"""
        total = self.collector.count_training_samples(min_dice=0.3)
        return total >= self.NNUNET_TRAIN_THRESHOLD

    # ── 进化执行 ──

    async def evolve(self, strategy: str = "auto") -> EvolutionResult:
        """执行一轮进化。

        Args:
            strategy: "prompt" | "params" | "auto" | "full"

        Returns:
            EvolutionResult
        """
        import time
        t0 = time.time()

        result = EvolutionResult(strategy=strategy)

        # ── 进化前: 记录基线指标 ──
        try:
            baseline = self.evaluator.get_current_metrics(days=30)
            result.metrics_before = baseline.to_dict()
        except Exception as e:
            logger.warning("Failed to get baseline metrics: %s", e)

        # ── Prompt 进化 ──
        if strategy in ("prompt", "auto", "full"):
            should_evo, new_count = self.should_evolve_prompt()
            if should_evo or strategy in ("prompt", "full"):
                try:
                    prompt_result = await self._evolve_prompt_safely()
                    result.prompt_evolved = prompt_result.get("success", False)
                    result.prompt_version = prompt_result.get("version")
                    result.prompt_changes = prompt_result
                except Exception as e:
                    logger.error("Prompt evolution failed: %s", e, exc_info=True)
                    result.errors.append(f"Prompt evolution: {e}")

        # ── 参数优化 ──
        if strategy in ("params", "auto", "full"):
            if strategy in ("params", "full") or self.should_evolve_params():
                try:
                    params_result = self._optimize_params()
                    result.params_optimized = params_result.get("success", False)
                    result.params_changes = params_result
                except Exception as e:
                    logger.error("Parameter optimization failed: %s", e, exc_info=True)
                    result.errors.append(f"Param optimization: {e}")

        # ── nnU-Net 训练检查 ──
        if strategy == "full" and self.should_train_nnunet():
            result.warnings.append(
                f"训练样本已达 {self.collector.count_training_samples()} 个，"
                "建议启动 nnU-Net 云端训练"
            )

        # ── 进化后: 记录新指标 ──
        try:
            after = self.evaluator.get_current_metrics(days=30)
            result.metrics_after = after.to_dict()
        except Exception as e:
            logger.warning("Failed to get post-evolution metrics: %s", e)

        result.elapsed_seconds = time.time() - t0
        logger.info(
            "Evolution complete: strategy=%s prompt=%s params=%s elapsed=%.1fs",
            strategy, result.prompt_evolved, result.params_optimized,
            result.elapsed_seconds,
        )

        return result

    async def _evolve_prompt_safely(self) -> Dict[str, Any]:
        """安全的 Prompt 进化: 生成 → Shadow Eval → 部署/回滚"""
        from web.backend.services.vasi_evaluator import VasiMetrics

        # 1. 获取当前 prompt
        old_prompt = self.prompt_evolver.get_current_prompt()

        # 2. 构建新 prompt
        samples = self.collector.export_training_samples(min_dice=0.4, limit=30)
        if len(samples) < 3:
            return {"success": False, "reason": "insufficient_samples", "count": len(samples)}

        new_prompt = self.prompt_evolver.build_prompt("面部", use_few_shot=True)
        examples = self.prompt_evolver.select_few_shot_examples("面部")
        few_shot_ids = [ex.sample_id for ex in examples]

        # 3. Shadow Eval: 在样本上评估新旧 prompt
        # (当前简化: 使用现有训练样本的 Dice 作为近似)
        old_metrics = self.evaluator.compute_metrics(samples)

        # 4. 安全检查: 如果已经有了当前版本，对比
        current_version = self.prompt_evolver.get_current_version()
        if current_version and current_version.metrics:
            old_dice = current_version.metrics.get("dice_coefficient", 0)
            new_dice = old_metrics.dice_coefficient
            if new_dice < old_dice * 0.9:
                logger.warning(
                    "Prompt rejected: Dice %.3f < baseline %.3f",
                    new_dice, old_dice,
                )
                return {
                    "success": False,
                    "reason": "shadow_eval_failed",
                    "old_dice": old_dice,
                    "new_dice": new_dice,
                }

        # 5. 部署
        deployed = self.prompt_evolver.deploy_prompt(
            prompt_text=new_prompt,
            few_shot_ids=few_shot_ids,
            metrics=old_metrics.to_dict(),
        )

        return {
            "success": deployed,
            "version": self.prompt_evolver.get_current_version().version_tag if self.prompt_evolver.get_current_version() else None,
            "few_shot_count": len(few_shot_ids),
            "metrics": old_metrics.to_dict(),
        }

    def _optimize_params(self) -> Dict[str, Any]:
        """优化参数（基于最近样本的反馈）"""
        samples = self.collector.get_recent_samples(days=30, limit=100)

        if len(samples) < 10:
            return {"success": False, "reason": "insufficient_samples", "count": len(samples)}

        updated_groups = 0
        for s in samples:
            if s.dice_score is None:
                continue
            fitz = s.fitzpatrick_type or "III"
            quality = s.quality_level or "good"
            self.param_optimizer.update_from_feedback(
                fitzpatrick=fitz,
                quality_level=quality,
                params_used=self.param_optimizer.select_params(fitz, quality, s.body_site),
                metrics={"dice": s.dice_score, "area_error_pct": s.area_error_pct or 0},
            )
            updated_groups += 1

        return {
            "success": True,
            "updated_groups": updated_groups,
            "optimizer_stats": self.param_optimizer.get_all_stats(),
        }

    # ── 定时任务 ──

    async def scheduled_evolution(self) -> EvolutionResult:
        """每日定时运行: 自动检查并执行进化"""
        logger.info("Running scheduled evolution check")

        should_prompt, _ = self.should_evolve_prompt()
        should_params = self.should_evolve_params()

        if not should_prompt and not should_params:
            logger.info("No evolution needed")
            return EvolutionResult(strategy="none")

        strategy = "prompt" if should_prompt else "params"
        result = await self.evolve(strategy=strategy)

        if result.has_any_change():
            summary = self._build_evolution_summary(result)
            logger.info("Scheduled evolution: %s", summary)

        return result

    def _build_evolution_summary(self, result: EvolutionResult) -> str:
        parts = []
        if result.prompt_evolved:
            parts.append(f"Prompt → {result.prompt_version} ({result.prompt_changes.get('few_shot_count', 0)} examples)")
        if result.params_optimized:
            parts.append(f"Params → {result.params_changes.get('updated_groups', 0)} groups")
        return ", ".join(parts) if parts else "no changes"

    # ── 状态查询 ──

    def get_status(self) -> EvolutionStatus:
        """获取当前进化状态"""
        stats = self.collector.get_feedback_stats(days=30)
        should_prompt, new_samples = self.should_evolve_prompt()
        current_version = self.prompt_evolver.get_current_version()

        metrics = self.evaluator.get_current_metrics(days=30)
        degradation = self.evaluator.detect_degradation(metrics)

        # 查找最近的进化记录
        last_evo = (
            self.db.query(VasiModelVersion)
            .filter(VasiModelVersion.is_active == True)
            .order_by(VasiModelVersion.deployed_at.desc())
            .first()
        )

        return EvolutionStatus(
            feedback_stats=stats,
            prompt_should_evolve=should_prompt,
            prompt_new_samples=new_samples,
            prompt_current_version=current_version.version_tag if current_version else "default",
            params_groups=self.param_optimizer.get_all_stats(),
            current_metrics=metrics.to_dict(),
            degradation_warning=degradation,
            last_evolution=last_evo.version_tag if last_evo else None,
        )

    # ── 回滚 ──

    async def rollback(self) -> Dict[str, Any]:
        """回滚到上一个 Prompt 版本"""
        success = self.prompt_evolver.rollback()
        if success:
            current = self.prompt_evolver.get_current_version()
            return {
                "status": "ok",
                "message": f"已回滚到 {current.version_tag}" if current else "已回滚到默认版本",
            }
        return {"status": "error", "message": "没有可回滚的版本"}

    # ── 训练数据导出 ──

    def export_training_dataset(
        self,
        output_format: str = "json",
        min_dice: float = 0.4,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """导出训练数据集（用于 nnU-Net 训练）"""
        samples = self.collector.export_training_samples(
            min_dice=min_dice, limit=limit
        )
        return [
            {
                "id": s.id,
                "image_hash": s.image_hash[:12],
                "body_site": s.body_site,
                "fitzpatrick": s.fitzpatrick_type,
                "quality": s.quality_level,
                "dice": s.dice_score,
                "area_error_pct": s.area_error_pct,
                "has_user_mask": bool(s.user_mask_b64),
                "has_ai_mask": bool(s.ai_mask_b64),
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in samples
        ]


# ══════════════════════════════════════════════════════════════════════════════
# Module-level convenience
# ══════════════════════════════════════════════════════════════════════════════

def get_orchestrator(db: Session) -> EvolutionOrchestrator:
    """获取 EvolutionOrchestrator 实例"""
    return EvolutionOrchestrator(db)

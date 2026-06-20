# 自我进化 VASI 模型 — 架构设计

> 设计日期: 2026-06-01
> 状态: 设计阶段
> 目标: 让 VASI 白斑测评模型具备自我进化能力，持续提升白斑范围与面积识别的准确性

---

## 1. 现状分析

### 1.1 当前管线

```
用户上传 → 质量检测(vasi_quality.py) → 预处理(vasi_preprocess.py)
  → VLM分类定位(qwen3-vl-plus) → SAM VLM-guided 分割 → nnU-Net 远程回退
```

### 1.2 已具备的进化基础设施

| 资产 | 状态 | 价值 |
|------|------|------|
| `contour_diff` 字段 | ✅ 已存储 | AI轮廓 vs 用户修正的差异 |
| `user_contours` 字段 | ✅ 已存储 | 用户手动修正的轮廓 |
| `user_mask_image` 字段 | ✅ 已存储 | 用户最终掩码 PNG |
| `confidence` 字段 | ✅ 已存储 | AI 置信度 |
| `quality_report_json` | ✅ 已存储 | 图片质量报告 |
| `is_user_corrected` | ✅ 标记 | 是否被用户修正过 |
| VLM + SAM 双模型 | ✅ 运行中 | 决策层 + 执行层 |
| 千问云 API | ✅ 已配置 | 可调用的视觉模型 |

### 1.3 关键瓶颈

| 瓶颈 | 影响 | 量化 |
|------|------|------|
| VLM 随机性 | 两次调用同一图片结果不一致 | IoU 经常 < 0.6 |
| 皮肤检测阈值固定 | 不同肤色用户检测效果差异大 | Fitzpatrick I vs VI 差异显著 |
| SAM prompt 简单 | 单点 prompt 无法精确分割边界 | 边界误差大 |
| 无反馈闭环 | 用户修正数据只存不用 | 100% 浪费 |
| 无 GPU | 无法本地训练深度学习模型 | 只能依赖云服务 |

---

## 2. 自我进化架构总览

### 2.1 核心闭环

```
                    ┌─────────────────────────────────────────┐
                    │           自我进化闭环 (Self-Evo Loop)    │
                    │                                          │
                    │   ┌──────────┐     ┌──────────────┐     │
                    │   │ 1.收集   │────▶│  2.学习      │     │
                    │   │ DATA     │     │  LEARN       │     │
                    │   │ 用户修正  │     │  参数优化    │     │
                    │   │ 隐式反馈  │     │  Prompt进化  │     │
                    │   │ 显式评分  │     │  阈值自适应  │     │
                    │   └──────────┘     └──────┬───────┘     │
                    │        ▲                  │              │
                    │        │                  ▼              │
                    │   ┌──────────┐     ┌──────────────┐     │
                    │   │ 4.监测   │◀────│  3.评估      │     │
                    │   │ MONITOR  │     │  EVALUATE    │     │
                    │   │ 指标看板  │     │  Before/After│     │
                    │   │ 退化告警  │     │  A/B测试     │     │
                    │   │ 自动回滚  │     │  回归测试    │     │
                    │   └──────────┘     └──────────────┘     │
                    └─────────────────────────────────────────┘
```

### 2.2 分层进化策略

自我进化在不同层面对应不同的学习机制：

```
┌─────────────────────────────────────────────────────────────────┐
│ Layer 1: Prompts & Parameters (分钟级，自动)                      │
│   → VLM prompt 的 few-shot 示例自动更新                          │
│   → 皮肤检测 HSV/YCrCb 阈值按 Fitzpatrick 类型自适应              │
│   → SAM 超参数按图片质量等级调优                                   │
├─────────────────────────────────────────────────────────────────┤
│ Layer 2: Heuristics & Rules (小时级，半自动)                      │
│   → 白斑检测的色彩空间阈值从用户修正中学习                         │
│   → 置信度-准确率校准曲线                                         │
│   → 体部位识别规则优化                                            │
├─────────────────────────────────────────────────────────────────┤
│ Layer 3: Model Weights (天/周级，人工触发)                        │
│   → SAM prompt encoder 微调（如 LoRA on cloud GPU）              │
│   → nnU-Net 从用户修正数据训练                                    │
│   → VLM 模型升级 (qwen3-vl-plus → qwen-vl-max)                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. 五大核心模块

### 3.1 模块一：数据收集层 (FeedbackCollector)

**文件**: `web/backend/services/vasi_feedback.py`

```python
class VasiFeedbackCollector:
    """收集多维度反馈信号，建立训练数据集"""

    # 1. 显式修正 (Explicit Correction)
    #    用户拖动轮廓点 → 保存 user_contours + contour_diff
    #    已有: VASIAssessment.user_contours, contour_diff, user_mask_image

    # 2. 隐式信号 (Implicit Signals) —— NEW
    def collect_implicit_signals(assessment_id: int) -> ImplicitFeedback:
        """
        - 用户是否在结果页停留 > 10s（认真看了）
        - 用户是否立即重新上传同一部位（对结果不满）
        - 用户是否分享了结果（认可准确度）
        - 用户是否在修正后再次修正（修正也不满意）
        """
        ...

    # 3. 主动询问 (Active Query) —— NEW
    def request_feedback(assessment_id: int) -> FeedbackPrompt:
        """
        对低置信度(confidence < 0.5)的结果，主动弹窗问：
        "AI 对这片白斑的识别准确吗？" [准确] [偏高] [偏低] [漏检]
        """
        ...

    # 4. 结构化存储
    def to_training_sample(assessment: VASIAssessment) -> TrainingSample:
        """
        将 VASIAssessment + 用户修正 → 标准化的训练样本:
        {
            "image_key": "...",
            "ai_mask_b64": "...",      # AI原始分割
            "user_mask_b64": "...",    # 用户修正后
            "contour_diff": {...},      # 差异分析
            "body_site": "面部",
            "fitzpatrick": "III",
            "quality_report": {...},
            "confidence": 0.45,
            "timestamp": "..."
        }
        """
        ...
```

**数据模型扩展** (新增DB表):

```sql
-- 反馈信号表
CREATE TABLE vasi_feedback_signals (
    id INTEGER PRIMARY KEY,
    assessment_id INTEGER NOT NULL REFERENCES vasi_assessments(id),
    signal_type TEXT NOT NULL,  -- 'explicit_correction' | 'implicit_stay' | 'implicit_reupload' | 'active_query'
    signal_value JSON,           -- {"rating": 4, "comment": "..."}
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 训练样本表 (去重后的高质量训练数据)
CREATE TABLE vasi_training_samples (
    id INTEGER PRIMARY KEY,
    image_hash TEXT UNIQUE NOT NULL,  -- 去重
    image_key TEXT NOT NULL,
    ai_mask_b64 TEXT NOT NULL,
    user_mask_b64 TEXT NOT NULL,
    contour_diff JSON NOT NULL,
    body_site TEXT NOT NULL,
    fitzpatrick_type TEXT,
    quality_level TEXT,  -- 'good'|'acceptable'|'poor'
    confidence FLOAT,
    usage_count INTEGER DEFAULT 0,
    last_used_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 模型版本表
CREATE TABLE vasi_model_versions (
    id INTEGER PRIMARY KEY,
    version_tag TEXT UNIQUE NOT NULL,  -- 'v3.1.0-prompt-opt-20260601'
    description TEXT,
    changes JSON,  -- {"layer": "prompt", "params": {...}}
    metrics_json JSON,  -- {"recall": 0.72, "mape": 0.18, ...}
    is_active BOOLEAN DEFAULT FALSE,
    deployed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 3.2 模块二：VLM Prompt 自我进化 (PromptEvolver)

**文件**: `web/backend/services/vasi_prompt_evolver.py`

**原理**: 利用千问云 VLM 的上下文学习能力，将高质量用户修正自动转为 few-shot 示例。

```python
class VasiPromptEvolver:
    """VLM prompt 的自我进化引擎"""

    def __init__(self):
        self.few_shot_cache = []  # 当前激活的 few-shot 示例
        self.max_examples = 3     # 最多3个（避免prompt过长）
        self.diversity_threshold = 0.3  # 新示例与已有示例最低差异度

    def select_few_shot_examples(
        self,
        body_site: str,
        fitzpatrick: str,
    ) -> List[FewShotExample]:
        """
        从训练样本库中筛选最相关的 few-shot 示例。

        筛选策略:
        1. 同部位优先 (body_site match)
        2. 相似肤色优先 (fitzpatrick match)
        3. 高质量优先 (quality='good', confidence 转化最大)
        4. 多样性保证 (不同示例间 contour_diff 差异 > threshold)
        """
        ...

    def evolve_prompt(
        self,
        base_prompt: str,
        body_site: str,
        fitzpatrick: str,
    ) -> str:
        """
        动态构建 prompt = 系统指令 + few-shot 示例 + 任务描述。

        Few-shot 示例格式:
        ```
        【参考案例 1】
        该用户上传了一张{body_site}照片，AI 最初检测到{ai_lesion_count}个白斑，
        用户修正后确认为{user_lesion_count}个白斑，主要差异是{key_diff}。
        最终分割结果如{user_mask_description}所示。
        学到的经验: {lesson_learned}
        ```
        """
        ...

    def auto_refresh(self) -> bool:
        """
        定时触发: 当训练样本库新增 > 20 个高质量样本时，
        重新选择 few-shot 示例并更新 prompt。
        """
        ...

    def get_evolved_prompt(self, body_site: str, image_quality: str) -> str:
        """返回当前最优的 VLM prompt"""
        ...
```

**Prompt 进化示例**:

```
系统 prompt (固定):
"你是一位经验丰富的皮肤科医生，擅长识别白癜风白斑..."

Few-shot 示例 (动态，从用户修正中学习):
【参考案例 1 — 面部，Fitzpatrick III】
原图: [image]  → AI 检出 3 个白斑，用户确认 2 个。
关键差异: AI 将眉骨高光误判为白斑（该区域正常肤色对比度仅 0.08）。
经验: 面部骨骼突起处的高光区域不纳入白斑判断。

【参考案例 2 — 手部，Fitzpatrick IV】
原图: [image]  → AI 检出 1 个白斑，用户修正后增加为 3 个。
关键差异: AI 漏检了手指侧面两个小面积白斑（<3%手部面积）。
经验: 手指间缝隙处的小面积白斑容易被忽略，需要主动搜索。

任务描述 (固定):
"请根据以上经验，仔细分析以下{body_site}照片..."
```

### 3.3 模块三：参数自适应 (ParameterOptimizer)

**文件**: `web/backend/services/vasi_param_optimizer.py`

**原理**: 将皮肤检测、白斑检测的可调参数按用户特征（肤色类型、图片质量）自适应。

```python
@dataclass
class AdaptiveParams:
    """按条件分组的自适应参数集"""
    # 皮肤检测
    skin_hsv_sat_low: int = 20
    skin_hsv_sat_high: int = 200
    skin_ycrcb_cr_low: int = 133
    skin_ycrcb_cr_high: int = 180

    # 白斑检测
    vitiligo_l_offset: float = 12.0     # L* lightness offset
    vitiligo_max_chroma: float = 35.0   # max chroma for white patches
    vitiligo_min_area_ratio: float = 0.005

    # SAM 参数
    sam_points_per_side: int = 16
    sam_pred_iou_thresh: float = 0.80
    sam_stability_thresh: float = 0.85

    # VLM 参数
    vlm_confidence_threshold: float = 0.85
    vlm_temperature: float = 0.1


class VasiParameterOptimizer:
    """
    参数自适应优化器。

    核心算法: 贝叶斯优化 (Bayesian Optimization)
    - 用高斯过程建模 参数 → 准确率 的映射
    - 每次一批用户修正后，更新后验分布
    - 选择 EI (Expected Improvement) 最大的参数组合
    """

    def __init__(self):
        self.param_sets: Dict[str, AdaptiveParams] = {
            # Fitzpatrick I-III (浅肤色): 更严格的白斑检测(避免高光误判)
            "light_skin_good": AdaptiveParams(
                vitiligo_l_offset=14.0,
                vitiligo_max_chroma=30.0,
                sam_pred_iou_thresh=0.85,
            ),
            "light_skin_poor": AdaptiveParams(
                vitiligo_l_offset=10.0,  # 光线差时放宽
                vitiligo_max_chroma=40.0,
                sam_pred_iou_thresh=0.75,
            ),
            # Fitzpatrick IV-VI (深肤色): 更灵敏的白斑检测(避免漏检)
            "dark_skin_good": AdaptiveParams(
                vitiligo_l_offset=10.0,
                vitiligo_max_chroma=35.0,
                sam_pred_iou_thresh=0.78,
            ),
            "dark_skin_poor": AdaptiveParams(
                vitiligo_l_offset=8.0,
                vitiligo_max_chroma=45.0,
                sam_pred_iou_thresh=0.72,
            ),
        }

    def select_params(
        self,
        fitzpatrick: str,
        quality_level: str,
        body_site: str,
    ) -> AdaptiveParams:
        """根据用户特征选择最优参数集"""
        key = self._build_key(fitzpatrick, quality_level)
        if key in self.param_sets:
            return self.param_sets[key]
        return AdaptiveParams()  # 默认参数

    def update_from_feedback(
        self,
        fitzpatrick: str,
        quality_level: str,
        current_params: AdaptiveParams,
        metrics: Dict[str, float],  # {"recall": 0.72, "precision": 0.85, ...}
    ) -> None:
        """
        贝叶斯优化更新:
        1. 记录 (params, metrics) 对
        2. 更新高斯过程后验
        3. 如果新参数组合的 EI > threshold，更新 param_sets
        """
        ...

    def get_confidence_calibration(
        self, confidence: float, body_site: str
    ) -> float:
        """
        置信度校准: 从用户修正数据中学习 confidence → 实际准确率 的映射。
        例如: AI 说 confidence=0.8，但该部位历史上只有 60% 准确 →
        校准后 confidence=0.6
        """
        ...
```

### 3.4 模块四：评估框架 (VasiEvaluator)

**文件**: `web/backend/services/vasi_evaluator.py`

```python
@dataclass
class VasiMetrics:
    """VASI 模型评估指标"""
    # 核心指标
    recall: float              # 白斑检出率 = TP / (TP + FN)
    precision: float           # 白斑精确率 = TP / (TP + FP)
    f1_score: float            # F1 = 2*P*R/(P+R)
    dice_coefficient: float    # Dice = 2|A∩B|/(|A|+|B|)  (mask级别)

    # 面积指标
    mape: float                # 面积误差 MAPE = mean(|pred-true|/true)
    mae_pct: float             # 绝对面积误差 mean(|pred_pct - true_pct|)
    bias_pct: float            # 系统性偏差 mean(pred_pct - true_pct)

    # 行为指标
    correction_rate: float     # 用户修正比例
    avg_correction_magnitude: float  # 用户平均修正幅度

    # 分层指标
    by_body_site: Dict[str, 'VasiMetrics']
    by_fitzpatrick: Dict[str, 'VasiMetrics']
    by_quality: Dict[str, 'VasiMetrics']


class VasiEvaluator:
    """评估框架：在部署前验证改进效果"""

    def evaluate_against_baseline(
        self,
        model_func: Callable,
        test_samples: List[TrainingSample],
    ) -> Tuple[VasiMetrics, VasiMetrics]:
        """
        在测试集上对比新旧模型。

        Returns:
            (baseline_metrics, new_metrics)
        """
        ...

    def run_regression_test(
        self,
        test_samples: List[TrainingSample],
        min_dice: float = 0.5,
    ) -> bool:
        """
        回归测试: 确保新模型在所有测试样本上的 Dice ≥ min_dice。
        如果任一样本退化 > 20%，拒绝部署。
        """
        ...

    def generate_report(self) -> str:
        """生成 Markdown 格式的评估报告"""
        ...

    def detect_degradation(
        self,
        current_metrics: VasiMetrics,
        window_size: int = 100,
    ) -> Optional[str]:
        """
        退化检测: 对比最近 N 次评估的指标趋势。
        如果连续 3 个窗口下降 > 5%，触发告警。
        """
        ...
```

### 3.5 模块五：进化编排器 (EvolutionOrchestrator)

**文件**: `web/backend/services/vasi_evolution.py`

```python
class EvolutionOrchestrator:
    """
    进化编排器 — 自我进化的中央控制器。

    负责:
    1. 触发条件判断 (什么时候该进化)
    2. 进化策略选择 (用哪种方式进化)
    3. 安全部署 (验证通过后上线)
    4. 回滚 (如果退化，自动回退)
    """

    def __init__(self):
        self.collector = VasiFeedbackCollector()
        self.prompt_evolver = VasiPromptEvolver()
        self.param_optimizer = VasiParameterOptimizer()
        self.evaluator = VasiEvaluator()
        self.current_version = self._load_active_version()

    # ── 触发条件 ──

    def should_evolve_prompt(self) -> bool:
        """当新增高质量样本 > 20 个时触发"""
        new_samples = self.collector.count_new_quality_samples(days=7)
        return new_samples >= 20

    def should_evolve_params(self) -> bool:
        """当某分组的准确率比其他分组低 15%+ 时触发"""
        metrics = self.evaluator.get_stratified_metrics()
        # 找出最差分组
        worst = min(metrics.by_fitzpatrick.values(), key=lambda m: m.f1_score)
        best = max(metrics.by_fitzpatrick.values(), key=lambda m: m.f1_score)
        return (best.f1_score - worst.f1_score) > 0.15

    def should_train_nnunet(self) -> bool:
        """当累积训练样本 > 200 个时触发"""
        return self.collector.count_training_samples() >= 200

    # ── 进化执行 ──

    async def evolve(self, strategy: str = "auto") -> EvolutionResult:
        """
        执行一轮进化。

        strategy 选项:
        - "prompt": 仅进化 VLM prompt
        - "params": 仅优化参数
        - "auto": 自动选择最需要的进化方式
        - "full": 全部执行
        """
        result = EvolutionResult()

        if strategy in ("prompt", "auto", "full") and self.should_evolve_prompt():
            result.prompt_changed = await self._evolve_prompt_safely()

        if strategy in ("params", "auto", "full") and self.should_evolve_params():
            result.params_optimized = await self._evolve_params_safely()

        if strategy in ("full") and self.should_train_nnunet():
            result.nnunet_trained = await self._train_nnunet_safely()

        return result

    async def _evolve_prompt_safely(self) -> bool:
        """安全的 prompt 进化: 生成 → 评估 → 部署/回滚"""
        old_prompt = self.prompt_evolver.get_current_prompt()
        new_prompt = self.prompt_evolver.evolve()

        # 使用历史数据做 shadow evaluation
        shadow_metrics = self.evaluator.shadow_eval(
            old_prompt=old_prompt,
            new_prompt=new_prompt,
            samples=self.collector.get_recent_samples(50),
        )

        if shadow_metrics.f1_score < self.current_version.metrics.f1_score * 0.95:
            logger.warning("Prompt evolution degraded, rolling back")
            return False

        # 部署新 prompt
        self.prompt_evolver.deploy(new_prompt)
        self._record_version(
            tag=f"prompt-evo-{datetime.now().strftime('%Y%m%d%H%M')}",
            changes={"prompt_hash": hash(new_prompt)},
            metrics=shadow_metrics,
        )
        return True

    # ── 定时任务 ──

    async def scheduled_evolution(self):
        """每日定时运行: 检查是否需要进化，如果需要则执行"""
        result = await self.evolve(strategy="auto")
        if result.has_any_change():
            await self._notify_admin(result)

    # ── 紧急回滚 ──

    async def rollback(self) -> bool:
        """回滚到上一个版本"""
        prev = self._get_previous_version()
        if prev:
            self._deploy_version(prev)
            return True
        return False
```

---

## 4. 数据流全景

```
用户拍照
    │
    ▼
┌──────────────────────────────────────────────────┐
│               VASI 推理管线                        │
│  Preprocess → VLM(PromptEvolver) → SAM(Adaptive)  │
│                      │                            │
│              confidence = 0.45                    │
└──────────────────────┬───────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────┐
│              用户查看结果                          │
│                                                  │
│  ┌─ confidence > 0.7: 正常显示                    │
│  ├─ confidence 0.4-0.7: 显示"AI 不太确定"         │
│  └─ confidence < 0.4: 主动请求用户修正             │
│                                                  │
│  用户行为:                                        │
│  - 满意 → 隐式信号 (停留时间长)                   │
│  - 修正轮廓 → contour_diff 保存                   │
│  - 不满意 → 重新上传 (负面隐式信号)               │
│  - 主动评分 → 显式反馈                            │
└──────────────────────┬───────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────┐
│            FeedbackCollector                      │
│  - 去重 (同图多次上传)                            │
│  - 质量筛选 (用户修正确实改善了结果)               │
│  - 结构化 → TrainingSample                       │
└──────────────────────┬───────────────────────────┘
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
    PromptEvolver  ParamOptimizer  nnUNetTrainer
    (每20样本)     (每50样本)      (每200样本)
          │            │            │
          └────────────┼────────────┘
                       ▼
              VasiEvaluator
              (Shadow Eval → 通过 → 部署)
                       │
                       ▼
              更新 active model
```

---

## 5. 实现路线图

### Phase 1: 数据收集基础 (1-2天)

| 任务 | 产出 |
|------|------|
| 实现 `vasi_feedback.py` FeedbackCollector | 新增 DB 表 + 反馈收集 API |
| 新增 implicit signal 收集逻辑 | 停留时间、重新上传检测 |
| 新增 active query 弹窗 | 低置信度时触发 |
| 实现 `TrainingSample` 导出 | 从 contour_diff 生成标准化样本 |

### Phase 2: Prompt 自我进化 (2-3天)

| 任务 | 产出 |
|------|------|
| 实现 `vasi_prompt_evolver.py` PromptEvolver | 动态 few-shot 示例选择 |
| 改写 `_call_vision_model()` 中的 prompt 构建 | 从静态字符串变为动态构建 |
| 实现 shadow evaluation | 新旧 prompt 对比框架 |
| 部署"安全开关" | 退化自动回滚 |

### Phase 3: 参数自适应 (2-3天)

| 任务 | 产出 |
|------|------|
| 实现 `vasi_param_optimizer.py` | 按 Fitzpatrick + quality 分组参数 |
| 改写 `vasi_skin_mask.py` | 接受自适应参数 |
| 改写 `vasi_segmentation.py` | SAM 参数按质量自适应 |
| 实现贝叶斯优化骨架 | Gaussian Process + EI 采集函数 |

### Phase 4: 评估框架 (1-2天)

| 任务 | 产出 |
|------|------|
| 实现 `vasi_evaluator.py` | 全套指标计算 |
| 实现回归测试 | 部署前自动验证 |
| 实现退化检测 | 连续下降告警 |
| 实现 A/B 测试框架 | 部分用户使用新模型 |

### Phase 5: 进化编排 (2-3天)

| 任务 | 产出 |
|------|------|
| 实现 `vasi_evolution.py` EvolutionOrchestrator | 中央控制器 |
| 实现定时任务 (cron / APScheduler) | 每日自动检查 |
| 实现管理员面板 API | 查看进化历史、手动触发 |
| 实现版本管理 | model_versions 表 + 回滚能力 |

### Phase 6: nnU-Net 训练 (依赖数据量)

| 里程碑 | 触发条件 |
|--------|----------|
| 训练数据准备脚本 | Phase 1 完成 |
| 云端 GPU 训练 | 累积 ≥ 200 个高质量训练样本 |
| nnU-Net 替换为自训练模型 | Dice > 当前最佳管线 |

---

## 6. 关键设计决策

### 6.1 为什么分三层进化？

| 层 | 速度 | 风险 | 影响范围 |
|----|------|------|----------|
| Prompt | 秒级 | 低（只是文本变化） | VLM 输出质量 |
| Parameters | 秒级 | 中（可能降低检出） | 分割 pipeline |
| Model Weights | 小时-天级 | 高（需要GPU训练） | 核心分割能力 |

分层设计确保快速迭代（prompt/params）和高风险改进（训练）互不阻塞。

### 6.2 没有 GPU 如何训练 nnU-Net？

- 使用火山引擎的 GPU 实例按需训练
- 训练数据量小 (200-500 样本) 时，几小时即可完成
- 训练好的模型可以导出为 ONNX 在 CPU 上推理
- 或者使用千问云的模型微调 API

### 6.3 如何保证进化不退化？

1. **Shadow Deployment**: 新模型先在上一个版本的数据上跑 shadow eval
2. **Regression Gate**: Dice < 0.95 * baseline → 拒绝部署
3. **Canary Release**: 先部署给 5% 用户观察 1 小时
4. **Auto-Rollback**: 核心指标连续 3 个检查窗口下降 > 5% → 自动回滚
5. **Human-in-the-loop**: 管理员在面板确认后才全量部署

### 6.4 用户隐私如何处理？

- 训练样本中不存储原始图片 URL，仅存储 mask（无身份信息）
- 用户可选择是否贡献数据（opt-in，默认同意，可关闭）
- 所有训练数据保留在服务器，不上传第三方

---

## 7. API 设计摘要

```
# 反馈收集
POST   /api/vasi/feedback          # 用户主动评分
GET    /api/vasi/feedback/status   # 查看数据贡献状态
POST   /api/vasi/feedback/opt-out  # 退出数据贡献

# 进化管理 (管理员)
GET    /api/admin/vasi/evolution/status     # 进化状态
POST   /api/admin/vasi/evolution/trigger    # 手动触发进化
POST   /api/admin/vasi/evolution/rollback   # 回滚
GET    /api/admin/vasi/evolution/history    # 进化历史

# 指标查询
GET    /api/admin/vasi/metrics/current      # 当前指标
GET    /api/admin/vasi/metrics/trend        # 指标趋势
GET    /api/admin/vasi/metrics/stratified   # 分层指标
```

---

## 8. 成功标准

| 指标 | 当前估值 | 3个月目标 | 6个月目标 |
|------|---------|----------|----------|
| 白斑检出率 (Recall) | ~30% | >60% | >85% |
| 面积误差 (MAPE) | ~50% | <25% | <15% |
| 用户修正率 | ~80% | <50% | <30% |
| 误检率 (FPR) | ~40% | <15% | <8% |
| Dice Coefficient | ~0.4 | >0.65 | >0.80 |

---

## 9. 附录: 文件结构

```
web/backend/services/
├── vasi.py                     # 主编排 (需改: 集成 EvolutionOrchestrator)
├── vasi_feedback.py            # [NEW] 数据收集
├── vasi_prompt_evolver.py      # [NEW] Prompt 进化
├── vasi_param_optimizer.py     # [NEW] 参数自适应
├── vasi_evaluator.py           # [NEW] 评估框架
├── vasi_evolution.py           # [NEW] 进化编排器
├── vasi_segmentation.py        # 分割 (需改: 接受自适应参数)
├── vasi_skin_mask.py           # 皮肤检测 (需改: 接受自适应参数)
├── vasi_preprocess.py          # 预处理 (不变)
├── vasi_quality.py             # 质量检测 (不变)
├── vasi_formula.py             # VASI 评分 (不变)
└── vasi_promptable.py          # 交互式 SAM (不变)

web/backend/api/
├── vasi.py                     # API 端点 (需扩展)
└── vasi_admin.py               # [NEW] 管理员进化管理

web/backend/models/
└── vasi.py                     # 数据模型 (需扩展: 新增表)

web/backend/database/
└── init_db.py                  # 数据库初始化 (需扩展)
```

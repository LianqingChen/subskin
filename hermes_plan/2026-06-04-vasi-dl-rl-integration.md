# VASI 自进化大模型 — 深度学习 + 强化学习深度融合设计

> 日期：2026-06-04
> 状态：规划阶段
> 关联文档：`2026-06-04-vasi-self-evolution-design.md`（基础架构规划）
> 目标：在已有数据飞轮基础上，引入 DL（深度学习）和 RL（强化学习）实现更根本的模型能力提升

---

## 0. 前置问题：为什么需要 DL/RL 而不止步于 Few-Shot Prompt？

### Few-Shot 的天花板

| 维度 | Few-Shot Prompt 能做到的 | 做不到的 |
|------|------------------------|---------|
| **VLM 语义理解** | ✅ 通过示例纠正 VLM 的判断偏好（漏检/误检模式） | ❌ 改变 VLM 本身的视觉感知能力 |
| **分割精度** | ✅ 提示 VLM 输出更精确的 bbox | ❌ 提升 SAM 的分割质量——SAM 看到的是像素，不是 prompt 文字 |
| **参数调优** | ❌ 无法触及 | ❌ SAM 阈值、预处理参数、颜色过滤参数 |
| **推理速度** | ❌ 反而会降低（更长的 prompt） | ❌ 无法优化 CPU 上的 SAM 推理 |
| **泛化到新部位/肤色** | ⚠️ 需要等够样本才能覆盖 | ❌ 无法 zero-shot 泛化 |

**结论：** Few-Shot 进化管"怎么想"，DL/RL 管"怎么看"和"怎么切"。两者互补。

---

## 1. 架构总览：四层进化金字塔

```
                         ┌─────────────────────────────────┐
                         │  L4: End-to-End Model           │
                         │  专用白斑分割模型（替代SAM+VLM） │
                         │  需要: 1000+ 精标注样本          │
                         │  训练: Supervised + Self-SL     │
                         ├─────────────────────────────────┤
                         │  L3: SAM Fine-Tune + RL Pipeline │
                         │  SAM微调 + RL参数自适应          │
                         │  需要: 500+ 样本                 │
                         │  DL: LoRA fine-tune + 对比学习   │
                         │  RL: 参数策略网络               │
                         ├─────────────────────────────────┤
                         │  L2: RL 参数优化 + Active Learning│
                         │  管线参数自动调优 + 主动学习     │
                         │  需要: 100+ 样本                 │
                         │  RL: Contextual Bandit           │
                         ├─────────────────────────────────┤
                         │  L1: Prompt 进化 (Few-Shot ICL) │
                         │  VLM prompt 自动优化            │
                         │  需要: 30+ 样本                  │
                         │  方法: Few-Shot + Diversity      │
                         └─────────────────────────────────┘
```

**L1（已完成）→ L2（新增 RL）→ L3（新增 DL）→ L4（远期目标）**

---

## 2. L2：强化学习驱动的管线参数自优化

### 2.1 核心思想

当前管线有大量**硬编码阈值和参数**，这些参数直接影响分割质量但从未被自动优化：

```python
# vasi_segmentation.py 中的硬编码参数
points_per_side = 8          # SAM 采样密度
pred_iou_thresh = 0.88       # SAM 预测 IoU 阈值
stability_score_thresh = 0.95
skin_hue_range = (0, 25)     # HSV 皮肤色调范围
skin_sat_range = (20, 180)   # 饱和度范围
vitiligo_l_offset = 12       # 白斑亮度偏移量
vitiligo_chroma_max = 35     # 色度上限

# vasi_preprocess.py 中的参数
white_balance_strength = 0.8
contrast_alpha = 1.2
sharpen_amount = 0.5
resize_target = 1024
```

**问题：** 这些参数对不同的肤色、光照、部位应该有不同的最优值，但现在是全局统一的。

### 2.2 RL 建模：Contextual Bandit

这不是一个序列决策问题（不需要多步 rollout），而是一个 **Contextual Bandit（上下文赌博机）** 问题：

```
State（状态）:  图片特征向量
                ├── 亮度直方图统计量 (mean, std, skew, kurtosis)
                ├── 肤色类型 (Fitzpatrick I-VI, 从 VLM 提取)
                ├── 身体部位 (one-hot)
                ├── 图像质量分数
                └── 白斑比例粗估计

Action（动作）: 参数向量
                ├── SAM: pred_iou_thresh, stability_score_thresh
                ├── 颜色: vitiligo_l_offset, vitiligo_chroma_max, skin_hue_range
                ├── 预处理: white_balance_strength, contrast_alpha, sharpen_amount
                └── 离散: points_per_side ∈ {8, 12, 16}

Reward（奖励）:  Dice score (AI mask vs 用户修正 mask)
                范围: [0, 1]，最大化 Dice
                或负的 area_error_pct 作为惩罚项
```

### 2.3 实现方案：轻量级策略网络

```
输入层: state_dim ≈ 30  (图片特征 + 部位 one-hot)
    ↓
隐藏层: 64 → 32  (两个全连接层 + ReLU)
    ↓
输出层: action_dim ≈ 10  (连续参数用 μ + σ 的高斯策略)
```

**训练数据来源：**
```python
# 每条训练样本就是一次 RL 交互记录
(state_features, action_params, reward_dice)

# 从 VasiTrainingSample 表提取：
for sample in training_samples:
    state = extract_features(sample.image)  # 从原始图片提取
    action = sample.pipeline_params          # 需要新增字段记录
    reward = sample.dice_score              # 已有
```

**训练算法：REINFORCE / PPO（简化版）**

```python
# 伪代码
policy_net = MLP(state_dim=30, action_dim=10)

for epoch in range(num_epochs):
    for batch in training_samples:
        states = extract_features_batch(batch)
        actions = batch.pipeline_params
        rewards = batch.dice_scores

        # Policy Gradient
        predicted_actions = policy_net(states)
        loss = -torch.mean(
            torch.log(predicted_actions) * (rewards - baseline)
        )
        loss.backward()
```

### 2.4 在线学习：每次用户修正都是一次训练

```python
# vasi_feedback.py 中新增
def record_explicit_correction(self, ...):
    # ... 现有代码 ...

    # 提取这次评估使用的参数
    state = extract_features(assessment)
    action = {
        "points_per_side": assessment.pipeline_params.get("points_per_side"),
        "pred_iou_thresh": ...,
        ...
    }
    reward = dice_score  # 从增强后的 contour_diff 中获取

    # 写入 RL 训练记录
    self._write_rl_experience(state, action, reward)

    # 每积累 50 条新记录，触发一次策略更新
    if self._count_unprocessed_rl_records() >= 50:
        self._trigger_policy_update()
```

### 2.5 部署方式

```
训练产出: policy_net.pth (~500KB)
部署方式: 替代硬编码参数查询表
推理开销: 一次 MLP 前向传播 (< 1ms, CPU)
```

每次 `assess_vasi()` 调用时：
```python
# 替换原来的硬编码参数
params = policy_net.predict(state_features)
sam_result = segment_with_params(image, params)
```

---

## 3. L2.5：主动学习 — RL 决定"该标注哪张图"

### 3.1 问题

管理员标注是 gold standard，但管理员时间有限。应该优先标注**最有学习价值的图片**，而不是按时间顺序。

### 3.2 RL 建模

```
State:  图片特征 + AI置信度 + 用户修正历史 + 该部位已有样本数
Action: request_label (请求管理员标注) 或 skip (跳过)
Reward: 标注加入训练样本后，模型在该部位/skin_type上的性能提升
        （Proxy: Dice improvement on a validation set）
```

### 3.3 简化实现（无需完整 RL）

使用**不确定性采样 + 多样性采样**的混合策略（UCB 风格）：

```python
def rank_images_for_labeling(pool: List[ImageLabel]) -> List[ImageLabel]:
    """给未标注图片排序，高价值的排前面"""
    for img in pool:
        # 1. AI 不确定性 (VLM confidence 越低越好)
        uncertainty = 1.0 - img.ai_confidence

        # 2. 数据稀缺性 (该部位/肤色的样本越少越好)
        site_skin_count = count_existing_samples(img.body_site, img.fitzpatrick)
        scarcity = 1.0 / (1.0 + site_skin_count)

        # 3. 用户行为信号 (被用户修正过的 == AI 可能不准)
        user_signal = 1.0 if img.has_user_correction else 0.5

        # 4. 多样性加分 (与已标注样本的特征距离)
        diversity = compute_diversity_score(img, existing_labeled)

        img.priority_score = (
            0.35 * uncertainty +
            0.25 * scarcity +
            0.20 * user_signal +
            0.20 * diversity
        )

    return sorted(pool, key=lambda x: x.priority_score, reverse=True)
```

---

## 4. L3：深度学习 — SAM Fine-Tune 白斑专用模型

### 4.1 为什么需要 Fine-Tune SAM

SAM 是通用分割模型，它"看到"边界但"不理解"白斑：

```
当前 SAM 的行为：
  输入: 一张包含手臂的照片
  输出: 手臂轮廓、手表轮廓、衣服褶皱、白斑边界 (全都分割出来)
        → 我们需要颜色阈值来过滤出白斑

Fine-Tune 后的 SAM：
  输入: 一张包含手臂的照片
  输出: 只有白斑区域的 mask (语义上理解"这是白斑")
```

### 4.2 训练数据

**来源：** `VasiTrainingSample` 表中 `sample_source='admin_labeling'` 的高质量样本

**数据量要求：**
- 最小可用：200 对 (image, admin_mask)
- 推荐：500+ 对
- 覆盖所有 12 个部位，至少 3 种 Fitzpatrick 类型

**数据格式：**
```python
# 每个训练样本
{
    "image": "原始照片 (保存为 1024px JPEG)",
    "mask": "管理员标注的 lesion mask (binary PNG)",
    "body_site": "面部",
    "fitzpatrick": "III",
    "bbox_prompt": [x1, y1, x2, y2],  # 作为 SAM 的 box prompt
}
```

### 4.3 Fine-Tune 方案

**方案 A：LoRA 微调 SAM Mask Decoder（推荐）**

```python
# 使用 segment-anything 库 + peft
from segment_anything import sam_model_registry
from peft import LoraConfig, get_peft_model

# 只训练 mask decoder，冻结 image encoder
sam = sam_model_registry["vit_b"](checkpoint="sam_vit_b_01ec64.pth")

# 冻结 image encoder
for param in sam.image_encoder.parameters():
    param.requires_grad = False

# LoRA 微调 mask decoder
lora_config = LoraConfig(
    r=8,                    # rank
    lora_alpha=16,
    target_modules=["q_proj", "v_proj"],
    lora_dropout=0.1,
)
sam.mask_decoder = get_peft_model(sam.mask_decoder, lora_config)

# 训练
optimizer = AdamW(sam.mask_decoder.parameters(), lr=1e-4)
loss_fn = DiceLoss() + BCEWithLogitsLoss()

for epoch in range(50):
    for image, mask, bbox in dataloader:
        # SAM 需要 prompt
        box = transform.apply_boxes(bbox, image.shape)
        pred = sam(image, boxes=box)
        loss = loss_fn(pred, mask)
        loss.backward()
        optimizer.step()
```

**优势：**
- 只训练 ~2M 参数（原 SAM ViT-B 的 ~2%）
- VRAM 需求：~4GB（可能仍需要 GPU，或者 CPU 上也能跑但很慢）
- 推理时额外开销 < 5%

**方案 B：知识蒸馏 → 轻量级专用模型（更适合 CPU）**

如果 GPU 不可用，可以将 fine-tuned SAM 的知识蒸馏到一个更小的模型：

```
Teacher: Fine-tuned SAM (GPU上训练，一次性)
Student: MobileNetV3 + FPN + Lightweight Mask Head (~5MB)

蒸馏后的模型在 CPU 上推理只需 0.5-2s（vs SAM 的 10-70s）
```

### 4.4 在线持续学习

```python
class ContinualLearningManager:
    """管理模型的持续更新，防止灾难性遗忘"""

    def should_retrain(self) -> bool:
        """每新增 100 个高质量样本或每30天触发一次"""
        new_samples = self.count_new_samples_since_last_train()
        days = self.days_since_last_train()
        return new_samples >= 100 or days >= 30

    def retrain(self):
        # 1. 加载当前模型权重
        # 2. 混合新旧数据 (旧数据保留 30% 防止遗忘)
        # 3. Fine-tune
        # 4. Shadow eval 对比新旧模型
        # 5. 如果提升 > 3% Dice，部署；否则保留旧模型
```

---

## 5. 对比学习：无标注数据的语义预训练

### 5.1 思想

即使没有 mask 标注，也可以利用大量**未标注的皮肤照片**来学习更好的皮肤/白斑特征表示。

### 5.2 SimCLR 风格对比学习

```python
# 正样本对：同一张图片的不同增强
aug1 = augment(image)  # 随机裁剪+颜色抖动
aug2 = augment(image)  # 另一种随机增强
# 负样本：batch 中的其他图片

# 目标：让同一图片的两个增强在嵌入空间中靠近
embedding_net = ResNet18(pretrained=True)
loss = NTXentLoss(embedding_net(aug1), embedding_net(aug2))
```

**数据来源：** 所有上传到 VASI 的图片（无需标注，~1000+ 张）

**产出：** 一个皮肤特征提取器，可用于：
- 更准确的 Fitzpatrick 分类
- 更好的白斑/正常皮肤区分特征
- 为 SAM fine-tune 提供更好的初始化

### 5.3 实际价值

```
对比学习特征 vs 原始 ResNet 特征:
  原始: 识别"手"、"脸"等语义类别 (ImageNet 预训练)
  对比学习后: 识别"浅色皮肤"、"深色皮肤"、"白斑区域"、"正常区域"
  → SAM fine-tune 时收敛更快，需要的标注样本更少
```

---

## 6. 强化学习 + 深度学习结合：RL 调度的智能管线

### 6.1 核心思想

当前管线是**固定的 7 级 fallback**，每一步都是硬编码决策。用 RL 学习一个**智能调度器**：

```
RL 调度器:
  State → 图片特征 + 已执行的步骤 + 中间结果
  Action → 下一步做什么？跑哪个模型？用哪个参数？还是直接返回？
  Reward → 最终 Dice score（或用户不修正的概率）
```

### 6.2 动作空间

```python
actions = [
    "run_vlm",           # 调用 VLM 分析
    "run_sam_quick",     # 快速 SAM (points_per_side=8)
    "run_sam_dense",     # 密集 SAM (points_per_side=16)
    "run_nnunet",        # 调用 nnU-Net
    "skip_to_merge",     # 跳过当前步骤，直接合并
    "return_result",     # 返回当前最优结果
    "retry_with_params", # 用不同参数重试当前步骤
]
```

### 6.3 学习信号

```python
# 每条轨迹
trajectory = [
    (state_0, "run_vlm",       0),       # 无即时奖励
    (state_1, "run_sam_quick", 0),       # 无即时奖励
    (state_2, "return_result", dice_final)  # 终端奖励 = Dice score
]

# 强化学习目标：最大化 E[最终 Dice score]
# 约束：总推理时间 < 30s (对 quick 模式)
```

### 6.4 实现路径

```
Phase 1: 离线 RL — 从历史数据中学习
  数据: 过去所有 VASIAssessment 的执行轨迹
  算法: Conservative Q-Learning (CQL) — 不需要在线探索
  
Phase 2: 在线微调 — epsilon-greedy 探索
  部署后，以 5% 概率随机尝试新路径
  用户修正 → reward 信号 → 更新调度策略
```

---

## 7. 实现路线图（分阶段）

### Phase 2：RL 参数优化（~3 周）

| 周次 | 任务 | 产出 |
|------|------|------|
| W1 | 图片特征提取器（亮度/颜色/纹理统计） | `extract_features()` 函数 |
| W1 | VasiTrainingSample 新增 `pipeline_params` JSON 字段 | DB migration |
| W2 | Contextual Bandit 策略网络 + REINFORCE 训练 | `rl_policy.py` |
| W2 | 训练数据采集（从用户修正中提取 state-action-reward） | `vasi_feedback.py` 改造 |
| W3 | Shadow eval 对比（RL 参数 vs 硬编码参数） | `rl_shadow_eval.py` |
| W3 | 部署上线 + 监控 | 生产部署 |

### Phase 2.5：主动学习（~1 周）

| 周次 | 任务 | 产出 |
|------|------|------|
| W4 | 图片优先级评分算法 | `active_learning.py` |
| W4 | 管理后台"优先标注"队列 | admin UI 改进 |

### Phase 3：SAM Fine-Tune（~4 周，需 GPU）

| 周次 | 任务 | 产出 |
|------|------|------|
| W5 | 训练数据准备（200+ admin_labeling 样本） | 数据集 |
| W6 | LoRA fine-tune SAM mask decoder | `sam_vitiligo_v1.pth` |
| W7 | Shadow eval + 知识蒸馏到轻量模型 | `vitiligo_segmenter_v1.onnx` |
| W8 | 在线持续学习框架 | `continual_learning.py` |

### Phase 3.5：对比学习（~2 周）

| 周次 | 任务 | 产出 |
|------|------|------|
| W9 | 无标注皮肤图片对比学习 | `skin_encoder.pth` |
| W10 | 集成到管线（Fitzpatrick 分类 + SAM prompt 增强）| 管线集成 |

### Phase 4：RL 智能调度器（~3 周）

| 周次 | 任务 | 产出 |
|------|------|------|
| W11 | 离线 CQL 训练 | `pipeline_scheduler.py` |
| W12 | 在线微调 + A/B 测试 | 生产 A/B 部署 |
| W13 | 全量上线 | 替代固定 fallback 链 |

---

## 8. 基础设施要求

### 当前环境
- CPU only（无 GPU）
- SQLite 数据库
- Python + FastAPI 后端

### 新增需求

| 组件 | 需求 | 用途 | 必要性 |
|------|------|------|--------|
| **PyTorch** | 已在 SAM 中使用 | RL 策略网络 + 对比学习 | ✅ 已有 |
| **GPU** (可选) | 1× T4/V100 | SAM fine-tune 训练（一次性） | ⚠️ 可以用云 GPU 按需租用，训练完即释放 |
| **ONNX Runtime** | 轻量推理引擎 | 部署蒸馏后的模型到 CPU | 📋 新增 |
| **模型存储** | ~100MB 磁盘 | 保存微调后的模型权重 | 📋 新增目录 |

### 无 GPU 的降级方案

```
GPU 不可用时的替代方案：

1. SAM Fine-Tune → 云端训练（Colab / AutoDL / 火山引擎）
   训练一次，产出 .pth → 下载到服务器
   
2. 对比学习 → CPU 可行（ResNet18 + 小 batch size）
   训练时间 ×10，但可后台跑

3. RL 策略网络 → CPU 完全可行（30维输入，2层MLP）
   训练 1-2 分钟，推理 < 1ms

4. ONNX 推理 → CPU 可行
   蒸馏后模型在 CPU 上 0.5-2s/张
```

---

## 9. 预期提升效果对比

| 方法 | Dice 提升 | 延迟影响 | 样本需求 | 实现周期 |
|------|----------|---------|---------|---------|
| **Few-Shot Prompt (L1)** | +0.05~0.10 | +2-5s (prompt更长) | 30+ | ✅ 已完成 |
| **RL 参数优化 (L2)** | +0.08~0.15 | 0 (推理 <1ms) | 100+ | ~3周 |
| **主动学习 (L2.5)** | 间接（样本质量提升） | 0 | 不限 | ~1周 |
| **SAM Fine-Tune (L3)** | +0.15~0.25 | -5~15s (更准=少fallback) | 500+ | ~4周 |
| **对比学习 (L3.5)** | +0.03~0.06 (辅助) | 0 | 1000+ (无标注) | ~2周 |
| **RL 调度器 (L4)** | +0.05~0.10 | -5~20s (跳过无效步骤) | 200+ | ~3周 |

**叠加预期总提升：Dice 从 ~0.50 → ~0.80+**

---

## 10. 核心优势总结

1. **Few-Shot (L1)** 解决了"VLM 怎么判断"的问题 —— 这是语义层面
2. **RL 参数优化 (L2)** 解决了"SAM 怎么切"的问题 —— 这是像素层面
3. **SAM Fine-Tune (L3)** 解决了"模型懂不懂白斑"的问题 —— 从通用分割到专用语义分割
4. **主动学习 (L2.5)** 解决了"优先学什么"的问题 —— 数据效率最大化
5. **对比学习 (L3.5)** 解决了"特征够不够好"的问题 —— 无标注数据也能提升
6. **RL 调度器 (L4)** 解决了"管线怎么跑最优"的问题 —— 速度+质量联合优化

**六层叠加，从 prompt 到像素、从数据到决策，形成完整的自进化智能体。**

# VASI 白斑识别精确度提升 — 专题规划

> 日期：2026-05-18
> 更新：2026-05-20 (Phase A+ Box Prompt 突破)
> 状态：Phase A 完成，Phase A+ 突破已验证
> 上下文：当前 VASI 测评依赖于 SAM + VLM 管线，但对照片中皮肤区域识别、白斑圈选和面积评估的精确度很低，基本依赖用户手动圈选。

---

## 1. 当前管线综述

### 1.1 完整评估流程

```
用户上传照片
  → ① 质量检测 (vasi_quality.py): 模糊度、亮度、皮肤占比
  → ② 图像预处理 (vasi_preprocess.py): 白平衡、对比度、锐化、缩放到1024px
  → ③ SAM 自动分割 (vasi_segmentation.py): SAM ViT-B on CPU
       ├─ Stage 1: HSV+YCrCb 双色彩空间检测皮肤前景
       ├─ Stage 2: 皮肤区域内，相对亮度阈值检测白斑 (median_L + 12)
       ├─ SAM 生成的 mask 必须与皮肤区域重叠 ≥70%
       └─ 白斑 mask 需通过色度验证 (chroma ≤ 35)
  → ④ VLM 分类 (vasi.py _call_vision_model):
       当前默认: DashScope qwen-vl-plus 或 Volcengine doubao-vision-pro-32k
       Prompt 仅要求返回 VASI 分数、面积估计、分类、分期
       **不生成轮廓** — 轮廓由 SAM 提供
  → ⑤ 合并结果: SAM 轮廓 + VLM 分类
  → ⑥ nnU-Net fallback (远程API)
  → ⑦ Mock fallback (随机数据)
```

### 1.2 核心技术栈

| 组件 | 技术 | 问题 |
|------|------|------|
| **分割模型** | SAM ViT-B (358MB)，CPU 模式 | 通用分割模型，**未针对白斑/皮肤训练**；CPU 慢(quick ~10s, precise ~70s) |
| **皮肤检测** | HSV + YCrCb 双色彩空间固定阈值 | 光照条件敏感；肤色多样性导致漏检/误检 |
| **白斑检测** | 相对亮度阈值 (skin_median_L + 12) + 色度过滤 | 白背景/白衣/纸张仍可能混入 |
| **视觉模型** | qwen-vl-plus / doubao-vision-pro-32k | 通用 VLM，非医疗专用；无法输出精确轮廓 |
| **GPU** | **无 GPU** | SAM 全部在 CPU 上运行，限制模型选择 |
| **nnU-Net** | 远程 API，无本地权重 | 似乎未实际部署/训练 |

### 1.3 精确度低的核心原因分析

```
根本原因层级分析：

第一层（最根本）：
  ┌─────────────────────────────────────────────────────┐
  │ SAM ViT-B 是通用分割模型，不做医学语义理解。       │
  │ 它"看到"边界的像素 → 产出任意形状的 mask，           │
  │ 但不"知道"什么是白斑 vs 正常皮肤 vs 伤疤。          │
  │ 后续的颜色过滤只是补救，本质上是"猜测"。             │
  └─────────────────────────────────────────────────────┘

第二层（采样密度不足）：
  ┌─────────────────────────────────────────────────────┐
  │ quick 模式 points_per_side=8 → 仅 64 个采样点       │
  │ 对于一张 1024×1024 的照片，平均每 128px 才有一个点  │
  │ 小的白斑 (<5%面积) 极易被完全遗漏                   │
  │ precise 模式 1024 点但 CPU 耗时 ~70s，体验不可接受   │
  └─────────────────────────────────────────────────────┘

第三层（颜色阈值脆弱）：
  ┌─────────────────────────────────────────────────────┐
  │ 相对亮度阈值 (median_L + 12) 的假设：               │
  │ "白斑一定比周围皮肤亮至少 12 个 L* 单位"            │
  │ 这在很多情况下不成立：                               │
  │  - 肤色深的用户: median_L 低，+12 仍然很低，可能误检 │
  │  - 肤色浅的用户: median_L 高，+12 接近 255 上限     │
  │  - 不均匀光照: median_L 是全局值，局部失去意义       │
  │  - 伤疤/反光: 亮度高但非白斑                         │
  └─────────────────────────────────────────────────────┘

第四层（无 GPU 限制模型选择）：
  ┌─────────────────────────────────────────────────────┐
  │ 没有 GPU 意味着：                                     │
  │  - 无法运行中型医疗分割模型 (nnU-Net, MedSAM)       │
  │  - SAM ViT-B 已经是最优选择（CPU 可运行的）          │
  │  - 任何改进必须考虑 CPU 推理时间                     │
  └─────────────────────────────────────────────────────┘
```

---

## 2. 改进方案矩阵

按"改造成本 vs 精度提升"排列，分三个梯队：

### 2.1 第一梯队：低改造成本，立即可行（1-2天）

#### 方案 A：优化 SAM 采样策略 ⭐⭐⭐

**问题**：quick 模式 64 个采样点极易遗漏小白斑。

**改进**：
- 增加快速模式的采样密度：`points_per_side=16`（256点，CPU ~20-30s）
- 对图片进行自适应分块（tiling）：将大图切为 512×512 的 tile，每个 tile 独立运行 SAM，再合并结果
- 使用 SAM promptable 模式（已实现！）：让用户在白斑区域点一下，SAM 精确分割该区域 — 这是目前最精准的方式

**现有基础**：`vasi_promptable.py` 已经实现了点击式 SAM，`/api/vasi/promptable/prepare` + `/api/vasi/promptable/click` 可用。

**推荐操作**：
1. 在前端增加"点击白斑区域"的半自动模式：用户点一下白斑，SAM 精确分割；不确定的区域再手动调整
2. 这比全自动 + 全手动都更实用

#### 方案 B：切换更强的 VLM 进行皮肤/白斑初步定位

**问题**：当前用 qwen-vl-plus（通义千问 VL Plus），不是最强的视觉模型。

**改进**：
- 升级到 `qwen3-vl-plus`（已确认可用，精度更高）
- 或使用 `doubao-1.5-vision-pro-32k`（火山引擎最强视觉模型）
- 让 VLM 输出更丰富的信息：皮肤区域边界框、白斑大致位置、光照质量评估

**改动点**：修改 `_call_vision_model` 中的模型名和 prompt，2小时工作量。

#### 方案 C：增加皮肤专用分割引导

**问题**：皮肤检测仅依赖 HSV/YCrCb 固定阈值，在不同肤色和光照下不可靠。

**改进**：
- 在 SAM 分割前，先用 VLM 做一次"皮肤区域识别"，返回皮肤的大致 mask 或边界框
- 将 VLM 的皮肤区域作为 SAM 的 prompt（box prompt），指导 SAM 在正确区域内分割
- 实现：VLM 返回 `{"skin_bbox": [x1,y1,x2,y2]}` → SAM 用 box prompt 做分割

**此方案将不可靠的颜色检测替换为 VLM 的语义理解**。

### 2.2 第二梯队：中等改造成本（1-2周）

#### 方案 D：引入 MedSAM — 医疗专用分割模型 ⭐⭐⭐⭐⭐

**这是最核心的改进方案。**

MedSAM (Medical Segment Anything Model) 是在 SAM 基础上用大量医学图像（含皮肤镜图像）微调的分割模型。论文发表在 Nature Communications (2024)。

| 对比 | SAM ViT-B | MedSAM ViT-B |
|------|-----------|-------------|
| 训练数据 | 自然图像 (SA-1B, 1100万张) | 医学图像 (150万张，包含皮肤病变) |
| 白斑分割 | 零样本，依赖颜色过滤 | 见过皮肤病变分割任务 |
| 模型大小 | 358MB | ~358MB (相同架构) |
| CPU 速度 | ~10s (quick) | 相同 |
| 可用性 | 已部署 | 需下载权重 (公开可用) |

**部署步骤**：
1. 下载 MedSAM 权重：`wget https://drive.google.com/.../medsam_vit_b.pth` 或从 HuggingFace 获取
2. 替换当前 `sam_vit_b_01ec64.pth`
3. `segment_anything` 包完全兼容，无需修改代码
4. 调整后处理参数（MedSAM 对医疗特征的理解更好）

**预期效果**：
- 白斑识别精确度 +30-50%
- 误检率（把背景当白斑）-60%
- 推理时间不变

#### 方案 E：Build-a-SAM 管线 — 双模型协作

**思路**：
1. **VLM 先看**：qwen3-vl-plus 先分析照片，输出：
   - 皮肤区域边界框
   - 每个疑似白斑的位置（点坐标）
   - 白斑数量估计
   - 光照方向和质量评估
2. **SAM 后分**：用 VLM 输出的定位信息作为 prompt：
   - `skin_bbox` → box prompt for SAM → 精确的皮肤 mask
   - `lesion_points` → point prompt for SAM → 精确的白斑 mask
3. **面积计算**：在皮区域内计算白斑占比，而非整张照片占比

**优势**：
- VLM 提供语义（"这是白斑"），SAM 提供精度（像素级 mask）
- 解决了 SAM 不知道"什么是白斑"的核心问题
- 当前代码已支持 point/box prompt（`vasi_promptable.py`）

**代码改动量**：中等。需要修改 `_call_vision_model` 的 prompt，增加 SAM promptable 调用。

#### 方案 F：用 VLM 直接生成精细分割（Zero-shot）

**新可能性**：部分最新 VLM（GPT-4o、Gemini 2.5 Pro、Claude 3.5 Sonnet）已经具备约 80% 精度的图像分割能力。

**测试方案**：
- 使用 GPT-4o 或 Gemini 2.5 Pro 测试：给照片 + 要求输出白斑的多边形 mask
- 对比 SAM 结果
- 如果 VLM 的轮廓精度可接受，可以直接用 VLM 替代 SAM，简化管线

**风险**：VLM 的像素级坐标精度通常不如专用分割模型，但对于大面积白斑可能足够。

### 2.3 第三梯队：高改造成本，长期投入（1-3月）

#### 方案 G：自训练 VASI-Net — 基于 nnU-Net 的专用白斑分割模型 ⭐⭐⭐⭐⭐

**这是终极方案，但需要大量标注数据。**

**路线图**：
1. **数据收集（1-3月）**：利用用户手动修正的轮廓数据（`contour_diff` 记录已存在！）
   - 每次用户手动修正白斑轮廓 → 保存为训练样本
   - 目标：收集 500-2000 张标注过的白斑照片
   - 数据增强：旋转、翻转、颜色抖动、皮肤色域变换
2. **模型训练**：使用 nnU-Net v2 框架
   - nnU-Net 自动配置网络结构、预处理、后处理
   - 只需提供图像 + mask 对
   - 可部署到火山引擎 ML 平台（已有 VOLC_ML_ENDPOINT 配置）
3. **持续优化**：RLHF 飞轮
   - `contour_diff` 已经在记录 AI vs 用户修正的差异
   - 差异大的样本 → 加入训练集重新训练
   - 形成"越用越准"的正循环

**优势**：
- 针对白斑的专用模型，精度远超通用方案
- 利用现有基础设施（nnU-Net 接口已预留）
- `contour_diff` 数据已在持续收集

**挑战**：
- 需要 GPU 训练（可用火山引擎 ML 平台）
- 需要足够的标注数据（用户手动修正可转化为标注）
- 模型服务需要 GPU 推理（可部署到火山引擎）

#### 方案 H：使用云端 GPU API 运行更强的模型

**选项**：
1. **火山引擎 ML 平台**：已配置 VOLC_ML_ENDPOINT，可部署 nnU-Net 推理服务
2. **HuggingFace Inference Endpoints**：部署 MedSAM 或专用分割模型
3. **Replicate / Modal**：按使用量付费的 GPU 推理

**成本估算**：
- 每次推理 ~0.05-0.20 元（T4/A10G GPU）
- 每天 100 次评估 = 5-20 元/天
- 每月 ~150-600 元

---

## 3. 立即可执行的三阶段路线图

### Phase A：本周 (5/19-5/23) — 低成本快速改善

| # | 任务 | 预期提升 | 工时 | 依赖 |
|---|------|---------|------|------|
| A1 | 升级 VLM 到 qwen3-vl-plus + 优化 prompt | 分类准确度 +20% | 2h | 无 |
| A2 | SAM 快速模式采样密度提升 (points_per_side=16) | 小斑块检出率 +30% | 1h | 无 |
| A3 | 前端增加半自动"点击白斑"引导（利用已有 promptable API） | 用户操作精度 +50% | 4h | 无 |
| A4 | VLM 返回皮肤区域 bbox → SAM box prompt 替代颜色检测 | 皮肤检测精度 +40% | 4h | A1 |
| A5 | 部署到 staging 测试 | — | 1h | A1-A4 |

**总计 ~12 小时，预期整体精度提升 40-60%。**

#### Phase A 已完成项 (5/18-5/20)

| 状态 | 任务 | 实现 |
|------|------|------|
| ✅ 完成 | A1 VLM 升级 qwen3-vl-plus | 连通验证(16s)，白斑检出 6 处 vs 旧版 3 处，诊断更专业 |
| ✅ 完成 | A2 SAM 采样密度提升 (points_per_side=16) | pred_iou 0.82→0.80, stability 0.88→0.85, min_area 500→200 |
| ✅ 完成 | A4 VLM skin_bbox → SAM box prompt | 已落地，替代颜色检测做皮肤裁剪 |
| ✅ 完成 | A3 前端增强 | 蚂蚁线动画轮廓、检测来源徽标、白斑计数、一键修正引导 |
| ✅ 完成 | Phase A 全部推生产 | SAM 快速模式 + VLM promptable + 前端优化 |

### Phase A+：Box Prompt 核心突破 (5/20) 🚀

**发现**：VLM 返回的 `estimated_size_percent` 可转化为 SAM box prompt，颠覆性提升分割精度。

**对比测试结果**：

| 方法 | 斑块数 | 单块面积范围 | 总面积 | 合理性 |
|------|--------|-------------|--------|--------|
| **旧方法** (point + neg ring + refine) | 1 块 | 99.0% | 99.0% | ❌ 完全无用 |
| **Box Prompt** (VLM size→box, no refine) | 5 块 | 0.5-3.0% | 7.4% (wider: 14.2%) | ✅ 合理 |

**关键修复**：
1. **box prompt 替代 point prompt**：VLM `estimated_size_percent` → `half_side = sqrt(target_area) * 0.50` → SAM box prompt → 紧密斑块 mask
2. **禁用 box prompt 后的 iterative refinement**：精炼会在均匀皮肤区域导致斑块 mask 灾难性膨胀 (1400-10000%)，box prompt 已经足够紧密
3. **tiling 集成到回退链**：guided SAM → auto SAM → tiling → 颜色回退，4 级 fallback

**性能**：推理时间 12-14s (与旧版相同)，CPU only。

**剩余差距**：
- Box 尺寸系数 0.50 下面积 14.2%，VLM 估计 ~22%（VLM 可能偏大）
- 6 个 VLM lesion 中 3 个因重叠被合并（合理）
- 极小白斑 (<1%) 仍可能漏检

### Phase B：两周内 (5/24-6/7) — MedSAM 替换

| # | 任务 | 预期提升 | 工时 |
|---|------|---------|------|
| B1 | 调研 MedSAM 权重获取和使用 | — | 2h |
| B2 | 下载 + 部署 MedSAM ViT-B 权重 | — | 2h |
| B3 | 在白斑测试集上对比 SAM vs MedSAM | — | 4h |
| B4 | 替换生产模型 + 回归测试 | 分割精度 +30-50% | 3h |
| B5 | 用户测试（staging → production） | — | 持续 |

### Phase C：长期 (6月中旬起) — 自训练 VASI-Net

| # | 任务 |
|---|------|
| C1 | 从 contour_diff 导出用户修正样本 |
| C2 | 建立白斑分割训练数据集 |
| C3 | 用 nnU-Net v2 训练专用模型 |
| C4 | 部署到火山引擎 ML 平台 |
| C5 | 建立持续训练 pipeline（RLHF 飞轮） |

---

## 4. 方案对比总结

| 方案 | 精度提升 | 改造成本 | 风险 | 推荐优先级 |
|------|---------|---------|------|-----------|
| **A1-A4: VLM升级 + SAM优化** | 中 (40-60%) | 低 (1-2天) | 低 | 🔴 立即执行 |
| **D: MedSAM** | 高 (30-50%) | 低 (1天) | 低 | 🟠 本周执行 |
| **E: Build-a-SAM 双模型** | 高 (50-80%) | 中 (3-5天) | 中 | 🟡 Phase A 后评估 |
| **F: VLM 直接分割** | 未知 | 低 (1天测试) | 高(可能不如SAM) | 🟡 快速验证 |
| **G: VASI-Net 自训练** | 最高 (80-95%) | 高 (1-3月) | 中 | 🟢 长期路线 |
| **H: 云端GPU推理** | 取决于模型 | 中 | 中(成本) | 🟢 配合G使用 |

---

## 5. 关键决策点

### 决策 1：是否需要 GPU？

- **如果购买 GPU**（如 RTX 4090, ~15000元）：可以使用 MedSAM-Large、nnU-Net 等更强的模型，本地推理 <2s
- **如果不购买 GPU**：继续 CPU 推理，优化路线为 MedSAM ViT-B + VLM 引导
- **折中方案**：使用火山引擎 ML 平台按需 GPU，随时扩展

### 决策 2：VLM 选型？

| 模型 | 视觉能力 | 速度 | 成本 | 可用性 |
|------|---------|------|------|--------|
| qwen-vl-plus (当前) | ⭐⭐ | 快 | 低 | DashScope |
| qwen3-vl-plus | ⭐⭐⭐ | 快 | 低 | DashScope |
| doubao-vision-pro-32k | ⭐⭐⭐ | 中 | 中 | 火山引擎 |
| GPT-4o | ⭐⭐⭐⭐⭐ | 中 | 高 | OpenAI API |
| Gemini 2.5 Pro | ⭐⭐⭐⭐ | 快 | 中 | Google API |

**推荐**：升级到 qwen3-vl-plus（DashScope）或 doubao-1.5-vision-pro（火山引擎），零额外成本。

### 决策 3：自动 vs 半自动 vs 全自动？

| 模式 | 精度 | 用户操作 | 适用场景 |
|------|------|---------|---------|
| 全自动 (当前SAM) | 30-50% | 上传照片即可 | 快速筛查 |
| **半自动 (Promptable SAM)** | **70-90%** | **点一下白斑** | **日常评估** |
| 手动圈选 (当前最佳) | 95%+ | 逐块圈选 | 精确评估 |

**推荐**：以"半自动"为主路径：
1. AI 自动检测 → 显示结果
2. 用户可一键修正（点/拖拽调整）
3. 全手动保留作为精确模式

---

## 6. 推荐执行方案（综合最优）

### 立即执行（本周）

```
1. VLM 升级 + Prompt 优化 (A1)
   - 模型: qwen-vl-plus → qwen3-vl-plus
   - Prompt 增加: 返回皮肤区域边界框 + 白斑大致位置

2. SAM 半自动模式引导 (A3)
   - 前端: 全自动结果出来后，提示"点一下白斑区域可精确分割"
   - 后端: 已有 promptable API，只需前端调用

3. VLM 引导 SAM (A4)
   - VLM 返回 skin_bbox → SAM box prompt
   - 替代不可靠的颜色皮肤检测
```

### 短期评估

```
4. 下载 MedSAM 权重，对比测试 (B1-B3)
5. 如果 MedSAM 效果更好，替换生产模型 (B4)
```

### 数据积累（持续）

```
6. 从 contour_diff 收集用户修正数据
7. 准备 VASI-Net 训练数据集
```

---

## 7. 技术细节附录

### 7.1 VLM Prompt 优化示例

```python
# 当前 prompt 问题：只要求语义判断，不要求定位
# 优化后 prompt：

"""
你是一位皮肤科AI助手。请分析这张白癜风患者的皮肤照片，返回以下JSON：

{
  "skin_region": {
    "bbox": [x1, y1, x2, y2],  // 皮肤区域的边界框，归一化坐标 0-1
    "confidence": 0.95
  },
  "suspected_lesions": [
    {
      "center": [x, y],          // 白斑中心点，归一化坐标 0-1
      "estimated_size": "small",  // small/medium/large
      "confidence": 0.85
    }
  ],
  "lighting_quality": "good",    // good/fair/poor
  "has_reference_card": false,   // 是否包含参考色卡
  "vasi_score": 25,
  "area_percentage_estimate": 15,
  "classification": "非节段型",
  "stage": "稳定期",
  "details": {
    "patch_count_estimate": 2,
    "color_type": "乳白",
    "border_clarity": "清晰",
    "description": "右上肢有2处边界清晰的乳白色脱色斑"
  }
}

注意：
1. 皮肤区域 bbox 使用归一化坐标 (0-1)，与图片宽高相乘得到像素坐标
2. 白斑中心点也使用归一化坐标
3. 只返回 JSON，不要其他文字
"""
```

### 7.2 MedSAM 部署要点

```python
# MedSAM 使用与 SAM 完全相同的 API
# 只需替换权重文件路径

from segment_anything import sam_model_registry, SamPredictor

model_path = "/root/subskin/models/medsam_vit_b.pth"  # 替换
sam = sam_model_registry["vit_b"](checkpoint=model_path)
```

### 7.3 VLM → SAM Box Prompt 伪代码

```python
# Step 1: VLM 识别皮肤区域
vlm_result = call_vision_model(image)
skin_bbox = vlm_result["skin_region"]["bbox"]  # [x1, y1, x2, y2] 归一化

# Step 2: 将归一化坐标转为像素坐标
h, w = image.shape[:2]
x1, y1 = int(skin_bbox[0] * w), int(skin_bbox[1] * h)
x2, y2 = int(skin_bbox[2] * w), int(skin_bbox[3] * h)

# Step 3: SAM 用 box prompt 分割皮肤区域
predictor = SamPredictor(sam_model)
predictor.set_image(image)
masks, scores, _ = predictor.predict(
    box=np.array([[x1, y1, x2, y2]]),
    multimask_output=True
)
skin_mask = masks[np.argmax(scores)]  # 取最高分的 mask

# Step 4: 在白斑中心点用 point prompt 分割白斑
for lesion in vlm_result["suspected_lesions"]:
    cx, cy = lesion["center"]
    px, py = int(cx * w), int(cy * h)
    masks, scores, _ = predictor.predict(
        point_coords=np.array([[px, py]]),
        point_labels=np.array([1]),  # 1 = foreground
        multimask_output=True
    )
    lesion_mask = masks[np.argmax(scores)]

# Step 5: 在皮肤区域内计算白斑占比
lesion_in_skin = np.logical_and(lesion_mask, skin_mask)
area_percent = lesion_in_skin.sum() / skin_mask.sum() * 100
```

---

## 8. 评估指标

改进后应当测量的关键指标：

| 指标 | 当前估计 | Phase A 目标 | Phase B 目标 | Phase C 目标 |
|------|---------|-------------|-------------|-------------|
| 白斑检出率 (Recall) | ~30% | >60% | >75% | >90% |
| 皮肤区域检测精度 (IoU) | ~50% | >75% | >85% | >95% |
| 面积误差 (MAPE) | ±50% | ±30% | ±20% | ±10% |
| 误检率 (False Positive) | ~40% | <20% | <10% | <5% |
| 用户手动修正比例 | ~80% | <50% | <30% | <15% |
| 推理总时间 (quick) | ~15s | <25s | <25s | <5s (GPU) |

---

## 9. 附录：现有管线代码地图

```
web/backend/services/
├── vasi.py                    # 主服务：编排完整评估管线
├── vasi_segmentation.py       # SAM 自动分割 + 颜色过滤
├── vasi_promptable.py         # SAM promptable 模式（点击分割）
├── vasi_skin_mask.py          # HSV+YCrCb 皮肤检测 + 白斑检测
├── vasi_preprocess.py         # 图像预处理（白平衡、对比度、缩放）
├── vasi_quality.py            # 照片质量检测
├── vasi_formula.py            # VASI 评分公式计算
├── vasi_formula.py            # VASI 评分公式计算

web/backend/api/vasi.py        # API 路由
web/backend/utils/llm_config.py # LLM 配置（DashScope/Volcengine/OpenAI）
web/app/src/views/AssessmentPage.vue          # 评估页面
web/app/src/composables/useVasiAssessment.ts  # 评估逻辑

models/sam_vit_b_01ec64.pth    # SAM ViT-B 权重 (358MB, CPU only)
```

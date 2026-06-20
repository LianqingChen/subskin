# SubSkin 测评页面整体重构设计方案

> 日期: 2026-06-13 | 版本: v1.0 | 状态: 审批中

---

## 一、现状审计报告

### 1.1 代码规模超标（违反 frontend-architect 规范）

| 文件 | 行数 | 规范上限 | 超标 |
|------|------|----------|------|
| `AssessmentWizard.vue` | **731** | 400（业务组件） | **+83%** |
| `useVasiAssessment.ts` | **637** | 200（composable） | **+219%** |
| `vasi.py` | 1530 | — | 过大 |
| `vasi_segmentation.py` | 1447 | — | 过大 |
| `api/vasi.py` | 1328 | — | 过大 |

**后端 VASI 服务文件: 14 个，总计 ~9,300 行** — 对于用户量不大的 MVP 产品严重过度工程化。

### 1.2 前端问题清单

#### 🔴 严重问题

1. **组件违反单一职责**: `AssessmentWizard` 同时管理：wizard 步骤流转、文件上传、相机、照片质量检查、AI 分析进度、MaskEditor 画布、结果展示、趋势图、评估历史（含分页/多选/滑动删除）、FeedbackPrompt、分享草稿。共 11 个独立职责。

2. **Composable 过载**: `useVasiAssessment` 同时管理：上传逻辑、评估提交、历史管理（分页/选择/滑动删除）、mask 编辑、精确评估、草稿创建、隐私脱敏、结果解读。共 8 个独立职责。

3. **5 步 Wizard 流程混乱**:
   - Step 1: 身体部位选择 ✚ 最近评估历史
   - Step 2: 照片上传 ✚ 拍照 ✚ 质量检查 ✚ 拍摄指南
   - Step 3: AI 分析进度 ✚ **VisualFeatures 分析（可选插入步骤）**
   - Step 4: MaskEditor 画布 ✚ AI 检测元数据 ✚ 跳过选项
   - Step 5: 结果卡片 ✚ 趋势图 ✚ 评分解读 ✚ 阶段说明 ✚ 分型 ✚ 分享 ✚ **评估历史（完整版）**
   
   **Step 3 的 VisualFeatures 是一个阻断性插入页** — 分析完后又弹出一个中间页，用户必须点"继续"才能进入画布。这个页面在快速测评流程中是多余的摩擦。

4. **布局不一致**: Step 1 使用 ReportPage 模式（固定 DigitalHuman + 白色卡片叠加层），Steps 2-5 使用标准布局（顶部 sticky 进度条 + 滚动内容）。两个布局的视觉风格完全不同。

5. **历史重复展示**: "最近评估"同时在 Step 1（最近 5 条）和 Step 5（完整分页列表）中出现，冗余。

#### 🟡 中等问题

6. **进度条复杂**: 5 个步骤的进度条支持点击跳回、完成打勾、移动端/桌面端两套显示、步骤间连接线。视觉信息量大但用户实际只用"下一步"。

7. **照片质量提示分散**: `PhotoGuideCard`（拍摄指南）、`qualityResult` 警告框、相机质量提示三个独立 UI 元素都在 Step 2 中。

8. **MaskEditor 步骤信息过载**: 显示 AI 检测来源标签、疑似白斑数量、置信度、可折叠的详细说明、皮肤/白斑颜色说明。大部分信息对用户无意义。

9. **结果页信息爆炸**: 一张卡片包含 VASI 评分、严重程度、白斑占比、病情阶段、趋势折线图、评分含义、阶段说明、分型、分享按钮、免责声明、FeedbackPrompt、评估历史（完整分页列表）。用户需要滚动很久才能看到历史记录。

### 1.3 后端问题清单

#### 🔴 严重问题

1. **过度工程化**: 14 个 VASI 服务文件实现了一个 7 级降级链路：
   ```
   VLM(ensemble?) → VLM-guided SAM → auto SAM → tiling → nnU-Net → mock
   ```
   每条路径都有独立的错误处理、日志、重试逻辑。对于一个用户量不大的 MVP，这是巨大的维护负担。

2. **自进化系统过早**: `vasi_feedback.py` (773行)、`vasi_evolution.py` (399行)、`vasi_rl_optimizer.py` (621行)、`vasi_param_optimizer.py` (383行)、`vasi_prompt_evolver.py` (671行)、`vasi_evaluator.py` (491行) — 共 ~3,300 行代码用于"自进化"，但在用户没有累积足够训练样本之前完全是无用代码。

3. **DB 模型膨胀**: `VASIAssessment` 表有 30+ 列，其中很多是自进化系统的（`final_contour_diff_metrics`、`user_mask_image` 等），大多数行这些列都是 NULL。

4. **VLM ensemble 模式**: `ENABLE_VLM_ENSEMBLE` 和 precise 模式下自动 ensemble 使 API 调用量翻倍。成本和延迟增加未必换来精度提升。

#### 🟡 中等问题

5. **Prompt 膨胀**: VLM 的 system prompt 包含复杂的结构化输出要求（skin_region bbox、lesion_centers、visual features 6维度），导致每次调用消耗大量 token。

6. **黑白名单逻辑分散**: 身体部位验证在 `vasi.py` 中有中文/英文两套映射，但在前端 `bodySites.ts` 中还有另一套。

7. **图片存储**: 当前存本地文件系统 (`data/uploads/vasi/`)，没有 CDN 或对象存储，不支持横向扩展。

### 1.4 LLM 配置分析

**当前状态**: LLM 配置系统本身是合理的 — 支持多供应商、按模块配置、密钥加密存储。

**问题**:
- VASI 模块用的是哪个模型？代码中通过 `get_llm_config('vasi')` 查询，但实际配置取决于部署环境。需要确认当前使用的是最优 vision model。
- VLM prompt 过于复杂，要求输出结构化 JSON（bbox、center、depigmentation_level、contrast_to_skin、confidence、estimated_size_percent 等），实际 VLM 模型对这些细粒度空间定位任务精度有限。
- 没有 A/B 测试框架来对比不同模型/参数的效果。

---

## 二、重构方案

### 方案 A（推荐）: 「3 步极简 + 后端精简」

**核心理念**: 测评 = 拍照→看结果，两步核心操作。画布标注是可选的辅助功能。视觉特征分析融入结果页而不是独立阻断页。

#### 前端: 5 步 → 3 步

```
旧流程 (5步):
  [选部位] → [上传+质量检查] → [分析进度+特征分析阻断页] → [画布标注] → [结果+历史]
  
新流程 (3步):
  [拍照评估] → [AI分析(含画布标注)] → [结果+解读]
  
  侧边栏: [评估历史]（始终可见，不随步骤切换隐藏）
```

**Step 1: 拍照评估** (合一: 部位选择 + 拍照/上传)
- 顶部: 紧凑的数字人（半屏），可点击选部位
- 下方: 拍照按钮（主操作）+ 相册按钮（次操作）
- 选部位提示: 在拍照按钮上方轻量显示
- 照片质量检查: 拍摄后内联显示，不阻断流程
- **删除**: 独立的 PhotoGuideCard（拍摄指南合并为 tooltip）
- **删除**: Step 1 中的"最近评估"列表（移到侧边栏）

**Step 2: AI 分析 + 画布标注** (合一: 分析进度 + 画布)
- 上传后直接进入分析动画（进度条 + 实时状态文字）
- 分析完成后自动展示 MaskEditor 画布
- AI 检测信息折叠为一个可展开的 info banner（默认折叠）
- 用户可选择：(A) 手动修正 → 确认 → 进入结果 (B) 直接跳过 → 进入结果
- **删除**: VisualFeatures 独立阻断页面 — 特征信息合并到结果页
- **删除**: 复杂的 AI 来源标签（"VLM 引导识别"等） — 只在 info banner 中简短提及

**Step 3: 结果 + 解读** (合一: 结果卡片 + 解读 + 趋势)
- 上半部分: VASI 评分大数字 + 核心指标（严重程度、白斑占比、阶段）
- 中部: AI 解读卡片（评分含义 + 阶段说明 + 视觉特征摘要）
- 下半部分: 趋势迷你图 + "分享"和"重新评估"按钮
- 免责声明固定在底部
- **删除**: 结果页中的完整评估历史列表（在侧边栏中）
- **删除**: FeedbackPrompt（降低摩擦，用户刚得到结果就要求反馈太激进）

**侧边栏: 评估历史**（始终可访问）
- 桌面端: 左侧固定侧边栏（w-52）
- 移动端: 底部"历史"tab 或结果页底部"查看历史"链接
- 支持: 分页、部位筛选、对比、删除

#### 组件拆分方案

```
旧结构:
  AssessmentPage.vue (10行) → AssessmentWizard.vue (731行)
  useVasiAssessment.ts (637行)

新结构:
  AssessmentPage.vue (≤200行) — 页面布局 + 侧边栏 + 步骤路由
  ├── composables/
  │   ├── useVasiUpload.ts (≤150行)       — 上传/相机/质量检查
  │   ├── useVasiAssess.ts (≤150行)       — 评估提交/结果处理
  │   └── useVasiHistory.ts (≤200行)      — 历史管理/分页/删除
  ├── components/tracker/
  │   ├── AssessmentStep1Capture.vue (≤250行)  — 部位选择 + 拍照
  │   ├── AssessmentStep2Analyze.vue (≤200行)  — AI分析 + 画布
  │   ├── AssessmentStep3Result.vue (≤300行)   — 结果 + 解读
  │   └── AssessmentHistoryPanel.vue (≤250行)  — 历史侧边栏
```

#### 后端精简方案

| 操作 | 影响 |
|------|------|
| **合并** `vasi_formula.py` + `vasi_preprocess.py` → `vasi_core.py` | -2 文件 |
| **归档** 自进化系统 (6个文件) → `vasi_evolution_archived/` | -6 文件，-3,300 行 |
| **简化** `_call_vasi_api` 降级链路: VLM→SAM→mock (3级) | 去掉 tiling、nnU-Net 中间层 |
| **关闭** VLM ensemble 默认值 | 成本减半 |
| **清理** DB 模型中未使用的列 (保留迁移脚本) | -15 NULL 列 |

**保留的自进化能力**: 
- 保留 `VasiTrainingSample` 表结构用于数据收集
- 保留 `contour_diff` 记录（AI vs 用户差异）用于离线分析
- 删除 RL optimizer、prompt evolver、param optimizer（数据不足，无法有效运行）

---

### 方案 B: 「保持 5 步 + 仅组件拆分」

保持现有 5 步流程不变，仅做代码层面的组件拆分和 composable 拆分以满足规范。改动最小，但不解决 UX 问题。

### 方案 C: 「2 步极速版」

```
[拍照] → [结果]
```
- 部位选择: 拍照后 AI 自动识别（或从 EXIF/用户历史推断）
- 画布标注: 完全隐藏，仅在用户点击"修正结果"时展开
- 历史/趋势: 独立子页面
- 风险: AI 自动识别部位可能不准

---

## 三、推荐方案对比

| 维度 | 方案 A (推荐) | 方案 B | 方案 C |
|------|:-----------:|:------:|:------:|
| **UX 简化度** | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ |
| **开发工作量** | 3-5天 | 1-2天 | 2-3天 |
| **风险** | 中 | 低 | 高(部位识别) |
| **核心功能保留** | 100% | 100% | 90% |
| **代码规范合规** | ✅ | ✅ | ✅ |
| **后端精简** | ✅ | ❌ | ✅ |

---

## 四、LLM 精度提升措施

### 4.1 简化 VLM Prompt

当前 prompt 要求输出过于复杂的结构化数据。建议:
- **分离关注点**: VLM 只做分类 + 粗略定位，不要求输出精确 bbox
- **减少输出字段**: 从 10+ 字段减少到 5 个核心字段
- **使用 Few-shot 示例**: 在 prompt 中加入 2-3 个标注好的示例

### 4.2 优化 SAM 参数

- `pred_iou_thresh`: 从 0.88 降到 0.82（减少漏检）
- `stability_score_thresh`: 从 0.92 降到 0.85（召回优先）
- 白斑检测阈值: 使用相对亮度（skin_median_L + N）而非绝对阈值，N 从 12 动态调整

### 4.3 模型选择

- VLM: 确认使用 qwen-vl-max（当前百炼最佳视觉模型）
- 如果预算允许，测试 qwen-vl-max-latest 的精度差异
- 定期对比 VLM 分类结果与用户修正结果，建立 confusion matrix

### 4.4 数据飞轮（轻量版）

- 保留 `contour_diff` 记录（已有）
- 每月一次离线分析: 找出 AI 误差最大的 50 个样本
- 人工审核并更新 few-shot 示例
- 不需要 RL pipeline

---

## 五、UI 统一设计规范

### 5.1 统一布局

整个测评流程使用**统一的单列滚动布局**（不再使用 Step 1 的特殊 ReportPage 布局）:

```
┌──────────────────────────────────┐
│  ← 返回    白斑测评    历史记录  │  ← sticky header
├──────────────────────────────────┤
│                                  │
│  [当前步骤内容]                   │  ← 统一 max-w-2xl mx-auto px-4
│                                  │
│                                  │
├──────────────────────────────────┤
│  [步骤指示器: ●○○]               │  ← 3 个圆点，current 高亮
│  [主操作按钮: 下一步/查看结果]     │  ← sticky bottom，safe-area 安全
└──────────────────────────────────┘
```

### 5.2 颜色系统

- 皮肤层标注: `primary-400`（蓝色系）
- 白斑层标注: `rose-400`（粉红系）
- 这不是硬编码 hex，使用 Tailwind 预设色板

### 5.3 画布标注 UI 简化

当前 MaskEditor 有: 3 种工具、笔刷大小、图层透明度、新手引导 tooltip、缩放/平移、撤销/重做。建议:
- 默认工具 = 白斑画笔（最常用）
- 笔刷大小 = 固定 32px（去掉调节滑块）
- 图层透明度 = 固定 0.5（去掉调节滑块）  
- 保留缩放/平移
- 新手引导: 3 秒后自动消失（当前 8 秒）

---

## 六、实施计划

| 阶段 | 内容 | 文件 | 估时 |
|------|------|------|------|
| **Phase 1** | 拆分 composable | `useVasiUpload.ts`, `useVasiAssess.ts`, `useVasiHistory.ts` | 1天 |
| **Phase 2** | 重写 3 步骤组件 | `AssessmentStep1Capture.vue`, `AssessmentStep2Analyze.vue`, `AssessmentStep3Result.vue` | 1.5天 |
| **Phase 3** | 侧边栏 + 页面布局 | `AssessmentPage.vue`, `AssessmentHistoryPanel.vue` | 0.5天 |
| **Phase 4** | 后端精简 | 合并/归档服务文件, 简化降级链路 | 1天 |
| **Phase 5** | LLM prompt 优化 | 简化 VLM prompt, 调整 SAM 参数 | 0.5天 |
| **Phase 6** | 测试 + Staging 部署 | 全流程测试, DEPLOY_LOG 记录 | 0.5天 |

**总计: ~5 天**

---

## 七、决策需要

请确认以下关键决策:

1. **流程方案**: 选择方案 A (3步) / 方案 B (5步仅拆分) / 方案 C (2步)？
2. **后端精简**: 是否同意归档自进化系统和简化降级链路？
3. **实施范围**: 是否 6 个 Phase 全部执行，还是优先某些 Phase？


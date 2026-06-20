# VASI 自我进化大模型 — 整体规划与设计方案

> 日期：2026-06-04
> 状态：规划阶段
> 目标：打通"用户端 VASI 测评 → 用户修正 → 管理后台打标 → 训练数据 → 模型进化"全闭环

---

## 0. 当前系统全景 — What We Have

### 0.1 用户端 VASI 测评流程

```
用户上传照片
  → ① 质量检测 (vasi_quality.py)
  → ② 预处理 (vasi_preprocess.py): 白平衡/对比度/缩放
  → ③ VLM 视觉分析 (qwen3-vl-plus): skin_region.bbox + suspected_lesions[].center
  → ④ SAM 引导分割 (vasi_segmentation.py): VLM centers → SAM point prompts
  → ⑤ 合并结果 → AI 初步轮廓展示给用户
  → ⑥ 用户进入 MaskEditor（轮廓编辑器）：
       - 用户涂改 AI 轮廓
       - 确认时提交 submit_contour_correction API
       - 后端计算 contour_diff、final_vasi_score、final_area_percentage
       - 记录 is_user_corrected=True
  → ⑦ 结果页：用户可选评分(1-5)、分享、停留、AI主动询问
```

**关键数据路径：** VASIAssessment 表 → user_contours + contour_diff + final_vasi_score + final_area_percentage + user_mask_image + ai_lesion_layer

### 0.2 管理后台图片打标流程

```
管理员访问 /admin/image-labels/
  → 图片列表（pending/labeled/skipped/rejected）
  → 点击某张图片进入 LabelingEditor
  → AI 预标注（复用 VASIService.assess()，蓝半透明叠加显示）
  → 管理员绘制/修改轮廓、填写诊断信息
  → 提交 admin_label_image API (POST /api/vasi/admin/image-labels/{id}/label)
  → 写入 image_labels 表 + image_label_annotations 表
  → 可选标记 training_eligible=True
  → 可选导出训练 manifest (training-export API)
```

### 0.3 自进化引擎（Phase 1+2 已实现，但数据链路未全通）

```
用户修正轮廓 → contour_diff → _upsert_training_sample → VasiTrainingSample 表
用户评分/停留/分享 → VasiFeedbackSignal 表
  ↓
管理员触发 /admin/evolution/trigger
  → PromptEvolver.build_prompt() → select_few_shot_examples()
  → 生成包含 few-shot 示例的新 prompt
  → deploy_prompt() → VasiModelVersion 表
  → 新的 VLM prompt 包含了从历史错误中学到的经验
```

**Pipeline 中已使用的入口：** `vasi.py` 的 `_call_vision_model` 方法中，在调用 VLM 前尝试加载 active prompt version（但当前默认 prompt 是硬编码的，进化版 prompt 需手动触发部署才会生效）。

### 0.4 两大数据库表体系的关系

| 系统 | 主表 | 用户修正源 | 管理员标注源 | 训练样本表 |
|------|------|-----------|-------------|-----------|
| **VASI 测评** | `vasi_assessments` | `user_contours` / `user_mask_image` | 无（仅 ImageQualityTag） | `vasi_training_samples`（从用户修正生成） |
| **图片打标** | `image_labels` | `user_body_site` 等字段 | `admin_body_site` 等字段 + `image_label_annotations` | 无（training_eligible 标记 + manifest 导出） |

**核心断点：** 两个系统的训练数据是孤岛。`VasiTrainingSample` 仅从用户修正生成，`image_labels` 中管理员的精标注数据没有被整合进进化闭环。

---

## 1. 核心断点分析 — 为什么当前进化链路不完整

### 断点 A：管理员精标注未纳入训练样本库

```
image_labels (管理员标注)  ←→  vasi_training_samples (进化引擎的样本库)
            ↑ 没有连接 ↑
```

管理员花时间精标注的图片（含轮廓、分型、分期等完整信息）没有自动转化为 VasiTrainingSample。导致最高质量的训练数据被浪费。

### 断点 B：VasiTrainingSample 的数据来源不统一

用户修正轮廓（`submit_contour_correction` → `vasi_feedback.py:_upsert_training_sample`）能生成训练样本，但**没有 body_site 中文/英文翻译、没有 fitzpatrick_type 填充、没有 admin 校准信息**。

### 断点 C：Prompt 进化未自动化

当前需要管理员手动调用 `/admin/evolution/trigger`。虽然有阈值检测 `should_evolve()`，但没有自动触发机制。

### 断点 D：评估指标闭环缺失

- 进化后的 prompt 部署后，没有**影子评估（shadow evaluation）**来量化"新 prompt 比旧 prompt 好多少"
- 没有 A/B 测试框架来安全地灰度发布
- 没有自动回滚机制

---

## 2. 整体架构设计

### 2.1 目标架构：统一训练数据飞轮

```
                    ┌──────────────────────────────────────┐
                    │         TrainingSample Hub           │
                    │     (统一训练样本管理服务)             │
                    │                                      │
                    │  • 统一入口：任何系统写入训练样本     │
                    │  • 质量评分：多维度质量评估            │
                    │  • 去重：image_hash 全局去重          │
                    │  • 进化：样本 → few-shot → prompt    │
                    └──────┬───────────────┬───────────────┘
                           │               │
           ┌───────────────┴───┐   ┌───────┴───────────────┐
           │ 用户修正通道       │   │ 管理员精标注通道       │
           │ (vasi_assessments) │   │ (image_labels)         │
           │                   │   │                        │
           │ • contour_diff    │   │ • admin annotations    │
           │ • user_mask       │   │ • admin contour        │
           │ • final_vasi      │   │ • vitiligo_type/stage  │
           │ • 隐式信号        │   │ • training_eligible    │
           └───────────────────┘   └────────────────────────┘
                      ↓                        ↓
           ┌──────────────────────────────────────────────┐
           │          VasiTrainingSample 表               │
           │  (image_hash 去重, quality_level 评分)       │
           │  + sample_source: "user_correction" |        │
           │                   "admin_labeling"           │
           └──────────────────┬───────────────────────────┘
                              │
           ┌──────────────────┴───────────────────────────┐
           │          进化引擎                            │
           │                                              │
           │  ┌─────────────────────────────────────┐     │
           │  │ Prompt 进化 (Phase 2 — 已实现)       │     │
           │  │  • 多样性筛选 few-shot              │     │
           │  │  • 版本管理 + 手动部署              │     │
           │  └─────────────────────────────────────┘     │
           │                                              │
           │  ┌─────────────────────────────────────┐     │
           │  │ 参数进化 (Phase 3 — 新增)            │     │
           │  │  • SAM 阈值调优                     │     │
           │  │  • 预处理参数调优                   │     │
           │  │  • 基于样本的 auto-tune             │     │
           │  └─────────────────────────────────────┘     │
           │                                              │
           │  ┌─────────────────────────────────────┐     │
           │  │ 影子评估 + A/B (Phase 4 — 新增)      │     │
           │  │  • shadow_eval 异步评估              │     │
           │  │  • 新旧 prompt 对比                  │     │
           │  │  • 自动部署/回滚决策                 │     │
           │  └─────────────────────────────────────┘     │
           └──────────────────────────────────────────────┘
```

### 2.2 五大进化层级

| 层级 | 进化对象 | 输入样本要求 | 进化频率 | 状态 |
|------|---------|------------|---------|------|
| **L1 - Prompt 进化** | VLM 的 system prompt + few-shot | 30+ 样本/部位 | 每 20+ 新样本 | ✅ Phase 2 已实现 |
| **L2 - 参数优化** | SAM 阈值、预处理参数 | 50+ 样本，含质量评分 | 每 100+ 新样本 | 📋 待实现 |
| **L3 - VLM 模型选择** | 按部位/skin_type 选最优 VLM | 200+ 样本/维度 | 每月 | 🔮 远期 |
| **L4 - SAM fine-tune** | SAM 模型权重微调 | 500+ 高质量 mask | 每季度 | 🔮 远期 |
| **L5 - 端到端模型** | 专用皮肤分割模型 | 1000+ 全标注样本 | 每半年 | 🔮 远期 |

**当前阶段聚焦 L1（完善） + L2（新增参数进化）。**

---

## 3. 无缝衔接方案 — 需要改造的内容

### 3.1 改造一：管理员标注 → VasiTrainingSample 自动转化

**触发点：** `admin_label_image()` API（`image_label.py` 第 360 行）

**改造思路：**
当管理员提交标注时，如果 `training_eligible=True`，自动从 `image_labels` + `image_label_annotations` 生成 `VasiTrainingSample`。

**具体步骤：**

1. **在 `vasi_feedback.py` 的 `VasiFeedbackCollector` 中新增方法：**
   ```python
   def upsert_from_admin_label(
       self, image_label: ImageLabel, admin_user_id: int
   ) -> Optional[VasiTrainingSample]:
   ```

2. **数据映射逻辑：**
   | VasiTrainingSample 字段 | 来源 |
   |------------------------|------|
   | image_hash | image_label.image_hash |
   | image_key | image_label.image_key |
   | body_site | image_label.admin_body_site or ai_body_site |
   | fitzpatrick_type | 从 ai_details JSON 提取或 VLM 重新分析 |
   | quality_level | 从 VASIAssessment.quality_report_json 提取 |
   | ai_mask_b64 | image_label.ai_details → 提取 lesion_layer |
   | ai_contours_json | image_label.ai_details → 提取 contours |
   | user_mask_b64 | image_label.user_area_percentage → 如有 |
   | user_contours_json | image_label 关联的 VASIAssessment.user_contours |
   | **admin_mask_b64** (新增) | image_label_annotations 中 source='admin' 的合并 mask |
   | **admin_contours_json** (新增) | image_label_annotations 中 source='admin' 的合并轮廓 |
   | contour_diff_json | admin vs ai 的差异 |
   | dice_score | admin_mask vs ai_mask 的 Dice |
   | area_error_pct | admin vs ai 的面积差异 |
   | confidence | image_label.ai_confidence |
   | assessment_source | 从关联的 VASIAssessment 获取 |
   | **sample_source** (新增) | "admin_labeling" |

3. **VasiTrainingSample 表需要新增的字段：**
   ```sql
   ALTER TABLE vasi_training_samples ADD COLUMN admin_mask_b64 TEXT;
   ALTER TABLE vasi_training_samples ADD COLUMN admin_contours_json TEXT;
   ALTER TABLE vasi_training_samples ADD COLUMN sample_source TEXT DEFAULT 'user_correction';
   -- sample_source: 'user_correction' | 'admin_labeling' | 'batch_import'
   ALTER TABLE vasi_training_samples ADD COLUMN vitiligo_type TEXT;
   ALTER TABLE vasi_training_samples ADD COLUMN vitiligo_stage TEXT;
   ```

4. **调用点：** 在 `admin_label_image()` 的最后添加：
   ```python
   if label.training_eligible:
       from web.backend.services.vasi_feedback import get_feedback_collector
       collector = get_feedback_collector(db)
       collector.upsert_from_admin_label(label, admin_user.id)
   ```

### 3.2 改造二：用户修正路径增强

**当前问题：**
`_upsert_training_sample()` 已能从用户修正生成训练样本，但缺少以下信息：
- body_site 可能是英文（`bodySites.ts` 的 key），需统一翻译
- fitzpatrick_type 未填充（需要从 raw_api_response 提取）
- vitiligo_type/stage 未记录

**改造步骤：**

1. **完善 `_upsert_training_sample()` 方法：**
   - 从 `VASIAssessment.raw_api_response` 提取 `skin_region.fitzpatrick_type`
   - 确保 body_site 为中文标签
   - 新增 `vitiligo_type`、`vitiligo_stage` 从 assessment 字段提取
   - 设置 `sample_source = "user_correction"`

2. **增强 `compute_contour_diff` 输出：**
   - 当前仅返回 avg_point_distance、match、modified
   - 需要新增：**dice_score**（mask IoU）、**area_error_pct**（面积差异百分比）
   - 计算公式：
     ```python
     # 已有 user_mask 和 ai_lesion_layer，直接逐像素计算
     dice = 2 * intersection / (ai_pixels + user_pixels)
     area_error_pct = (user_pixels - ai_pixels) / user_pixels * 100
     ```

### 3.3 改造三：统一训练样本管理中心

**新增服务文件：** `web/backend/services/vasi_training_hub.py`

**职责：**
- 统一所有训练样本的 CRUD 操作
- 质量评分：根据 image quality tag + dice + admin validation 计算综合质量分
- 去重策略：image_hash 全局唯一，admin_labeling 优先级 > user_correction（管理员标注覆盖用户修正）
- 样本审计日志：记录哪些样本被用于 few-shot、哪些被淘汰

**API 接口：**
```
GET  /api/vasi/admin/training/stats          — 样本库统计（按来源、部位、质量）
GET  /api/vasi/admin/training/samples        — 样本列表（支持多维筛选）
POST /api/vasi/admin/training/samples/{id}/quality — 管理员手动调整样本质量
POST /api/vasi/admin/training/sync           — 手动触发全量同步（从 image_labels 和 vasi_assessments）
DELETE /api/vasi/admin/training/samples/{id}  — 移除低质量样本
```

### 3.4 改造四：Shadow Evaluation（影子评估）

**目标：** 在有新 prompt 版本时，异步对比新旧 prompt 在相同样本上的表现，量化提升幅度。

**新增服务：** `web/backend/services/vasi_shadow_eval.py`

**流程：**
```
Deploy prompt v3 → 触发 shadow_eval
  → 从 VasiTrainingSample 随机抽取 20 个样本（stratified by body_site）
  → 对每个样本：
      ① 用旧 prompt + VLM 分析原图 → 旧结果
      ② 用新 prompt + VLM 分析原图 → 新结果
      ③ 计算旧结果 vs ground truth (admin/user mask) 的 Dice、area_error
      ④ 计算新结果 vs ground truth 的 Dice、area_error
  → 汇总对比报告：
      - recall 提升/下降百分比
      - precision 提升/下降百分比
      - 各部位的提升分布
      - 提升显著的案例 + 反而退化的案例
  → 写入 VasiModelVersion.metrics_json
```

**决策阈值：**
- 如果 F1 提升 > 5% → 保留新版本
- 如果 F1 下降 > 5% → 自动回滚到旧版本
- 中间状态 → 标记为 "pending_review"，需管理员手动确认

### 3.5 改造五：自动化进化触发

**当前：** 管理员手动点击 `/admin/evolution/trigger`

**改造为：**
```python
# vasi_feedback.py 中
def record_explicit_correction(self, ...):
    # 每次用户修正后，检查是否达到自动进化阈值
    new_count = self.count_training_samples(quality_level=None, min_dice=0.4)
    if new_count >= self.last_evolution_count + self.AUTO_EVOLVE_THRESHOLD:
        self._schedule_auto_evolution()
```

**触发条件（可配置）：**
- 新增 20+ 个高质量 training sample
- 或 每周定时检查（cron job）
- 或 管理员手动触发

**安全机制：**
- 自动进化仅在 staging 环境验证通过后才可推送到生产
- 每次进化保留前 3 个版本（用于快速回滚）
- 如果 shadow eval 发现退化，自动中止并通知管理员

### 3.6 改造六：Pipeline 中接入进化版 Prompt

**当前状态：** `_call_vision_model()` 已在加载 active prompt version，但默认仍用硬编码 prompt。

**验证点：**
检查 `vasi.py` 中 `_call_vision_model()` 的第 ~370 行是否已接入 `get_prompt_evolver()`。如果是，确认部署后的 prompt 能在下一次 VLM 调用时生效。

**改造：** 确保进化 prompt 在 `assess_vasi()` 的 VLM 调用路径中被使用，且有 fallback 到默认 prompt。

---

## 4. 数据流总结

```
                     用户端                              管理后台
                        │                                   │
         ┌──────────────┼──────────────┐       ┌────────────┼────────────┐
         ▼              ▼              ▼       ▼            ▼            ▼
   上传照片        VLM+SAM分析     AI轮廓展示  图片列表   标注编辑器   提交标注
         │              │              │       │            │            │
         │              │              │       │            │            │
         └──────────────┼──────────────┘       └────────────┼────────────┘
                        │                                   │
                        ▼                                   ▼
              VASIAssessment                         image_labels
              + user_contours                    + image_label_annotations
              + contour_diff                     + admin_body_site
              + user_mask                        + admin_contour
              + final_vasi                       + training_eligible
                        │                                   │
                        └────────────┬──────────────────────┘
                                     │  (改造一：自动转化)
                                     ▼
                          ┌─────────────────────┐
                          │ VasiTrainingSample   │
                          │ (统一训练样本库)      │
                          │ sample_source:       │
                          │  'user_correction'   │
                          │  'admin_labeling'    │
                          └──────────┬──────────┘
                                     │  (多样筛选 + few-shot 组装)
                                     ▼
                          ┌─────────────────────┐
                          │ VasiModelVersion     │
                          │ (Prompt 版本管理)     │
                          │ + shadow_eval 指标   │
                          └──────────┬──────────┘
                                     │  (进化prompt注入VLM调用)
                                     ▼
                          ┌─────────────────────┐
                          │ VLM API 调用         │
                          │ (使用进化版 prompt   │
                          │  含 few-shot 示例)   │
                          └─────────────────────┘
                                     │
                                     ▼
                          更好的 AI 预标注结果
                          更少的用户修正需求
```

---

## 5. 改造工作清单（按优先级排序）

### Phase 1A：补全数据链路（P0，~2天）

| # | 任务 | 文件 | 改造量 |
|---|------|------|--------|
| 1 | `_compute_contour_diff` 新增 dice_score + area_error_pct | `vasi.py` | ~30 行 |
| 2 | `_upsert_training_sample` 完善字段填充（fitzpatrick、body_site 翻译、vitiligo_type） | `vasi_feedback.py` | ~40 行 |
| 3 | 新增 `upsert_from_admin_label()` 方法 | `vasi_feedback.py` | ~80 行 |
| 4 | VasiTrainingSample 表新增字段（admin_mask、sample_source、vitiligo_type/stage） | `vasi.py` models | ~20 行 + migration |
| 5 | `admin_label_image()` 调用 `upsert_from_admin_label` | `image_label.py` | ~10 行 |
| 6 | 验证 `_call_vision_model` 正确接入进化 prmopt | `vasi.py` | ~20 行检查 |

### Phase 1B：统一训练样本中心（P1，~1天）

| # | 任务 | 文件 | 改造量 |
|---|------|------|--------|
| 7 | 新增 `vasi_training_hub.py` 服务 | 新文件 | ~200 行 |
| 8 | 新增训练样本管理 API（list/stats/sync/quality） | `vasi.py` API | ~100 行 |
| 9 | 管理后台"训练样本"页面（可选，先只做 API） | admin | 可选 |

### Phase 2：Shadow Evaluation（P2，~2天）

| # | 任务 | 文件 | 改造量 |
|---|------|------|--------|
| 10 | 新增 `vasi_shadow_eval.py` 服务 | 新文件 | ~250 行 |
| 11 | 进化触发后自动运行 shadow eval | `vasi_prompt_evolver.py` | ~40 行 |
| 12 | shadow eval 结果写入 metrics_json + 展示在 admin | `vasi.py` API | ~30 行 |
| 13 | 自动回滚逻辑（F1 下降 > 5%） | `vasi_prompt_evolver.py` | ~30 行 |

### Phase 3：自动化闭环（P3，~1天）

| # | 任务 | 文件 | 改造量 |
|---|------|------|--------|
| 14 | 自动进化触发（新增 20+ 样本时） | `vasi_feedback.py` | ~30 行 |
| 15 | 参数进化框架（SAM 阈值 auto-tune） | 新文件 | ~300 行 |
| 16 | 进化仪表板（admin 统计页面） | admin | 可选 |

---

## 6. 预期提升效果

### 阶段性量化目标

| 阶段 | 指标 | 当前基线 | 目标 |
|------|------|---------|------|
| Phase 1 完成 | Dice score (AI vs 用户 mask) | ~0.45-0.55（估计） | 0.60+ |
| Phase 1 完成 | 白斑漏检率 | ~30-40%（估计） | < 25% |
| Phase 2 完成 | 用户修正率（需要手动改轮廓的用户比例） | ~70-80%（估计） | < 50% |
| Phase 2 完成 | 主动询问"不准确"反馈率 | 未知 | 下降 30% |
| Phase 3 完成 | 平均用户修正时间 | ~30-60s（估计） | < 20s |

### 进化效果示意

```
进化轮次:  0 ──── 1 ──── 2 ──── 3 ──── 4 ──── 5 ...
         (初始)  (20样本) (40样本) (80样本) (150样本) ...

F1 Score: 0.55 → 0.62 → 0.67 → 0.71 → 0.74 → ...

                ↑每轮few-shot从最新的高质量样本中学习
                    覆盖更多部位/肤色/光照条件
```

### 为什么这个方案能有效

1. **Few-shot 是 VLM 最强的能力之一** — 好的示例比规则调参效果好一个数量级
2. **数据飞轮加速** — 用户越多，修正越多，样本越丰富，AI 越准确，用户越愿意用
3. **管理员标注是 gold standard** — 皮肤科知识的精标注高于用户的自我修正，能修正用户可能的错误判断
4. **部位 × 肤色 的组合爆炸** — 12个部位 × 6种肤色 = 72种场景组合。只有通过不断积累和自动选择才能覆盖
5. **影子评估保证安全** — 不会因为一次坏的进化搞垮线上质量

---

## 7. 风险与缓解

| 风险 | 概率 | 缓解措施 |
|------|------|---------|
| 用户修正不准确（非皮肤科医生） | 高 | admin_labeling 权重 > user_correction；dice_score 明显异常(<0.3)的样本标记为 low_quality |
| few-shot 示例过多导致 prompt 过长、成本翻倍 | 中 | 限制 MAX_FEW_SHOT=3；按部位+肤色精选；监控 token 消耗 |
| VLM 对 few-shot 过度拟合（按示例的模式回答而非分析图片） | 中 | 多样性约束（不同示例的关键差异不重复）；影子评估检测退化 |
| 管理员标注量不足（初期只有少量 labeled 图片） | 高 | 用户修正也可生成 sample；降低 early-stage 的 sample 阈值(10→20→50) |
| 隐私风险（训练样本含用户照片数据） | 低 | image_hash 脱敏；不存储原始图片 URL 在 training sample 中；`is_user_deleted` 标记处理 |
| DB 膨胀（vasi_training_samples 存储 base64 mask） | 中 | 限制 mask 分辨率 256px；定期归档旧版本样本；考虑迁移到文件存储 |

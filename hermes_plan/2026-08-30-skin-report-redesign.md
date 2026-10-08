# 白斑变化报告（多选分析）整体重构规划

> 日期：2026-08-30
> 范围：`SkinReportViewPage.vue`（对比报告页）+ `web/backend/services/`（skin_report / spot_compare / photo_align）
> 目标：报告以「前后对比」为中心、极简客观、可分享；白斑识别与变化判定与白斑测评共用**一套模型、一套标准**。

---

## 一、问题诊断（用户反馈 → 代码根源）

| # | 用户反馈 | 代码根源 |
|---|---------|---------|
| 1 | 变化时间轴=照片堆叠，夜间看不出对比 | `skin_report.py::_build_timeline_stack()`（L724-827）：PIL 中心裁方+亮度对齐堆叠，**日期直接烧印在照片内部左上角**（L792-810），本质是缩略图拼贴，不构成对比 |
| 2 | 日期遮挡照片；对比应默认首末、可切换 | `BeforeAfterSlider.vue:79-84` 日期 pill 浮层盖在图上；`timeline_stack` 日期烧字；且 `pair_metrics` 只为首末对和 max 对计算，无法切换任意日期 |
| 3 | 热力图不准，衣服被标成"复色" | `photo_align.py::align_and_diff()`（L58-164）：ORB 配准后**纯灰度亮度差分**（阈值±20），`变暗=绿色=复色`——**无皮肤掩膜、无白斑掩膜**，衣服换色/阴影/背景变暗全部误判为复色；且对比 prompt（`spot_compare.PAIR_COMPARE_PROMPT` L85-132）**缺少测评 prompt 里的"排除衣物/背景"指令** |
| 4 | "变化最明显"与"前后对比"重复 | `_pick_max_change_pair()`（L669-699）：CV 快扫+条件 VLM 挑变化最大图对，与首末对比并列展示，信息重复，还多花一次 VLM 调用 |
| 5 | 标题一句话太长、无层次 | 封面 `metrics.headline` 为 LLM 生成的整句周报式标题（周报/月报），对比报告复用同一封面结构 |
| 6 | 分析/洞察/建议太长、有误导与合规风险 | `narrative_sections`/`insights`/`recommendations` 由 `_call_report_llm()`（L546-587）用 chat 模型基于 metrics 生成，非医生视角长文 |
| 7 | 需要专业美观、可分享 | 已有 PDF（html2canvas）/海报（Canvas 手绘）/社区分享/链接 4 种方式，海报与新版式需同步改版 |

**关键事实**：测评与报告已共用同一视觉模型配置（`get_llm_config("vasi")` → 默认 qwen-vl-max），但 prompt、皮肤掩膜、质量门禁、复色定义**各自为政**——这是"两套标准打架"的根源。

---

## 二、设计原则

1. **一张图胜过一段话**：结论用对比图 + 客观数字表达，文字只做客观事实陈述（面积 A%→B%），不做医学解读、不给建议。
2. **不精确就不展示**：任何可视化（热力图/对齐视图/指标）在置信度不足时降级为"无法可靠分析 + 原因"，绝不输出似是而非的结果。
3. **一套标准**：白斑识别的模型、prompt 基座、皮肤掩膜、脱失分级、质量门禁全站唯一，报告对比建立在测评产物（分割层/画布掩膜）之上，不另起炉灶。
4. **对比报告 ≤ 2 屏**：封面 + 前后对比 + 客观指标 + 极简变化摘要 + 免责声明，完。

---

## 三、新版对比报告信息架构

```
┌────────────────────────────────────────────┐
│ ① 封面（分层标题，≤3 行）                    │
│   [对比报告] 徽章                           │
│   主标题：手部 · 白斑变化报告                │
│   副标题：2026-06-01 → 2026-08-30 · 4 次记录│
│   指标 chips：复色中 ▲ · 复色指数 62→74 ·   │
│              白斑面积 -1.4%（客观数字）      │
├────────────────────────────────────────────┤
│ ② 前后对比（核心，置顶）                     │
│   日期选择行：[06-01][06-20][07-15][08-30]  │
│   ↳ chips 仅含本次所选照片日期，默认选中     │
│     首末两张；点选即切换对比对（无需日历）    │
│   日期标签在图片上方/下方（不遮挡照片）       │
│   视图：并排 / 滑块 / 叠影 / 动画（保留）     │
│   变化要点 chips + 置信度提示（保留）         │
├────────────────────────────────────────────┤
│ ③ 变化热力图（Phase 2 重做后展示；           │
│   不达标时整块隐藏，显示原因文案）            │
├────────────────────────────────────────────┤
│ ④ 变化摘要（极简，仅客观事实）               │
│   · 白斑面积 6.2% → 4.8%（-22%）            │
│   · 复色指数 55 → 72，边缘内收、点状复色     │
│   每条一句话，无解读无建议                    │
├────────────────────────────────────────────┤
│ ⑤ 免责声明一行 + 操作栏（PDF/海报/分享/链接）│
└────────────────────────────────────────────┘
  删除：变化时间轴、来源报告、变化最明显、
        AI 分析、关键洞察、建议 六个区块
```

---

## 四、逐点设计

### 1. 变化时间轴 → 删除
- 前端删除 section（`SkinReportViewPage.vue:374-389`）；"看不同时间点"的需求由 ② 的日期 chips 承担（时间轴的正确形态就是切换器本身）。
- 后端新报告停用 `_build_timeline_stack()`（省时省钱）；`timeline_stack_url` 字段保留兼容旧报告（前端已不渲染）。
- 旧报告该字段不再展示，无迁移成本。

### 2. 前后对比置顶 + 日期 chips 切换
**前端**：
- `SkinReportViewPage.vue`：对比 section 移到封面后第一位；数据源用 `metrics.timeline_frames`（每点已含 `date`/`image_url`/`body_site`/vasi 字段，`_build_points()` L140 已产出）。
- 新增 `PairDateSwitcher` 组件：两行 chips（前/后各一行）或单行点选两张；默认选首末；选中态 `bg-primary-50 text-primary-700`；chips 上对低质量照片显示 ⚠ 光线不足角标。
- 切换时调用新 API 拉取该日期对的 `pair_metrics` + `pair_align`，加载态骨架屏（VLM 对比需数秒）。
- `ComparisonViews.vue`：并排视图已有图片下方 figcaption（保留统一为图上方案签）；`BeforeAfterSlider` 浮层 pill 移出图片——改为滑块容器上方左右两个日期标签；叠影/动画视图标签同步外移。
- 删除"变化最明显"section（`:544-558`）。

**后端**：
- 新增 `GET /api/skin-reports/{report_id}/pair-compare?index_a=&index_b=`：
  - 鉴权：报告所有者（分享页不支持切换，仅展示默认对）；
  - 复用 `spot_compare.compare_pair()`——其结果天然缓存在 `spot_comparisons` 表（ref_a/ref_b 唯一索引），二次切换零成本；
  - 对齐图复用 `_save_aligned_pair()`，新增按 (ref_a, ref_b) 的文件缓存避免重复配准；
  - 返回结构与首末对一致（`PairMetrics` + `PairAlign`），前端零特判；
  - 限制：单报告照片 2-4 张 → 最多 6 对；加简单频控（VLM 调用有成本）。

### 3. 变化热力图 → 基于"白斑掩膜差分"重做（Phase 2 核心）
**现状问题**：`align_and_diff` 纯灰度差分，无皮肤约束 → 衣服/阴影全中。
**新管线**（`photo_align.py` 重写 diff 部分，配准保留 ORB+RANSAC）：
1. B 图配准到 A 图（现有逻辑，保留）；
2. 双侧皮肤掩膜：统一调用测评侧 `vasi_skin_mask.build_skin_mask`，取配准后交集（仅两侧都可见的皮肤参与分析）；
3. 白斑掩膜获取：
   - `va:` 来源（测评照片）→ **直接复用 `VASIAssessment.ai_lesion_layer` / `user_lesion_layer`**（SAM 精修 + 用户手工修正过的掩膜，最强统一复用点）；
   - `pi:` 来源（相册照片）→ 跑测评同款 guided 分割（`vasi_segmentation.segment_vitiligo_guided`，VLM 定位 + SAM）；
4. 掩膜差分分类（配准空间内逐像素）：
   - **复色** = A 为白斑（脱失≥1 级）且 B 恢复肤色（0 级）→ 绿色
   - **扩大** = 白斑区域增大 → 红色
   - **新发** = B 新增白斑 → 琥珀色
   - 稳定 → 不着色
5. **门禁**（任一不满足则不出热力图，显示"照片角度/光线差异较大，无法生成可靠热力图"）：
   - 配准内点数达标（现有 good/inlier 门槛）；
   - 两侧照片 `vasi_quality_checker` 均 non-poor、亮度差在阈值内（现有光线不匹配检测复用）；
   - 白斑掩膜置信度 ≥ 阈值。
6. 图例改为与分类一致：绿=复色、红=扩大、琥珀=新发；文案删掉"基于亮度差异生成"。

### 4. 删除"变化最明显"
- 前端删 section；后端 `_pick_max_change_pair()` 不再调用（每次报告省 0-1 次 VLM + 全量 CV 快扫）；字段保留兼容。

### 5. 封面标题分层
- 弃用 LLM `headline` 整句；封面改为固定结构（见架构图 ①）：徽章（报告类型）+ 主标题（`body_site` + 固定词"白斑变化报告"）+ 副标题（起止日期 · 记录次数 · 跨越天数）+ 客观指标 chips（复色指数 A→B、面积变化 %、趋势词：复色中/稳定/扩大中——趋势词沿用 `metrics.trend`，不新增解读文字）。
- 周报/月报封面 `headline` 若超长则截断为副标题，主标题同样固定结构（本次一并统一）。

### 6. 分析/洞察/建议 → 客观"变化摘要"
- **对比报告后端停用 `_call_report_llm()`**：不再生成 narrative/insights/recommendations（省 LLM 成本、消除误导与合规风险）；字段置空，前端条件渲染自动隐藏。
- 新增"变化摘要"块：由 `pair_metrics` 直接拼装，每部位 1-2 条客观事实（面积变化、复色指数变化、复色模式阳性项）；`low_confidence` 时仅追加一句"照片条件差异较大，结果仅供参考"。
- 文案红线：不出现"建议/治疗/用药/预后"等词；免责声明保留（"本报告基于照片的客观比对，不构成医疗建议"）。
- 周报/月报的 HealthReportSections（心情/体检/问答）不在本次范围，后续单独评估。

### 7. 分享专业化
- **海报 `SkinReportPoster.vue` 改版**：新版式 = 品牌 + 分层标题 + 大图前后对比（日期已在图下方，保持）+ 2-3 个客观指标 chips + 二维码；**删除海报中的 AI 摘要**（合规）。
- **分享页 `SkinReportSharedPage.vue`**：同步新版式；`_strip_private_metrics` 继续剥离热力图/对齐图（对齐图即医疗照片，公开页只保留并排原图 + 指标）。
- PDF：html2canvas 截取新 DOM，自动继承新版式；校验分页不切断对比图。

---

## 五、与白斑测评的统一（一套模型一套标准）

新建 `web/backend/services/vitiligo_vision_standard.py`（Phase 3 固化），作为唯一"白斑视觉标准"：

| 统一项 | 唯一来源 | 消费方 |
|-------|---------|-------|
| 视觉模型配置 | `get_llm_config("vasi")`（现状已共用，维持） | 测评 / 报告对比 / 轻量分析 |
| prompt 基座 | 标准模块导出：脱失分级 0-3 + Fitzpatrick 基线 + **"衣物/背景/参考卡非皮肤，一律排除"** + 复色三模式定义；单图测评与双图对比 prompt 由此拼装，仅输出 schema 不同 | `VASI_VISION_PROMPT` / `PAIR_COMPARE_PROMPT` |
| 皮肤掩膜 | `vasi_skin_mask.build_skin_mask` | 测评分割 / 热力图 / `_cv_measure` / 质检 |
| 复色定义 | 脱失等级下降或复色模式阳性；VLM `melanin.score` 与 0-3 级锚定映射 | 测评 stage / 报告 pair_metrics / 热力图分类 |
| 质量门禁 | `vasi_quality_checker`（同阈值）：poor → 测评拒绝、报告警示并降置信度 | 测评 / 报告对比 / 热力图 |
| 分割产物 | `VASIAssessment` 的 lesion 层与 `canvas_json` 掩膜，报告 `va:` 来源直接复用（含用户修正） | 报告对比 / 热力图 |

- Admin 后台提示词编辑：两个 key（`vasi/vision_analysis`、`skin_report/comparison_report`）改为"基座 + 任务段"结构，改基座全站生效。
- 回归保障：`llm-testing` skill 建固定照片对回归集（同一组照片 → 断言复色/扩大/新发判定与脱失分级一致），prompt 或模型变更必跑。

---

## 六、分阶段实施

### Phase 1：报告重构（前端为主 + 1 个新接口）
| 改动 | 文件 |
|------|------|
| 页面重排：对比置顶、日期 chips、删时间轴/变化最明显/AI 分析/洞察/建议 | `web/app/src/views/SkinReportViewPage.vue` |
| 新组件：日期切换器（chips、加载态、低质量角标） | `web/app/src/components/report/PairDateSwitcher.vue`（新增） |
| 日期标签外移出图片 | `ComparisonViews.vue`、`BeforeAfterSlider.vue` |
| pair-compare API 封装 | `web/app/src/api/skin_report.ts` |
| 新接口 `GET /skin-reports/{id}/pair-compare`（复用 compare_pair 缓存 + 对齐文件缓存） | `web/backend/api/skin_report.py`、`services/skin_report.py` |
| 生成管线瘦身：停用 timeline_stack / max_change_pair / narrative LLM；产出"变化摘要"与封面指标 chips 所需字段 | `services/skin_report.py` |
| 海报改版（去 AI 摘要、新标题结构） | `web/app/src/components/diary/SkinReportPoster.vue` |
| 分享页同步 | `SkinReportSharedPage.vue` |

### Phase 2：热力图精准化（后端）
- `services/photo_align.py`：掩膜差分管线（皮肤掩膜交集 + 白斑掩膜 + 四分类渲染 + 门禁）；
- `services/spot_compare.py`：PAIR_COMPARE_PROMPT 换用统一基座（补"排除衣物/背景"）；
- `pi:` 来源照片接入 guided 分割（复用 `vasi_segmentation`）。

### Phase 3：标准固化与回归
- `vitiligo_vision_standard.py` 基座模块落地，两个 prompt key 迁移；
- llm-testing 回归集；Admin 提示词后台适配；`docs/specs/` 补设计文档。

### 部署与风险（遵循 AGENTS.md）
- ⚠️ Phase 1/2 均含后端改动（共享后端，**立即影响正式环境**）：新接口为纯增量（低风险）；停用 narrative/timeline/max_pair 为行为变更（旧报告不受影响，字段保留）；热力图重写影响新生成报告。
- 前端改动 → `npm run build` 部署 staging；后端改动前向用户预警；全部记录 DEPLOY_LOG.md。

### 验收标准
1. 报告首屏即前后对比，日期 chips 可切换任意所选照片对，默认首末；
2. 任何日期标签不遮挡照片；
3. 衣物/背景不再出现"复色"标注（用含换色衣物的照片对回归验证）；不达标时热力图整体隐藏并给出原因；
4. 报告全文无"建议/治疗"类表述，变化摘要每条 ≤ 1 行；
5. 夜间/模糊照片有明确警示标识；
6. 海报/PDF/分享页版式与页面一致、专业美观；
7. 同一照片在测评与报告中的脱失分级、面积、复色判定一致（回归集断言）。

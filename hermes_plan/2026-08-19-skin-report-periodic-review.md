# 白斑周报/月报功能 — 规划同行评审与补充方案

> 本文件是对 GLM-5.3 已产出规划（`.zcode/plans/plan-sess_63fbeec4-c264-4224-919a-e9bf138e45ee.md`）的**同行评审 + 补充优化版**。
> 目的：在动手编码前，把「GLM-5.3 考虑到的」和「还没考虑周全的」一起摆到桌面上，供 LianqingChan 统一决策。
> 结论先行：GLM-5.3 的方向是对的（复用 SkinReport 已有端到端链路，补齐「配对对比引擎 + 周期报告」），基础盘点基本准确；但存在 **1 处事实错误、若干隐私/医疗合规/工程健壮性遗漏**，需要在编码前补齐。

---

## 1. 当前进度快照（同步跟进结果）

- **GLM-5.3 当前阶段**：规划阶段（已完成规划初稿，文件最后更新于 2026-08-19 00:52）。
- **规划结论**：白斑对比报告（SkinReport）已端到端存在，`skin_reports.report_type` 已预留 `weekly/monthly`，本次是「补齐已规划好的第二期」，不另起炉灶。
- **规划主线**：P0 配对识别引擎（spot_compare）→ P1 周报/月报引擎 → P2 前端周期版式+含照片海报 → P3 补录+自动生成 → P4 导航同步+部署。
- **代码是否已改动**：截至评审时，未见 spot_compare / generate_periodic_report 等新代码落地（services/ 下无 `spot_compare.py`，`skin_report.py` 仍只有 `generate_comparison_report`），说明仍在规划、尚未开工。

> 说明：本次评审基于对现有代码的实际核对（`skin_report.py`、`api/skin_report.py`、`database/models.py`、`models/vasi.py`、`diary_image.py`、`vasi_quality.py`、`vasi_segmentation.py`、`llm_config_service.py`、`main.py`、`api/notifications.py`、前端 `SkinReport*Page.vue`、`bodySites.ts`、`file-url.ts`）。

---

## 2. 需要修正的事实性错误（GLM-5.3 盘点的偏差）

| # | GLM-5.3 原文 | 实际情况 | 修正建议 |
|---|---|---|---|
| C1 | P0 需「注册 `skin_report` 到 `llm_config_service.py` 的 `DEFAULT_MODULES`」 | **已经注册**（`llm_config_service.py:135`，module_name="白斑报告生成"） | 该步骤可删除；只需确认 `skin_report` 模块有可用的视觉模型配置（视觉模型 key 走 `vasi` 模块，见 C2） |
| C2 | 复用「`vasi` 的视觉模型配置」 | `diary_image.py:127` 确实 `get_llm_config("vasi")` 取 `vision_model`；但 `skin_report.py` 当前 `_call_report_llm` 用的是**文本** `chat_model`（对比报告叙事） | spot_compare 的双图对比属**视觉**调用，应明确走 `vasi` 模块的 `vision_model`，而非 `skin_report` 的 `chat_model`。两套模型/配置要分开表述，避免实现时取错 |
| C3 | 「VASI 测评照片按 image_hash 去重，与 post_images 合并」 | `vasi_assessments` 有 `image_hash`；但 `post_images` **没有 image_hash 字段**（只有 `image_url`） | 跨源去重无法靠 image_hash 对齐。需改用 `image_url` 匹配，或为 `post_images` 补 image_hash；同时注意 `post_images.vasi_assessment_id` 已单向关联了部分 VASI，合并时要先去重避免同一张照片被算两次 |
| C4 | 「周期窗口过滤」对 VASI 数据用照片日期 | `vasi_assessments` 的日期字段是 `assessment_date`（DateTime），**不是** `capture_date`；`post_images` 才有 `capture_date` | 周期窗口对 VASI 用 `assessment_date`，对 post_images 用 `capture_date`，两者字段名不同、时区不同（见 G10），实现时要分别处理 |

---

## 3. 遗漏的风险点与补充（按严重程度排序）

### 🔴 P0 级：隐私与 L3 数据保护（AGENTS.md 生死线，必须前置解决）

GLM-5.3 的规划只字未提新增资产（封面拼图、海报、周报详情）在**公开分享链路**下的脱敏问题，这是本次最关键的遗漏。

- **G1 — `cover_composite_url` 是新的 L3 资产，公开页会泄露**：
  现有 `api/skin_report.py:55` 的 `_report_to_dict(include_private=False)` 只剥离了 `metrics.first/last.image_url`，**没有剥离** `cover_composite_url`。周报一旦写入封面合成图，公开分享页 `/share/report/{token}` 会把「各部位前后对比照片拼图」直接吐给未登录访客 → 等于把病情照片（L3）公开。**必须**在 P1 同步扩展公开脱敏：`include_private=False` 时同时移除 `cover_composite_url` 与 `metrics`/`source_data` 内所有 `image_url`。
- **G2 — 海报是新的公开传播媒介，必须带免责声明**：P2 海报规划只有「大字 headline + 指标芯片 + QR 码」，未要求「本文不构成医疗建议」免责声明。海报会被用户保存/转发，必须固定包含免责声明（现有对比报告网页版有，海报没有）。
- **G3 — EXIF 只取 `DateTimeOriginal` 但未提 GPS 风险**：P3 从 EXIF 取拍摄日期没问题，但 EXIF 常含 GPS 经纬度（病情照片 = 家庭住址级隐私）。服务端必须**只解析日期、剥离/丢弃其余 EXIF（尤其 GPS）**，且不持久化原始 EXIF。
- **G4 — backfill 脚本越权风险**：`backfill_spot_comparisons.py` 若按「用户+部位+日期」遍历，会处理**其他用户**的照片（既烧 VLM 成本，也触碰他人 L3 数据）。脚本必须默认只对**指定单个 user_id** 运行，并打印将处理的照片数供确认后再执行。
- **G5 — 自动生成的站内通知**：P3「完成发站内通知」需明确复用 `api/notifications.py:82` 的 `create_notification(db, user_id, type, title=..., body=..., ...)`（注意它在 api 层，服务/调度器调用属跨层 import，需评估是否下沉到 service）。

### 🟠 P1 级：医疗合规（量化指标措辞）

- **G6 — 周报引入了更强的「数值化」结论**：对比报告只用 VASI 数值 + 轻量摘要；周报/月报新增「复色指数 / 面积变化% / 边缘内收」等由 VLM+CV 估算出的**半定量指标**。这类数字比「好转/稳定/加重」更像诊断，需在周报专用 LLM prompt 中**强制**：措辞用「观察到/估算/建议」，并加「以上为照片估算值，精确评估请就医/做深度白斑评估」；当 `confidence < 阈值` 时明示「置信度低，不作结论」。GLM-5.3 已强调「诚实比好看重要」，这点方向对，但要落到 prompt 与 UI 的硬约束上。
- **G7 — 周报正文与海报必须有免责声明兜底**：与 G2 同理，覆盖网页版、PDF、海报、社区分享四类出口。

### 🟡 P2 级：工程健壮性

- **G8 — `spot_comparisons` 表设计**：
  - 唯一索引 `(image_a_id, image_b_id)` 有方向性，(A,B) 与 (B,A) 会成两行 → 需**规范化顺序**（如始终「旧图在前」）并在写入层强制，或改存规范化 pair_key；
  - 建议唯一索引加 `body_site`，避免跨部位误命中；并补 `(user_id, body_site)` 查询索引；
  - `metrics_json` 需定义**版本化 schema**（`model_version` 已有，但字段结构要写死），否则周报聚合端解析不稳定。
- **G9 — 异步生成的生命周期不完整**：P1 的「后台线程生成(status=generating)」缺三件事：
  1. 幂等要落到**唯一约束** `(user_id, report_type, period_start)`（防并发重复生成），不能只靠「查已有则返回」的应用层判断；
  2. 失败/超时要有兜底：后台线程异常时把 status 置 `failed` 并写 `error_message`（字段已存在），否则用户永远看到「生成中」；建议加一个「超时/孤儿状态回收」；
  3. 线程池要受控（复用有界 executor），避免多用户同时生成打满线程。
- **G10 — 时区与周期边界**：`capture_date` 是 naive Date，`assessment_date` 是 UTC DateTime，混用会出「周一/月末」的 off-by-one。必须统一为 **Asia/Shanghai（UTC+8）**，并明确 weekly 的 period_start/period_end 计算函数，含「周期前最近一张基线照片」的边界定义（首周无基线时如何降级）。
- **G11 — 封面/海报文件的生命周期**：删除报告时（`DELETE /{report_id}` 现仅删行）不会删除 `cover_composite_url` 对应文件 → 孤儿文件累积 + 数据留存合规风险。删除报告需连带清理生成物；周报月报累积也需考虑留存/归档策略。
- **G12 — 现有报告页的合规债**：`SkinReportViewPage.vue`/`SkinReportListPage.vue` 当前**违反 AGENTS.md 设计规范**（硬编码 teal 十六进制 `#0f766e/#14b8a6/#0d9488` 而非 `primary-*`、容器 `max-width:800px` 而非 `max-w-6xl`、标题「白斑变化报告」而非唯一事实源里的「白斑报告」）。P2 若只加周期版式、不顺手统一，会让同一模块内两套风格并存。建议把「报告模块命名与主题色统一」纳入 P2 显式范围，并决策是否 retrofitting 现有对比报告页。

### 🟢 P3 级：成本/性能/测试

- **G13 — CV 交叉验证的重量级选型**：`vasi_segmentation.py` 的 `segment_vitiligo` 走 SAM 模型，backfill 跑几百对会非常慢/贵。spot_compare 的 CV 交叉验证应优先用 `_fallback_segmentation`（亮度阈值启发式）做「白斑像素占比变化」，而非逐对跑 SAM；如确需 SAM，要限流并明确成本预算。
- **G14 — 缺少自动化测试**：项目有完整 pytest 套件（AGENTS.md 明确）。规划只有 `eval_spot_compare.py`（离线评估），缺 `spot_compare`、`generate_periodic_report`、新 API、**公开脱敏** 的单元/集成测试。建议 P0/P1 各配最小测试集，尤其 G1 的脱敏用例要作为回归测试固化。
- **G15 — `trend_chart_data` 多序列升级的向后兼容**：现有对比报告存单序列，前端 `initChart` 只读 `vasi_scores`。升级多序列（VASI/面积%/复色指数）后，旧的 comparison 报告仍须正常渲染，不能只适配 periodic。

---

## 4. 优化后的完整执行规划（建议修订版）

> 沿用 GLM-5.3 的 P0–P4 主线，插入「**P0.5 隐私/合规门禁**」，并把评审补充项落到各阶段。方括号 `[Gx]` 对应上文风险点。

### P0 — 配对识别引擎（`spot_compare.py` + `spot_comparisons` 表）
1. 新表 `spot_comparisons`：字段按 G8 修订（规范化 pair 顺序、唯一索引含 body_site、`(user_id, body_site)` 查询索引、版本化 `metrics_json` schema）。
2. `compare_pair()`：质量门禁（复用 `vasi_quality.check_blur/check_lighting`，低质量标记 `low_confidence`）→ **视觉模型走 `vasi` 模块 `vision_model`（C2）**，双图严格 JSON → CV 交叉验证**优先轻量亮度启发式（G13）** → 缓存命中直接返回。
3. 明确周报指标措辞红线（G6）写进 prompt 模板。
4. 离线评估：`backfill_spot_comparisons.py`（**仅指定 user_id，G4**）+ `eval_spot_compare.py`（用 VASI ground truth 对一致性）。
5. 测试：spot_compare 单元测试 + 脱敏回归（G14）。

### P0.5 — 隐私/合规门禁（本次评审新增，编码前定稿）
1. 确定 `cover_composite_url`、海报、周报详情在**公开分享链路**的脱敏规则（G1）。
2. 定稿周报/月报/海报的**免责声明文案**与必现位置（G2/G7）。
3. EXIF 只取 `DateTimeOriginal`、丢弃 GPS 等其余字段（G3）。
4. 明确通知走 `create_notification` 的跨层方案（G5）。
5. 明确时区（Asia/Shanghai）与周期边界算法（G10）。
6. 明确报告删除→连带清理生成物、周报累积留存策略（G11）。

### P1 — 周报/月报生成引擎（`generate_periodic_report` + API）
1. 周期窗口：weekly 自然周（周一~周日）/ monthly 自然月，**统一 UTC+8**（G10）；VASI 用 `assessment_date`、post_images 用 `capture_date`（C4）。
2. 数据源合并：post_images + vasi_assessments(status=active)，**先按 `vasi_assessment_id` 关联去重，再按 image_url 去重（C3）**，body_site 归一化到 14 部位 taxonomy。
3. 幂等：唯一约束 `(user_id, report_type, period_start)`（G9-1）。
4. 异步生成：有界 executor + status=generating/completed/failed + error_message + 孤儿状态回收（G9-2/3）。
5. 封面拼图（PIL）写 `cover_composite_url`；`trend_chart_data` 升级多序列并**保持旧 comparison 兼容**（G15）。
6. 周报专用 LLM prompt（含 G6 红线）+ `headline`。
7. **公开脱敏扩展**：`_report_to_dict(include_private=False)` 移除 `cover_composite_url` 与 metrics/source_data 内所有 image_url（G1）。
8. 测试：periodic 引擎 + 脱敏用例（G14）。

### P2 — 前端周报/月报体验（含命名/主题统一）
1. `SkinReportViewPage.vue` 增 periodic 版式：封面 hero、14 部位状态总览、每部位卡片（BeforeAfterSlider + 指标徽章 + mini 趋势）、ECharts 多序列（tree-shaken）。
2. `SkinReportListPage.vue`：顶部「生成上周周报/生成本月月报」快捷卡（preview 可用性）+ 筛选。
3. `SkinReportPoster.vue` 升级：含照片 + headline + 指标芯片 + QR + **免责声明（G2）**；1080×1920。
4. **同步统一报告模块合规**：标题统一为「白斑报告」、主题色 `primary-*`、容器 `max-w-6xl mx-auto px-4`（G12，需决策是否 retrofitting 现有对比报告页）。
5. PDF 导出复用 `exportElementToPdf`，验证周期版式打印。

### P3 — 批量补录 + 自动化（验证通过后）
1. 补录流（网格编辑器逐图编辑日期/部位）走现有 `image_metas`。
2. EXIF 自动日期：仅取 `DateTimeOriginal`，丢弃 GPS（G3）。
3. 自动生成调度：lifespan asyncio 循环（沿用 token 清理模式），每天 06:00 检查；周一生成上周周报、1 号生成上月月报；仅数据充足用户；幂等；完成发站内通知（G5）。
4. 分享到白友圈附封面拼图（用户主动分享=授权，公开页维持脱敏）。

### P4 — 导航同步 + 部署 + 端到端验证
1. `site-modules.json` 白斑报告模块描述加「周报/月报」；`rag.py` 导航表 + `SITE_FEATURE_KEYWORDS` 同步；`page-names.json` 补 `/community/reports`。
2. 部署前 `npm run type-check`（vue-tsc）+ `pytest`。
3. 前端 `npm run build` → staging；**后端重启前先提醒**（共享后端=立即影响正式环境）；记录 `DEPLOY_LOG.md`。
4. 最终验证：用 LianqingChan 账号历史照片 backfill → 生成真实周报+月报 → 验收识别精度/排版/脱敏 → 迭代 prompt。

---

## 5. 需要 LianqingChan 拍板的决策清单

1. **脱敏口径（G1）**：周报封面拼图在公开分享页是否一律隐藏？还是提供「脱敏版封面」？建议默认隐藏 + 仅本人可见。
2. **海报免责声明（G2）**：海报是否强制带「本文不构成医疗建议」？建议强制。
3. **现有对比报告页是否本次一并 retrofitting（G12）**：统一命名「白斑报告」+ `primary-*` 色板 + `max-w-6xl`，还是只新周期版式遵守、老页面暂不动？（影响 P2 范围与工作量）
4. **CV 交叉验证的算力成本（G13）**：接受「轻量亮度启发式为主、SAM 仅关键对」还是需要更准但更贵的全量 SAM？建议前者。
5. **自动生成是否默认开启（P3）**：周报/月报自动生成+通知，是上线即默认开启，还是先手动生成验证一段时间再开自动？建议先手动 → 再自动。
6. **报告留存策略（G11）**：报告/封面/海报文件是否永久保留？删除报告是否连带删生成物？建议删除连带清理 + 数据不永久无限累积。

---

## 6. 一句话总结

GLM-5.3 的规划**架构方向正确、复用判断准确**，可据此开工；但编码前需先补齐 **P0.5 隐私/合规门禁**（尤其 `cover_composite_url` 公开脱敏、海报免责、EXIF 去 GPS、backfill 越权），修正 **4 处事实偏差**（skin_report 已注册、视觉模型归属、跨源去重 key、VASI 日期字段），并把**并发幂等/时区/删除清理**纳入实现。以上 6 项决策定了，即可进入编码。

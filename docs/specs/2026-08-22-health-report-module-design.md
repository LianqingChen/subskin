# 综合健康报告模块设计（独立「报告」导航）

> 日期：2026-08-22
> 状态：规划稿（待确认后进入实现）
> 关联：现有「白斑报告」`SkinReport`（`/community/reports`，照片对比+VASI+日记+治疗事件）

## 1. 目标与定位

把现有的「白斑报告」升级并**独立**为一个顶层「报告」模块，导航放在「分享」之后。
报告不再是单一的白斑照片对比，而是**综合健康报告**：按 **本周 / 本月 / 本年** 聚合用户在
**AI 问答、白斑测评（VASI）、体检报告、分享（含日记）** 四类数据，提炼出**白斑变化**、
**心情变化**、**体检指标变化**、**互动回顾**等，图文并茂、言简意赅，把专业病情数据翻译成
用户能看懂的话，同时自然激发分享欲。

**核心价值一句话**：让用户「坚持记录 → 定期收获一份看得懂、值得晒的病情报告 → 更有动力继续记录」。

## 2. 命名与导航

| 项 | 方案 |
|----|------|
| 顶层模块名 | **报告**（`label`） |
| 路径 | `/report`（原 `/report` 目前 302 到 `/assessment?tab=report`，需改为正式路由） |
| 图标 | `ri-file-chart-line`（沿用现有报告图标，语义一致） |
| 位置 | BottomNav / AppHeader 的 `NAV_PATHS` 中插到 `/community`（分享）之后 |

**与现有「白斑报告」的关系（推荐：收编而非并存）**：
- 现有 `SkinReport`（对比/周报/月报）降级为「综合报告」里的一个**数据章节**（白斑变化），能力全部复用。
- 老路由 `/community/reports` → 301 到 `/report`；`/community/reports/:id` 保留（报告详情页复用它承载综合报告）。
- `site-modules.json` 中：新增顶层「报告」模块；原「白斑报告」条目从 `modules` 移除、并入「报告」的 keywords（"白斑报告/周报/月报/年报/变化报告"），避免重复导航项。

## 3. 数据源整合（核心）

### 3.1 四类数据源 → 结构化「聚合事实」汇总表

后端在周期窗口 `[d_start, d_end]` 内聚合，统一产出 `HealthReportPayload`：

| 数据源 | 表/模型 | 定量（结构化） | 非结构化 → 提炼 |
|--------|---------|----------------|------------------|
| 白斑测评 | `VASIAssessment` | `final_vasi_score`、`final_area_percentage`、`stage`(好转/稳定/扩散)、`depigmentation_level`、`assessment_date` | —（本身已结构化） |
| 照片对比 | `PostImage` + `spot_compare` | 复色指数 `melanin_score`、`size_change_percent`、趋势 | 轻量视觉摘要 `visual_analysis_json.summary` |
| 体检报告 | `MedicalReport.interpretation_json` | `risk_level`、`parsed_indicators`(value/ref_range/status)、`abnormal_items`、`sections`(红黄绿) | 各指标 `interpretation`/`suggestions`（已通俗化） |
| 分享/日记 | `Post` | `mood`(💪坚持中/😔低落/🎉好转/🤔疑问)、发帖数、`PostLike`/`PostComment` 互动数 | `ai_extracted_json`(心情/睡眠/用药/皮损)、`content_text`、`ai_summary` |
| AI 问答 | `Conversation` + `Message` | 提问条数、按周期计数 | 用户提问文本 → LLM 提炼高频主题/关键词 |
| 治疗事件 | `TreatmentEvent` | 事件类型/日期 | 标题/描述 |

### 3.2 定量数据的分析结果（复用既有算法，不重造轮子）

- **白斑趋势**：复用 `services/skin_report.py` 的 `_trend_from_percent`（±5% 阈值）、
  `_compute_periodic_metrics`（部位好转/稳定/加重计数）、`spot_compare.compare_pair`（复色指数）。
- **体检指标变化**：复用 `services/medical/report_interpreter.py` 的对比能力，产出
  `newly_abnormal / resolved_abnormal / persistent_abnormal / large_delta` 四类变化 + 红黄绿分区块；
  重点筛选与白癜风相关指标（甲状腺、免疫、肝功能、微量元素铜/锌、维生素 D）。
- **心情趋势**：把 `Post.mood` + `ai_extracted_json.mood/sleep/stress` 归一为 `积极/平稳/低落`
  三档，按日期做序列（供趋势图），并统计周期内占比。
- **互动活跃度**：发帖数、获赞数、获评论数、被收藏数（`PostLike`/`PostComment`/`Bookmark`）。

### 3.3 非结构化内容的整合（LLM 提炼，单次调用）

把以下「非结构化压缩」喂给 LLM（`health_report` 模块，管理后台可编辑提示词）：
- 问答：周期内用户提问列表（截断，去敏）；
- 日记/分享：`ai_extracted_json` 摘要 + `content_text` 前 80 字 + mood；
- 体检：各 `section_summary` + 异常指标 `interpretation`。

LLM 输出（严格 JSON）：
```json
{
  "headline": "6-16字亮点标题",
  "narrative_sections": [{"kind":"skin|mood|exam|social|qa","title":"...","body":"..."}],
  "mood_summary": {"trend":"变好|平稳|波动","keyword":"...","comfort_line":"一句暖心话"},
  "qa_topics": ["高频话题1","话题2"],
  "insights": ["3-5条"],
  "recommendations": ["2-4条"]
}
```
红线（沿用现有皮肤报告约定）：非诊断、只基于给定数据、不捏造数值、无 LLM 时降级到模板叙事。

## 4. 报告结构（页面模块，图文并茂）

一份综合报告详情页 = 以下 10 块，由上到下：

1. **封面头部** — `headline` + 周期徽章 + 整体趋势徽章 + 封面海报图（复用 `_build_cover_composite`，扩展为主题化海报）。
2. **KPI 指标卡（4-6 个）** — 定量一眼看懂：
   - 白斑：`趋势` + `VASI Δ` / `复色部位数`
   - 心情：`情绪倾向` + `积极占比`
   - 体检：`报告份数` + `异常指标数` + `风险等级`
   - 互动：`发帖数` + `获赞/评论`
   - 问答：`提问数` + `Top 话题`
3. **白斑变化** — 前后对比照片滑块 + VASI/复色指数趋势曲线（ECharts，多序列）+ 分部位卡片（复用现有 `SkinReportViewPage`）。
4. **心情变化** — 心情日历热力图 + 情绪占比（环形图）+ 情绪关键词 + AI 暖心句。
5. **体检指标** — 红黄绿分区块 + 关键指标变化（新增/恢复/持续）+ 白癜风相关指标高亮 + 通俗解释条。
6. **AI 问答洞察** — 高频话题标签云（手写 flex 标签，避免新增依赖）+ 问题摘要。
7. **分享互动回顾** — 发帖时间线 + 最受欢迎内容 + 白友互动摘要。
8. **AI 综合叙事** — 按 `narrative_sections` 分段呈现（白斑/心情/体检/互动）。
9. **洞察与建议** — insights + recommendations 列表。
10. **底部操作栏 + 免责声明** — 生成海报 / 复制链接 / 发布到分享 / 导出 PDF / "本文不构成医疗建议"。

## 5. 图文呈现技术选型

| 元素 | 方案 |
|------|------|
| 趋势曲线 / 环形图 / 柱状图 | `echarts`（已在依赖，`SkinReportViewPage` 已有封装可抽公共组件） |
| 心情热力图 | `echarts` Heatmap 或手写日历网格（首选手写，轻量） |
| 前后对比照片滑块 | 复用现有 spot_compare 滑块 + 封面拼图 |
| 话题标签云 | 手写 flex + 权重字号（不新增 echarts-wordcloud 依赖） |
| 分享海报 | 复用 `PageSharePoster` + `html2canvas`（已在依赖） |
| 导出 PDF | 复用现有 `jspdf` 能力 |

## 6. 分享刺激设计（激发分享欲）

1. **默认生成一张高质感海报**：正面成果类标题（"复色进行中"）+ 封面拼图 + 品牌，用户一键长图保存/发朋友圈。
2. **一键发布到分享**：复用 `share-to-community`，生成「治疗分享」帖（含内嵌报告链接），文案自动带鼓励语气。
3. **分享仅脱敏**：公开分享（`share_token`）只保留叙事/聚合指标/脱敏封面，**去掉原始图片 URL 与体检原始数值**。
4. **分享后送正向反馈**：分享成功提示 + 统计"本报告被浏览 N 次"，制造二次分享动机。

## 7. 技术架构

### 7.1 后端（改动需⚠️同步提醒：共享后端 = 立即影响正式环境）

- 新增 `services/health_report.py`：
  - `generate_health_report(db, user_id, period_type)`（weekly/monthly/yearly）
  - `_period_window` 扩展 `yearly`（自然年）
  - 数据采集函数：`_collect_vasi` / `_collect_exam` / `_collect_mood_social` / `_collect_qa` / `_collect_treatment`
  - LLM 整合 `_call_health_llm` + 降级模板
- 扩展 `SkinReport` 模型（**additive only**）：新增可选列承载综合指标，或复用 `metrics_json` 塞入
  `mood_summary` / `exam_summary` / `qa_topics` / `social_summary`（推荐后者，零迁移）。
- `api/skin_report.py`：`report_type` 支持 `yearly`；新增聚合详情返回综合字段（向后兼容旧字段）。
- `services/rag.py`：`SITE_FEATURE_KEYWORDS` 增加「报告/健康报告/年报/我的报告/综合报告」；
  导航表/关键词由 `site-modules.json` 自动派生（改 json 即可）。
- 体检相关指标重点：甲状腺/免疫/肝功能/铜/锌/维生素D（`indicator_normalizer` 已有 canonical 映射可复用）。

### 7.2 前端（改动仅前端，可独立部署）

- `web/shared/site-modules.json`：新增「报告」模块（keywords 含 白斑报告/周报/月报/年报/变化报告/健康报告）。
- `BottomNav.vue` / `AppHeader.vue`：`NAV_PATHS = ['/', '/assessment', '/community', '/report']`，并修正 `isActive` 对 `/report` 的匹配。
- `router/index.ts`：`/report` 正式路由；`/community/reports` 301。
- 新增 `views/ReportHubPage.vue`（周期切换 + 一键生成 + 历史列表）——或改造现有 `SkinReportListPage.vue`。
- 改造/新增 `ReportViewPage`（综合报告详情，复刻并扩展 `SkinReportViewPage.vue`）。
- 拆组件：`ReportKpiCards` / `MoodHeatmap` / `ExamIndicatorPanel` / `QaTopicCloud` / `SocialTimeline` / `ReportTrendChart`（抽公共 ECharts 封装）。
- `api/health_report.ts` + `composables/useHealthReport.ts`（遵守 view 不直连 api 分层）。
- Schema.org：报告详情页加 `MedicalCondition`/`WebPage` 结构化数据。

## 8. 隐私与合规（生死线）

- 全部聚合在服务端完成，仅所有者接口返回原始图片 URL 与体检数值。
- 公开分享（`share_token`）严格 `_strip_private_metrics`：去图片 URL、去体检原始数值、去问答原文。
- 「发布到分享」「公开分享」走 `AuditLog` 不可篡改审计（who/what/when/scope/revokeable）。
- 体检报告为 L3 高敏：报告里仅呈现**解读结论/趋势**，不渲染原始报告文件给他人。
- 不新增个人信息采集；AI 处理仅在服务端，问答原文不进前端日志。

## 9. 分阶段实施（建议）

| 阶段 | 内容 | 风险 |
|------|------|------|
| **P1 周报/月报扩容** | 顶部导航 + `/report` + 周期切换 + 在现有 skin_report 基础上加 心情/体检/问答/互动 四类聚合 + KPI 卡 | 中（后端） |
| **P2 年报** | `yearly` 窗口 + 年度叙事 + 年度回顾海报 | 低 |
| **P3 分享增强** | 主题化海报、词云、浏览计数、分享引导 | 低 |
| **P4 打磨** | 空态引导（无数据时教用户去测评/发帖/上传体检）、埋点、A/B | 低 |

## 10. 需要你拍板的决策点

1. **命名**：顶层模块叫「报告」还是「健康报告」/「我的报告」？（推荐「报告」，简洁、与导航字长一致）
2. **收编关系**：现有「白斑报告」并入新「报告」作为其中一章（推荐），还是两者并存？
3. **年报口径**：自然年（1/1-12/31）还是滚动 365 天？（推荐自然年）
4. **首期范围**：先做 P1（周/月）验证，还是直接 P1+P2（含年报）一起？

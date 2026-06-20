# 体检报告模块改造规划

> 创建时间: 2026-05-07 | 状态: 规划阶段（Oracle 审核通过）
> 最近更新: 2026-05-07 — 整合 Oracle 审核建议：合并 P2+P3，增加 schema versioning，P5 确定性优先，P4 确认优先，P1 认证修复

---

## 目标

将 SubSkin「体检解读」模块从当前的"上传 → AI片段解读"升级为"上传 → 完整原文查看 → AI全量结构化解读(含溯源) → 自动建档(确认优先) → 趋势追踪(确定性优先)"的全链路体检报告管理功能。

---

## 当前问题诊断

### 问题 2.1 — 体检报告原文无法查看
**根因**: 
- `ReportDetailPage.vue` 中的文件链接使用 `<a :href="getFileViewUrl(file.id, authStore.token)">`，后端 `/api/files/view/{file_id}?access_token=...` 返回 HTML viewer 页面
- 空白页面的可能原因：① 用户 token 与报告 owner 不匹配导致 404；② PDF 预转换页缺失时回退到下载页；③ WeChat WebView 可能阻止了 viewer_template.html 渲染
- 当前用户需要下载 PDF 才能查看，体验差
- **安全风险**（Oracle 发现）：access_token 在 query string 中会泄漏到日志、浏览器历史、Referrer 头

### 问题 2.2 — AI 解读内容严重不完整
**根因**:
- `report_interpreter.interpret()` 只将 **异常指标 (flagged)** + **前 2000 字符** 的原始文本发送给 LLM
- 血常规、尿常规、肝功能等大类中的正常指标被完全丢弃
- `report_parser.py` 的指标提取能力有限，对复杂中文体检报告格式覆盖不足
- 默认 LLM `max_tokens=4096`，无法容纳完整报告解读

### 问题 2.3 — AI 解读缺少来源追溯
**根因**:
- 当前的 `AbnormalItem` 数据结构中，`interpretation` 字段仅存放 AI 生成的文本，没有存放支撑该结论的源指标和原始数据
- 用户无法判断 AI 结论是"从报告原文指标推导得出的"还是"AI 基于通用知识猜测的"
- 没有任何 page/line/section 级别的定位信息

### 问题 2.4 — 缺少用户信息关联与建档
**根因**:
- `MedicalReport` 模型仅有 `user_id` 字段，不存储被检查人的姓名、年龄、性别
- `PatientProfile` 模型已存在（name/gender/birth_date/relationship），但 `MedicalReport` 未与其关联
- `user_context`（age/gender）由前端手动传参，未自动从 PatientProfile 获取
- 体检报告原文中的体检人信息未被提取和利用

---

## 竞品调研结论

基于对蚂蚁集团阿福、爱康国宾、Apple Health、以及开源项目 (parselabs, MOSAICX, RxLM-Med) 的调研，可借鉴的核心模式：

| 模式 | 来源 | 应用方式 |
|------|------|---------|
| **过程透明化** | 阿福 | 展示 上传→识别→分析→解读 的实时进度 |
| **分层信息披露** | Apple Health | 总览摘要 → 分项详细 → 原始数据 三级递进 |
| **异常分级展示** | 爱康国宾 | 🔴危急 🟡关注 🟢正常 + 按复查频率排序 |
| **交通灯分类系统** | 多产品 | 按 Section（血常规/尿常规/肝功能等）整体标色 |
| **历史趋势对比** | 爱康+Apple | 同一指标跨报告对比折线图 |
| **行动路由** | 阿福+爱康 | 解读后提供"继续咨询"/"预约医生"/"复查计划" |
| **家族账户** | 阿福 | 支持管理多人体检报告，分别建档追踪 |
| **数据溯源** | Kantesti+开源 | 每个结论链接回原文具体页和行 |
| **隐私脱敏** | 阿福+OpenMed | 上传时自动检测并隐藏个人身份信息 |

---

## 改造计划（5个阶段）

> **阶段排序原则**（Oracle 建议）：先建立结构化、可溯源的每报告数据基础（P1→P2），再在其上构建建档（P3）和对比（P4），最后打磨体验（P5）。P4 对比依赖于归一化、可溯源的报告事实，而非自由文本解读。

### Phase 1: 报告原文在线查看 + 认证修复 ⭐ 最高优先级
**目标**: 用户上传的报告 PDF/图片可直接在页面内浏览，无需下载；修复 token 传输安全问题

**任务**:
1. **[1.1]** 修复文件链接跳转空白问题 — 诊断 token/auth/ownership 问题
2. **[1.2]** 修复 token-in-query-string 安全问题（Oracle 发现）：
   - 当前 `/api/files/view/{file_id}?access_token=...` 将认证 token 暴露在 URL 中
   - 方案：改用短期签名 URL 或 cookie-based auth，避免 token 泄漏到日志/Referrer/浏览器历史
   - 具体实现：新增 `GET /api/files/serve/{file_id}` 接受 Bearer auth header；前端改用 `fetch()` + `URL.createObjectURL()` 加载图片
3. **[1.3]** 在 `ReportDetailPage` 中嵌入 PDF 分页查看器，使用后端已有的 `/api/files/pages/{file_id}/{page}` 接口
4. **[1.4]** 添加图片报告的缩放/全屏查看功能
5. **[1.5]** 支持左右分栏布局：左侧原文，右侧 AI 解读

> **注意**（Oracle）：PNG 分页查看仅作为**稳定化方案**，不是长期架构承诺。如未来需要高清缩放、文字选择、搜索等功能，需升级到 pdf.js。

**文件**:
- 前端: `ReportDetailPage.vue`, `ReportUploader.vue`
- 后端: `api/files.py`, `api/medical_report.py`

**QA 场景**:
- **[1.1-QA1]** 诊断空白页：浏览器 DevTools → Network → 点击文件链接 → 验证 HTTP 状态码不是 401/404。`curl -I "http://localhost:8000/api/files/serve/{file_id}" -H "Authorization: Bearer {valid_token}"` 应返回 200。
- **[1.1-QA2]** 检查 PDF 预转换页：`ls data/uploads/pages/{file_id}/page-*.png` 应有分页文件存在。
- **[1.2-QA1]** 认证安全：查看后端访问日志 → 不应出现 `access_token=` 参数。前端改用 `fetch()` + Bearer header 后，图片加载不应在 URL 中暴露 token。
- **[1.3-QA1]** PDF 查看器：在 `ReportDetailPage` 中内嵌分页查看器（使用 `<img>` + prev/next 按钮），Desktop Chrome 访问 → 应能逐页翻看 PDF。
- **[1.3-QA2]** 微信 WebView 验证：在微信内置浏览器中打开报告详情页 → 分页查看器应正常显示（非空白）。
- **[1.3-QA3]** 多页 PDF：上传 10 页 PDF → 验证所有 10 页都能正常翻页查看。
- **[1.4-QA1]** 图片缩放：上传 JPG/PNG 报告 → 点击图片应能放大查看，支持拖拽平移。
- **[1.5-QA1]** 分栏布局：Desktop（≥1024px）下应显示为左侧 PDF 查看器 + 右侧 AI 解读的双栏布局；Mobile（≤768px）下应显示为上下堆叠布局。

**验收标准**:
- ✅ 点击上传的文件能在页面内直接查看，不下载
- ✅ PDF 支持翻页（上一页/下一页）
- ✅ 图片支持缩放和拖拽
- ✅ 移动端（含微信WebView）可用
- ✅ 认证 token 不出现在 URL query string 中

---

### Phase 2: AI 全量结构化解读 + 溯源 ⭐ 最高优先级（合并原 P2+P3）

> **设计原则**（Oracle）：不要"先做完整解读，再补溯源"——这会导致 `interpretation_json` 被设计两次。正确做法是将结构化结论、归一化指标、证据锚点设计在同一个 schema 中一起输出。

**目标**: 覆盖报告中的所有检查项目，按 Section 分类输出完整解读；每个 AI 结论都能追溯到报告原文中的具体指标和数据

**任务**:
2. **[2.1]** 定义新的解读输出契约（interpretation contract）：
   - 每个 report 产出：
     - `conclusions[]` — 每个结论含 `source_indicators[]`（源指标名+值）+ `source_text_excerpt`（原文片段）+ `confidence`（0-1）
     - `normalized_indicators[]` — 归一化指标（canonical name + unit family），为 P4 对比做准备
     - `evidence[]` — 证据锚点（indicator_id / page / snippet）
   - 添加 schema versioning 元数据：
     ```json
     {
       "schema_version": "2.0",
       "parser_version": "1.0",
       "llm_model": "gpt-4o-mini",
       "generated_at": "2026-05-07T10:30:00Z",
       "risk_level": "...",
       "summary": "...",
       "sections": [...],
       "conclusions": [...],
       "normalized_indicators": [...],
       "evidence": [...],
       "recommendations": [...],
       "disclaimer": "..."
     }
     ```
   - 旧版 interpretation_json 识别：`schema_version` 不存在时视为 v1，前端做兼容处理
2. **[2.2]** 重构 `report_interpreter.py`：
   - 将主路径切换为 `interpret_full_text()`（Section 级分析）
   - 移除 2000 字符截断，支持至少 30000 字符
   - 增加 `max_tokens` 至 8192 或更高
   - 在 LLM prompt 中同时要求输出溯源信息（source_indicators、source_text_excerpt、confidence）
2. **[2.3]** 优化 `report_parser.py`：
   - 增加对中文体检报告常见格式的解析覆盖（如"项目名称 结果 单位 参考范围"表格格式）
   - 支持识别 Section 标题（血常规、尿常规、生化全套、彩超等）
   - 增加指标名归一化：输出 `canonical_name` + `unit_family`（为 P4 对比做准备）
2. **[2.4]** 重新设计 LLM Prompt：
   - 加入"必须覆盖报告中出现的每一个检查项目"约束
   - 加入"正常指标以列表形式展示，异常指标以详细解读展示"
   - 加入 Section 级别的强制输出结构
   - **新增溯源要求**：每个结论必须标明依据的具体指标名称
   - **新增区分要求**：区分"报告明确显示的结论"和"基于通用医学知识的推论"
2. **[2.5]** 前端溯源展示：
   - 每项 AI 解读下方展示"数据来源"折叠区，列出支撑该结论的具体指标
   - 低置信度结论（confidence < 0.6）标注"⚠️ 此结论置信度较低，建议咨询医生核实"
2. **[2.6]** 添加解读过程进度展示：
   - 前端展示：OCR 提取中 → 指标结构化中 → AI 分析中 → 生成报告中
   - 每阶段显示进度百分比

**文件**:
- 后端: `services/medical/report_interpreter.py`, `services/medical/report_parser.py`, `api/medical_report.py`, `models/community.py`
- 前端: `ReportDetailPage.vue`, `api/medical-report.ts` (TypeScript types)

**QA 场景**:
- **[2.1-QA1]** Schema versioning 验证：调用 `POST /medical-reports/{id}/interpret` → 返回 JSON 应包含 `schema_version: "2.0"`、`parser_version`、`llm_model`、`generated_at` 字段。
- **[2.1-QA2]** 旧版兼容：对 `schema_version` 缺失的旧 interpretation_json → 前端应按 v1 格式渲染，不崩溃。
- **[2.1-QA3]** 溯源数据结构验证：返回 JSON 中每个 `abnormal_items[*]` 应包含 `source_indicators`（数组）、`source_text_excerpt`（字符串）、`confidence`（0-1 数字）。
- **[2.2-QA1]** 完整覆盖测试：上传包含 血常规(20项)+尿常规(10项)+肝功能(8项)+肾功能(4项)+彩超(2项) 的综合体检报告 PDF → AI 解读结果中应包含所有 Section，每个 Section 列出全部正常和异常指标。
- **[2.2-QA2]** 截断验证：发送一份 15000 字符的报告 → LLM 应收到完整的 15000 字符文本（通过 `len(full_text)` 日志确认 > 2000）。
- **[2.3-QA1]** 指标名归一化：解析"谷丙转氨酶" → `canonical_name: "ALT"`、`unit_family: "U/L"`。解析"WBC" → `canonical_name: "WBC"`（白细胞计数）。
- **[2.4-QA1]** Prompt 验证：LLM 返回的 JSON 中 `sections` 数组不为空，每个 section 包含 `section_name`、`indicators`（含正常项）和 `abnormal_items`（含 source_indicators）。
- **[2.5-QA1]** 前端溯源展示：在 `ReportDetailPage` 中展开任意异常指标解读 → 应显示"数据来源"折叠区，列出源指标名称、值和参考范围。
- **[2.5-QA2]** 低置信度标识：若 `confidence < 0.6` → 结论下方应有黄色警告标识文字。
- **[2.5-QA3]** 无数据编纂：手动检查 AI 解读结果 → 所有提到的指标名称和数值均可在报告原文中找到对应行。不应出现报告中没有的检测项目。
- **[2.6-QA1]** 进度可视化：浏览器中触发解读 → 应看到进度条或阶段提示（"正在提取文本..." → "正在分析血常规..." → "正在汇总..."），最终进入结果页面。总耗时 ≤ 30 秒。

**验收标准**:
- ✅ 覆盖血常规、尿常规、肝功能、肾功能、血脂、血糖、血压、彩超等全部常见体检项目
- ✅ 每个 Section 独立展示，含正常指标列表 + 异常指标详细解读
- ✅ 每个 AI 解读结论都能点击展开查看"数据来源"
- ✅ 低置信度结论有明确标识
- ✅ 没有任何 AI 编纂的指标数据
- ✅ 解读过程有可视化进度提示
- ✅ 解读时间控制在 30 秒内（正常报告）
- ✅ interpretation_json 包含 schema_version 元数据

---

### Phase 3: 用户信息提取与自动建档（确认优先） ⭐ 高优先级

> **设计原则**（Oracle）：绝不静默自动创建或自动关联 PatientProfile。OCR 提取的体检人信息只是"候选项"，必须经用户确认后才写入 patient_profile_id。

**目标**: 从体检报告中自动提取体检人信息，在报告详情页展示候选项，用户确认后关联或创建 PatientProfile

**任务**:
3. **[3.1]** 在 OCR 解析阶段增加"体检人信息提取"：
   - 提取字段：姓名(name)、性别(gender)、年龄/出生日期(birth_date)
   - 在 LLM prompt 中增加体检人信息提取指令
   - **提取结果存入** `MedicalReport.extracted_patient_info_json`（新增字段），不直接写入 PatientProfile
3. **[3.2]** 在 `MedicalReport` 模型中增加字段：
   - `patient_profile_id` 外键（可为空），遵循现有迁移模式
   - `extracted_patient_info_json` 字段（可为空，存储 OCR 提取的候选项）
   - 迁移函数（参考已有的 `ensure_medical_report_interpretation_column`）:
     ```python
     def ensure_medical_report_patient_profile_columns() -> None:
         inspector = inspect(engine)
         try:
             columns = {c["name"] for c in inspector.get_columns("medical_reports")}
         except Exception:
             return
         if "patient_profile_id" not in columns:
             with engine.begin() as connection:
                 _ = connection.execute(
                     text("ALTER TABLE medical_reports ADD COLUMN patient_profile_id INTEGER REFERENCES patient_profiles(id)")
                 )
         if "extracted_patient_info_json" not in columns:
             with engine.begin() as connection:
                 _ = connection.execute(
                     text("ALTER TABLE medical_reports ADD COLUMN extracted_patient_info_json TEXT")
                 )
     ensure_medical_report_patient_profile_columns()
     ```
3. **[3.3]** 确认优先的建档流程（Oracle 推荐：报告详情页内嵌确认卡片，非弹窗、非独立页面）：
   - Step 1: 上传文件 → 后台 OCR + 提取体检人信息 → 存入 `extracted_patient_info_json`
   - Step 2: 报告详情页加载 → 如果 `patient_profile_id` 为空且 `extracted_patient_info_json` 不为空 → 显示"识别到患者信息"常驻卡片
   - Step 3: 用户点击卡片 → 展开可编辑表单（姓名/性别/年龄/关系），预填 OCR 提取的值 + "来自报告"提示
   - Step 4: 用户选择"关联已有档案"或"创建新档案"或"跳过"
   - Step 5: 确认后才写入 `patient_profile_id`
3. **[3.4]** `user_context`（age/gender）自动从关联的 PatientProfile 获取，无需前端手动传参
3. **[3.5]** **禁止规则**：
   - 不覆盖已有 PatientProfile 的字段（OCR 结果仅作建议）
   - 不静默自动创建 PatientProfile
   - 不静默自动关联 MedicalReport 与 PatientProfile

**文件**:
- 后端: `database/models.py`, `app/main.py` (迁移), `api/medical_report.py`, `api/patient_profile.py`
- 前端: `ReportDetailPage.vue`（确认卡片）, `ReportUploader.vue`

**QA 场景**:
- **[3.2-QA1]** 数据库迁移验证：启动后端服务 → `sqlite3 data/subskin.db "PRAGMA table_info(medical_reports);"` 应显示 `patient_profile_id` 和 `extracted_patient_info_json` 两列。
- **[3.2-QA2]** 幂等性验证：重启后端 2 次 → 不应出现 "column already exists" 错误。
- **[3.1-QA1]** 信息提取准确性：上传一份包含"姓名：张三 性别：男 年龄：35" 的体检报告 → `extracted_patient_info_json` 应为 `{name: "张三", gender: "男", age: 35}`。
- **[3.3-QA1]** 确认卡片展示：上传报告后进入详情页 → 应看到"识别到患者信息"卡片（非弹窗），展开后可编辑姓名/性别/年龄。
- **[3.3-QA2]** 关联已有档案：如果用户已有 `name="张三"` 的 PatientProfile → 卡片中应提供"关联已有档案"选项，选择后 `patient_profile_id` 被设置。
- **[3.3-QA3]** 创建新档案：选择"创建新档案" → 应创建 PatientProfile 并设置 `patient_profile_id`。
- **[3.3-QA4]** 跳过：选择"跳过" → `patient_profile_id` 保持为空，卡片消失，不影响后续使用。
- **[3.3-QA5]** 未提取到信息时：上传一份不包含体检人信息的报告 → 不显示确认卡片，不阻断操作。
- **[3.4-QA1]** 自动 context：关联 PatientProfile 后重新触发 AI 解读 → LLM prompt 中应自动包含年龄和性别信息。
- **[3.5-QA1]** 禁止静默创建：查看后端日志 → 不应出现未经用户确认的 PatientProfile 创建操作。

**验收标准**:
- ✅ 上传报告后自动提取体检人姓名、性别、年龄
- ✅ 提取结果作为候选项展示，用户确认后才关联/创建
- ✅ 绝不静默自动创建或自动关联
- ✅ 报告解读时自动应用正确的年龄/性别作为参考上下文

---

### Phase 4: 多报告对比与趋势解读（确定性优先） ⭐ 高优先级

> **设计原则**（Oracle）：对比的核心是**确定性计算**，不是 LLM 自由文本。归一化指标名、计算差值、判断趋势 → 全部本地确定性完成。LLM 只负责对**已计算出的变化事实**做叙事性解读。

**目标**: 用户可选择 2-3 份历史体检报告进行横向对比，系统先做确定性指标对比，再调用 LLM 对变化事实做趋势叙事

**任务**:
4. **[4.1]** 报告选择交互：
   - 在 `ReportPage`（报告列表页）增加"对比模式"：勾选 2-3 份报告后点击"对比分析"
   - 支持按体检时间、体检人（PatientProfile）筛选可选报告
4. **[4.2]** 后端对比 API — **多阶段设计**（Oracle 推荐）：
   - 新增 `POST /medical-reports/compare` 接口，接收 `[report_id1, report_id2, ...]`
   - **Pass 1 — 本地确定性计算**（不调用 LLM）：
     a. 归一化指标名（使用 P2 建立的 canonical_name 字典）
     b. 对齐同 canonical_name 的指标
     c. 归一化单位（同 unit_family 内换算）
     d. 分类每个指标：
        - `newly_abnormal` — 之前正常，本次异常
        - `resolved_abnormal` — 之前异常，本次正常
        - `persistent_abnormal` — 持续异常
        - `large_delta` — 变化幅度大
        - `unchanged_stable` — 无明显变化
        - `not_measured` — 某份报告中未检测
   - **Pass 2 — LLM 叙事**（仅发送变化事实）：
     a. 发送：报告日期/元数据 + 已变化或有临床意义的指标 + 紧凑的值/参考/单位表 + 各报告的 section 摘要
     b. 不发送：全部原始报告文本、所有正常且无变化的指标
     c. LLM 生成：趋势解读（改善/稳定/恶化 + 原因分析 + 建议）
   - 返回结构：
     ```json
     {
       "reports": [{ "id": 1, "date": "2025-03-01", "title": "..." }],
       "indicators": [
         {
           "canonical_name": "WBC",
           "display_name": "白细胞计数",
           "unit": "10^9/L",
           "ref_range": "3.5-9.5",
           "values": [
             { "report_id": 1, "date": "2025-03-01", "value": 12.5, "status": "high" },
             { "report_id": 2, "date": "2025-06-01", "value": 8.2, "status": "normal" },
             { "report_id": 3, "date": "2025-09-01", "value": 6.5, "status": "normal" }
           ],
           "change_category": "resolved_abnormal",
           "delta": -6.0,
           "trend": "improving",
           "trend_interpretation": "白细胞从偏高的12.5逐步恢复至正常范围6.5，炎症情况正在好转。"
         }
       ],
       "summary": {
         "total_indicators": 45,
         "comparable": 32,
         "newly_abnormal": 2,
         "resolved": 3,
         "persistent_abnormal": 1,
         "unchanged": 26,
         "not_measured": 13
       },
       "overall_assessment": {
         "trend": "improving",
         "summary": "整体身体状况较3月份有明显改善：白细胞和C反应蛋白恢复正常，肝功能指标稳定。",
         "highlights": [
           "✅ 白细胞恢复至正常范围（12.5→6.5）",
           "✅ 转氨酶从偏高降至正常"
         ],
         "concerns": [
           "⚠️ 总胆固醇持续偏高（5.8→6.2→6.4），需关注"
         ],
         "recommendations": ["保持当前饮食和运动习惯", "建议3个月后复查血脂"]
       }
     }
     ```
4. **[4.3]** 对比结果展示页面（新增 `ReportComparePage.vue`）：
   - 顶部：对比概要卡片（总体趋势 + 改善项数/恶化项数/稳定项数）
   - 中部：指标对比表格，每行一个指标，列按报告时间排列
     - 数值旁标注变化量（▲+0.3 / ▼-2.1）
     - 颜色编码：恢复绿色，恶化红色，稳定灰色，未检测灰色斜体
   - 每个指标行可展开查看 AI 趋势解读
   - 底部：整体评估区（改善/稳定/恶化 总结 + 关注项 + 建议）
4. **[4.4]** 指标归一化策略（Oracle 推荐的静态字典方案）：
   - 使用静态 canonical indicator dictionary：
     ```python
     CANONICAL_INDICATORS = {
       "ALT": {
         "aliases": ["谷丙转氨酶", "丙氨酸氨基转移酶", "Alanine Aminotransferase", "ALT", "GPT"],
         "unit_family": "U/L",
         "panel": "liver"
       },
       "WBC": {
         "aliases": ["白细胞计数", "白细胞", "White Blood Cell", "WBC"],
         "unit_family": "10^9/L",
         "panel": "cbc"
       },
       # ... 更多指标
     }
     ```
   - 匹配优先级：① 精确别名匹配 → ② 归一化字符串匹配（去标点/空格） → ③ 受限模糊匹配（仅当 unit_family + panel 兼容时）
   - **不使用 LLM 做指标名匹配**（Oracle：慢、不一致、难调试）
   - 未匹配的指标在对比中单独列出，不强行归并
   - 某份报告中缺失的指标标注为"未检测"（`not_measured`），不等同于"正常"或"0"

**文件**:
- 后端: `api/medical_report.py`（新增 compare 接口）, `services/medical/report_interpreter.py`（新增对比 prompt）, `services/medical/indicator_normalizer.py`（新增归一化模块）
- 前端: 新增 `ReportComparePage.vue`, 修改 `ReportPage.vue`（增加对比模式入口）, `api/medical-report.ts`

**QA 场景**:
- **[4.2-QA1]** 对比 API 基础：`curl -X POST "http://localhost:8000/api/medical-reports/compare" -d '{"report_ids": [1, 2, 3]}'` → 返回包含 `indicators` 数组和 `overall_assessment` 的完整 JSON。
- **[4.2-QA2]** 确定性计算验证：给定白细胞依次为 12.5(高)→8.2(正常)→6.5(正常) → `change_category` 应为 `"resolved_abnormal"`，`trend` 应为 `"improving"`。此计算不应依赖 LLM。
- **[4.2-QA3]** 恶化判断：给定总胆固醇依次为 5.8→6.2→6.4（均偏高）→ `trend` 应为 `"worsening"`，`overall_assessment.concerns` 应包含该指标。
- **[4.2-QA4]** Token 经济验证：检查 Pass 2 发送给 LLM 的 prompt 长度 → 不应超过 4000 token（仅发送变化指标）。
- **[4.1-QA1]** 报告选择 UI：进入报告列表页 → 点击"对比"按钮进入选择模式 → 勾选 3 份报告 → 点击"开始对比" → 跳转到 `ReportComparePage`。
- **[4.1-QA2]** 最少选择限制：只勾选 1 份报告时，"开始对比"按钮应为禁用状态，提示"至少选择 2 份报告"。
- **[4.3-QA1]** 对比表格渲染：页面应显示所有同名指标的对比表 → 每列标注日期 → 异常值有颜色标识 → 变化量有 ▲/▼ 箭头。
- **[4.3-QA2]** 展开 AI 解读：点击指标行 → 展开区域显示 LLM 生成的趋势解读文本。
- **[4.4-QA1]** 指标名对齐：报告A中"谷丙转氨酶"和报告B中"ALT" → 应被归一化为同一 canonical_name `"ALT"`，在对比表中合并为一行。
- **[4.4-QA2]** 缺失指标：报告A有"尿酸"但报告B缺失 → 对比表中报告B列应显示"未检测"。
- **[4.4-QA3]** 单位不匹配：报告A中肌酐单位 mg/dL、报告B中 μmol/L → 若 unit_family 不同则分开显示，不强行换算比较。

**验收标准**:
- ✅ 用户可选择 2-3 份报告进行对比分析
- ✅ 同名指标自动归一化对齐，展示数值变化和趋势判断
- ✅ 趋势判断由本地确定性计算完成，不依赖 LLM
- ✅ LLM 仅对已计算出的变化事实做叙事性解读
- ✅ 异常变化有明显视觉标识（颜色 + 箭头 + 变化量）
- ✅ 未检测指标明确标注，不等同于正常

---

### Phase 5: 交互体验升级
**目标**: 基于竞品最佳实践，全面提升体检报告功能的交互与视觉体验

**任务**:
5. **[5.1]** 分层信息披露设计：
   - 第1层：总体摘要卡片（风险等级 + 核心发现 + 关键指标数）
   - 第2层：Section 卡片列表（红/黄/绿边条，可展开）
   - 第3层：指标详细列表（含来源追溯 + 历史趋势迷你图，点击可跳转至 P4 多报告对比）
5. **[5.2]** 行动路由：
   - 解读完成后提供："继续咨询AI" / "对比历史报告"（跳转P4） / "生成医生分享报告" / "设置复查提醒"
5. **[5.3]** emoji 替换为 RemixIcon（符合 AGENTS.md 规范）
5. **[5.4]** 移动端适配验证（375px/768px/1024px/1440px）

**文件**:
- 前端: `ReportDetailPage.vue`, `ReportPage.vue`, `ReportUploader.vue`
- 后端: `api/medical_report.py`

**QA 场景**:
- **[5.1-QA1]** 三层展示：访问一份已解读的报告详情页 → 应依次看到：顶部风险摘要卡片 → Section 分类卡片列表 → 点击展开后看到指标详细列表。
- **[5.1-QA2]** 交通灯颜色：红色 Section 卡片应有 `border-l-red-500`，黄色 `border-l-yellow-500`，绿色 `border-l-green-500`。
- **[5.1-QA3]** 趋势迷你图入口：指标详情中如果有历史数据 → 显示迷你趋势图 + "对比历史"链接 → 点击跳转至 `ReportComparePage`。
- **[5.2-QA1]** 行动路由按钮：解读结果页面底部应有"继续咨询AI"和"对比历史报告"等操作入口。
- **[5.3-QA1]** RemixIcon 审计：搜索报告相关前端文件 `grep -r "🔴\|🟡\|🟢\|✅\|⚠️\|❌" web/app/src/views/Report*.vue web/app/src/components/tracker/Report*.vue` → 应无 emoji 结果（或已替换为 `<i class="ri-...">`）。
- **[5.4-QA1]** 响应式测试：Chrome DevTools 分别设置 375px、768px、1024px、1440px 宽度 → 每个断点下布局正常，无横向滚动条，文字不溢出。

**验收标准**:
- ✅ 三级分层信息展示完整可用
- ✅ 解读结果可一键跳转到多报告对比
- ✅ 所有图标使用 RemixIcon
- ✅ 移动端（含微信WebView）体验良好

---

## 决策记录

| 日期 | 决策 | 理由 |
|------|------|------|
| 2026-05-07 | 合并原 P2+P3 为新 P2 | Oracle：先做完整解读再补溯源会导致 interpretation_json 被设计两次；应设计一个统一的 evidence-backed schema |
| 2026-05-07 | 对比核心为确定性计算，LLM 仅叙事 | Oracle：归一化/对齐/差值/趋势判断必须本地确定性完成；LLM 做自由匹配会慢、不一致、难调试 |
| 2026-05-07 | 建档流程为"确认优先" | Oracle：绝不静默自动创建 PatientProfile；OCR 结果仅作候选项，用户确认后才写入 |
| 2026-05-07 | P1 PNG 查看器仅作稳定化方案 | Oracle：PNG 渲染不支持高清缩放/文字选择/搜索；长期需考虑 pdf.js，但 P1 阶段优先修复空白页 |
| 2026-05-07 | 修复 token-in-query-string 认证问题 | Oracle：access_token 在 URL 中泄漏到日志/Referrer/浏览器历史，属于安全风险 |
| 2026-05-07 | 添加 schema versioning | Oracle：interpretation_json 格式变化后，旧报告数据无法兼容；需 schema_version + parser_version + llm_model + generated_at |
| 2026-05-07 | 指标归一化使用静态字典 | Oracle：医学术语词汇量有限，静态 canonical dictionary 足够 MVP；不用 LLM 做指标名匹配 |
| 2026-05-07 | 未检测指标标注 not_measured | Oracle：缺失指标不等同于"正常"或"0"，必须明确标注 |
| 2026-05-07 | 新增 `extracted_patient_info_json` 字段 | Oracle：OCR 提取的体检人信息存储在此字段而非直接写入 PatientProfile，确认后才关联 |
| 2026-05-07 | 新增多报告对比功能为独立 Phase 4 | 用户主动选择 2-3 份报告进行横向对比 + AI 趋势解读 |
| 2026-05-07 | 报告解读主路径从 `interpret()` 切换为 `interpret_full_text()` | `interpret()` 仅发送异常的2000字符，覆盖不全 |
| 2026-05-07 | 新增 `patient_profile_id` 到 MedicalReport 模型 | 支持家庭多成员体检报告管理 |
| 2026-05-07 | 报告原文查看使用后端已有 PDF 分页 PNG 方案 | 避免引入新的 PDF 渲染依赖，兼容性好 |

---

## 技术依赖

| 依赖 | 用途 | 备注 |
|------|------|------|
| PyMuPDF (fitz) | PDF 分页转换 | 已在后端使用 |
| pdfplumber | PDF 表格提取 | 新增，用于优化指标解析 |
| OpenAI/通义千问 Vision API | 扫描件 OCR | 已在后端使用 |
| OpenAI/通义千问 Text API | LLM 解读 | 已在后端使用 |

---

## 风险与应对

| 风险 | 影响 | 应对 |
|------|------|------|
| LLM token 限制无法覆盖超长报告 | 解读不完整 | 分 Section 发送，多轮汇总 |
| 多报告对比时指标名无法自动对齐 | 对比结果不准确 | 静态 canonical 字典 + 归一化字符串匹配 + 受限模糊匹配；未匹配指标单独列出 |
| 微信 WebView 不支持 PDF 分页查看 | 无法查看报告原文 | 检测环境，回退到图片模式 |
| 体检人信息提取准确率不足 | 建档错误 | 所有提取结果仅作候选项，用户确认后才保存；不覆盖已有档案 |
| 单位/参考范围不一致导致错误对比 | 对比结果错误 | unit_family 不兼容时不强行换算；使用 change_category 分类而非绝对值 |
| 旧版 interpretation_json 格式不兼容 | 前端渲染崩溃 | schema_version 兼容处理；v1 缺失时走旧渲染逻辑 |
| L3 医疗数据发送至第三方 LLM 的隐私风险 | 数据泄漏 | P1 阶段修复 token-in-query-string；后续评估是否需在发送前脱敏 |

---

## 文件变更总览

| 层级 | 文件 | Phase |
|------|------|-------|
| 🔧 后端 | `services/medical/report_interpreter.py` | P2, P4 |
| 🔧 后端 | `services/medical/report_parser.py` | P2 |
| 🔧 后端 | `services/medical/indicator_normalizer.py` | P4 (新增) |
| 🔧 后端 | `api/medical_report.py` | P1, P2, P3, P4, P5 |
| 🔧 后端 | `api/files.py` | P1 |
| 🔧 后端 | `database/models.py` | P3 |
| 🔧 后端 | `app/main.py` | P3 (DB迁移) |
| 🔧 后端 | `models/community.py` | P2 |
| 🎨 前端 | `ReportDetailPage.vue` | P1, P2, P3, P5 |
| 🎨 前端 | `ReportComparePage.vue` | P4 (新增) |
| 🎨 前端 | `ReportUploader.vue` | P1, P3 |
| 🎨 前端 | `ReportPage.vue` | P3, P4, P5 |
| 🎨 前端 | `api/medical-report.ts` | P2, P4 |

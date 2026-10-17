# 00 · 多 Agent 协同、无缝交接与项目治理总纲

> **文档编号**: `STD-00`  
> **适用范围**: 所有进入 `/root/subskin` 项目空间的 AI 编码助手、Agent 框架与大语言模型（Claude Code、Cursor、OpenCode、Codex、Hermes、Windsurf、Qoder 等）  
> **更新日期**: 2026-10-17  
> **状态**: 强制执行（MANDATORY）

---

## 一、核心目标：跨 Agent / 跨大模型的零损耗无缝交接

SubSkin 由多个 AI Agent 与不同底座大模型在持续迭代中共同建设。为了彻底杜绝「换一个 Agent 就丢失上下文、改乱已有设计、写反隐私逻辑、误发正式环境、重复造轮子」的问题，本项目建立了 **统一事实来源（Single Source of Truth）+ 模块化标准文档库（`docs/standards/`）+ 统一技能库（`.agents/skills/`）+ 变更账本（`DEPLOY_LOG.md`）** 的四维治理体系。

任何新进入本项目的 Agent，只需遵循本文档规定的 **「5 步进场接手 SOP」**，即可在 3 分钟内完整掌握项目架构、前序进度与安全红线，无缝接手维护、升级与改造。

---

## 二、全项目唯一事实来源矩阵（Single Source of Truth）

严禁任何 Agent 在工具私有目录（如 `.claude/`、`.opencode/`、`.cursor/`）中创建独立的规则副本或与以下文件冲突的文档：

| 维度 | 唯一事实来源路径 | 核心职责与约束 |
|------|------------------|----------------|
| **1. Agent 最高宪章** | `/root/subskin/AGENTS.md` | 所有 Agent 进入仓库的第一必读文件（`CLAUDE.md` 仅为指向它的指针文件）。 |
| **2. 全栈开发与维护规范库** | `/root/subskin/docs/standards/*.md` | 本系列 8 篇核心规范文档，同时由管理后台「开发文档」（`/#/dev-docs`）实时渲染展示。 |
| **3. 全站设计系统详细规范** | `/root/subskin/docs/specs/2026-10-17-subskin-design-system.md` | Cursor & GitHub 现代科技质感 × 医疗温度的设计令牌、多端适配与分享海报规范。 |
| **4. 统一 Skill 技能库** | `/root/subskin/.agents/skills/<name>/SKILL.md` | 全项目唯一的 Skill 目录，包含前端、后端、UI 审计、部署验证、PWA、LLM 测试等 11 个专项技能。 |
| **5. 站点模块与页面命名源** | `/root/subskin/web/shared/site-modules.json`<br>`/root/subskin/web/shared/page-names.json` | 全站导航、页面标题、埋点与 AI 助手（小白管家）意图路由的唯一命名源，严禁硬编码旧模块名。 |
| **6. 环境部署与待发账本** | `/root/subskin/DEPLOY_LOG.md` | 记录 Staging 已部署但尚未推送到 Production 的所有累积变更（Pending Changes）及历史上线记录。 |
| **7. 实施计划归档** | `/root/subskin/hermes_plan/YYYY-MM-DD-*.md` | 复杂特性的多步骤设计方案与执行计划统一存放在此目录，作为项目长期工程记忆。 |
| **8. 问题排查与经验沉淀** | `/root/subskin/docs/solutions/` | 已攻克的疑难 Bug、架构演进与性能优化复盘文档。 |

---

## 三、新 Agent 进场与无缝接手 5 步 SOP（Mandatory Onboarding）

每当一个新的会话、新的 Agent 工具或新的大模型接手任务时，**必须在写下第一行代码前**按顺序执行以下 5 步：

### Step 1：读取当前状态与待发布队列
1. 阅读 `/root/subskin/AGENTS.md` 掌握全局红线。
2. 阅读 `/root/subskin/DEPLOY_LOG.md` 的 **`Pending Changes`** 章节：
   - 了解当前测试环境（`staging.subskin.cn`）有哪些已开发完成、正在等待用户验收同步到正式环境的功能。
   - **严禁覆盖或回退**前序 Agent 仍在 `Pending Changes` 中的未上线改动。
3. 运行 `git status` 与 `git diff --stat`，确认工作区是否有未提交的进行中改动。

### Step 2：按任务类型挂载对应规范与 Skill
根据用户指令涉及的领域，立即使用文件读取工具加载对应的规范文档与 `.agents/skills/`：

| 任务领域 | 必读规范文档 (`docs/standards/`) | 必读 Skill (`.agents/skills/`) |
|----------|----------------------------------|--------------------------------|
| **新增/修改前端页面、组件、样式** | `01-product-ux-user-journey.md`<br>`02-ui-design-cross-platform.md`<br>`04-frontend-pwa-architecture.md` | `frontend-architect`<br>`ui-audit`<br>`vue-tsc-guard` |
| **修改对外分享页、Canvas 海报、周报** | `02-ui-design-cross-platform.md` (§六) | `ui-audit` |
| **新增/修改后端 API、Service、数据库** | `03-privacy-security-compliance.md`<br>`05-backend-ai-data-architecture.md` | `backend-architect` |
| **修改 AI 问答、RAG、VASI 评估、Prompt** | `05-backend-ai-data-architecture.md` (§四) | `llm-testing`<br>`backend-architect` |
| **执行构建、部署、Nginx 配置或上线** | `06-environments-deployment-ops.md`<br>`07-testing-quality-checklists.md` | `deploy-verification`<br>`pwa-verification`<br>`nginx-config` |

### Step 3：使用 CodeGraph 进行结构化影响面分析
本项目配置了基于 AST 的 `codegraph` 索引。在修改公共函数、组件、数据模型或 API 路由前：
1. 若刚完成文件修改，先执行 `codegraph sync` 同步索引。
2. 使用 `codegraph_search`、`codegraph_callers`、`codegraph_impact` 追踪符号的所有调用方，确保修改不会破坏其他模块。

### Step 4：开发、验证与立即部署测试环境
1. 严格按照规范编写代码，保持前后端类型安全（前端 `npx vue-tsc --noEmit` 零错误，后端兼容 Python 3.9 类型注解）。
2. 将变更记录写入 `/root/subskin/DEPLOY_LOG.md`。
3. **立即部署对应的环境**：
   - 用户端改动（`web/app/`）：立即执行 `cd /root/subskin/web/app && npm run build` 部署至 `staging.subskin.cn`（**未经用户明确指令，绝对禁止执行 `npm run deploy:prod`**）。
   - 管理后台改动（`web/admin/`）：立即执行 `cd /root/subskin/web/admin && npx vite build` 部署至 `admin.subskin.cn`。
   - 后端改动（`web/backend/`）：修改前必须提醒用户「⚠️ 后端修改会立即影响所有正式环境用户」，重启 `systemctl restart subskin-backend` 并验证 `/api/health`。

### Step 5：交接留痕与规范同步（Handover & Doc Sync）
任务完成前，必须确保下一个接手的 Agent 不会遇到信息断层：
1. **代码索引同步**：执行 `codegraph sync`。
2. **更新 `DEPLOY_LOG.md`**：准确记录本次构建的 `buildTime`、修改文件清单与功能说明。
3. **更新开发文档**：如果本次任务新增了页面路由、修改了模块名称、调整了数据库表结构或新增了工程约定，**必须同步更新 `docs/standards/` 下对应的规范文档与 `AGENTS.md`，并重新构建 `web/admin`（`npx vite build`）**，确保管理后台「开发文档」栏目始终反映最新架构。
4. **清理临时制品**：删除临时脚本、一次性调试文件，保持仓库整洁。

---

## 四、统一 Skill 库目录与职责一览

所有 Skill 统一存放在 `/root/subskin/.agents/skills/<skill-name>/SKILL.md`，要求包含标准 YAML frontmatter（`name` + `description`），且禁止绑定特定工具私有字段：

| Skill 名称 | 路径 | 核心守门职责 |
|------------|------|--------------|
| `frontend-architect` | `.agents/skills/frontend-architect/SKILL.md` | Vue 3 + TS 组件架构、单文件 <500 行、Composables 抽离、设计令牌强制使用 |
| `backend-architect` | `.agents/skills/backend-architect/SKILL.md` | FastAPI 三层架构、服务层零框架依赖、领域异常转换、异常详情零泄露、Python 3.9 兼容 |
| `ui-audit` | `.agents/skills/ui-audit/SKILL.md` | 15 条全站 UI/UX 铁律审计、深色模式完整性、微信/华为浏览器兼容、海报与分享页一致性 |
| `vue-tsc-guard` | `.agents/skills/vue-tsc-guard/SKILL.md` | TypeScript 严格类型检查守门，防止 `TS6133`/`TS2339` 等阻塞生产环境构建 |
| `deploy-verification` | `.agents/skills/deploy-verification/SKILL.md` | Staging 与 Production 构建产物、Bundle 体积、关键特性对齐验证 |
| `pwa-verification` | `.agents/skills/pwa-verification/SKILL.md` | `version.json`、`manifest.webmanifest`、`sw.js` 及环境更新提示横幅验证 |
| `nginx-config` | `.agents/skills/nginx-config/SKILL.md` | Production / Staging / Admin 三套 Nginx 站点配置、SSL、反向代理与 `nginx -t` 校验 |
| `llm-testing` | `.agents/skills/llm-testing/SKILL.md` | DashScope/Volcengine LLM 配置、RAG 向量化（`text-embedding-v4`）、智能问答与 VASI 接口验证 |
| `3d-model-work` | `.agents/skills/3d-model-work/SKILL.md` | `DigitalHuman.vue`（24 部位 SVG 木头小人）与 3D 资源维护规范 |
| `brainstorming` | `.agents/skills/brainstorming/SKILL.md` | 复杂新功能开发前的需求澄清、边界探索与方案比选 |
| `planning-with-files` | `.agents/skills/planning-with-files/SKILL.md` | 在 `hermes_plan/` 中编写结构化实施计划与阶段检查点 |

---

## 五、接手 Agent 快速提示词模板（Copy-Paste Prompt）

当管理员或开发者开启一个新的 AI 会话时，可直接复制以下指令发送给任何 Agent：

```text
请先完整阅读 /root/subskin/AGENTS.md 以及 /root/subskin/docs/standards/ 下的规范文档，并检查 DEPLOY_LOG.md 中的 Pending Changes。
在接下来的开发任务中，请严格遵守：
1. 三环境隔离与零容忍部署原则（用户端改动先构建部署到 staging.subskin.cn，未经我明确指令严禁部署到正式环境；管理后台改动在 web/admin 构建直接生效）；
2. Cursor & GitHub × 医疗温度全站设计规范（使用 main.css 设计令牌、RemixIcon 图标、完整 dark: 模式、微信 WebView 与华为浏览器兼容）；
3. L1-L4 隐私与数据安全生死线（绝不硬编码敏感信息、绝不向客户端泄露内部异常 str(e)、L3 数据强制脱敏）。
```

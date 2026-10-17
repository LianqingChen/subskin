# 07 · 质量门禁、测试规范与全栈交付验收清单

> **文档编号**: `STD-07`  
> **适用范围**: 所有前端、后端、AI 算法、分享海报与管理后台任务的完工验收  
> **关联 Skill**: `vue-tsc-guard`、`ui-audit`、`backend-architect`、`deploy-verification`、`pwa-verification`  
> **更新日期**: 2026-10-17  
> **状态**: 强制执行（MANDATORY — 未通过对应清单检查不得宣告任务完成）

---

## 一、自动化质量门禁命令速查（Automated Quality Gates）

任何 Agent 在提交代码或向用户汇报“已完成”前，必须根据修改范围运行对应的自动化验证命令：

### 1. 用户端前端门禁 (`web/app/`)
```bash
# 1) TypeScript 全量严格类型检查（必须 0 报错）
cd /root/subskin/web/app && npm run type-check

# 2) 构建并部署至测试环境 staging.subskin.cn
cd /root/subskin/web/app && npm run build

# 3) 校验构建产物与 PWA 清单
cat /usr/share/nginx/html/subskin-staging/version.json
ls -lh /usr/share/nginx/html/subskin-staging/sw.js /usr/share/nginx/html/subskin-staging/manifest.webmanifest
```

### 2. 管理后台前端门禁 (`web/admin/`)
```bash
# 构建管理后台并直接部署至 /usr/share/nginx/html/subskin-admin/
cd /root/subskin/web/admin && npx vite build

# 校验管理后台构建时间戳
cat /usr/share/nginx/html/subskin-admin/version.json
```

### 3. 后端与数据管线门禁 (`web/backend/` & `src/`)
```bash
cd /root/subskin
source .venv/bin/activate

# 1) 运行单元与回归测试
pytest

# 2) 运行 Ruff 代码静态检查
ruff check web/backend/ src/ tests/

# 3) 检查后端健康状态
curl -s http://127.0.0.1:8000/api/health
```

### 4. CodeGraph 代码图谱同步门禁
```bash
# 每次完成一批文件编辑后立即执行，确保 AST 索引最新
codegraph sync
```

---

## 二、五大场景化交付验收清单（Delivery Checklists）

### 清单 A：新增或修改用户端页面 / 组件验收清单
- [ ] **A1. 容器与布局**：外层容器是否使用了标准 `.page` / `.page-wide` / `.page-narrow`？底部 `fixed` 栏是否添加了 `.app-fixed-x` 避让桌面侧栏？移动端底部抽屉是否有 `sm:max-w-md sm:mx-auto` 桌面宽度约束？
- [ ] **A2. 配色与暗色模式**：是否 100% 使用 `main.css` 中的 `--color-primary-*` 与表面令牌？是否所有背景、文字、边框、输入框、弹窗均具备完整的 `dark:*` 适配？
- [ ] **A3. 图标与数字排版**：是否全部使用 RemixIcon (`<i class="ri-*"></i>`)，零内联业务 `<svg>`、零 Emoji 图标？统计数值、日期、百分比是否添加了 `tabular-nums`？
- [ ] **A4. 微信 WebView 与华为浏览器兼容**：Flex 容器内的 `<input class="flex-1">` 是否加了 `min-w-0`？手写 `100dvh`/`100svh` 是否前置了 `100vh` 回退？Canvas 是否使用 `traceRoundedRect` 而非 `ctx.roundRect`？
- [ ] **A5. 模块命名与 AI 导航同步**：模块名称是否严格对齐 `web/shared/site-modules.json`？若新增了路由或功能，是否同步更新了 `site-modules.json`、`page-names.json` 与 `rag.py`？
- [ ] **A6. 多视口实测**：是否在 `375px`（手机）、`768px`（iPad 竖屏）、`1024px`（iPad 横屏）、`1440px`（桌面大屏）下验证无横向滚动条、无文字截断、无按钮挤压？

### 清单 B：对外分享落地页与 Canvas 生成海报验收清单
- [ ] **B1. 品牌视觉统一**：海报顶栏是否采用 `#0f766e` → `#0d9488` 渐变？内嵌卡片是否为 `#f8fafc` 底色 + `#e2e8f0` 描边？
- [ ] **B2. 字体与圆角安全**：Canvas `ctx.font` 是否包含 `"HarmonyOS Sans SC", "PingFang SC"`？是否完全消除了原生 `ctx.roundRect()` 调用？
- [ ] **B3. 署名、二维码与免责声明**：尾注是否统一为 `SubSkin · 白癜风病友的AI记录和分享社区` 及标准模块名（严禁出现旧名）？二维码路由是否真实可访问？底部是否包含医疗免责声明？
- [ ] **B4. 分享审计与权限**：生成公开分享链接是否记录了 `AuditLog`？未公开或已撤销的 Token 访问时是否正确拦截？

### 清单 C：新增或修改后端 API / Service / 数据库验收清单
- [ ] **C1. 共享后端预警**：修改前是否已明确告知用户“⚠️ 后端修改会立即影响所有正式环境用户”？
- [ ] **C2. 三层架构纯净性**：`services/` 层是否做到了零 `fastapi` 导入、只抛 `SubSkinException` 子类领域异常？是否存在跨模块导入 `_private` 私有函数的违规行为？
- [ ] **C3. 异常零泄露与 PII 脱敏**：所有 `HTTPException(status_code=500)` 的 `detail` 是否均为安全的通用中文文案（绝不包含 `str(e)`）？返回的手机号、邮箱是否已通过 `get_user_response` 或 `redact_pii` 脱敏？
- [ ] **C4. Python 3.9 与增量迁移兼容**：是否避免了 `X | None` 与 `match/case` 语法？数据库变更是否严格遵循“只增不删、向后兼容”？

### 清单 D：推送至正式环境（Production Full Sync）前终审清单
- [ ] **D1. 用户明确授权**：是否已获得用户的明确指令（如“推送到正式环境” / “更新到正式环境”）？
- [ ] **D2. 全量变更核对**：是否已向用户展示 `DEPLOY_LOG.md` 中 `Pending Changes` 的完整累积列表？
- [ ] **D3. Staging 零缺陷确认**：`staging.subskin.cn` 上所有待发功能是否已通过测试，且 `npm run type-check` 零报错？
- [ ] **D4. 产线构建与双端校验**：执行 `npm run deploy:prod` 后，是否已运行 `deploy-verification` 与 `pwa-verification` 确认 `subskin.cn` 的 `version.json`、`manifest.webmanifest`、`sw.js` 与关键页面全部正常？
- [ ] **D5. 账本归档**：是否已将 `DEPLOY_LOG.md` 中的所有 `Pending Changes` 移入 `Production Deployment History`？

### 清单 E：Agent 会话结束与交接清理清单（Session Handover Cleanup）
- [ ] **E1. 变更账本最新**：本次所有 Staging / Admin / Backend 改动是否已完整写入 `DEPLOY_LOG.md`？
- [ ] **E2. 规范文档同步**：若本次改动涉及架构、路由、模块名或设计规范演进，是否已同步更新 `docs/standards/*.md` 与 `AGENTS.md`，并重新构建 `web/admin`？
- [ ] **E3. 临时文件清理**：是否已删除所有临时测试脚本、一次性任务草稿，并保持實施计划规整存放在 `hermes_plan/`？
- [ ] **E4. AST 索引同步**：是否已运行 `codegraph sync`？

# 06 · 三套环境隔离、部署流程、Nginx 与运维监控规范

> **文档编号**: `STD-06`  
> **适用范围**: 测试环境（`staging.subskin.cn`）、正式环境（`subskin.cn`）、管理后台（`admin.subskin.cn`）、共享后端与 Nginx  
> **关联 Skill**: `deploy-verification`、`pwa-verification`、`nginx-config`  
> **更新日期**: 2026-10-17  
> **状态**: 强制执行（零容忍 — 违反任何部署规则均视为严重违规）

---

## 一、三套环境全景拓扑与严格边界

SubSkin 线上运行着 **三套独立的前端站点** 与 **一个共享的 FastAPI 后端**。任何开发者或 Agent 必须熟记下表，**绝对禁止交叉部署**：

| 环境名称 | 访问域名 | 源代码目录 | 构建命令 | Nginx 静态产物目录 | Nginx 配置文件 | 发布审批要求 |
|----------|----------|------------|----------|---------------------|----------------|--------------|
| **1. 测试环境 (Staging)** | `https://staging.subskin.cn` | `/root/subskin/web/app/` | `npm run build` | `/usr/share/nginx/html/subskin-staging/` | `/etc/nginx/conf.d/subskin-staging.conf` | **每次修改用户端代码后立即自动部署**，无需等待用户催促 |
| **2. 正式环境 (Production)** | `https://subskin.cn`<br>`https://www.subskin.cn` | `/root/subskin/web/app/` | `npm run deploy:prod` | `/usr/share/nginx/html/subskin/` | `/etc/nginx/conf.d/subskin.conf` | **必须先在 Staging 验证，并获得用户明确口头指令后才可执行全量同步** |
| **3. 管理后台 (Admin)** | `https://admin.subskin.cn` | `/root/subskin/web/admin/` | `npx vite build` | `/usr/share/nginx/html/subskin-admin/` | `/etc/nginx/conf.d/subskin-admin.conf` | 独立内部应用，无测试/正式之分，**修改后直接构建生效** |
| **4. 共享后端 (Backend)** | `http://127.0.0.1:8000/api/*` | `/root/subskin/web/backend/` | `systemctl restart subskin-backend` | — (Systemd 服务) | 由上述三个 Nginx 配置的 `location /api/` 反向代理 | **修改前必须向用户发出共享后端影响预警** |

---

## 二、零容忍部署四大铁律（Zero-Tolerance Deployment Rules）

### 铁律 1：用户端改动必须「立即部署 Staging，严禁擅自发 Production」
1. 每当对 `web/app/` 完成任何代码修改（哪怕只改了 1 行样式或文案），Agent **必须立即**执行：
   ```bash
   cd /root/subskin/web/app && npm run type-check && npm run build
   ```
2. 构建完成后，立即将变更追加记录到 `/root/subskin/DEPLOY_LOG.md` 的 **`Pending Changes`** 表格中，并告知用户：「已部署到测试环境（https://staging.subskin.cn）」。
3. **在用户明确说出“推送到正式环境” / “更新到正式环境” / “deploy to prod”之前，绝对禁止运行 `npm run deploy:prod`！**

### 铁律 2：正式环境发布必须是「全量同步（Full Sync）」
当用户在 Staging 验收通过并下达“推送到正式环境”指令时：
1. 查阅 `/root/subskin/DEPLOY_LOG.md` 中的 **`Pending Changes`**，向用户完整列出自上次正式环境发布以来累积的所有变更项。
2. 执行 `cd /root/subskin/web/app && npm run deploy:prod`。
3. 构建完成后，在 `DEPLOY_LOG.md` 中将所有 `Pending Changes` 作为一个完整批次移入 **`Production Deployment History`**，清空 `Pending Changes`。
4. **严禁选择性/部分发布**：Staging 与 Production 必须始终保持 100% 代码基线同步（除 4 项环境标识差异外）。

### 铁律 3：严禁跨应用交叉部署（Three Strikes Out）
- ❌ **绝对禁止**将 `web/app/` 的构建产物复制到 `/usr/share/nginx/html/subskin-admin/`（会导致管理后台被覆盖为普通用户端！）。
- ❌ **绝对禁止**将 `web/admin/` 的构建产物复制到 `subskin` 或 `subskin-staging`。
- ❌ **绝对禁止**直接用 `cp -r` 将 `subskin-staging` 目录暴力覆盖到 `subskin`（因为两者的 `manifest.webmanifest`、`version.json` 和内置 `__APP_ENV__` 常量不同，必须分别通过 `npm run build` 和 `npm run deploy:prod` 构建）。

### 铁律 4：每次构建后必须执行四项健康核验
每次执行完前端构建或后端重启后，必须运行以下命令验证结果：
```bash
# 1. 验证 Staging version.json 时间戳已更新
cat /usr/share/nginx/html/subskin-staging/version.json

# 2. 若更新了管理后台，验证 Admin version.json 时间戳已更新
cat /usr/share/nginx/html/subskin-admin/version.json

# 3. 验证共享后端服务健康状态
curl -s http://127.0.0.1:8000/api/health
```

---

## 三、Nginx 配置与反向代理维护规范

1. **配置文件位置**：
   - 线上实际生效配置位于 `/etc/nginx/conf.d/subskin*.conf`（仓库 `web/deploy/` 下为参考模板，以 `/etc/nginx/conf.d/` 为准）。
2. **修改 Nginx 的强制安全流程**：
   ```bash
   # 第一步：先测试语法，绝不盲目重启
   nginx -t
   # 第二步：确认 syntax is ok 且 test is successful 后，平滑重载
   systemctl reload nginx
   ```
3. **关键路由规则保护**：
   - `/api/` 必须反向代理至 `http://127.0.0.1:8000`，且保留 WebSocket 升级头（用于 IM/流式响应）及 `client_max_body_size`（支持高清患处图片与化验单上传）。
   - `version.json` 与 `sw.js` 必须配置 `Cache-Control: no-cache, no-store, must-revalidate`，确保 PWA 版本检测与更新永不被浏览器强缓存卡死。

---

## 四、故障分级与应急回滚预案（Incident Response & Rollback）

| 故障等级 | 典型场景 | 响应时限与处置流程 |
|----------|----------|--------------------|
| **🔴 P0 致命** | 网站白屏无法打开、后端进程崩溃 502、数据泄露风险 | **立即响应**：先回滚后端代码并 `systemctl restart subskin-backend` 或回滚前端并重新构建，恢复线上可用后再排查根因。 |
| **🟠 P1 严重** | 核心功能不可用（无法登录、AI 问答报错、日记无法上传照片） | **1 小时内**：定位根因 → 修复并部署 Staging 验证 → 请用户确认后紧急同步 Production。 |
| **🟡 P2 一般** | 局部样式错位、次要筛选失效、有替代操作路径 | 按标准流程修复 → 部署 Staging → 随下一次常规批次同步 Production。 |
| **🟢 P3 轻微** | 文案微调、边缘设备像素级细节优化 | 按标准流程修复 → 部署 Staging 累积。 |

### 应急重启命令速查
```bash
# 查看后端服务状态与最近 50 行错误日志
systemctl status subskin-backend
journalctl -u subskin-backend -n 50 --no-pager

# 重启共享后端服务并检查健康端点
systemctl restart subskin-backend && sleep 2 && curl -s http://127.0.0.1:8000/api/health
```

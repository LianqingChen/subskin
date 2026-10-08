# 管理后台「终端」Tab — tmux 持久化网页终端 + AI Agent

- 日期：2026-09-27
- 目标环境：admin.subskin.cn（`web/admin/`，独立 SPA，无 staging/prod 之分）
- 状态：实施中

## 一、需求

在 SubSkin 管理后台新增独立 tab「终端」：

1. 网页内直接输入终端命令，控制服务器
2. 用 tmux 持久化任务：关闭浏览器/重启后端后任务仍在跑，重开页面可接回
3. AI 能力：
   - 自然语言 → 命令生成（带解释与风险评级，确认后执行）
   - 输出解读 / 报错诊断
   - 一键启动 agent CLI 会话（claude / codex / dsh / opencode）
   - 自主 agent 循环（多步执行-观察-纠错）
4. 严格安全模式：仅 `is_admin` 可访问；危险命令拦截 + 二次确认；全量审计

## 二、决策（已与用户确认）

| 决策点 | 选择 |
|--------|------|
| 终端引擎 | 真 PTY + xterm.js（Python stdlib `pty` + `tmux attach`） |
| AI 范围 | 四项全做：NL→命令、输出解读、agent CLI 会话、自主 agent 循环 |
| 安全策略 | 严格模式：仅 is_admin、危险命令拦截+二次确认、全量 AuditLog |
| 交付 | 完整实现并部署到 admin.subskin.cn（含 nginx WS 修复） |

## 三、架构

```
┌─ admin.subskin.cn/#/terminal ───────────────────────────────┐
│  SessionSidebar │ xterm.js TerminalPane │ AI 面板            │
└───────┬──────────────────────┬──────────────────┬───────────┘
        │ REST                 │ WS 终端          │ WS Agent
        │ /api/admin/terminal/ │ /ws?token=&...   │ /agent/ws
        ▼                      ▼                  ▼
┌─ web/backend/api/admin_terminal.py ─────────────────────────┐
│  REST: get_admin_user 依赖                                   │
│  WS:   verify_token_ws(token) + is_admin 校验                │
└───────┬──────────────────────┬──────────────────┬───────────┘
        ▼                      ▼                  ▼
  services/terminal.py   services/terminal_safety.py   services/terminal_agent.py
  (tmux CRUD + PTY)      (风险评级 + 脱敏, 纯函数)      (LLM: suggest/explain/loop)
        │
        ▼
  tmux -L subskin new-session -A -s subskin-term-<name>
```

### 持久化语义

- 每个网页终端 = 一个 tmux 会话 `subskin-term-<name>`
- 专用 tmux socket：`-L subskin`（与操作员手上的默认 tmux 隔离，避免互相干扰）
- 浏览器关闭 → `tmux attach` 进程退出，**tmux 会话继续运行**
- 后端重启 → 同上，会话不受影响，重开页面重新 attach
- 服务器重启 → tmux 会话丢失（如需跨重启，需 systemd 恢复单元，本期不做）

## 四、文件清单

### 后端（新增）

| 文件 | 职责 |
|------|------|
| `web/backend/services/terminal.py` | tmux 会话 CRUD、PTY 桥接、pane 抓取、send-keys。**不依赖 FastAPI** |
| `web/backend/services/terminal_safety.py` | 命令风险评级（safe/warn/danger）、危险模式库、敏感信息脱敏。纯函数 |
| `web/backend/services/terminal_agent.py` | LLM 调用：`suggest_command` / `explain_output` / 自主循环决策。**不依赖 FastAPI** |
| `web/backend/api/admin_terminal.py` | REST + 终端 WS + Agent WS，唯一允许依赖 FastAPI 的层 |

### 后端（修改）

- `web/backend/app/main.py`：`app.include_router(admin_terminal.router)`

### 前端（新增，`web/admin/`）

| 文件 | 职责 | 行数上限 |
|------|------|----------|
| `src/api/terminal.ts` | axios REST 封装 + WS URL 构造 | — |
| `src/composables/useTerminalSessions.ts` | 会话列表/新建/删除/重命名 | ≤200 |
| `src/composables/useTerminalSocket.ts` | xterm 实例 + WS 生命周期 + 尺寸同步 | ≤200 |
| `src/composables/useTerminalAgent.ts` | AI suggest / explain / agent 循环状态 | ≤200 |
| `src/components/terminal/SessionSidebar.vue` | 会话列表 + 新建/关闭/快捷启动 | ≤400 |
| `src/components/terminal/TerminalPane.vue` | xterm 容器 + 工具栏（清屏/重连/尺寸） | ≤400 |
| `src/components/terminal/AiCommandPanel.vue` | 自然语言 → 命令 | ≤400 |
| `src/components/terminal/AiExplainPanel.vue` | 输出解读 / 报错诊断 | ≤400 |
| `src/components/terminal/AgentTaskPanel.vue` | 自主 agent 循环 | ≤400 |
| `src/views/Terminal.vue` | 组合根，仅编排 | ≤500 |

### 前端（修改）

- `package.json`：`@xterm/xterm`、`@xterm/addon-fit`、`@xterm/addon-web-links`
- `src/router/index.ts`：新增 `terminal` 路由
- `src/views/Layout.vue`：菜单项「终端」`ri-terminal-box-line` + 路由映射

### 运维（修改）

- `/etc/nginx/conf.d/subskin-admin.conf`：新增 `location /api/admin/terminal/` 块，含
  `proxy_http_version 1.1` + `Upgrade`/`Connection` + 长超时。**不改动既有 `/api` 块**，最小化影响面。

## 五、安全设计（严格模式）

### 1. 鉴权

- REST：`Depends(get_admin_user)`
- WS：浏览器无法设置 header → `?token=<access_token>`；复用 `services/auth.py::verify_token_ws`，
  再强制 `user.is_admin`，否则 `close(code=4403)`
- 不把 token 写入任何日志

### 2. 危险命令拦截

`terminal_safety.assess_command(cmd)` → `{"risk": "safe|warn|danger", "reasons": [...]}`

danger 模式（示例）：
- 递归删除根/关键目录：`rm -rf /`、`rm -rf /*`、`rm -rf /root/subskin`
- 磁盘/文件系统：`mkfs`、`dd ... of=/dev/`、`> /dev/sd*`、`fdisk`、`parted`
- 关机/重启：`shutdown`、`reboot`、`halt`、`poweroff`、`init 0/6`
- 杀伤进程/服务：`kill -9 1`、`systemctl stop subskin-backend`、`pkill -9 -f uvicorn`
- fork 炸弹：`:(){:|:&};:`
- 权限/属主爆破：`chmod -R 777 /`、`chown -R ... /`
- 数据库破坏：`DROP DATABASE`、`DROP TABLE`、`truncate`
- 强制推送/历史重写：`git push --force`、`git reset --hard`（warn 级）
- 凭据外泄：`cat /root/subskin/.env` 等（warn 级，提示可能泄露密钥）

**前端二次确认**：danger 命令必须在弹窗中手抄/明确确认（显示风险原因），warn 级确认一次，safe 直接放行。

### 3. 审计

- 所有 REST 动作与 PTY 中执行的命令 → `AuditLogService.log(db, action="terminal.exec", actor_id=admin.id, target_type="terminal_session", details={"session":..., "command":...})`
- 写审计前用 `terminal_safety.redact_secrets()` 脱敏 `password=`/`token=`/`api_key=`/`Bearer xxx` 等
- 审计失败不阻塞命令执行，但必须 `logger.error`

### 4. 其他

- tmux socket 独立（`-L subskin`），会话名白名单 `[A-Za-z0-9_-]{1,32}` → 杜绝参数注入
- 命令通过 `tmux send-keys -l -- <text>` 传递，永不经过 shell 拼接
- 子进程 cwd 限定在允许目录白名单内（默认 `/root/subskin`）

## 六、AI 设计

统一走 `web/backend/utils/llm_config.py::get_llm_config()`（复用项目 LLM 配置，含 LLMConfigService 模块级覆盖）。

| 能力 | 输入 | 输出 |
|------|------|------|
| `suggest_command` | 用户意图 + 当前 pane 上下文（近 N 行）+ 系统信息 | `{command, explanation, risk, danger_reason, alternatives[]}` |
| `explain_output` | pane 输出（近 N 行） | `{summary, root_cause, fix_commands[], severity}` |
| agent 循环 | 目标 + 每步 pane 输出 | 每步 `{thought, command, is_done, needs_confirm}` |

LLM 返回严格 JSON；解析失败时降级为「原样文本建议」而非崩溃。
无可用 LLM 配置（`provider == "none"`）时，接口返回明确提示，不假装成功。

### 自主 agent 循环（进阶，最高风险）

- 服务端驱动，WebSocket 逐步推送：`thought` → `command` → 等待前端确认 → 执行 → 抓取输出 → 下一轮
- 硬上限：默认 12 步（前端可调，上限 30）
- 每步命令**必须**经过 `assess_command`；danger 一律拒绝执行，warn 需人工确认
- 「自动执行安全命令」为**显式开关**，默认关闭（即每步都要点确认）
- 可随时「中止」，中止后 tmux 会话内容保留供人工接管

## 七、验证计划

1. 后端单测级冒烟：`curl` 列会话 / 建会话 / 删会话（带 admin token）
2. WS 冒烟：`websockets` 客户端 attach，发 `echo hello`，断言回显
3. tmux 持久化：建会话 → 断开 WS → `tmux -L subskin ls` 确认仍在 → 重连看到历史
4. 安全检查：`rm -rf /` 被判 danger；审计表出现脱敏命令
5. nginx：`nginx -t` 通过；`wss://admin.subskin.cn/api/admin/terminal/ws` 握手 101
6. 前端：`npm run build`（vue-tsc）零错误；`npx vite build` 部署
7. 浏览器端到端：admin.subskin.cn/#/terminal 实际执行命令、AI 生成、agent 循环
8. 移动端：375px 下可用（终端以横向滚动 / 全屏模式呈现）

## 八、风险与回滚

| 风险 | 缓解 |
|------|------|
| 后端重启影响正式环境 | 纯新增文件 + 一行 include_router，无 DB schema 变更、无既有接口行为改动；重启前先备份文件清单 |
| nginx 改动影响 admin 整站 | 仅新增独立 `location` 块，不动 `/api`；`nginx -t` 通过后才 reload；保留 `.bak` |
| 远程 shell 权限过大 | 严格模式 + 危险命令拦截 + 全量审计；tmux socket 隔离 |
| 前端新增依赖构建失败 | `@xterm/*` 为纯前端包，构建失败可回退 `package.json` 与 lock 文件 |
| 会话被误杀 | 删除会话前端二次确认；tmux 会话名带前缀，列表只显示前缀匹配的会话 |

回滚：删除 `admin_terminal` 路由注册 → 重启后端；还原 nginx `.bak` → reload；`git` 还原 admin 前端 → 重新 build。

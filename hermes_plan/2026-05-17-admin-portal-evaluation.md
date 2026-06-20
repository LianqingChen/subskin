# SubSkin 管理后台评估与方案推荐

日期：2026-05-17
评估人：Hermes

---

## 一、现状盘点

### 1.1 技术架构

| 层级 | 技术栈 | 位置 |
|------|--------|------|
| 前端（用户端） | Vue 3 + Vite + TailwindCSS + Pinia + PWA | `web/app/` |
| 后端 API | FastAPI + SQLAlchemy + SQLite | `web/backend/` |
| 部署 | nginx + systemd | `/usr/share/nginx/html/subskin` |
| 数据库 | SQLite | `data/subskin.db`（约 20MB） |
| 域名 | subskin.cn / staging.subskin.cn | HTTPS |

### 1.2 已有管理类后端 API（基本就绪）

后端已经存在大量管理接口，只是缺少统一的前端界面：

| 模块 | 路由前缀 | 说明 |
|------|----------|------|
| 数据监控 | `/api/analytics/*` | DAU、留存、漏斗、页面访问、功能使用 |
| 审计日志 | `/api/audit/*` | 用户操作审计、日志查询、撤销支持 |
| 评论管理 | `/api/admin/comment/*` | 评论审核、删除、状态管理 |
| 内容审核/风控 | `/api/moderation/*` | AI 自动审核、人工复核、违规记录、用户处罚 |
| 用户管理 | `/api/users/*` | 用户列表、封号/禁言、资料管理 |
| IM 管理 | `/api/im_admin/*` | 群组、消息、举报管理 |
| 事件追踪 | `/api/events/*` | 用户行为事件查询 |
| 通知 | `/api/notifications/*` | 系统通知推送 |

### 1.3 数据库已有管理相关字段

`users` 表：
- `is_admin` — 管理员标识
- `user_status` — normal / muted / banned
- `muted_until`, `banned_at`, `ban_reason` — 禁言/封号
- `violation_count`, `critical_count`, `warning_count` — 违规统计
- `is_test` — 测试账号过滤

### 1.4 缺失的管理能力

- 无管理后台前端界面（目前只有后端 API）
- 内容生成管理（每日简报生成状态、知识库更新触发）
- LLM 消费管理（各模型调用量、费用估算、API Key 状态、模型切换）
- 系统资源管理（磁盘/日志/备份/服务状态/定时任务监控）
- 数据库级操作（用户数据检索、批量导出、数据修复）

---

## 二、需求拆解

你提到的 6 大模块，按优先级和依赖关系拆解：

```
P0（核心）
  ├─ 网站数据监控 → 后端已有 analytics，只需前端看板
  ├─ 用户管理 → 后端已有 user + moderation，只需前端界面
  └─ 风控管理 → 后端已有 moderation + audit，只需前端界面

P1（重要）
  ├─ 内容生成 → 需新增后端接口（简报生成触发、知识库更新状态）
  └─ 后台大模型消费及管理 → 需新增后端接口（调用量统计、费用、Key 管理）

P2（进阶）
  └─ 系统及资源管理 → 需新增后端接口（systemd 状态、磁盘/日志、备份）
```

---

## 三、方案对比

### 方案 A：在用户端前端里加 `/admin` 路由

**做法**：在 `web/app/` 的 Vue Router 里增加 `/admin/*` 路由，通过路由守卫限制访问。

| 维度 | 评估 |
|------|------|
| 开发成本 | 低，复用现有项目和组件 |
| 构建产物 | 与用户端混在一起，admin 代码会打进 PWA bundle |
| UI/UX | 差。用户端是 mobile-first 设计，管理后台需要 desktop-first（表格、复杂筛选、大屏） |
| 安全隔离 | 弱。同域名、同构建产物，难以做 IP 白名单、独立缓存策略 |
| 长期维护 | 差。两种 UI 范式在同一个代码库，会越来越臃肿 |
| **结论** | 不推荐 |

### 方案 B：独立管理后台前端项目（推荐）

**做法**：新建 `web/admin/` 目录，独立 Vite + Vue 3 项目，共享后端 FastAPI。部署上可用子域名 `admin.subskin.cn` 或子路径 `/admin`。

| 维度 | 评估 |
|------|------|
| 开发成本 | 中。新建项目初期有脚手架工作量，但后端 API 基本就绪 |
| 构建产物 | 独立构建，不污染 PWA，可针对 desktop 优化 |
| UI/UX | 优。可选用 Naive UI / Ant Design Vue 等成熟 Admin 组件库，天然适配桌面端 |
| 安全隔离 | 强。可独立配置：IP 白名单、子域名隔离、独立缓存/安全头 |
| 长期维护 | 优。用户端和管理端解耦，迭代互不干扰 |
| **结论** | **强烈推荐** |

### 方案 C：独立前后端 + 独立数据库

**做法**：管理后台有自己的 FastAPI 服务和独立数据库，通过数据同步或只读副本连接主库。

| 维度 | 评估 |
|------|------|
| 开发成本 | 高。需要维护第二套后端服务、数据库同步、部署流程 |
| 适用场景 | 大规模系统（数据量 TB 级、团队 20+ 人） |
| 当前适用性 | 过度设计。SubSkin 数据量仅 20MB SQLite，后端服务资源占用很低 |
| **结论** | 现阶段不推荐，未来数据量和团队规模扩大后可考虑 |

---

## 四、推荐方案（方案 B 详细设计）

### 4.1 整体架构

```
用户端（已有）              管理后台（新建）
  web/app/                    web/admin/
       │                            │
       └────────┬───────────────────┘
                │
         nginx（统一入口）
                │
       ┌────────┴────────┐
       │                 │
subskin.cn        admin.subskin.cn  ← 推荐子域名部署
       │                 │
       └────────┬────────┘
                │
        FastAPI (localhost:8000)
                │
        SQLite (data/subskin.db)
```

### 4.2 前端技术选型

| 选型 | 建议 | 理由 |
|------|------|------|
| 框架 | Vue 3 + TypeScript | 与用户端一致，团队无需学习成本 |
| 构建 | Vite | 与用户端一致 |
| UI 组件库 | **Naive UI** | Vue 3 原生、Admin 场景成熟、暗色主题支持好、体积适中 |
| 状态管理 | Pinia | 与用户端一致 |
| 图表 | ECharts | 用户端已在用，可复用经验 |
| 路由 | Vue Router 4 + hash 模式 | admin 单页应用，hash 模式避免 nginx 额外配置 |

备选 UI 库：Ant Design Vue（生态最丰富，但 bundle 更大）、Element Plus（老牌稳定，但 Vue 3 适配略慢）。

### 4.3 后端调整（轻量）

现有后端不需要大改，只需：

1. **统一 Admin 路由前缀**：
   ```python
   # web/backend/api/admin/__init__.py
   from fastapi import APIRouter
   admin_router = APIRouter(prefix="/api/admin", tags=["Admin"])
   ```
   将现有分散的 admin 接口（analytics、comment_admin、im_admin 等）统一挂载。

2. **新增接口（按需迭代）**：
   - `GET /api/admin/llm/usage` — LLM 调用量统计
   - `GET /api/admin/llm/cost` — 费用估算
   - `POST /api/admin/content/generate-briefing` — 手动触发简报生成
   - `GET /api/admin/system/resources` — 系统资源（CPU/内存/磁盘）
   - `GET /api/admin/system/logs` — 后端日志查询
   - `GET /api/admin/system/services` — systemd 服务状态

3. **Admin 鉴权增强**：
   - 保留现有 `is_admin` + 手机号白名单机制
   - Admin 接口增加操作审计（已有 audit 服务可复用）
   - 可考虑增加 TOTP/二次验证（后期）

### 4.4 部署方案

**推荐：子域名部署（admin.subskin.cn）**

nginx 新增 server 块：

```nginx
server {
    listen 443 ssl http2;
    server_name admin.subskin.cn;

    ssl_certificate /etc/letsencrypt/live/subskin.cn/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/subskin.cn/privkey.pem;

    # 安全增强：可配置 IP 白名单（可选）
    # allow 1.2.3.4; deny all;

    location / {
        root /usr/share/nginx/html/subskin-admin;
        try_files $uri $uri/ /index.html;
        add_header Cache-Control "no-cache, no-store, must-revalidate";
    }

    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

前端构建产物输出到 `/usr/share/nginx/html/subskin-admin`。

**备选：子路径部署（subskin.cn/admin）**

- 优点：无需额外域名/SSL 证书
- 缺点：nginx 配置更复杂（SPA fallback、API 代理路径冲突），安全隔离较弱

### 4.5 目录结构规划

```
web/
├── app/                    # 用户端（已有，不动）
│   ├── src/
│   ├── package.json
│   └── vite.config.ts
│
├── admin/                  # 管理后台（新建）
│   ├── src/
│   │   ├── api/            # Admin API 客户端
│   │   ├── views/
│   │   │   ├── Dashboard.vue      # 数据监控首页
│   │   │   ├── UserManagement.vue # 用户管理
│   │   │   ├── Moderation.vue     # 风控/内容审核
│   │   │   ├── ContentGen.vue     # 内容生成
│   │   │   ├── LLMManage.vue      # 大模型管理
│   │   │   └── SystemMonitor.vue  # 系统资源
│   │   ├── components/     # 复用组件（图表卡片、数据表格等）
│   │   ├── router/
│   │   ├── stores/
│   │   └── App.vue
│   ├── package.json
│   └── vite.config.ts
│
└── backend/                # 后端（已有，轻量扩展）
    ├── api/
    │   ├── admin/          # 新增：统一 admin 路由
    │   ├── analytics.py
    │   ├── moderation.py
    │   └── ...
    └── app/main.py
```

---

## 五、实施建议（分阶段）

### Phase 1：基础骨架 + 数据监控（1-2 周）

1. 搭建 `web/admin/` 项目骨架（Vite + Vue 3 + Naive UI + Pinia）
2. 实现登录页（复用后端 `/api/user/login` + admin 校验）
3. 实现数据监控看板（复用 `/api/analytics/*`）
   - 核心指标卡片（DAU、新增用户、帖子数、VASI 评估数）
   - 趋势折线图
   - 页面访问排行
4. nginx 配置 `admin.subskin.cn` + SSL
5. 部署上线

### Phase 2：用户管理 + 风控（1 周）

1. 用户列表页（表格、筛选、搜索、分页）
2. 用户详情/编辑（状态修改、禁言/封号）
3. 内容审核队列（复用 `/api/moderation/*`）
4. 审计日志查询页（复用 `/api/audit/*`）

### Phase 3：内容生成 + LLM 管理（1 周）

1. 简报生成控制台（触发生成、查看历史、状态监控）
2. LLM 调用统计看板（各模型用量、费用估算）
3. API Key 状态管理（火山、OpenAI、Anthropic 等）

### Phase 4：系统资源管理（1 周）

1. 服务器资源监控（CPU、内存、磁盘、SQLite 大小）
2. 服务状态面板（systemd 服务：subskin-backend、subskin-scheduler）
3. 日志查看器（后端日志 tail/filter）
4. 备份状态

---

## 六、风险与注意事项

| 风险 | 应对措施 |
|------|----------|
| Admin 接口暴露公网 | nginx 加 IP 白名单；admin 接口独立鉴权；所有 admin 操作记入 audit log |
| 前端构建产物安全 | admin 站点不启用 PWA、不加 Service Worker，避免缓存敏感页面 |
| SQLite 并发写入 | Admin 后台主要是读取操作，写入通过后端 API 串行处理；当前并发量无压力 |
| 域名/SSL | 若使用 admin.subskin.cn，需确保证书覆盖该子域名（Let's Encrypt wildcard 或单独申请） |
| 前后端 CORS | admin 站点加入后端 CORS allow_origins；或走同域名代理（无 CORS） |

---

## 七、总结

| 项目 | 结论 |
|------|------|
| **是否值得单独切出管理后台** | **值得**。现有后端 API 已覆盖 60%+ 管理需求，但用户端前端不适合承载 Admin 功能 |
| **推荐方案** | **独立前端项目（web/admin/）+ 共享后端 FastAPI + 子域名部署** |
| **技术栈** | Vue 3 + Vite + Naive UI + ECharts |
| **预估工期** | 完整 4 个 Phase 约 4-5 周；Phase 1 上线约 1-2 周 |
| **最小可用（MVP）** | Phase 1（数据监控看板）即可上线给管理员使用 |

下一步如需推进，我可以帮你：
1. 搭建 `web/admin/` 项目骨架
2. 设计 Admin 路由聚合和鉴权增强
3. 实现 Phase 1 数据监控看板

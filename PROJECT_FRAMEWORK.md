# SubSkin 项目架构

> **更新时间**: 2026-05-25

## 项目定位

SubSkin 是一个面向白癜风患者和关注者的综合知识平台，由两大子系统构成：

1. **数据 Pipeline** (`src/`)：自动化爬取、AI 翻译、摘要生成
2. **社区 Web App** (`web/`)：Vue 3 PWA 前端 + FastAPI 后端

## 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                      展示层                              │
│  Vue 3 PWA (Vite) + Tailwind CSS + Three.js 3D          │
│  小白助手 │ 小白追踪 │ 小白社区 │ 小白百科                │
└────────────────────────┬────────────────────────────────┘
                         │ REST / WebSocket
┌────────────────────────┴────────────────────────────────┐
│                      应用层                              │
│  FastAPI + Uvicorn                                       │
│  Auth │ Community │ RAG │ VASI │ IM │ Medical Report     │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────┴────────────────────────────────┐
│                      数据层                              │
│  SQLAlchemy ORM + SQLite                                 │
│  Pydantic Models                                         │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────┴────────────────────────────────┐
│                      AI 层                               │
│  OpenAI / Anthropic / DashScope                          │
│  SAM / VLM 图像分割                                      │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                   数据 Pipeline (离线)                    │
│  Crawlers → Dedup → Translate → Summarize → Export       │
│  PubMed / Semantic Scholar / ClinicalTrials.gov          │
└─────────────────────────────────────────────────────────┘
```

## 前端架构 (`web/app/`)

- **框架**: Vue 3 + TypeScript + Vite
- **状态管理**: Pinia
- **样式**: Tailwind CSS (dark mode via `class` strategy)
- **PWA**: vite-plugin-pwa, Service Worker with runtime caching
- **3D**: Three.js (数字人体模型)
- **路由**: Vue Router (SPA mode)

### 页面模块

| 路由 | 模块 | 说明 |
|------|------|------|
| `/` | 小白助手 | AI 对话助手，RAG 问答 |
| `/tracker` | 小白追踪 | 3D 身体图、VASI 评估、报告管理 |
| `/community` | 小白社区 | 帖子信息流、发帖、互动 |
| `/encyclopedia` | 小白百科 | 白癜风知识库 |
| `/chat` | IM 聊天 | 即时通讯 |
| `/profile` | 个人中心 | 用户设置、隐私管理 |

## 后端架构 (`web/backend/`)

- **框架**: FastAPI + Uvicorn
- **数据库**: SQLite (via SQLAlchemy)
- **认证**: JWT + SMS/Email 验证码 + OAuth (微信/支付宝)

### 核心服务

| 服务 | 文件 | 职责 |
|------|------|------|
| Auth | `services/auth.py` | JWT 签发、验证码登录 |
| Community | `services/community.py` | 帖子 CRUD、信息流、关注 |
| RAG | `services/rag.py` | AI 问答、知识检索、站点导航 |
| VASI | `services/vasi.py` | 白斑图像分析、VASI 评分 |
| IM | `services/im_service.py` | WebSocket 即时通讯 |
| Medical | `services/medical/` | 报告解析、指标解读 |

## 数据 Pipeline 架构 (`src/`)

```
Crawlers → Processors → Exporters → Notifications
   ↓            ↓            ↓            ↓
 采集原始    翻译/摘要    JSON/MD     QQ/微信
 论文数据    去重/分类    导出        推送
```

## 数据隐私分级

项目实行四级数据分类，严格控制不同敏感级别的数据：

- **L4 极高**: 密码 (bcrypt)、JWT Token — 绝不对外暴露
- **L3 高**: 手机号、邮箱、病情图片 — API 脱敏返回
- **L2 中**: 昵称、头像、帖子内容 — 用户自主选择公开范围
- **L1 低**: 百科内容、统计数据 — 可公开访问

## 技术选型决策

| 决策点 | 选择 | 原因 |
|--------|------|------|
| 前端框架 | Vue 3 + Vite | 生态成熟，响应式优先 |
| PWA | vite-plugin-pwa | 离线可用，类原生体验 |
| CSS 方案 | Tailwind CSS | 原子化 CSS，暗色模式支持好 |
| 3D 引擎 | Three.js | 浏览器兼容性最好 |
| 后端框架 | FastAPI | 异步支持，自动 OpenAPI 文档 |
| 数据库 | SQLite | 轻量部署，单机足够 |
| 图标库 | RemixIcon | 开源免费，风格统一 |

# 04 · 前端技术栈、工程架构与 PWA 开发规范

> **文档编号**: `STD-04`  
> **适用范围**: 用户端 PWA（`web/app/`）与管理后台 SPA（`web/admin/`）  
> **关联 Skill**: `frontend-architect`、`pwa-verification`、`vue-tsc-guard`、`3d-model-work`  
> **更新日期**: 2026-10-17  
> **状态**: 强制执行（MANDATORY）

---

## 一、双前端工程架构边界（Main App vs Admin Panel）

SubSkin 仓库内包含**两个完全独立的前端工程**，必须严格区分，严禁交叉混用或错误部署：

| 维度 | 用户端主应用 (`web/app/`) | 管理后台 (`web/admin/`) |
|------|---------------------------|-------------------------|
| **目标受众** | 全体白癜风病友与访客（Production + Staging） | 平台内部管理员（仅 `is_admin = True` 可访问） |
| **核心技术栈** | Vue 3.4+ + TypeScript + Vite + Pinia + Vue Router + Tailwind CSS | Vue 3.4+ + TypeScript + Vite + Pinia + NaiveUI + ECharts + Tailwind CSS |
| **路由模式** | HTML5 History 模式（`createWebHistory`） | Hash 模式（`createWebHashHistory`，如 `/#/dashboard`） |
| **PWA / SW** | **完整 PWA**（`vite-plugin-pwa`、Service Worker、`version.json` 轮询） | **无 PWA**（在入口主动注销残留 Service Worker） |
| **构建部署命令** | 测试环境：`npm run build`<br>正式环境：`npm run deploy:prod`（需用户确认） | 直接构建生效：`npx vite build` |
| **部署输出目录** | 测试：`/usr/share/nginx/html/subskin-staging/`<br>正式：`/usr/share/nginx/html/subskin/` | `/usr/share/nginx/html/subskin-admin/` |

---

## 二、用户端 (`web/app/`) 目录结构与分层职责

```text
web/app/src/
├── components/         # 可复用 UI 与业务组件（按领域分子目录）
│   ├── auth/           # 登录/注册弹窗 (LoginModal.vue)
│   ├── chat/           # AI 问答与悬浮小白管家组件
│   ├── common/         # 全局通用组件 (AppHeader, AppSidebar, BottomNav, PageShareSheet, PageSharePoster 等)
│   ├── community/      # 发现社区卡片、发布抽屉、评论列表
│   ├── diary/          # 白斑日记、周报海报 (DiaryWeeklyPoster)、变化报告海报 (SkinReportPoster)
│   ├── hospitals/      # 就医经验列表、医院卡片、申诉弹窗
│   ├── report/         # 白斑报告展示组件
│   └── tracker/        # 数字人部位选择 (DigitalHuman.vue)、多边形核对 (MaskEditor)
├── composables/        # 组合式逻辑函数 (useTheme, useGeolocation, usePWA, useAuth 等)
├── router/             # 路由表与导航守卫 (router/index.ts)
├── services/           # API 请求封装与 HTTP 客户端 (api.ts)
├── stores/             # Pinia 全局状态管理
├── styles/             # 全局设计令牌与通用组件类 (main.css)
├── types/              # TypeScript 接口与类型定义
├── utils/              # 纯工具函数 (colors.ts, page-names.ts, assessment-story/render.ts 等)
└── views/              # 路由级页面视图组件 (*Page.vue / *View.vue)
```

---

## 三、Vue 3 + TypeScript 代码质量铁律

### 1. 组件体积与单一职责限制（500 行红线）
- 单个 `.vue` 文件（含 `<template>` + `<script setup>` + `<style>`）**不得超过 500 行**（推荐控制在 300 行以内）。
- 当页面逻辑复杂时（如 `AssessmentPage.vue`、`CommunityPage.vue`），必须：
  1. 将数据获取、状态机、分页/筛选逻辑抽离到 `src/composables/useXxx.ts`；
  2. 将独立弹窗、子面板、卡片拆分为 `src/components/<domain>/Xxx.vue` 子组件。

### 2. TypeScript 严格模式与零报错门禁（`vue-tsc-guard`）
- 必须使用 `<script setup lang="ts">`，通过泛型声明 `defineProps<{ ... }>()` 与 `defineEmits<{ ... }>()`。
- **严禁**使用 `as any`、`@ts-ignore`、`@ts-expect-error` 掩盖类型错误。
- `tsconfig.json` 开启了 `noUnusedLocals: true` 与 `noUnusedParameters: true`：
  - 任何定义了但未使用的变量、导入或 `watch` 回调参数都会触发 `TS6133`，**直接阻断 `npm run deploy:prod` 生产构建**。
  - 每次修改前端代码后，必须运行 `cd /root/subskin/web/app && npx vue-tsc --noEmit` 确保 0 报错。

### 3. SPA 路由导航与防白屏铁律
- **站内跳转一律使用 `<router-link>` 或 `router.push()`**：
  - 严禁对站内路由使用 `<a href="/xxx">`（会触发整页刷新并破坏 PWA 状态）。
  - 严禁使用 `<a href="#" @click.prevent="router.push(...)">`。
  - `<a href="..." target="_blank" rel="noopener noreferrer">` 仅用于跳转外部网站（如 PubMed 论文原文链接）。
- **严禁在 `<router-view>` 外层包裹 `<Transition mode="out-in">`**（含动态 `:is="Component"` 过渡）：
  - 在移动端弱网或懒加载分包切换时，`out-in` 过渡极易卡死导致路由切换后页面全白。让 Vue Router 直接切换视图组件。

---

## 四、PWA 架构与版本热更新机制（PWA Architecture）

SubSkin 作为跨端渐进式 Web 应用（PWA），其构建产物必须同时满足离线缓存、桌面安装与实时热更新通知：

### 1. 环境感知构建配置
- `vite.config.ts` / `vite.config.staging.ts`：构建 Staging 环境（`__APP_ENV__ = 'staging'`），输出至 `/usr/share/nginx/html/subskin-staging/`。
- `vite.config.prod.ts`：构建 Production 环境（`__APP_ENV__ = 'production'`），输出至 `/usr/share/nginx/html/subskin/`。

### 2.Staging 与 Production 的 4 项唯一受控差异
除以下 4 项由环境变量自动驱动的标识外，两个环境的业务代码与功能必须保持 100% 对齐：

| 对比维度 | 测试环境 (`staging.subskin.cn`) | 正式环境 (`subskin.cn`) |
|----------|----------------------------------|-------------------------|
| **1. 顶部导航栏配色** | 深岩蓝底色 (`bg-slate-800`) + `[STAGING]` 标识 | 浅色冷白毛玻璃 / 品牌青绿点缀 |
| **2. PWA Manifest 名称** | `name`: `"SubSkin [STAGING]"`<br>`short_name`: `"SubSkin-STG"`<br>`theme_color`: `"#1e293b"` | `name`: `"SubSkin - 白癜风病友的AI手帐和分享社区"`<br>`short_name`: `"SubSkin"`<br>`theme_color`: `"#26A69A"` |
| **3. `version.json` 环境字段** | `{"buildTime": ..., "env": "staging"}` | `{"buildTime": ..., "env": "production", "lastProdBuildTime": ...}` |
| **4. 新版本更新横幅文案** | `"测试环境有新版本可用"` | `"有新版本可用"` |

### 3. `version.json` 轮询与无感更新流程
- 前端 `usePWA` 每 30 秒轮询当前域名下的 `/version.json?t=...`。
- 当检测到服务端 `buildTime` 大于本地加载时的 `buildTime` 时，顶部平滑弹出更新提示横幅，用户点击「立即更新」后清理旧缓存并刷新加载最新资源。

---

## 五、特殊交互组件维护规范

### 1. 数字人身体部位选择器（`DigitalHuman.vue`）
- 路径：`web/app/src/components/tracker/DigitalHuman.vue`
- **架构说明**：当前生产架构为 **SVG 木头小人模型**（正面 12 部位 + 背面 12 部位 = 24 个标准解剖部位，映射定义于 `bodySites.ts`），体积轻量（Bundle 约 9.8KB），**不再使用重量级 Three.js 实时渲染**（GLB 模型文件仅作为静态资产保留在部署目录）。
- 修改该组件时，必须确保正背面全部 24 个部位的点击热区与 `@select(bodyPart)` 事件完整可用。

### 2. 白斑多边形核对画布（`MaskEditor`）
- 支持用户在 AI 自动分割的初始白斑轮廓基础上，通过触控或鼠标新增、删除、拖拽多边形顶点。
- 必须同时监听 Pointer / Touch / Mouse 事件，并在移动端画布操作时局部阻止页面默认滚动（`touch-action: none`），确保手指勾勒精准流畅。

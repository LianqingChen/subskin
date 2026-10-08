---
kind: frontend_style
name: SubSkin 前端样式体系：Tailwind CSS + CSS 变量主题 + NaiveUI 组件库
category: frontend_style
scope:
    - '**'
source_files:
    - web/app/tailwind.config.ts
    - web/app/src/styles/main.css
    - web/admin/src/styles/main.css
    - web/admin/package.json
    - web/app/package.json
    - web/vitepress/.vitepress/config.js
---

## 1. 系统与工具
- 用户端应用（web/app）：基于 Vue3 + Vite + Tailwind CSS 3.x，使用 PostCSS + Autoprefixer 构建，支持 PWA（vite-plugin-pwa、workbox-window）。
- 管理后台（web/admin）：基于 Vue3 + Vite + Tailwind CSS 4.x（@tailwindcss/vite），搭配 NaiveUI 2.x 作为主要 UI 组件库。
- 文档站点（web/vitepress）：基于 VitePress，默认主题样式，通过 .vitepress/config.js 配置导航与侧边栏。

## 2. 核心文件与位置
- web/app/tailwind.config.ts：Tailwind 主题扩展（颜色、字体、圆角等）。
- web/app/src/styles/main.css：全局 CSS 变量、基础层、组件层、工具层定义。
- web/admin/src/styles/main.css：Tailwind 4 import + NaiveUI 响应式覆盖。
- web/admin/package.json：NaiveUI、ECharts、Pinia、RemixIcon 等依赖。
- web/app/package.json：Tailwind 3、VueUse、TipTap、QRCode、Weixin JS-SDK 等依赖。
- web/vitepress/.vitepress/config.js：VitePress 站点配置。

## 3. 架构与设计约定
- 设计令牌（Design Tokens）：在 web/app/src/styles/main.css 的 :root 中集中定义 HSL 色板（primary/secondary/accent/success）、背景色、文本色、安全区域变量（safe-area-inset-*），并通过 CSS 变量供 Tailwind 颜色引用。
- Tailwind 主题扩展：在 tailwind.config.ts 中将 primary/secondary/accent/success 映射到 CSS 变量，实现主题可替换；字体族统一为 Inter/PingFang SC/Noto Sans SC/system-ui。
- 分层样式组织：main.css 使用 @layer base/components/utilities 三段式，base 定义 html/body/交互基线，components 封装 btn-primary/btn-secondary/btn-ghost/card/input-field/badge 等通用原子组件样式，utilities 提供 safe-bottom/no-scrollbar/overscroll-dock 等工具类。
- 暗色模式：Tailwind darkMode: 'class'，配合 body 的 dark:bg-gray-950 切换，所有组件样式均提供 dark:* 变体。
- 移动端适配：admin 端通过 @media (max-width: 768px) 对 NaiveUI 组件（表格、卡片、模态框、分页、表单）进行针对性覆盖；app 端通过 env(safe-area-inset-*) 与 pwa-safe-top/pwa-safe-bottom 工具类处理刘海屏与底部安全区。
- 触摸体验：按钮最小高度 44px，active 缩放 0.97 反馈，禁用选中行为，iOS 下关闭拖拽与点击高亮。

## 4. 约束与规范
- 用户端（web/app）必须使用 Tailwind 3.x 并通过 main.css 的 @layer 结构组织样式，新增组件样式应放入 components 层并遵循 btn-*/card/input-field/badge 命名约定。
- 管理后台（web/admin）使用 Tailwind 4 + NaiveUI，禁止直接覆盖 NaiveUI 全局样式，仅通过 @media 768px 断点做移动端适配。
- 所有颜色必须通过 CSS 变量或 Tailwind 扩展色名引用，禁止在组件内硬编码十六进制色值（除 secondary/accent/success 固定色外）。
- 暗色模式需同时提供 light/dark 两套样式，使用 dark:* 前缀而非独立 class 分支。
- VitePress 文档站点不引入自定义 CSS，仅通过 config.js 调整主题配置。

## 5. 关键依赖与版本
- web/app：tailwindcss@3.4.17、@tailwindcss/typography@0.5.19、vue@3.5.13、pinia@2.3.0、vite-plugin-pwa@1.2.0、weixin-js-sdk@1.6.5。
- web/admin：tailwindcss@4.3.0、@tailwindcss/vite@4.3.0、naive-ui@2.41.0、echarts@5.6.0、vue@3.5.13、pinia@2.3.1。
- web/vitepress：vitepress（由 package.json 管理）。

## 6. 与后端集成方式
- 静态资源通过 Vite 构建后由 Nginx（deploy/nginx*.conf）分发，PWA 缓存由 workbox-window 管理。
- 管理后台与用户端共享同一后端 FastAPI 服务，样式层面无跨端耦合。

置信度：high — 仓库中存在完整的 Tailwind 配置、CSS 变量主题、组件样式层与多端适配规则，证据充分且一致。
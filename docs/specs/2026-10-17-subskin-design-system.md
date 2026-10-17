# SubSkin 全站设计系统与多端适配规范 (Design System & Cross-Platform Specification)

> **版本**: 2026-10-17  
> **状态**: 强制执行 (MANDATORY — 适用于所有后续 Agent、新增功能页面、组件、对外分享页、Canvas 海报及生成图片)  
> **样式入口**: `web/app/src/styles/main.css`、`web/app/tailwind.config.ts`  
> **命名唯一事实来源**: `web/shared/site-modules.json`、`web/shared/page-names.json`

---

## 一、设计哲学：Cursor & GitHub 现代科技质感 × 医疗人文温度

SubSkin 的视觉语言融合了 **Cursor 官网的克制精密（Surface Hierarchy + Hairline Borders + Tabular Metrics）**、**GitHub Primer 的清晰结构（高对比度排印 + 语义化控件层次）** 与 **医疗健康产品的温和信任感（Clinical Teal 青绿主色）**：

1. **克制的高对比画布（Surface Hierarchy）**：
   - 摒弃浑浊的大面积彩色背景与浮夸的弥散重阴影。
   - 浅色模式采用 GitHub Primer 风格的冷白画布（`#f6f8fa`）配纯白卡片表面（`#ffffff`）；深色模式采用 Cursor 风格的深碳蓝黑画布（`#0b0f17`）配深岩灰卡片表面（`#111827`）。
2. **1px 精密微边框（Hairline Border Architecture）**：
   - 容器、卡片、输入框、代码/指标块、下拉面板均以 **1px 精细边框**（浅色 `#e2e8f0` / `rgba(15, 23, 42, 0.08)`，深色 `#1e293b` / `rgba(255, 255, 255, 0.08)`）界定边界，配合极轻的微阴影（`--shadow-xs` / `--shadow-sm`）。
3. **顶部微高光与触感按钮（Tactile Controls）**：
   - 主按钮（`.btn-primary`）采用深青绿实色（`#0d9488` → 悬停 `#0f766e`）配顶部 1px 内高光（`inset 0 1px 0 rgba(255, 255, 255, 0.16)`）；次按钮（`.btn-secondary`）采用白底/深灰底 + 1px 边框 + 微阴影。
4. **等宽数字与清晰层级（Typography & Tabular Numerals）**：
   - 所有统计数值、VASI 评分、百分比、日期、倒计时统一启用 `font-variant-numeric: tabular-nums`，确保数据对齐与科技感。

---

## 二、色彩令牌体系 (Color Tokens)

所有颜色定义在 `web/app/src/styles/main.css` 的 `:root` 与 `html.dark` 中，严禁在页面或组件中硬编码冲突的十六进制颜色（如 `#f5f7fa`、`#10b981`）或使用原生 `blue-*`、`purple-*`、`emerald-*` 作为品牌色。

### 2.1 品牌主色 (`primary-*` — Clinical Tech Teal)

| Token | 浅色模式 (Light) | 深色模式 (Dark — 透明叠加防刺眼) | 用途 |
|-------|------------------|----------------------------------|------|
| `--color-primary-50` | `#f0fdfa` | `rgba(20, 184, 166, 0.10)` | 选中项浅底、徽章背景、温和提示底色 |
| `--color-primary-100` | `#ccfbf1` | `rgba(20, 184, 166, 0.16)` | 悬浮态浅底、次级高亮背景 |
| `--color-primary-200` | `#99f6e4` | `rgba(20, 184, 166, 0.24)` | 激活态细边框、聚焦光环 |
| `--color-primary-300` | `#5eead4` | `#5eead4` | 深色模式下的高亮图标/文字 |
| `--color-primary-400` | `#2dd4bf` | `#2dd4bf` | 深色模式下的链接与主色文字 |
| `--color-primary-500` | `#14b8a6` | `#14b8a6` | 品牌标准色、图表主色、聚焦边框 |
| `--color-primary-600` | `#0d9488` | `#0d9488` | **主按钮 (CTA) 背景**、浅色模式强调文字 |
| `--color-primary-700` | `#0f766e` | `#2dd4bf` | 主按钮 Hover 态、浅色模式高对比度主色文字 |
| `--color-primary-800` | `#115e59` | `#5eead4` | 按下态 (Active)、报告封面深青渐变起点 |
| `--color-primary-900` | `#134e4a` | `rgba(19, 78, 74, 0.45)` | 极深青背景、深色模式徽章底色 |

### 2.2 画布、表面与边框令牌 (Surfaces & Borders)

| Token | 浅色模式 (Light) | 深色模式 (Dark) | Tailwind 对应写法 |
|-------|------------------|-----------------|-------------------|
| `--color-bg` (全局画布) | `#f6f8fa` | `#0b0f17` | `bg-[#f6f8fa] dark:bg-[#0b0f17]` |
| `--color-surface` (一级卡片/弹窗) | `#ffffff` | `#111827` | `bg-white dark:bg-gray-900` 或 `.card` |
| `--color-surface-subtle` (二级内嵌块) | `#f8fafc` | `#161f30` | `bg-gray-50/80 dark:bg-gray-800/60` |
| `--color-surface-muted` (骨骼屏/胶囊槽) | `#f1f5f9` | `#1e293b` | `bg-gray-100 dark:bg-gray-800` |
| `--color-border` (标准 1px 边框) | `#e2e8f0` | `#1e293b` | `border-gray-200/80 dark:border-gray-800` |
| `--color-text` (一级正文/标题) | `#0f172a` | `#f8fafc` | `text-gray-900 dark:text-gray-100` |
| `--color-text-secondary` (二级正文) | `#475569` | `#94a3b8` | `text-gray-600 dark:text-gray-300` |
| `--color-text-muted` (辅助说明/时间戳) | `#64748b` | `#64748b` | `text-gray-500 dark:text-gray-400` |

### 2.3 医疗语义色 (Semantic Colors)

仅用于趋势指标、体检异常标注、表单校验与状态提示：
- **好转 / 正常 / 成功 (Success)**：`emerald-600` (`#059669`)，浅底 `bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300`
- **稳定 / 注意 / 警告 (Warning)**：`amber-600` (`#d97706`)，浅底 `bg-amber-50 dark:bg-amber-950/60 text-amber-700 dark:text-amber-300`
- **加重 / 异常 / 危险 (Danger)**：`rose-600` / `red-600` (`#dc2626`)，浅底 `bg-red-50 dark:bg-red-950/60 text-red-700 dark:text-red-300`
- **社区分类标签**：必须统一调用 `@/utils/colors` 中的 `getCategoryColor(categoryName)`，严禁各页面自行定义颜色数组。

---

## 三、字体排印与层级规范 (Typography)

### 3.1 跨平台字体栈 (`tailwind.config.ts` & `main.css`)

兼顾 macOS/iOS (`PingFang SC`)、华为鸿蒙设备 (`HarmonyOS Sans SC`)、Windows (`Microsoft YaHei`) 与 Linux：
- **无衬线主字体 (`font-sans`)**：
  `'Inter', -apple-system, BlinkMacSystemFont, "HarmonyOS Sans SC", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Noto Sans SC", sans-serif`
- **等宽技术字体 (`font-mono`)**：
  `'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace`

### 3.2 标准字号与排版类

| 层级 | 标准类名 / 样式 | 规范说明 |
|------|-----------------|----------|
| 页面主标题 (`<h1>`) | `.page-title` (`text-lg md:text-xl font-bold tracking-tight text-gray-900 dark:text-gray-100`) | 每页唯一 `<h1>`，字重 `700`，紧凑字距 `-0.02em` |
| 页面副标题 | `.page-subtitle` (`text-xs md:text-sm text-gray-500 dark:text-gray-400 mt-0.5`) | 补充说明页面核心价值，简洁克制 |
| 区块标题 (`<h2>`) | `.section-title` (`text-base md:text-lg font-semibold tracking-tight text-gray-900 dark:text-gray-100`) | 區塊分割标题 |
| 卡片标题 (`<h3>`) | `text-sm md:text-base font-semibold text-gray-900 dark:text-gray-100` | 列表项、卡片主标题 |
| 正文内容 | `text-sm leading-relaxed text-gray-700 dark:text-gray-300` | 默认行高 `1.6` |
| 辅助元信息 / 时间 | `text-xs text-gray-500 dark:text-gray-400 tabular-nums` | 日期、阅读数、点赞数必须带 `tabular-nums` |

---

## 四、响应式布局与多端适配规范 (Responsive & Cross-Browser Adaptation)

### 4.1 视口断点与导航形态

SubSkin 必须同时完美适配 **手机端 (`375px–767px`)**、**平板竖屏 (`768px–1023px`)**、**平板横屏/小屏笔记本 (`1024px–1279px`)** 与 **桌面大屏 (`≥1280px`)**：

| 视口范围 | `--app-sidebar-w` | 全局主导航形态 | 页面内容容器宽度 |
|----------|-------------------|----------------|------------------|
| `< 768px` (手机端) | `0px` | 顶部 `AppHeader` + 底部 `BottomNav` (5 项固定栏) | `100%` (`px-3.5`) |
| `768px – 1023px` (iPad 竖屏) | `0px` | 顶部 `AppHeader` (含水平文字导航) | `.page` / `.page-wide` (`px-5`) |
| `1024px – 1279px` (iPad 横屏) | `72px` | 左侧 `72px` 窄图标轨 (`AppSidebar`) + 顶部 `AppHeader` | 自动扣除左侧 `72px` (`px-6`) |
| `≥ 1280px` (桌面端) | `224px` | 左侧 `224px` 完整侧边栏 (`AppSidebar`) + 顶部 `AppHeader` | 自动扣除左侧 `224px` (`px-8`) |

### 4.2 页面容器宽度三档标准 (`main.css`)

严禁手写 `max-w-* mx-auto px-*` 或在 scoped CSS 中硬编码像素宽度，一律使用以下三个容器类之一：
1. **`.page-wide`** (`max-width: 80rem / 1280px`)：全站顶栏、三栏工作台（如日记记录工作台、对比工作台）。
2. **`.page`** (`max-width: 72rem / 1152px`)：常规业务页、发现社区瀑布流、就医经验列表、个人中心。
3. **`.page-narrow`** (`max-width: 48rem / 768px`)：沉浸式单列阅读/对话/表单页（问答对话、帖子详情、报告阅读、协议长文）。

### 4.3 固定定位底栏规则 (`.app-fixed-x`)

任何使用 `fixed` 横跨视口底部的操作栏、输入栏或移动端目录栏，**必须**添加 `.app-fixed-x` 类（定义：`left: var(--app-sidebar-w); right: 0;`），防止在 `≥1024px` 桌面端遮挡左侧 `AppSidebar`。

### 4.4 微信内置浏览器 (WeChat WebView)、华为浏览器与 iOS Safari 专项兼容铁律

1. **动态视口单位渐进回退 (`100vh` → `100dvh`/`100svh`)**：
   - 旧版微信 WebView、部分安卓系统 WebView 不支持 `dvh`/`svh`。
   - `main.css` 已为 `.min-h-dvh`、`.h-dvh`、`.max-h-[92dvh]`、`.max-h-[90dvh]`、`.max-h-[88dvh]`、`.max-h-[85dvh]` 内置 `vh` 级联回退。
   - 若在组件 `<style scoped>` 中手写 `100dvh` 或 `100svh`，**必须**在前一行紧跟声明 `100vh` 回退：
     ```css
     height: calc(100vh - 56px);
     height: calc(100dvh - 56px);
     ```
2. **水平溢出裁剪回退 (`overflow-x: hidden` → `overflow-x: clip`)**：
   - 根容器必须同时声明 `overflow-x: hidden; overflow-x: clip;`，防止旧版 WebView 因不支持 `clip` 出现横向滚动条。
3. **毛玻璃降级保护 (`.surface-glass`)**：
   - 低端安卓机或旧版微信 WebView 对 `backdrop-filter` 支持不稳定时，底色必须具备高不透明度回退（浅色 `rgba(255, 255, 255, 0.92)`，深色 `rgba(17, 24, 39, 0.92)`），或直接使用 `.surface-glass`。
4. **Flex 容器内 `<input>` 最小宽度 (`min-w-0`)**：
   - 任何处于 `flex` 容器内的 `<input class="flex-1">`、`<select>`、`<textarea>` **必须**同时添加 `min-w-0`，防止在 `375px` 小屏手机与华为浏览器大字号模式下撑破右侧按钮。
5. **Canvas 绘图禁止直接调用 `ctx.roundRect()`**：
   - 微信内置浏览器与部分移动端 WebView 的 `CanvasRenderingContext2D` 不支持原生 `.roundRect()`，直接调用会导致海报生成抛异常白屏。
   - **强制要求**：所有 Canvas 圆角矩形必须使用基于 `moveTo` + `arcTo` 的 `traceRoundedRect(ctx, x, y, w, h, r)` 辅助函数！
6. **禁止 iOS 输入框自动放大与电话号码误识别**：
   - 移动端输入框字号不小于 `14px`（推荐 `text-sm` + `viewport` 锁定），`index.html` 保持 `<meta name="format-detection" content="telephone=no, email=no" />`。
7. **底部抽屉在平板/桌面端的宽度约束**：
   - 移动端底部弹出的 ActionSheet / Modal（如 `CreatePostSheet`、`PageShareSheet`、`LoginModal`），在 `sm:` / `md:` 及以上视口必须居中并限制最大宽度（`sm:max-w-md sm:mx-auto sm:rounded-2xl`），严禁在电脑端横跨整个屏幕宽度。

---

## 五、核心组件与图标规范 (Component & Icon Standards)

### 5.1 标准基础组件类 (`main.css`)

| 组件 | 标准类名 | 视觉特征 |
|------|----------|----------|
| 主按钮 | `.btn-primary` | `#0d9488` 实色背景 + 顶部 1px 内高光 + 微青阴影，`rounded-lg` (`8px`)，最小触控高 `38px–44px` |
| 次按钮 | `.btn-secondary` | 白底 (`dark: #1e293b`) + 1px `#cbd5e1` (`dark: #334155`) 边框 + `--shadow-xs`，GitHub 风格高质感次级按钮 |
| 幽灵按钮 | `.btn-ghost` | 透明背景，悬停浅灰底 (`hover:bg-gray-100 dark:hover:bg-gray-800`) |
| 标准卡片 | `.card` | `rounded-xl` (`12px`)，白底 (`dark: #111827`)，1px 精细边框 (`--color-border`)，`--shadow-xs` |
| 可交互卡片 | `.card-hover` | 在 `.card` 基础上悬停时边框加深并上浮 `--shadow-md` |
| 紧凑筛选条 | `.control-slim` | `min-h-8 rounded-lg border px-2.5 text-xs`，用于工具栏筛选、排序下拉触发器 |
| 标准输入框 | `.input-field` | `rounded-lg border px-3.5 py-2.5 text-sm`，聚焦时 `primary-500` 边框 + `3px` 半透明青色光环 |

### 5.2 图标系统唯一规范：RemixIcon (零容忍)

- **全站唯一图标库**：[RemixIcon](https://remixicon.com/)（`<i class="ri-xxx-line"></i>` 或 `<i class="ri-xxx-fill"></i>`）。
- **严禁使用内联 `<svg>` 绘制业务图标**：所有关闭按钮、返回箭头、分享图标、点赞爱心、上传图标、加载动画（统一用 `<i class="ri-loader-4-line animate-spin"></i>`）必须使用 RemixIcon。
  - *唯一例外*：解剖部位人体示意图（`BodySilhouetteSvg.vue`）、复杂医学多边形标注画布（`MaskEditor`）、底部导航中心凸起弧线背景（`BottomNav.vue` 装饰性 notch path）。
- **严禁使用 Emoji 充当 UI 图标**：不得在标题、按钮、空状态、Canvas 海报标题中使用 `✨`、`🔥`、`📱`、`🔒` 等 Emoji 字符。

---

## 六、对外分享链接、海报与生成图片统一规范 (Shared Links & Generated Posters)

所有对外传播触点（公开分享网页、Canvas 生成海报、周报长图、白斑变化报告长图、轮廓故事海报）代表 SubSkin 的品牌形象，必须与站内保持 100% 视觉与文案一致：

### 6.1 涉及文件清单

1. **通用分享面板与页面/帖子海报**：
   - `web/app/src/components/common/PageShareSheet.vue`
   - `web/app/src/components/common/PageSharePoster.vue`
2. **日记周报与白斑变化报告海报**：
   - `web/app/src/components/diary/DiaryWeeklyPoster.vue`
   - `web/app/src/components/diary/SkinReportPoster.vue`
3. **轮廓故事海报 (Canvas)**：
   - `web/app/src/utils/assessment-story/render.ts`
4. **公开外部分享落地页（免登录访问）**：
   - `web/app/src/views/SkinReportSharedPage.vue` (`/share/report/:token`)
   - `web/app/src/views/CollectionSharePage.vue` (`/collection/:slug`)
   - `web/app/src/views/SkinReportViewPage.vue` + `web/app/src/components/report/SkinReportView.css`

### 6.2 海报与外部分享强制规范

1. **品牌头部与配色统一**：
   - Canvas 海报顶部横幅统一使用品牌深青科技渐变：`#0f766e` → `#0d9488`（或深色主题下的 `#115e59` → `#0d9488`）。
   - 海报内部卡片背景统一使用 `#f8fafc`，分割线使用 `#e2e8f0`，主标题文字 `#0f172a`，次级正文 `#475569`，辅助说明 `#64748b`，高亮指标值 `#0d9488` / `#0f766e`。
2. **Canvas 字体栈统一**：
   - 所有 Canvas `ctx.font` 必须包含 `"HarmonyOS Sans SC", "PingFang SC"`，禁止裸写 `sans-serif`。
3. **Canvas 圆角绘制安全**：
   - 严禁调用 `ctx.roundRect()`，统一使用 `traceRoundedRect()` (`arcTo` 实现)。
4. **品牌尾注与模块命名统一**：
   - 品牌主标：**`SubSkin`**
   - 品牌副标：**`白癜风病友的AI记录和分享社区`**
   - 模块归属署名：统一使用 **`SubSkin · 白斑日记`**、**`SubSkin · 发现`**、**`SubSkin · 体检解读`**、**`SubSkin · 就医经验`**、**`SubSkin · 同行`**（严禁出现已废弃的 `小白日记`、`AI病情日记`、`小白知识库`、`小白追踪`、`白友圈`）。
   - 二维码跳转路径：必须指向真实有效路由（如 `/assessment`、`/community/:id`、`/share/report/:token`），严禁指向已废弃的 `/diary` 或 `/tracker`。
5. **医疗免责声明必现**：
   - 所有分享页与生成海报底部必须包含免责声明：`分享内容仅供参考，不构成医疗建议，治疗请遵医嘱`（或同等合规表述）。

---

## 七、模块命名唯一事实来源 (Single Source of Truth for Naming)

任何前端页面、导航、海报、弹窗、提示词引用模块名时，必须严格对齐 `web/shared/site-modules.json` 与 `web/shared/page-names.json`：

| 模块 Key | 官方名称 | 路由路径 | 严禁在 UI/海报中使用的旧名 (仅作后端搜索别名) |
|----------|----------|----------|-----------------------------------------------|
| `qa` | **问答** | `/` | 小白助手、AI助手 |
| `diary` | **日记** (子页：白斑日记 / 白斑记录 / 变化报告) | `/assessment` | 小白手账、手帐、小白日记、AI病情日记、小白追踪、病情追踪、测评 |
| `exam` | **体检解读** | `/assessment/exam` | — |
| `community` | **发现** | `/community` | 白友圈、小白社区、病友社区、分享（作为主模块名时） |
| `hospitals` | **就医经验** (归属「发现」模块) | `/hospitals` | 医评、公益 |
| `contribution` | **同行** | `/contribution` | — |
| `care` | **调养** (`nav_hidden: true`) | `/care` | 护理优选 |
| `profile` | **个人中心** (移动端底栏简称「我的」) | `/profile` | — |

---

## 八、新增页面与接手 Agent 自检清单 (Pre-Merge & Staging Verification Checklist)

任何 Agent 在新增页面、修改现有组件或生成分享图后，在构建部署到测试环境（`npm run build`）前，必须逐项通过以下 10 条检查：

- [ ] **1. 配色与深色模式**：是否使用了 `main.css` 定义的设计令牌？所有新增背景、文字、边框、弹窗是否 100% 具备 `dark:` 样式且无白底黑字穿帮？
- [ ] **2. 容器与侧边栏避让**：页面外层是否使用了 `.page` / `.page-wide` / `.page-narrow`？底部固定栏是否添加了 `.app-fixed-x`？底部抽屉在桌面端是否有 `sm:max-w-md sm:mx-auto` 约束？
- [ ] **3. 图标纯粹性**：是否 100% 使用 RemixIcon (`ri-*`)？确保未引入任何内联业务 `<svg>` 或 Emoji 图标。
- [ ] **4. 命名一致性**：页面标题、面包屑、空状态、分享文案是否完全符合 `web/shared/site-modules.json`？
- [ ] **5. WebView 兼容性**：
  - Flex 容器内的 `<input class="flex-1">` 是否加了 `min-w-0`？
  - 手写 `dvh`/`svh` 是否有 `vh` 回退？
  - Canvas 是否使用了 `traceRoundedRect` 而非 `ctx.roundRect`？
- [ ] **6. 分享与海报同步**：若页面支持分享，其 `shareTitle`、海报头部/尾注、二维码路由是否符合第六节规范？
- [ ] **7. 医疗免责声明**：涉及健康信息、AI 解读、病情记录、经验分享的页面或海报是否包含医疗免责声明？
- [ ] **8. 类型检查**：执行 `cd /root/subskin/web/app && npm run type-check` 是否 0 报错通过？
- [ ] **9. 测试环境先行部署**：是否已执行 `cd /root/subskin/web/app && npm run build` 部署至 `staging.subskin.cn`，校验 `version.json` 并更新 `DEPLOY_LOG.md`？
- [ ] **10. 多视口验证**：是否在 `375px` (手机)、`768px` (平板竖屏)、`1024px` (平板横屏)、`1440px` (桌面端) 及深浅色模式下验证布局无溢出、无遮挡？

# 02 · 全站 UI 设计系统、多端适配与分享海报规范

> **文档编号**: `STD-02`  
> **适用范围**: 用户端（`web/app/`）、对外分享落地页、所有 Canvas 生成海报与长图  
> **详细规格源**: `/root/subskin/docs/specs/2026-10-17-subskin-design-system.md`  
> **样式定义源**: `web/app/src/styles/main.css`、`web/app/tailwind.config.ts`  
> **更新日期**: 2026-10-17  
> **状态**: 强制执行（MANDATORY）

---

## 一、视觉设计哲学：Cursor & GitHub 现代科技质感 × 医疗人文温度

SubSkin 采用统一的现代设计语言，融合 **Cursor 官网的精密表面层级（Surface Hierarchy + 1px Hairline Borders + Tabular Metrics）**、**GitHub Primer 的高对比度清晰排版** 与 **临床医疗产品的青绿温和信任感（Clinical Tech Teal）**：

1. **高对比度冷白/碳黑画布**：
   - 浅色模式全局画布统一为 `#f6f8fa`（严禁硬编码旧式灰暗 `#f5f7fa`），一级卡片表面为纯白 `#ffffff`。
   - 深色模式全局画布统一为 `#0b0f17`，一级卡片表面为 `#111827`，二级内嵌块为 `#161f30`。
2. **1px 精密微边框（Hairline Borders）**：
   - 所有卡片、侧边栏、模态框、代码/指标块均通过 `1px solid` 精细边框（浅色 `#e2e8f0`，深色 `#1e293b`）配合微阴影（`--shadow-xs` / `--shadow-sm`）建立秩序，摒弃浮夸的大范围重阴影。
3. **顶部内高光触感控件（Tactile Buttons）**：
   - 主操作按钮（`.btn-primary`）采用 `#0d9488`（Hover `#0f766e`）配顶部 1px 微高光（`inset 0 1px 0 rgba(255, 255, 255, 0.16)`）；次操作按钮（`.btn-secondary`）采用白底/深灰底 + 1px 边框 + 微阴影。
4. **等宽数字对齐（Tabular Numerals）**：
   - 所有统计卡片、百分比、VASI 评分、日期时间戳、倒计时强制启用 `tabular-nums`（`font-variant-numeric: tabular-nums`）。

---

## 二、核心设计令牌速查表（Design Tokens）

### 2.1 品牌主色令牌 (`primary-*`)

定义于 `web/app/src/styles/main.css`，严禁在业务组件中硬编码 `#10b981`、`#34d399` 或使用 `blue-*`、`purple-*`、`emerald-*` 冒充品牌主色：

| CSS 变量 | Tailwind 类 | 浅色模式值 | 深色模式值 | 标准用途 |
|----------|-------------|------------|------------|----------|
| `--color-primary-50` | `bg-primary-50` | `#f0fdfa` | `rgba(20, 184, 166, 0.10)` | 选中项浅底、徽章背景、温和提示框底色 |
| `--color-primary-100` | `bg-primary-100` | `#ccfbf1` | `rgba(20, 184, 166, 0.16)` | 悬浮态浅底、次级高亮标签 |
| `--color-primary-200` | `border-primary-200` | `#99f6e4` | `rgba(20, 184, 166, 0.24)` | 激活态细边框、聚焦光环 |
| `--color-primary-400` | `text-primary-400` | `#2dd4bf` | `#2dd4bf` | 深色模式下的高亮图标与主色文字 |
| `--color-primary-500` | `bg-primary-500` | `#14b8a6` | `#14b8a6` | 品牌标准色、图表主色、输入框聚焦边框 |
| `--color-primary-600` | `bg-primary-600` | `#0d9488` | `#0d9488` | **主按钮 (`.btn-primary`) 背景**、浅色模式强调色 |
| `--color-primary-700` | `text-primary-700` | `#0f766e` | `#2dd4bf` | 主按钮 Hover 态、浅色模式高对比度主色文字 |
| `--color-primary-800` | `bg-primary-800` | `#115e59` | `#5eead4` | 按下态、报告与海报封面深青渐变起点 |

### 2.2 表面、文本与医疗语义色

| 类别 | 令牌 / 规范写法 | 浅色模式 | 深色模式 | 说明 |
|------|-----------------|----------|----------|------|
| 全局画布 | `bg-[#f6f8fa] dark:bg-[#0b0f17]` | `#f6f8fa` | `#0b0f17` | 页面最外层背景必须继承画布 |
| 一级卡片 | `.card` / `bg-white dark:bg-gray-900` | `#ffffff` | `#111827` | 配合 `border-gray-200/80 dark:border-gray-800` |
| 二级内嵌块 | `bg-gray-50/80 dark:bg-gray-800/60` | `#f8fafc` | `#161f30` | 卡片内部的参数区、引用块、摘要区 |
| 一级文字 | `text-gray-900 dark:text-gray-100` | `#0f172a` | `#f8fafc` | 标题与核心正文 |
| 二级文字 | `text-gray-600 dark:text-gray-300` | `#475569` | `#94a3b8` | 常规描述正文 |
| 三级辅助字 | `text-gray-500 dark:text-gray-400` | `#64748b` | `#64748b` | 时间戳、次要说明 |
| 语义-好转/正常 | `text-emerald-600 dark:text-emerald-400` | `#059669` | `#34d399` | 复色好转、指标正常 |
| 语义-稳定/注意 | `text-amber-600 dark:text-amber-400` | `#d97706` | `#fbbf24` | 面积稳定、轻度偏离 |
| 语义-异常/警示 | `text-red-600 dark:text-red-400` | `#dc2626` | `#f87171` | 指标异常、删除警示 |
| 社区分类色 | `getCategoryColor(name)` (`@/utils/colors`) | 动态映射 | 动态映射 | 严禁在组件内手写分类颜色字典 |

---

## 三、字体排印与组件样式标准（Typography & Components）

### 3.1 跨平台字体栈
- **无衬线字体 (`font-sans`)**：`'Inter', -apple-system, BlinkMacSystemFont, "HarmonyOS Sans SC", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Noto Sans SC", sans-serif`
- **等宽字体 (`font-mono`)**：`'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace`

### 3.2 通用基础类（定义于 `main.css`，优先复用）
- **布局容器**：
  - `.page-wide`（`80rem / 1280px`）：顶栏、多栏复杂工作台
  - `.page`（`72rem / 1152px`）：常规业务页面、社区列表、个人中心
  - `.page-narrow`（`48rem / 768px`）：AI 问答、文章阅读、报告详情、单列表单
- **标题与卡片**：
  - `.page-title`：页面唯一 `<h1>` 主标题（`text-lg md:text-xl font-bold tracking-tight`）
  - `.section-title`：区块 `<h2>` 标题（`text-base md:text-lg font-semibold tracking-tight`）
  - `.card` / `.card-hover`：标准 12px 圆角卡片与可悬停卡片
  - `.surface-glass`：带高不透明度降级保护的毛玻璃表面（顶栏、底栏、浮动条）
- **交互控件**：
  - `.btn-primary` / `.btn-secondary` / `.btn-ghost`：三级标准按钮
  - `.control-slim` / `.menu-slim`：紧凑型筛选按钮与下拉菜单面板
  - `.input-field`：带主色聚焦光环的标准输入框

### 3.3 RemixIcon 唯一图标规范（零容忍）
1. 全站所有 UI 图标必须使用 **RemixIcon**（`<i class="ri-xxx-line"></i>` 或 `<i class="ri-xxx-fill"></i>`）。
2. 加载状态统一使用 `<i class="ri-loader-4-line animate-spin"></i>`。
3. **严禁**使用内联业务 `<svg>` 图标（仅人体部位解剖图 `BodySilhouetteSvg.vue`、医学多边形画布 `MaskEditor`、底栏装饰弧线除外）。
4. **严禁**使用 Emoji 字符（如 ✨、🔥、📱、🔒）充当 UI 图标或海报装饰。

---

## 四、多端响应式与微信 WebView / 华为浏览器专项兼容铁律

SubSkin 必须在 **手机 (`375px+`)**、**iPad 竖屏 (`768px`)**、**iPad 横屏 (`1024px`)**、**桌面大屏 (`1280px+ / 1440px+`)** 以及 **微信内置浏览器、华为浏览器、iOS Safari** 下完美运行：

| 序号 | 兼容场景 | 强制工程规范 |
|------|----------|--------------|
| **1** | **桌面侧边栏避让** | 全局 CSS 变量 `--app-sidebar-w` 在 `<1024px` 为 `0px`，`1024–1279px` 为 `72px`（窄图标轨），`≥1280px` 为 `224px`（完整侧栏）。任何底部 `fixed` 定位元素**必须**加上 `.app-fixed-x`（`left: var(--app-sidebar-w); right: 0;`），防止遮挡桌面侧栏。 |
| **2** | **页面内部子导航** | 页面内部的 Tab/分类/历史导航在桌面端（`md:`/`lg:`）优先采用左侧可折叠边栏（展开 `w-52`，激活态 `bg-primary-50 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300`），在移动端采用水平滚动胶囊条或抽屉。 |
| **3** | **底部抽屉桌面端约束** | 移动端从底部弹出的抽屉（`fixed inset-x-0 bottom-0`），在平板/桌面端**必须**追加 `sm:max-w-md sm:mx-auto sm:bottom-6 sm:rounded-2xl`，严禁在电脑屏幕上铺满整行。 |
| **4** | **`dvh` / `svh` 渐进回退** | 旧版微信 WebView 与部分安卓浏览器不支持 `100dvh`。凡在 `<style scoped>` 中使用 `dvh`/`svh`，前一行**必须**写明 `vh` 回退（如 `height: 100vh; height: 100dvh;`）。 |
| **5** | **Flex 输入框防撑破** | 任何处于 `flex` 容器内的 `<input class="flex-1">`、`<select>` **必须**同时添加 `min-w-0`，防止在 `375px` 小屏或华为浏览器大字号下把右侧按钮挤出屏幕。 |
| **6** | **Canvas 禁用 `ctx.roundRect()`** | 微信 WebView 与旧版移动端不支持原生 `ctx.roundRect()`，调用即导致海报生成崩溃白屏。所有 Canvas 圆角矩形**必须**使用基于 `moveTo` + `arcTo` 的 `traceRoundedRect()` 函数。 |
| **7** | **横向溢出双保险** | 根容器同时声明 `overflow-x: hidden; overflow-x: clip;`，杜绝移动端左右晃动。 |

---

## 五、对外分享落地页与 Canvas 生成海报统一规范

所有对外分享页面与生成的长图海报是 SubSkin 的外部品牌名片，必须遵循统一模板：

### 5.1 纳管范围
- **通用分享组件**：`PageShareSheet.vue`、`PageSharePoster.vue`
- **日记与报告海报**：`SkinReportPoster.vue`、`DiaryWeeklyPoster.vue`、`utils/assessment-story/render.ts`
- **免登录外部分享页**：`SkinReportSharedPage.vue` (`/share/report/:token`)、`CollectionSharePage.vue` (`/collection/:slug`)、`SkinReportViewPage.vue`

### 5.2 强制视觉与品牌规范
1. **头部渐变**：统一采用品牌深青渐变 `#0f766e` → `#0d9488`（或深色 `#115e59` → `#0d9488`）。
2. **内部卡片与文字**：海报画布内卡片使用 `#f8fafc` 底色 + `#e2e8f0` 1px 描边；主标题 `#0f172a`，正文 `#475569`，辅助文字 `#64748b`，核心指标高亮 `#0d9488`。
3. **字体与圆角**：Canvas `ctx.font` 必须包含 `"HarmonyOS Sans SC", "PingFang SC"`；圆角绘制一律使用 `traceRoundedRect`。
4. **品牌署名与二维码**：
   - 主品牌名：**`SubSkin`**
   - 品牌副标题：**`白癜风病友的AI记录和分享社区`**
   - 模块尾注：`SubSkin · 白斑日记` / `SubSkin · 发现` / `SubSkin · 体检解读` / `SubSkin · 就医经验` / `SubSkin · 同行`
   - 二维码必须指向真实可访问路由（如 `/assessment`、`/community/:id`、`/share/report/:token`），严禁指向已废弃路由。
5. **医疗免责声明**：所有海报页脚与分享页底部必须包含「分享内容仅供参考，不构成医疗建议，治疗请遵医嘱」。

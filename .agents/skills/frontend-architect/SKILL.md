---
name: frontend-architect
description: Use when writing, reviewing, or modifying SubSkin frontend Vue 3/TypeScript code — new pages, components, composables, stores, UI design, responsive layout, PWA features, or semantic HTML. Triggers on 前端审查、前端架构、FE review、组件拆分、代码审查、前端review、前端检查、新功能实现、新页面、新组件.
---
# Frontend Architect Skill

> 前端架构师 — SubSkin 项目前端代码质量守门人
>
> **触发词**: 前端审查、前端架构、FE review、组件拆分、代码审查、代码审计、前端review、前端检查、新功能实现、新页面、新组件
>
> **关键原则**: 此 Skill 是 SubSkin 前端代码的最高质量标准。所有新增功能、页面、组件必须符合本 Skill 的规定。

---

## 角色定义

你是 SubSkin 项目的前端架构师，负责确保前端代码符合以下质量标准。你对代码有最终否决权 — 不符合规范的 PR 不应合并。

---

## 一、组件拆分规范 (Component Composition)

### 1.1 文件行数硬限制

| 类型 | 最大行数 | 超限处理 |
|------|----------|----------|
| View 页面 | **≤ 500 行** | 必须拆分为子组件 |
| 业务组件 | **≤ 400 行** | 必须拆分为子组件 |
| UI 组件 | **≤ 200 行** | 评审是否违反单一职责 |
| Composable | **≤ 200 行** | 拆分为多个小 composable |

### 1.2 单一职责检查清单

每个组件必须通过以下检查，任一项不通过则需拆分：

- [ ] 组件只处理 **一个** 业务领域（如：个人资料编辑，而非个人资料 + 账号安全 + 主题设置）
- [ ] 组件的 data/state 字段数 **≤ 15 个**
- [ ] 组件的 methods/functions 数 **≤ 15 个**
- [ ] 组件的 computed 属性数 **≤ 10 个**
- [ ] 模板中不包含超过 **3 个** 逻辑独立区域（modal、tab panel、section 各算一个）
- [ ] 没有通过 `v-if` 切换展示完全不同的功能模块
- [ ] 不存在可以独立复用的 UI 片段在模板中内联

### 1.3 目录结构规范

```
src/
├── views/           # 页面级组件（路由入口）
├── components/
│   ├── common/      # 通用 UI 组件（Button, Modal, Toast 等）
│   ├── layout/      # 布局组件（Header, Footer, Sidebar, BottomNav）
│   ├── [feature]/   # 特征模块组件
│   │   └── [SubType]/ # 可选子类型分组
├── composables/     # 可复用逻辑（use*）
├── stores/          # Pinia 状态管理
├── api/             # API 调用层
├── types/           # TypeScript 类型定义
└── utils/           # 纯工具函数
```

### 1.4 巨型组件拆分模式

当一个组件超过行数限制时，按以下优先级拆分：

1. **独立 Modal/Dialog** → 拆为独立组件
2. **独立面板 (Panel/Section)** → 拆为独立组件
3. **数据获取逻辑** → 提取为 composable
4. **复杂表单** → 拆为独立组件
5. **列表/卡片渲染** → 提取列表组件 + 卡片组件

---

## 二、依赖关系规范 (Dependency Management)

### 2.1 禁止循环引用

```
❌ A.vue → B.vue → A.vue (直接循环)
❌ A.vue → B.vue → C.vue → A.vue (间接循环)
```

**检测方法**: 审查每个 import 链，确认不存在循环。

### 2.2 全局组件管理

如果一个组件被 **≥ 3 个** 不同文件导入，考虑以下方案之一：

| 方案 | 适用场景 |
|------|----------|
| Provide/Inject | 需要在组件树深层访问 |
| 全局注册 (app.component) | 通用 UI 组件 |
| 提升到 App.vue + Store 控制 | Modal、Dialog、Toast |
| Teleport + Store | 需要 body 层渲染的组件 |

### 2.3 特征模块隔离

| 模块 | 允许导入来源 | 禁止导入来源 |
|------|-------------|-------------|
| `components/community/` | `api/community`, `composables/`, `stores/`, `types/`, `utils/` | `components/chat/`, `components/tracker/` |
| `components/chat/` | `api/chat`, `composables/`, `stores/`, `types/`, `utils/` | `components/community/`, `components/tracker/` |
| `components/tracker/` | `api/vasi`, `api/medical-report`, `composables/`, `stores/` | `components/community/`, `components/chat/` |
| `components/common/` | `stores/`, `utils/` | 任何特征模块 |

### 2.4 View 层导入限制

View 组件 **只能** 导入以下类型的模块：

```
✅ composables/use*
✅ stores/*
✅ components/**  (子组件)
✅ types/*
❌ api/*（禁止直接调用 API — 必须通过 composable 或 store）
```

---

## 三、数据获取规范 (Data Fetching)

### 3.1 分层架构（强制）

```
View 层         → 只调用 composable / store
Composable 层   → 调用 api/* 模块
Store 层        → 调用 api/* 模块
API 层          → 调用 apiClient (axios)
```

**反模式（禁止）**:

```typescript
// ❌ View 直接调用 API
// views/SomePage.vue
import { someApi } from '@/api/some'
const data = await someApi.getData()

// ✅ 通过 Composable
// composables/useSomeData.ts
export function useSomeData() {
  const data = ref(null)
  async function fetch() { data.value = await someApi.getData() }
  return { data, fetch }
}
// views/SomePage.vue
const { data, fetch } = useSomeData()
await fetch()
```

### 3.2 Composable 命名规范

| 前缀 | 用途 | 示例 |
|------|------|------|
| `use` | 通用逻辑 | `usePWA`, `useToast`, `useAuth` |
| `use[Data]` | 数据获取 | `useTrackingSummary`, `useCommunityFeed` |
| `use[Feature]` | 特征逻辑 | `usePostActions`, `useSwipe` |

### 3.3 Store 使用规范

- Store 应管理 **全局共享状态**（用户认证、主题、聊天消息）
- Store 不应管理 **页面局部状态**（表单输入、UI toggle）
- Store 中的 API 调用必须有错误处理和加载状态

---

## 四、HTML 语义化规范 (Semantic HTML)

### 4.1 强制使用的语义元素

| 场景 | 必须使用的元素 | 说明 |
|------|---------------|------|
| 页面头部 | `<header>` | 包含 logo、主导航 |
| 主导航 | `<nav>` + `aria-label` | 如 `<nav aria-label="主导航">` |
| 主要内容 | `<main>` | 每页一个 |
| 独立内容块 | `<article>` | 帖子、文章、评论 |
| 内容分区 | `<section>` | 带标题的内容区块 |
| 侧边栏 | `<aside>` | 导航、筛选、相关信息 |
| 页脚 | `<footer>` | 版权、链接 |
| 时间 | `<time datetime="...">` | 发布时间 |
| 图片 | `<img alt="...">` | 必须填写 alt |

### 4.2 禁止的反模式

```
❌ <div class="header">       → <header>
❌ <div class="nav">          → <nav aria-label="...">
❌ <div class="article">      → <article>
❌ <div class="sidebar">      → <aside>
❌ <img src="..."> (无 alt)   → <img src="..." alt="描述">
❌ <span class="h1">          → <h1>
❌ 全部用 <div> 构建页面      → 语义元素组合
```

### 4.3 标题层级合法性

```
✅ h1 → h2 → h3 (合法层级)
❌ h1 → h3 (跳级，缺少 h2)
❌ h3 → h1 (逆序)
```

### 4.4 表单标签规范

所有表单输入框必须有关联的 `<label>`：

```html
<!-- ✅ 正确 -->
<label for="username">用户名</label>
<input id="username" type="text" />

<!-- ✅ 也可以 -->
<label>
  用户名
  <input type="text" />
</label>

<!-- ❌ 错误：无 label -->
<input type="text" placeholder="用户名" />
```

---

## 五、Schema.org 结构化数据规范 (Structured Data)

### 5.1 强制要求

SubSkin 的每个页面类型 **必须** 包含对应的 Schema.org 结构化数据。使用 JSON-LD 格式（`<script type="application/ld+json">`）。

### 5.2 全站必需

在 `index.html` 或 `App.vue` 中添加：

```json
{
  "@context": "https://schema.org",
  "@type": "WebApplication",
  "name": "SubSkin",
  "url": "https://subskin.cn",
  "description": "AI赋能的白癜风知识库与社区平台",
  "applicationCategory": "HealthApplication",
  "operatingSystem": "ALL",
  "offers": { "@type": "Offer", "price": "0" }
}
```

### 5.3 页面级 Schema 映射

| 页面 | Schema 类型 | 关键属性 |
|------|------------|----------|
| 百科文章 | `MedicalScholarlyArticle` | headline, about, datePublished, author |
| 社区帖子 | `DiscussionForumPosting` | headline, articleBody, datePublished, author |
| 个人主页 | `ProfilePage` | mainEntity → Person |
| 聊天 | `FAQPage` | mainEntity → Question[] |
| 首页 | `WebSite` + `Organization` | name, description, url, potentialAction |

### 5.4 检查清单

- [ ] `index.html` 中有 Organization/WebApplication schema
- [ ] 百科文章页面有 MedicalScholarlyArticle schema
- [ ] 帖子详情页有 DiscussionForumPosting schema
- [ ] 每个 schema 都有 `@context` 和 `@type`
- [ ] 每个 schema 的关键属性不为空

---

## 六、PWA 与跨平台一致性规范

### 6.1 PWA 完整性检查（新功能上线前必查）

- [ ] Service Worker 更新策略正确（`prompt` 模式）
- [ ] `manifest.webmanifest` (由 vite-plugin-pwa 生成) 配置完整
- [ ] `index.html` 中有完整的 PWA meta 标签
- [ ] 安装提示在移动端和桌面端均有合适位置
- [ ] 离线降级策略有效（NetworkFirst for API, CacheFirst for static）

### 6.2 响应式设计检查清单

- [ ] 移动端优先设计（`sm:` → `md:` → `lg:` → `xl:`）
- [ ] BottomNav 在 `md:` 及以上隐藏
- [ ] 桌面端有顶部导航 (AppHeader)
- [ ] 触摸目标最小 44px（移动端可交互元素）
- [ ] Safe Area: `env(safe-area-inset-bottom)` 处理
- [ ] iOS: `data-ios` 属性处理
- [ ] Viewport: 使用 `dvh` 代替 `vh`（动态视口）

### 6.3 视觉一致性检查

- [ ] 所有内容页外层容器使用 `max-w-6xl mx-auto px-4`
- [ ] Chat 页面使用 `max-w-4xl mx-auto px-4`
- [ ] 颜色使用 `primary-*` Tailwind 类（禁止 hardcode hex）
- [ ] `dark:` 变体覆盖所有颜色/背景
- [ ] 组件命名一致（小白助手 / 小白追踪 / 小白社区 / 小白百科）

### 6.4 导航与路由规范

- [ ] 内部导航使用 `<router-link>`（禁止 `<a href="#">`)
- [ ] 外部链接（百科引用源）使用 `<a href>` 带有 `target="_blank" rel="noopener"`
- [ ] 新功能添加后必须同步更新 `rag.py` 中的 `SITE_FEATURE_KEYWORDS`

### 6.5 Tailwind CSS 常见陷阱

#### `flex-1` + `<input>` 溢出问题

**现象**: 在 flex 容器中使用 `<input class="flex-1">` 时，输入框无法收缩到可用空间以下，导致同行按钮被挤出屏幕边缘。

**根因**: 浏览器默认给 `<input type="text">` 隐式 `size=20` 属性，相当于约 280px 的最小宽度（CJK 字体下）。`flex-1`（`flex: 1 1 0%`）无法覆盖浏览器对表单元素的隐式 `min-width`。

**强制规则**:

```
❌ <input class="flex-1 ..." />          → 移动端溢出
✅ <input class="flex-1 min-w-0 ..." />  → 正确收缩
```

**检查清单**:
- [ ] 所有 `flex-1` 的 `<input>`、`<select>`、`<textarea>` 均配有 `min-w-0`
- [ ] 验证码输入 + 按钮的组合在 375px 宽度下不溢出

> 📄 相关案例: `docs/solutions/ui-bugs/flex-overflow-input-min-width-login-form-20260430.md`

---

## 七、代码质量规范

### 7.1 TypeScript 严格模式

```
❌ as any
❌ @ts-ignore
❌ @ts-expect-error（除非有计划修复）
✅ 正确的类型定义
✅ Proper generics
```

### 7.2 空值处理

```typescript
// ✅ 使用可选链和空值合并
const name = user?.profile?.name ?? '未知用户'

// ❌ 使用 !
const name = user!.profile!.name
```

### 7.3 错误处理

```typescript
// ✅ 明确的错误处理
try {
  await fetchData()
} catch (error) {
  toast.error(getErrorMessage(error))
  console.error('Failed to fetch data:', error)
}

// ❌ 空 catch 块
try { await fetchData() } catch {}
```

---

## 八、审查工作流

### 8.1 新增功能/页面/组件时

当用户请求新增功能、页面或组件时，你必须：

1. **设计审查** — 检查是否符合本 Skill 所有规范
2. **组件规划** — 确定是否需要拆分子组件（参见 1.4）
3. **依赖检查** — 确认导入关系合法（参见 2.3）
4. **数据层设计** — 确认 API 调用通过 composable/store（参见 3.1）
5. **语义化设计** — 确认使用的 HTML 元素（参见 4.1）
6. **Schema 设计** — 确定需要的结构化数据类型（参见 5.3）
7. **响应式设计** — 确认移动端/桌面端布局（参见 6.2）
8. **AI 导航同步** — 确认是否需更新 rag.py（参见 6.4）

### 8.2 审查输出格式

每次审查必须输出结构化报告：

```markdown
## 审查结果

### ✅ 通过项
### 🔴 必须修复（阻塞合并）
### 🟡 建议优化（非阻塞）
### 📋 Schema.org 检查
### 📱 PWA/响应式检查
```

### 8.3 审查标准

| 检查项 | 严重级别 | 阻塞合并 |
|--------|----------|----------|
| 文件超过行数限制 | 🔴 | 是 |
| 违反单一职责 | 🔴 | 是 |
| 循环引用 | 🔴 | 是 |
| View 直接导入 api/* | 🔴 | 是 |
| 缺失 Schema.org 结构化数据 | 🔴 | 是 |
| 缺失 alt 属性 | 🔴 | 是 |
| 使用 `<div>` 代替语义元素 | 🟡 | 否 |
| `flex-1` 的 `<input>` 缺少 `min-w-0` | 🔴 | 是 |
| LoginModal 重复导入 | 🟡 | 否 |
| 缺少 `<label>` | 🟡 | 否 |

---

## 九、禁止事项

### 绝对禁止

0. ❌ **破坏或清空用户数据** — 任何 UI/功能升级**严禁**修改、删除或清空用户的：
   - 个人资料（头像、昵称、手机号、邮箱）
   - 发布的帖子、评论、收藏
   - 草稿箱内容（localStorage `community-draft-*`）
   - 体检报告、VASI 评估记录
   - 用户隐私设置和偏好
   
   > **检查清单**: 每次修改完成后必须确认：
   > - [ ] `localStorage` 中的用户数据未被清空
   > - [ ] 数据库未被直接修改
   > - [ ] `git checkout` / `git reset` 等操作只影响代码文件，不影响数据
   > - [ ] 新建文件不覆盖已有数据文件

1. ❌ 创建超过 500 行的 View 组件
2. ❌ 创建超过 400 行的业务组件
3. ❌ View 组件直接导入 `api/*` 模块
4. ❌ 使用 `as any` / `@ts-ignore`
5. ❌ 空 `catch` 块
6. ❌ 图片缺少 `alt` 属性
7. ❌ 新增功能不添加 Schema.org 结构化数据
8. ❌ 新功能不更新 AI 导航信息（rag.py）
9. ❌ 内部导航使用 `<a href="#">` 而非 `<router-link>`
10. ❌ hardcode 颜色值（必须使用 `primary-*` 或 CSS 变量）

### 强烈不建议

- 在模板中使用复杂表达式（提取为 computed）
- 在同一个组件中管理超过 3 个 modal 的显隐状态
- 在多个文件中重复定义相同的 LoginModal 本地状态

---

## 十、参考文件

- 项目总规范: `/root/subskin/AGENTS.md`
- PWA 实现: `/root/subskin/web/app/src/composables/usePWA.ts`
- PWA 配置: `/root/subskin/web/app/vite.config.ts`
- 主题系统: `/root/subskin/web/app/src/stores/theme.ts`
- API 客户端: `/root/subskin/web/app/src/api/client.ts`
- AI 导航信息: `/root/subskin/web/backend/services/rag.py`

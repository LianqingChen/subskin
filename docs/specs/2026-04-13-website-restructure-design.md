# SubSkin 网站重构设计规范

> **版本**: 2.0 | **日期**: 2026-04-13 | **方案**: 渐进式改造（方案A）

## 1. 架构总览

### 1.1 双轨架构

```
SubSkin 网站
├── VitePress 内容站（保留，SEO友好）
│   ├── /encyclopedia/     → 百科全书（现有md页面）
│   ├── /news/             → 最新动态
│   ├── /weekly/           → 每周分享
│   └── 纯内容页面（无需登录）
│
└── Vue 3 SPA 应用（新建，核心理功能）
    ├── /app/              → SPA入口
    │   ├── /app/          → 首页（混合型）
    │   ├── /app/chat      → AI智能问答
    │   ├── /app/tracker   → 病情量化追踪
    │   ├── /app/community → 病友社区
    │   └── /app/profile   → 个人中心
    └── 需要登录的交互功能
```

### 1.2 导航整合

顶部导航栏统一：
```
[Logo] SubSkin  |  AI问答  |  病情追踪  |  病友社区  |  百科全书  |  [登录/用户头像]
```

- **AI问答、病情追踪、病友社区** → 跳转Vue SPA页面
- **百科全书** → 跳转VitePress内容站
- **登录/用户头像** → 登录弹窗或个人中心

### 1.3 复用策略

| 模块 | 策略 | 说明 |
|------|------|------|
| 后端API | 100%复用 | FastAPI后端不做改动 |
| 用户认证 | 100%复用 | 手机/邮箱/微信登录 |
| AI问答(RAG) | 100%复用 | API不变，重构前端UI |
| VASI评估 | 迁移Vue组件 | VASIAssessment.vue迁移到SPA |
| 百科内容 | 保留VitePress | SEO友好 |
| chat.html | 重构为Vue组件 | 2000+行HTML拆分为可维护组件 |
| 评论系统 | 扩展为社区前端 | 后端API已存在 |

## 2. 设计系统

### 2.1 色彩系统

```css
:root {
  /* 主色调 - 专业信赖蓝 */
  --color-primary: #2563EB;
  --color-primary-light: #3B82F6;
  --color-primary-dark: #1D4ED8;
  --color-primary-50: #EFF6FF;
  --color-primary-100: #DBEAFE;

  /* 辅助色 - 温暖人文橙 */
  --color-accent: #F59E0B;
  --color-accent-light: #FCD34D;

  /* 语义色 - 健康改善绿 */
  --color-success: #10B981;
  --color-success-light: #D1FAE5;

  /* 语义色 - 警示提醒 */
  --color-warning: #F59E0B;
  --color-error: #EF4444;

  /* 皮肤色系 - 用于病情追踪模块 */
  --color-skin-light: #FDE8D0;
  --color-skin-medium: #E8B98A;
  --color-skin-dark: #C68642;

  /* 中性色 */
  --color-gray-50: #F9FAFB;
  --color-gray-100: #F3F4F6;
  --color-gray-200: #E5E7EB;
  --color-gray-300: #D1D5DB;
  --color-gray-400: #9CA3AF;
  --color-gray-500: #6B7280;
  --color-gray-600: #4B5563;
  --color-gray-700: #374151;
  --color-gray-800: #1F2937;
  --color-gray-900: #111827;

  /* 背景色 */
  --color-bg: #FFFFFF;
  --color-bg-soft: #F9FAFB;
  --color-bg-muted: #F3F4F6;
}
```

### 2.2 字体系统

```css
:root {
  --font-sans: 'Inter', 'PingFang SC', 'Noto Sans SC', system-ui, sans-serif;
  --font-mono: 'JetBrains Mono', 'Fira Code', monospace;

  /* 字号阶梯 */
  --text-xs: 0.75rem;    /* 12px */
  --text-sm: 0.875rem;   /* 14px */
  --text-base: 1rem;     /* 16px */
  --text-lg: 1.125rem;   /* 18px */
  --text-xl: 1.25rem;    /* 20px */
  --text-2xl: 1.5rem;    /* 24px */
  --text-3xl: 1.875rem;  /* 30px */
  --text-4xl: 2.25rem;   /* 36px */

  /* 行高 */
  --leading-tight: 1.25;
  --leading-normal: 1.5;
  --leading-relaxed: 1.75;

  /* 字重 */
  --font-normal: 400;
  --font-medium: 500;
  --font-semibold: 600;
  --font-bold: 700;
}
```

### 2.3 间距系统

```css
:root {
  --space-1: 0.25rem;   /* 4px */
  --space-2: 0.5rem;    /* 8px */
  --space-3: 0.75rem;  /* 12px */
  --space-4: 1rem;     /* 16px */
  --space-5: 1.25rem;  /* 20px */
  --space-6: 1.5rem;   /* 24px */
  --space-8: 2rem;     /* 32px */
  --space-10: 2.5rem;  /* 40px */
  --space-12: 3rem;    /* 48px */
  --space-16: 4rem;    /* 64px */
  --space-20: 5rem;    /* 80px */
}
```

### 2.4 圆角与阴影

```css
:root {
  --radius-sm: 0.375rem;   /* 6px */
  --radius-md: 0.5rem;     /* 8px */
  --radius-lg: 0.75rem;   /* 12px */
  --radius-xl: 1rem;      /* 16px */
  --radius-2xl: 1.5rem;   /* 24px */
  --radius-full: 9999px;

  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.05);
  --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
  --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
  --shadow-xl: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
}
```

## 3. 页面布局设计

### 3.1 SPA首页（混合型 - AI优先）

```
┌─────────────────────────────────────────────────┐
│ [Logo] SubSkin  AI问答 病情追踪 社区 百科 [登录] │
├─────────────────────────────────────────────────┤
│                                                 │
│  🌿 SubSkin · 白癜风智能助手                     │
│                                                 │
│  ┌─────────────────────────────────────────┐   │
│  │  💬 在这里输入你的问题...              [发送] │   │
│  └─────────────────────────────────────────┘   │
│                                                 │
│  💡 热门问题:                                   │
│  [白癜风会传染吗] [最新管理方法] [日常饮食注意]   │
│                                                 │
├─────────────────────────────────────────────────┤
│         ✨ 核心功能                              │
│                                                 │
│  🤖 AI智能问答    📊 病情量化    💬 病友社区      │
│  基于百科全书和    上传照片对比   真实经验分享     │
│  社区经验，专业    色斑变化追踪   治疗心得交流     │
│  解答你的疑问      生成改善记录   互相支持鼓励     │
│                                                 │
│  [立即体验]      [开始追踪]     [加入社区]       │
│                                                 │
├─────────────────────────────────────────────────┤
│  👥 真实分享                              [更多] │
│                                                 │
│  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐       │
│  │ 头像 │  │ 头像 │  │ 头像 │  │ 头像 │       │
│  │ 小王  │  │ 李姐  │  │ 张哥  │  │ 陈姐  │       │
│  │ 3个月 │  │ 6个月 │  │ 1年  │  │ 2年  │       │
│  │ 改善  │  │ 分享  │  │ 心路  │  │ 药效  │       │
│  └──────┘  └──────┘  └──────┘  └──────┘       │
│                                                 │
├─────────────────────────────────────────────────┤
│  🛡️ 信任保障                                    │
│                                                 │
│  📄 基于文献   🔒 隐私保护   👨‍⚕️ 专业参考        │
│  2000+论文     照片加密存储  医学顾问审核         │
│                                                 │
│  ⚠️ 本文不构成医疗建议                          │
└─────────────────────────────────────────────────┘
```

### 3.2 AI智能问答页面

**核心设计理念**：参考DeepSeek/ChatGPT风格，全屏对话体验。

```
移动端（<768px）:
┌──────────────────────┐
│ [☰] AI问答    [用户] │
├──────────────────────┤
│                      │
│ 🤖 SubSkin AI        │
│                      │
│ 白癜风是一种...       │
│                      │
│ ┌─ 参考来源 ──────┐  │
│ │ [文献1] [文献2]  │  │
│ └──────────────────┘  │
│                      │
│ ⚠️ 仅供参考          │
│                      │
│ 👤 你                 │
│ 白癜风会传染吗？      │
│                      │
├──────────────────────┤
│ 🔄 新对话  [📎] [➤]  │
│ [__输入问题_______] │
└──────────────────────┘

桌面端（≥1024px）:
┌───────────┬───────────────────────────┬──────────────┐
│ 对话列表   │                            │ 知识参考     │
│           │  🤖 SubSkin AI             │              │
│ 📌 今日   │                            │ 📚 相关知识  │
│ ├ 白癜风?  │  白癜风是一种获得性...      │              │
│ ├ 饮食?   │                            │ ├ 什么是白癜风│
│           │  ┌─ 参考来源 ────┐         │ ├ 病因病机   │
│ 📅 昨天   │  │ [PubMed#1]   │         │ ├ 管理方法   │
│ └ ...     │  │ [社区分享#1] │         │ └ 饮食建议   │
│           │  └──────────────┘         │              │
│ [新对话]  │                            │ 💬 社区相关   │
│           │  ⚠️ 仅供参考              │              │
│           │                            │ 👤 小王分享:  │
│           │  👤 你                     │ "我用了3个月" │
│           │  白癜风会传染吗？           │              │
│           │                            │ 👤 李姐经验:  │
│           ├──────────────────────────  │ "光疗半年..."│
│           │ [📎上传] [_输入问题___] [➤] │              │
└───────────┴───────────────────────────┴──────────────┘
```

**新增功能**：
- 💡 AI心理咨询模式（温暖对话风格，非临床诊断）
- 📎 图片上传（上传白斑照片，AI辅助解读）
- 📚 右侧知识面板（桌面端）
- 🔄 多轮对话历史
- 🏷️ 问题分类标签

### 3.3 病情量化追踪页面

**核心设计理念**：照片对比 + 数据可视化，让用户直观看到变化。

```
┌─────────────────────────────────────────────────┐
│  [☰] 病情追踪                    [用户]          │
├─────────────────────────────────────────────────┤
│                                                 │
│  📊 我的追踪面板                                 │
│                                                 │
│  ┌──────────────────┐  ┌──────────────────┐     │
│  │  最新VASI评分      │  │  首次评估         │     │
│  │                   │  │                  │     │
│  │    2.3            │  │   4.1            │     │
│  │  较上次 ↓ 0.8     │  │  6个月前          │     │
│  │                   │  │                  │     │
│  │  📈 改善44%      │  └──────────────────┘     │
│  └──────────────────┘                           │
│                                                 │
│  📸 今日评估                                    │
│  ┌──────────────────────────────────────────┐   │
│  │                                          │   │
│  │   [点击上传照片]  或  [拍照]              │   │
│  │                                          │   │
│  │   支持格式：JPG/PNG，最大10MB            │   │
│  └──────────────────────────────────────────┘   │
│                                                 │
│  部位选择: [面部] [颈部] [手部] [躯干] [四肢]     │
│                                                 │
│  🔒 照片仅存储在你的账户中，不会公开              │
│                                                 │
├─────────────────────────────────────────────────┤
│  📈 变化趋势                                    │
│                                                 │
│  VASI评分                                        │
│  4.5 │                                          │
│  4.0 │  ●                                      │
│  3.5 │                                          │
│  3.0 │       ●                                  │
│  2.5 │                                          │
│  2.0 │            ●  ← 现在                     │
│      └──────────────────────────                │
│       11月  12月  1月  2月  3月  4月            │
│                                                 │
├─────────────────────────────────────────────────┤
│  📸 照片对比                                 │
│                                                 │
│  ┌──────────┐   ←→   ┌──────────┐            │
│  │ 2025-10  │         │ 2026-04  │            │
│  │ [旧照片]  │         │ [新照片]  │            │
│  │           │         │           │            │
│  └──────────┘         └──────────┘            │
│                                                 │
│  [滑动对比] [叠加对比] [并排对比]                 │
│                                                 │
└─────────────────────────────────────────────────┘

移动端底部Tab:
┌──────┬──────┬──────┬──────┐
│ 问答  │ 追踪  │ 社区  │ 我的 │
│  🤖  │  📊  │  💬  │  👤  │
└──────┴──────┴──────┴──────┘
```

**新增功能**：
- 📸 照片对比（滑动/叠加/并排三种模式）
- 📈 VASI趋势图（ECharts）
- 🔒 隐私提示（照片加密存储）
- 📋 部位选择器
- 💊 管理记录（用药/治疗与评分关联）

### 3.4 病友社区页面

**核心设计理念**：类小红书卡片流+分类筛选，温暖有温度的社区氛围。

```
┌─────────────────────────────────────────────────┐
│  [☰] 病友社区                    [用户]          │
├─────────────────────────────────────────────────┤
│                                                 │
│  [✏️ 发布分享]                                  │
│                                                 │
│  分类: [全部] [治疗经验] [药效分享] [医院评价]     │
│        [日常忌口] [遮盖妙招] [心情驿站] [新确诊]  │
│                                                 │
├─────────────────────────────────────────────────┤
│                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐     │
│  │ 👤 小王   │  │ 👤 李姐   │  │ 👤 张哥   │     │
│  │          │  │          │  │          │     │
│  │ 📷 照片   │  │ 📷 照片   │  │          │     │
│  │          │  │          │  │ "3年心路"  │     │
│  │ 308激光  │  │ 他克莫司  │  │  历程分享" │     │
│  │ 3个月心得 │  │ 药效记录  │  │          │     │
│  │          │  │          │  │ ❤️128     │     │
│  │ ❤️89    │  │ ❤️56     │  │ 💬34      │     │
│  │ 💬23     │  │ 💬12     │  │          │     │
│  └──────────┘  └──────────┘  └──────────┘     │
│                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐     │
│  │ 👤 陈姐   │  │ 👤 刘哥   │  │ 👤 赵姐   │     │
│  │          │  │          │  │          │     │
│  │ "协和体  │  │ 📷       │  │ "遮盖秘  │     │
│  │  验分享"  │  │ 饮食打卡 │  │  诀分享"  │     │
│  │          │  │ 忌口清单  │  │          │     │
│  │ ❤️67    │  │ ❤️203    │  │ ❤️156    │     │
│  │ 💬28     │  │ 💬89     │  │ 💬45      │     │
│  └──────────┘  └──────────┘  └──────────┘     │
│                                                 │
│  [加载更多...]                                  │
│                                                 │
└─────────────────────────────────────────────────┘

移动端 - 帖子详情页:
┌──────────────────────┐
│ [←] 帖子详情  [⋯]    │
├──────────────────────┤
│ 👤 小王 · 3月12日     │
│ 治疗: 308激光          │
│ 病程: 2年              │
│                       │
│ 308准分子激光治疗3个月 │
│ 经验分享...           │
│                       │
│ 📷                    │
│ [治疗前后对比照]       │
│                       │
│ ❤️ 89  💬 23  📤     │
├──────────────────────┤
│ 精选评论              │
│                       │
│ 👤 李姐  · 2天前      │
│ 赞！我也在做308...    │
│                       │
│ 👤 张哥  · 1天前      │
│ 请问每次多长时间？    │
│                       │
│ 👤 小王  · 1天前      │
│ 每次约5分钟...         │
├──────────────────────┤
│ [💬 写评论____] [发送] │
└──────────────────────┘
```

**社区帖子类型（发布时选择）**：
1. 🏥 **治疗经验** - 治疗方法、疗程、效果
2. 💊 **药效分享** - 具体药物/治疗方案效果记录
3. 🔍 **医院评价** - 就医体验、医生推荐
4. 🍽️ **日常忌口** - 饮食经验、忌口清单
5. 💄 **遮盖妙招** - 遮盖化妆技巧
6. 💪 **心情驿站** - 心路历程、互相鼓励
7. 🆕 **新确诊指南** - 给新病友的建议

### 3.5 个人中心页面

```
┌─────────────────────────────────────────────────┐
│  个人中心                                        │
├─────────────────────────────────────────────────┤
│                                                 │
│  ┌─────────────────────────────────────────┐    │
│  │  [头像]                                  │    │
│  │  用户名                                  │    │
│  │  📊 VASI轨迹: 改善中 📈                  │    │
│  │  📅 加入SubSkin: 2025年10月              │    │
│  └─────────────────────────────────────────┘    │
│                                                 │
│  📊 我的追踪数据                                │
│  ┌──────────┬──────────┬──────────┐            │
│  │ 评估次数   │ 改善率     │ 追踪天数  │            │
│  │    8      │   44%    │   180天  │            │
│  └──────────┴──────────┴──────────┘            │
│                                                 │
│  💬 我的社区                                    │
│  ├── 我发布的 (12)                               │
│  ├── 我收藏的 (34)                               │
│  └── 我的评论 (56)                               │
│                                                 │
│  ⚙️ 设置                                       │
│  ├── 个人信息                                    │
│  ├── 隐私设置                                    │
│  ├── 照片权限                                    │
│  └── 退出登录                                    │
│                                                 │
└─────────────────────────────────────────────────┘
```

## 4. 移动端底部Tab设计

```css
/* 底部导航 - 移动端核心 */
.nav-bottom {
  display: flex;
  justify-content: space-around;
  align-items: center;
  height: 64px;
  background: white;
  border-top: 1px solid var(--color-gray-200);
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 50;
  padding-bottom: env(safe-area-inset-bottom);
}

.nav-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  font-size: var(--text-xs);
  color: var(--color-gray-400);
}

.nav-item.active {
  color: var(--color-primary);
}

.nav-item .icon {
  width: 24px;
  height: 24px;
}

/* Tab项 */
.question → AI问答 (🤖)
tracker → 病情追踪 (📊)
community → 病友社区 (💬)
profile → 个人中心 (👤)
```

## 5. 组件库

### 5.1 必需组件清单

#### 基础组件
- `SubButton` - 按钮变体（primary/secondary/ghost/danger）
- `SubCard` - 卡片容器
- `SubModal` - 弹窗（替代HTML原生dialog）
- `SubToast` - 通知提示（替代当前Toast）
- `SubAvatar` - 用户头像
- `SubTab` - 标签切换
- `SubTag` - 标签/徽章
- `SubInput` - 输入框（含验证状态）
- `SubLoading` - 加载状态

#### 业务组件
- `ChatWindow` - AI对话窗口（核心重构chat.html）
- `ChatMessage` - 单条消息组件
- `ChatInput` - 消息输入区
- `SuggestionChips` - 推荐问题标签组
- `KnowledgePanel` - 右侧知识面板（桌面端）
- `PhotoUploader` - 照片上传组件
- `PhotoCompare` - 照片对比（滑动/叠加/并排）
- `VasiScoreCard` - VASI评分卡片
- `VasiTrendChart` - VASI趋势图
- `CommunityPostCard` - 社区帖子卡片
- `CommunityPostForm` - 帖子发布表单
- `CategoryFilter` - 分类筛选栏
- `UserLoginModal` - 登录弹窗（复用现有逻辑）
- `TrustBadges` - 信任标识栏
- `DisclaimerBanner` - 免责声明横幅

### 5.2 photo Compare交互设计

**三种对比模式**：

1. **滑动对比（Slide）**：
   - 两张照片叠加，中间一条竖线
   - 拖动竖线左右滑动，展示旧/新照片
   - 默认模式，最直观

2. **叠加对比（Overlay）**：
   - 新照片半透明覆盖在旧照片上
   - 左右滑动调整透明度
   - 适合细微变化对比

3. **并排对比（Side-by-side）**：
   - 两张照片左右排列
   - 同时放大/缩小/平移（联动）
   - 适合整体对比

## 6. 技术实现方案

### 6.1 Vue 3 SPA 技术栈

```
web/app/
├── public/
├── src/
│   ├── App.vue
│   ├── main.ts
│   ├── router/
│   │   └── index.ts           # Vue Router
│   ├── stores/
│   │   ├── auth.ts            # Pinia - 用户认证
│   │   ├── chat.ts            # Pinia - AI对话
│   │   ├── tracker.ts         # Pinia - 病情追踪
│   │   └── community.ts       # Pinia - 社区
│   ├── composables/
│   │   ├── useAuth.ts         # 认证逻辑
│   │   ├── useChat.ts         # 对话逻辑
│   │   └── useTracker.ts      # 追踪逻辑
│   ├── components/
│   │   ├── common/            # 基础组件
│   │   ├── chat/              # AI问答
│   │   ├── tracker/           # 病情追踪
│   │   ├── community/         # 社区
│   │   └── layout/            # 布局
│   ├── views/
│   │   ├── HomePage.vue
│   │   ├── ChatPage.vue
│   │   ├── TrackerPage.vue
│   │   ├── CommunityPage.vue
│   │   ├── PostDetailPage.vue
│   │   └── ProfilePage.vue
│   ├── api/
│   │   ├── client.ts          # Axios实例
│   │   ├── auth.ts            # 认证API
│   │   ├── chat.ts            # 对话API
│   │   ├── tracker.ts         # 追踪API
│   │   └── community.ts       # 社区API
│   └── styles/
│       ├── variables.css      # 设计Token
│       ├── global.css         # 全局样式
│       └── animations.css     # 动画
├── index.html
├── vite.config.ts
├── tsconfig.json
└── package.json
```

**依赖**：
- Vue 3 + TypeScript
- Vue Router 4
- Pinia（状态管理）
- Tailwind CSS（样式框架）
- Axios（API调用）
- ECharts（图表）
- VueUse（工具组合式函数）

### 6.2 构建与部署

```
# 开发
cd web/app && npm run dev

# 构建
cd web/app && npm run build
# → 输出到 web/app/dist/

# VitePress构建
cd web/vitepress && npm run build
# → 输出到 web/vitepress/docs/.vitepress/dist/

# Nginx配置（统一入口）
location / {
  # SPA路由
  try_files $uri $uri/ /index.html;
}
location /encyclopedia/ {
  # VitePress静态内容
  alias /var/www/vitepress/;
}
location /api/ {
  # FastAPI后端
  proxy_pass http://localhost:8000;
}
```

## 7. 后端API扩展（新增）

### 7.1 社区帖子API

```python
# web/backend/api/community.py

# 帖子CRUD
POST   /api/community/posts          # 发布帖子
GET    /api/community/posts           # 帖子列表（分页、分类筛选）
GET    /api/community/posts/{id}      # 帖子详情
PUT    /api/community/posts/{id}      # 更新帖子
DELETE /api/community/posts/{id}      # 删除帖子

# 帖子互动
POST   /api/community/posts/{id}/like     # 点赞/取消点赞
POST   /api/community/posts/{id}/favorite  # 收藏/取消收藏

# 评论
POST   /api/community/posts/{id}/comments  # 添加评论
GET    /api/community/posts/{id}/comments  # 评论列表

# 分类
GET    /api/community/categories        # 获取分类列表
```

### 7.2 新增数据模型

```python
# web/backend/database/models.py 新增

class CommunityCategory(Base):
    """社区帖子分类"""
    __tablename__ = "community_categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)           # 分类名
    slug = Column(String, unique=True, index=True)  # URL友好名
    icon = Column(String, nullable=True)            # 图标emoji
    description = Column(String, nullable=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class Post(Base):
    """社区帖子"""
    __tablename__ = "community_posts"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    category_id = Column(Integer, ForeignKey("community_categories.id"))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    view_count = Column(Integer, default=0)
    like_count = Column(Integer, default=0)
    comment_count = Column(Integer, default=0)
    is_pinned = Column(Boolean, default=False)       # 置顶
    is_approved = Column(Boolean, default=False)     # 审核状态
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    author = relationship("User", back_populates="posts")
    category = relationship("CommunityCategory")
    images = relationship("PostImage", back_populates="post")
    likes = relationship("PostLike", back_populates="post")
    comments = relationship("PostComment", back_populates="post")


class PostImage(Base):
    """帖子图片"""
    __tablename__ = "post_images"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("community_posts.id"))
    image_url = Column(String, nullable=False)
    sort_order = Column(Integer, default=0)
    post = relationship("Post", back_populates="images")


class PostLike(Base):
    """帖子点赞"""
    __tablename__ = "post_likes"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("community_posts.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

    post = relationship("Post", back_populates="likes")
    __table_args__ = (UniqueConstraint('post_id', 'user_id'),)


class PostComment(Base):
    """帖子评论"""
    __tablename__ = "post_comments"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("community_posts.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    content = Column(Text, nullable=False)
    parent_id = Column(Integer, ForeignKey("post_comments.id"), nullable=True)  # 回复
    created_at = Column(DateTime, default=datetime.utcnow)

    post = relationship("Post", back_populates="comments")
    author = relationship("User")
```

## 8. 实施优先级

### Phase 1 - 基础框架（P0）
1. 创建 Vue 3 SPA 项目脚手架
2. 搭建路由和布局结构
3. 实现统一导航栏和底部Tab
4. 迁移登录/注册弹窗
5. 实现首页（混合型设计）

### Phase 2 - AI问答重构（P0）
1. 将chat.html拆分为Vue组件
2. 实现移动端/桌面端响应式布局
3. 添加知识面板（桌面端侧边栏）
4. 对接现有RAG API
5. 添加心理咨询模式入口

### Phase 3 - 病情追踪增强（P1）
1. 迁移VASI评估组件到SPA
2. 实现照片上传和对比功能（滑动/叠加/并排）
3. 集成ECharts趋势图
4. 实现VASI历史记录面板
5. 添加部位选择器

### Phase 4 - 社区功能（P1）
1. 实现社区帖子列表（卡片流）
2. 实现分类筛选
3. 实现帖子详情页
4. 实现帖子发布表单
5. 实现评论和点赞

### Phase 5 - 优化打磨（P2）
1. 性能优化（代码分割、懒加载）
2. PWA支持
3. 深色模式
4. 无障碍优化
5. SEO优化（SPA预渲染）

## 9. 合规声明检查清单

所有页面和组件必须包含：
- [ ] 底部或弹窗免责声明："本文不构成医疗建议"
- [ ] 使用"皮肤管理"而非"诊断/治疗"
- [ ] 使用"改善"而非"治愈/康复"
- [ ] AI回答标注"AI生成，仅供参考"
- [ ] 照片隐私声明："照片仅存储在你的账户中"
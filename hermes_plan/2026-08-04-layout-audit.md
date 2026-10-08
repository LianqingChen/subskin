# SubSkin Web App 桌面端布局与风格一致性审计

- 日期: 2026-08-04
- 范围: /root/subskin/web/app (Vue3 + TS + Tailwind)
- 标准: .agents/skills/ui-audit/SKILL.md
- 触发: 用户反馈 /diary 在桌面宽屏上显得特别窄

## 一、全局布局容器规范

### 现状
- App.vue (src/App.vue): <main> 无宽度约束(L5)，仅处理 BottomNav 的 padding-bottom；宽度完全由各页面自带容器决定。
- main.css (src/styles/main.css): 定义设计系统组件类 card / btn-primary / btn-secondary / btn-ghost / badge / input-field / section-title；body 背景为 var(--color-bg) (#F5F7FA)。
- tailwind.config.ts: primary 映射 CSS 变量(--color-primary-*)，主题为 teal 系 (H=174, S=63%, L=50%)。
- AppHeader.vue L94: 内部容器 max-w-6xl mx-auto px-4 sm:px-6。

### 结论: 项目统一宽度规范
| 类型 | 规范 | 依据 |
|---|---|---|
| 常规内容页 | max-w-6xl mx-auto px-4 (1152px) | SKILL 规则 + AppHeader 及 12+ 页面遵循 |
| 详情/阅读页 | max-w-4xl mx-auto px-4 | SKILL 规则; Drafts/UserProfile/PhotoGuide 已遵循 |
| 弹窗 | max-w-sm ~ max-w-2xl 按需 | 现状 |

偏离页面: DiaryPage(scoped CSS 640px)、CommunityPage(max-w-2xl + sm:px-5)、PostDetailPage(max-w-2xl + px-3)、MessagesPage/ChatRoomPage(无宽度约束)、AssessmentPage测评流(主内容 max-w-md/lg 且与 Report Tab max-w-6xl 不一致)。

## 二、逐页审计 (src/views/)

| 页面 | 容器 class (位置) | 桌面表现 | 评价 |
|---|---|---|---|
| ChatAssistantPage | max-w-6xl mx-auto w-full px-4 (L267/285/315/341 四处一致) | 正常 | OK |
| DiaryPage | scoped CSS .diary-page{max-width:640px} (L394-399)，无断点 | 仅640px，两侧大片留白 | P0 |
| AssessmentPage | 测评流无容器，Step组件内部 max-w-md/max-w-lg mx-auto；Report Tab: max-w-6xl px-4 pb-24 md:pb-8 (L381) | 测评流仅约448-512px宽；两个子Tab宽度跳变 | P1 |
| CommunityPage | max-w-2xl mx-auto px-4 py-3 space-y-3 sm:px-5 sm:space-y-4 (L343) | 仅672px，瀑布流拥挤 | P1 |
| PostDetailPage | max-w-2xl mx-auto px-3 pb-24 (L241/406) | 窄且 px-3 违反 px-4 规则 | P1 |
| ProfilePage | max-w-6xl mx-auto w-full px-4 py-6 space-y-6 (L534) | 正常；card p-4/p-6/p-8 混用 | OK/P2 |
| EncyclopediaNewPage | 文章 max-w-3xl (L184)；索引 max-w-6xl (L265) | 正常 | OK |
| MessagesPage | 无 max-w，仅 min-h-screen bg-[#F5F7FA] (L42) | 列表桌面全宽拉伸 | P1 |
| ChatRoomPage | 无 max-w，气泡 max-w-[75%] (L208) | 宽屏气泡过宽 | P2 |
| DraftsPage / UserProfilePage / PhotoGuidePage | max-w-4xl mx-auto px-4 | 正常，符合详情页规范 | OK |
| VasiDetailPage / VasiComparePage / ReportDetailPage / ReportComparePage | max-w-6xl mx-auto px-4 | 正常 | OK |
| ContactsPage / GroupInfoPage / CollectionSharePage / PrivacyPolicyPage / TermsOfServicePage / DashboardPage | max-w-6xl mx-auto px-4 | 正常 | OK |

备注: EncyclopediaNewPage 水平内边距为 px-4 sm:px-6 lg:px-8，与全局 px-4 规范略有出入，视觉影响小(P2)。

## 三、DiaryPage 深度分析 (P0)

文件: src/views/DiaryPage.vue

1. 宽度根因: L394-399 `.diary-page { max-width: 640px; margin: 0 auto; padding: 16px 16px 100px; min-height: 100vh; }` —— 无 @media 断点，桌面恒定 640px，即用户反馈"电脑上特别窄"的直接原因。对比同级的 ChatAssistant/Profile/Assessment(Report Tab) 均为 max-w-6xl。
2. 样式体系孤立: 整页使用 BEM scoped CSS (diary-header / diary-stats / diary-tabs / diary-input / diary-list)，未使用 Tailwind 工具类与 card / btn-primary 等设计系统类；暗色模式手写 html.dark 选择器 (L424/475/577/612/634 等)。
3. 主色硬编码: 页内 12 处 #26A69A (L412/443/480/492/523/583/605/640/689/716/754 及 moodConfig L63)；另有 rgba(38,166,154,x) 多处。绕过了 primary-* 主题变量。
4. DiaryWeeklyReport (components/diary/DiaryWeeklyReport.vue): 根元素无 max-width，继承父级 640px；内部全部单列移动端布局 (stats flex 一行、心情分布、每日情绪列表)，宽屏下内容稀疏。头部渐变 L208 硬编码 #26a69a→#00897b，装饰元素 absolute right:-40px。拓宽后需 md+ 栅格化并处理溢出。
5. DiaryWeeklyPoster (components/diary/DiaryWeeklyPoster.vue): 弹窗 max-w-[375px] (L387) 是手机海报预览，宽屏下居中展示合理，保持不变；canvas 绘制色 #26A69A (L135/186/241/259) 属分享图美术色，可豁免。
6. 其余日记组件同样硬编码: DiaryEntryCard (L148/240)、DiaryQuickPanel (L211/245/267/279)、DiaryCalendarMini (L201/218)。整个 diary 模块合计 25+ 处 #26A69A。
7. 缺失项: 无 MedicalDisclaimer (SKILL 要求内容页必备)；空状态/加载态自造 (diary-list__empty / diary-list__spinner)，未用 EmptyState / LoadingSpinner。

## 四、风格一致性问题

### 1. 主题色 (P1)
- 项目主色: primary = teal 系 HSL 变量 (main.css L6-20, H=174)。
- diary 模块 + BottomNav 激活态 (BottomNav.vue L126/130/144/164) 硬编码 #26A69A，色相接近但不跟随主题变量与暗色调。
- PostDetailPage.vue L59-65 分类徽章使用 Tailwind 原生色 bg-blue/purple/pink/green/cyan/yellow-100，违反 SKILL "分类徽章必须用 getCategoryColor()" 规则。
- 豁免项: red-*(删除/点赞/退出)、yellow-*(收藏) 为语义色；AppHeader L214 staging 模式 bg-blue-500 为环境标识；ChatAssistantPage L306 text-green-600 (知心陪伴模式) 属语义强调。
- 背景色三种写法并存: App.vue bg-gray-50 (#f9fafb) vs main.css body var(--color-bg) (#F5F7FA) vs AssessmentPage L301 / ChatRoomPage L141 / MessagesPage L42 硬编码 bg-[#F5F7FA]，存在细微色差 (#f9fafb 偏灰白 vs #F5F7FA 偏青灰)。

### 2. 卡片 (P2)
- 标准 .card = bg-white rounded-xl shadow-sm border (main.css L146-148)。多数页面遵循。
- diary 模块自造卡片: 白底 + border #e2e8f0 + border-radius 16px + 无 shadow-sm (DiaryPage L626-632)，与 .card 不一致。
- ProfilePage 混用 card p-4 / p-6 / p-8 (SKILL 默认 p-5)。
- AssessmentStep1Capture.vue L106 自定义 shadow-[0_-4px_20px...] 底部浮动卡，属特殊交互可接受。

### 3. 空状态 (P1)
- components/common/EmptyState.vue 存在但全项目 0 处引用 (grep 验证)。
- 实际存在至少 4 种空状态实现: DiaryPage diary-list__empty (图标+标题+描述)、CommunityPage emoji 📝+文字 (L462)、MessagesPage ri-lock-line 大图标 (L122)、PostDetailPage 纯文字"加载中..." (L257)。
- 加载态同样不统一: LoadingSpinner.vue 0 引用；diary 用 ri-loader-4-line 旋转、EncyclopediaNewPage 用 border 圆环 spinner (L177)、MessagesPage 用 ri-loader-4-line。

### 4. 按钮与 Tab (P2)
- btn-primary / btn-secondary / btn-ghost 已定义 (main.css L120-144)，但采用率低。
- Tab 样式至少 5 种并存: AssessmentPage 子Tab 圆角药丸 (bg-primary-500 text-white, L353-376)、DiaryPage 分段容器 (rgba teal 底 + 白色激活, L551-590)、DashboardPage 灰槽 tabs (bg-gray-100 + 白色激活, L27-39)、EncyclopediaNewPage 文字按钮 (bg-primary-50, L201-237)、ChatAssistantPage 圆角药丸切换 (L298-309)。
- 登录按钮 3 种: DiaryPage 自造 pill (L436-450)、MessagesPage 自造 rounded-xl bg-primary-500 (L126-130)、CommunityPage 用 btn-primary (L454)。

### 5. 标题层级与间距 (P2)
- SKILL 规定页标题 h1 为 text-2xl→md:text-3xl。EncyclopediaNewPage 遵循 (L187/267)；DiaryPage h1 固定 22px (L467)；MessagesPage/ChatRoomPage h1 仅 text-lg (偏小)。
- 间距节奏: SKILL 规定区块间 space-y-6。ProfilePage 遵循；CommunityPage 为 space-y-3 sm:space-y-4 (偏紧)；DiaryPage 手写 margin/gap。

### 6. 命名 (P1)
- EncyclopediaNewPage.vue L267 标题为"白白百科"，按 SKILL 规范应为"小白百科"。其余导航命名 (问答/日记/测评/白友圈) 在 AppHeader 与 BottomNav 一致。

### 7. 医疗免责声明 (P1)
- MedicalDisclaimer.vue 存在但 0 引用；CommunityPage (L487-488) 与 ProfilePage (L818-819) 用行内小字，DiaryPage/PostDetailPage 无显式声明。
- 更正核实: PostDetailPage L362 有行内免责声明 (amber 小字)；确认无声明的是 DiaryPage 与 ChatAssistantPage。声明样式不统一: 红色段落(Terms)/amber 行内(PostDetail)/灰色小字(Profile/Community)。

## 五、统一方案

### 宽度规范 (执行 SKILL 既有标准)
- 常规内容页: max-w-6xl mx-auto px-4 py-4 md:py-6
- 单列沉浸/详情页 (日记、帖子详情、消息、聊天): max-w-4xl mx-auto px-4 py-6
- 弹窗: max-w-sm ~ 2xl 按需
- 水平内边距统一 px-4 (取消 sm:px-5 / lg:px-8 特例)

### 风格规范
- 主色一律 primary-*；teal 硬编码 #26A69A / rgba(38,166,154,*) 全部替换
- 卡片统一 card p-5 (紧凑列表 p-4、重表单 p-6)
- 空状态统一 <EmptyState icon title desc />；加载态统一 <LoadingSpinner />
- 主按钮 btn-primary、次按钮 btn-secondary、文字按钮 btn-ghost
- 分段 Tab 统一为 DashboardPage 灰槽样式 (bg-gray-100 rounded-xl p-1 + 激活 bg-white shadow-sm) 或 AssessmentPage 药丸样式，二选一并复用
- 页标题 h1: text-2xl md:text-3xl font-bold；区块间距 space-y-6
- 免责声明统一 <MedicalDisclaimer />，替换所有行内小字

## 六、逐文件修复清单

### P0

**src/views/DiaryPage.vue**
1. L394-399: .diary-page max-width 640px → 改为 class="max-w-4xl mx-auto px-4 py-6 pb-24 md:pb-10 space-y-6"（最小改动方案: 仅加 @media(min-width:768px){.diary-page{max-width:896px}}，但建议一步迁移到 Tailwind 与全站一致）。
2. L412/443/480/492/523/583/605/640/689/716/754: #26A69A → text-primary-500 / bg-primary-500 / border-primary-500；rgba(38,166,154,x) → primary-*/透明度。
3. L240-253 stats bar → grid grid-cols-3 gap-3，单元用 card p-3。
4. L263-280 tabs → 统一分段 Tab 样式 (灰槽或药丸)。
5. L328-356 输入区容器 → card p-4；提交按钮 → btn-primary。
6. L360-369 空状态 / L284-287 与 L360-363 加载态 → 改用 <EmptyState /> 与 <LoadingSpinner />。
7. 页尾补 <MedicalDisclaimer />。
8. L467 h1 22px → text-2xl md:text-3xl font-bold。

**src/components/diary/DiaryWeeklyReport.vue**
1. 根元素配合父级拓宽；建议外层 max-w-4xl 下周报卡片自身 max-w-3xl mx-auto，或 md:grid md:grid-cols-2 gap-4 展开各 section。
2. L208 渐变 #26a69a→#00897b → var(--color-primary-500)→var(--color-primary-700)。
3. L321/367/494/526 #26a69a → primary 变量。
4. 头部装饰 (right:-40px) 需在容器加 overflow-hidden。

**src/components/diary/DiaryWeeklyPoster.vue**
- 保持 max-w-[375px] 弹窗与 canvas 美术色不变 (豁免)。仅需确认宽屏居中展示 (当前 fixed inset-0 + items-center，已满足)。

**src/components/diary/DiaryEntryCard.vue / DiaryQuickPanel.vue / DiaryCalendarMini.vue**
- 替换全部 #26A69A 为 primary 变量 (EntryCard L148/240、QuickPanel L211/245/267/279、CalendarMini L201/218)；卡片容器改用 .card。

### P1

**src/views/AssessmentPage.vue**
1. L387-464 测评流 main 区: 在 <main> 内为 Step 内容包一层 max-w-4xl mx-auto w-full (当前 Step 组件 max-w-md/lg 在满宽 main 内，桌面偏窄且偏左)。
2. 统一两个子 Tab 的宽度档位: Report Tab 现为 max-w-6xl (L381)，建议同为 max-w-4xl，避免切换时宽度跳变。
3. L301 bg-[#F5F7FA] → 使用 var(--color-bg) 或全局统一背景。

**src/views/CommunityPage.vue**
1. L343: max-w-2xl → max-w-4xl mx-auto px-4 py-4 space-y-6 (去掉 sm:px-5 / sm:space-y-4 特例)。
2. FeedWaterfall 保持 md:grid-cols-3，可加 lg:grid-cols-4 利用更宽容器。

**src/views/PostDetailPage.vue**
1. L241 / L406: max-w-2xl px-3 → max-w-4xl mx-auto px-4 (正文与底部操作栏同宽)。
2. L59-65: 分类色映射改为调用 @/utils/colors 的 getCategoryColor()，移除 bg-blue/purple/pink/green/cyan/yellow-100 硬编码。

**src/views/MessagesPage.vue**
1. L42 起增加内容容器: max-w-3xl mx-auto px-4 (会话列表、未登录提示 L122 同宽)。
2. L76-78 通知下拉面板同步加 max-w-3xl mx-auto。
3. L47 h1 text-lg → text-2xl md:text-3xl。

**src/views/EncyclopediaNewPage.vue**
1. L267: "白白百科" → "小白百科"。
2. L184/L265: px-4 sm:px-6 lg:px-8 → 统一 px-4 (P2)。

**src/views/ChatRoomPage.vue**
1. L168-170 消息区与 L144 header 内容: 包一层 max-w-3xl mx-auto w-full，避免宽屏气泡过度拉伸。

### P2

**src/App.vue**
- L2: bg-gray-50 与 body var(--color-bg)(#F5F7FA) 存在色差，建议统一为 bg-[var(--color-bg)] 或全站统一 gray-50。

**src/components/layout/BottomNav.vue**
- L126/130: 激活色 #26A69A → var(--color-primary-500)；L90/102/144/164 的 rgba(38,166,154,*) 同步替换，使移动端导航与桌面 AppHeader (primary-600/700) 激活色一致。

**src/views/ProfilePage.vue**
- L536/598/613: card p-6 / p-8 / p-4 混用 → 按 SKILL 收敛为 p-5 默认、p-4 紧凑。

**全站通用组件接入**
- EmptyState / LoadingSpinner / MedicalDisclaimer 目前 0 引用: 建议在本次修复中至少在 DiaryPage / CommunityPage / PostDetailPage / MessagesPage 接入，形成示范。

## 七、优先级汇总

| 级别 | 问题 | 文件 |
|---|---|---|
| P0 | 日记页桌面固定 640px，全样式体系脱离设计系统 | views/DiaryPage.vue |
| P0 | diary 模块主色硬编码 25+ 处 | components/diary/* + DiaryPage |
| P1 | 社区/帖子详情/消息页宽度与内边距不符规范 | CommunityPage / PostDetailPage / MessagesPage |
| P1 | 测评流桌面过窄且与体检报告 Tab 宽度不一致 | AssessmentPage.vue |
| P1 | EmptyState/LoadingSpinner/MedicalDisclaimer 零接入，空状态 4 套实现 | 全站 |
| P1 | "白白百科"错误命名 | EncyclopediaNewPage.vue |
| P2 | 卡片内边距、Tab/按钮风格、标题层级、间距节奏、背景色三种写法 | 见上文逐项 |

## 八、最严重的 5 个不一致点

1. DiaryPage 桌面恒定 640px (scoped CSS 无断点) —— 用户投诉的直接根因 (DiaryPage.vue L394-399)。
2. diary 模块整体脱离设计系统: BEM scoped CSS + 25+ 处硬编码 #26A69A，与全站 Tailwind + primary-* 体系割裂。
3. 宽度档位混乱: 同为单列内容，社区 max-w-2xl、帖子详情 max-w-2xl px-3、消息页无约束、测评流 max-w-md/lg vs Report Tab max-w-6xl。
4. 通用组件零接入: EmptyState / LoadingSpinner / MedicalDisclaimer 定义了却 0 引用，空状态/加载态/免责声明各页自造。
5. Tab 与按钮风格 5 套并存 (药丸/分段/灰槽/文字按钮/自造 pill)，登录按钮 3 种实现。

## 九、验证建议
- 修复后在 1280px / 1440px / 1920px 桌面宽度 + 375px 移动端各巡检一遍上述页面。
- 用 grep "max-w-2xl|max-width: 6|#26A69A" 做回归检查。
- 参照 .agents/skills/vue-tsc-guard 与 deploy-verification skill 完成构建与上线验证。

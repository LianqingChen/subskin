# AI助手页面全面改造计划

> 创建时间：2026-05-04
> 状态：待执行
> 目标：改造 SubSkin 的 AI助手页面 —— 金斑蝶形象、智能对话、语音通话、心理疏导

---

## 一、目标总览

| 编号 | 目标 | 优先级 |
|------|------|--------|
| A | 智能化 AI 对话体验（多轮、流式、历史、上下文） | P0 |
| B | 金斑蝶吉祥物统一（去熊猫化） | P0 |
| C | UI/UX 全面重构 | P0 |
| D | 语音通话功能（类似豆包打电话） | P1 |
| E | 白癜风心理疏导专属模块 | P1 |

---

## 二、现状分析

### 2.1 当前文件结构

```
TrackerPage.vue (1230行，单文件组件)
├── View: home        → DigitalHuman(蝴蝶) + Chat输入框 + 统计卡片
├── View: assessment  → DigitalHuman(部位轮廓) + 上传 + 结果解读
└── View: report      → ReportUploader

DigitalHuman.vue (552行)
├── 图片: /cyber_panda.png  ← 【需改为蝴蝶】
├── SVG路径: 蝴蝶身体部位（翅膀、触角等）
├── 效果: 代码雨、wave扫描
└── 功能: 自由画线标注

已有基础设施:
├── useSpeechSynthesis.ts   → TTS 语音播报（Web Speech API）
├── useSpeechRecognition.ts → STT 语音识别（Web Speech API）
├── chatApi (SSE streaming) → /rag/ask-stream, 对话历史
└── 后端 RAG 服务已含心理相关关键词
```

### 2.2 关键问题

| 问题 | 影响 |
|------|------|
| TrackerPage.vue 1230行巨单文件 | 难以维护，AI助手和评估逻辑耦合 |
| 聊天只有单轮 Q&A、预设问题8条 | 缺乏多轮上下文、个性化和深度 |
| 无语音对话功能 | 缺失对标豆包的核心交互 |
| 无心理疏导模块 | 白癜风患者核心情感需求未满足 |
| DigitalHuman 图片名 `cyber_panda.png` | 与吉祥物金斑蝶不一致 |
| Chat 消息不持久化（页内 ref） | 刷新丢失、无历史回顾 |

---

## 三、改造方案

### 3.1 页面架构重构

**拆分 TrackerPage.vue：**

```
AI助手页面（新）                    VASI测评页面（保留）
├── ButterflyMascot.vue             ├── DigitalHuman.vue (蝴蝶轮廓)
├── ChatPanel.vue                   ├── 上传 + 评估流程
├── VoiceCallPanel.vue              └── 历史记录
├── CounselingModule.vue
└── QuickActions.vue
```

**路由调整：**
- `/` → AI助手页面（新 ChatAssistantPage.vue）
- `/assessment?view=assessment` → VASI测评页面（TrackerPage.vue 改为 AssessmentPage.vue）
- `/tracker` → redirect `/assessment?view=assessment`

### 3.2 金斑蝶形象统一

1. `cyber_panda.png` → `golden_butterfly.png` 或 `butterfly_mascot.png`
2. DigitalHuman.vue 中注释/变量名 `pandaCompressed` → `butterflyCompressed` 等
3. page-names.ts 中 `/tracker` 的页面名称保持 "小白手账" 不变
4. 确认 logo 和 PWA icon 是否需要同步更新

### 3.3 AI 对话重构（目标 A）

**新 ChatPanel.vue 设计：**

```
┌─────────────────────────────────┐
│  🦋 小金（金斑蝶AI助手）         │
│  💬 我能帮你了解白癜风知识、     │
│     缓解焦虑、陪伴你的康复之路   │
├─────────────────────────────────┤
│  [对话历史区域 — 滚动]           │
│  用户: 308激光效果怎么样？       │
│  小金: 308nm准分子激光...        │
│      ┌─ 知识卡片 ────────────┐   │
│      │ 📄 《光疗指南》        │   │
│      │ 来源: 小白百科         │   │
│      └──────────────────────┘   │
│  用户: 疼不疼？                  │
│  小金: 不用担心...               │
├─────────────────────────────────┤
│  [快捷操作栏]                    │
│  🎙语音 │ 📋心理自评 │ 📖百科   │
│  ┌──────────────────────────┐   │
│  │ 输入你想问的...     📤 🎤 │   │
│  └──────────────────────────┘   │
└─────────────────────────────────┘
```

**改进点：**
- 消息持久化：利用已有 `/rag/conversations` API
- 流式输出：已有 SSE stream，改进打字机效果渲染
- 来源引用卡片：显示知识来源（小白百科/论文）
- 快捷问题面板：分类整理（病情、治疗、心理、生活）
- 会话管理：新建对话、历史对话列表
- 输入工具栏：语音输入按钮、附件上传

### 3.4 语音通话功能（目标 D）

**主要难点：Web Speech API 的 SpeechRecognition 是语句级识别，不是实时流式（每次识别一句，有停顿）。要实现豆包式的"打电话"体验，需要：**

#### 方案 A：利用现有 Web Speech API（快速实现，体验一般）
- `useSpeechRecognition` + `useSpeechSynthesis` 组合
- 用户说一句 → STT 转文字 → 发给后端 RAG → 返回文本 → TTS 播报
- 限制：有停顿感，无法实时打断

#### 方案 B：WebSocket 实时语音流（理想方案，工程量大）
- 前端：MediaRecorder 采集音频 → WebSocket 发送
- 后端：接收音频流 → 实时 STT → LLM → TTS → 返回音频流
- 需要：ASR 服务（如火山引擎/阿里云）、TTS 服务
- 优势：流畅对话、可打断、接近豆包体验

**建议：先用方案 A 快速上线，方案 B 列为 Phase 2**

**VoiceCallPanel.vue 设计：**

```
┌─────────────────────────────────┐
│                                 │
│          🦋 金斑蝶动画           │
│         (翅膀轻轻扇动)           │
│                                 │
│       🟢 正在倾听...            │
│     "我想了解一下308激光"        │
│                                 │
│     ┌───────────────────┐       │
│     │   🔴 挂断电话      │       │
│     └───────────────────┘       │
│     ┌───────────────────┐       │
│     │   🔊 扬声器 │ ⏸ 静音  │   │
│     └───────────────────┘       │
└─────────────────────────────────┘
```

**流程：**
1. 用户点击「打电话」→ 进入全屏通话界面
2. 蝴蝶动画 + AI 主动问候「你好，我是小金，今天感觉怎么样？」
3. TTS 播报 → 用户说话 → STT 识别
4. 发送到心理疏导专用 prompt → 流式返回 → TTS 播报
5. 循环直到用户挂断，生成通话摘要

### 3.5 心理疏导模块（目标 E）

**设计理念：** 白癜风患者的心理需求远超单纯的医学知识问答。需要一个「温暖的、有同理心的」AI 陪伴。

**CounselingModule.vue 设计：**

```
┌─────────────────────────────────┐
│  💚 心理陪伴                      │
│  ─────────────────────────────── │
│  🧘 每日心情记录                  │
│  [😊 😀 😐 😢 😞]               │
│  ─────────────────────────────── │
│  📊 本周情绪趋势                  │
│  ▁▂▃▄▅▆▇ (sparkline)             │
│  ─────────────────────────────── │
│  🎯 心理疏导场景                  │
│  ┌──────────────────────────┐   │
│  │ 🌅 早晨自我肯定练习       │   │
│  │ "今天我很勇敢..."         │   │
│  └──────────────────────────┘   │
│  ┌──────────────────────────┐   │
│  │ 🧘 正念呼吸引导(3分钟)    │   │
│  │ 跟随蝴蝶翅膀的节奏呼吸... │   │
│  └──────────────────────────┘   │
│  ┌──────────────────────────┐   │
│  │ 📝 情绪日记              │   │
│  │ 写下今天的感受...         │   │
│  └──────────────────────────┘   │
│  ┌──────────────────────────┐   │
│  │ 💬 找人聊聊              │   │
│  │ 立即与AI小金对话           │   │
│  │ 或 → 跳转社区「心理支持」 │   │
│  └──────────────────────────┘   │
│  ─────────────────────────────── │
│  📚 心理科普文章                  │
│  · 白癜风患者的心理调适           │
│  · 如何面对他人的目光             │
│  · 父母如何支持患白斑的孩子       │
└─────────────────────────────────┘
```

**后端 Prompt 工程：**

心理疏导需要专用 system prompt：

```
你是「小金」，一只温柔的金斑蝶，也是白癜风患者的AI心理陪伴者。
你的角色定位：
- 温暖、耐心、不评判、不空喊口号
- 承认患者的痛苦是真实的，不轻描淡写
- 帮助患者发现自己的力量和资源
- 引导积极的自我对话和应对策略

心理疏导框架（整合 CBT + ACT + 正念）：
1. 共情：先认真倾听、表达理解
2. 正常化：让患者知道自己的感受是正常的
3. 认知重构：帮助看到不同的视角
4. 行动引导：提出小而可行的建议
5. 资源连接：推荐社区、百科文章、医生

特别注意：
- 如果患者表达自杀/自伤想法 → 提供危机热线并建议立即就医
- 区分心理陪伴和专业心理治疗 → 明确边界
- 鼓励寻求专业帮助
```

**心理疏导专属对话流（与普通问答分开）：**
- 入口1：心理疏导模块中点击「找人聊聊」
- 入口2：语音通话默认使用心理疏导 prompt
- 入口3：普通聊天中检测到情绪相关关键词自动切换

### 3.6 UI/UX 重构（目标 C）

**新 AI助手页面整体布局（移动端优先）：**

```
┌─────────────────────────────────┐
│  🦋 蝴蝶形象区 (30vh)            │
│  · 金斑蝶动画（微微浮动）        │
│  · 状态文字（"今天想聊什么？"）  │
│  · 语音通话按钮（悬浮）          │
├─────────────────────────────────┤
│  📑 Tab切换栏                     │
│  [智能问答] [心理陪伴] [语音]    │
├─────────────────────────────────┤
│  Tab内容区（scrollable）          │
│  (根据选中的Tab渲染不同内容)      │
└─────────────────────────────────┘
```

**视觉设计方向：**
- 主题色：蝴蝶金+温暖橙色（替代原来的纯 cyan）
- 蝴蝶动画：CSS 翅膀轻扇（`transform: scaleX` 周期变化）
- 卡片：温暖柔和的圆角卡片
- 语音按钮：大圆形脉冲动画

---

## 四、实施步骤

### Phase 1：基础重构（预计 3-4 小时）

| 步骤 | 文件 | 内容 |
|------|------|------|
| 1.1 | `ChatAssistantPage.vue` **新建** | 新 AI助手主页面框架：蝴蝶形象区 + Tab切换 + ChatPanel |
| 1.2 | `ChatPanel.vue` **新建** | 聊天面板：流式消息渲染、历史加载、来源卡片 |
| 1.3 | `ButterflyMascot.vue` **新建** | 金斑蝶组件（从 DigitalHuman 提取蝴蝶部分，去代码雨） |
| 1.4 | `router/index.ts` | 路由：`/` → ChatAssistantPage；新增 `/assessment` |
| 1.5 | `DigitalHuman.vue` | 重命名 `pandaCompressed` → `butterflyCompressed`；图片路径改蝴蝶 |
| 1.6 | `page-names.ts` | 更新路由映射 |
| 1.7 | TrackerPage.vue → `AssessmentPage.vue` | 提取评估逻辑到独立页面，移除 chat 相关代码 |

### Phase 2：AI 对话增强（预计 2-3 小时）

| 步骤 | 内容 |
|------|------|
| 2.1 | ChatPanel 消息持久化：用 `/rag/conversations` API 加载历史 |
| 2.2 | 流式打字机效果：逐 token 渲染 + 自动滚动 |
| 2.3 | 来源引用卡片：解析 SSE 的 `sources` 字段渲染 |
| 2.4 | 快捷问题分类：病情 / 治疗 / 心理 / 生活 |
| 2.5 | 会话管理：新建对话、历史列表、切换/删除 |

### Phase 3：语音通话（预计 3-5 小时）

| 步骤 | 内容 |
|------|------|
| 3.1 | `VoiceCallPanel.vue` **新建**：全屏通话 UI + 蝴蝶动画 |
| 3.2 | `useVoiceCall.ts` **新建**：组合 STT + TTS + SSE，实现一问一答循环 |
| 3.3 | 通话状态机：idle → listening → thinking → speaking → listening... |
| 3.4 | 按键打断：用户可打断 AI 正在说的话 |
| 3.5 | 通话摘要：挂断后显示通话要点 |

### Phase 4：心理疏导模块（预计 3-4 小时）

| 步骤 | 内容 |
|------|------|
| 4.1 | `CounselingModule.vue` **新建**：心情记录 + 情绪趋势 + 疏导场景卡片 |
| 4.2 | 后端心理疏导 prompt：`services/counseling.py` 专用 system prompt |
| 4.3 | 后端新增 API：`/counseling/chat` — 心理疏导专用对话 |
| 4.4 | 情绪日记：前端记录 + 后端存储 + 趋势统计 |
| 4.5 | 正念引导：蝴蝶呼吸动画（跟随翅膀扇动节奏） |
| 4.6 | 危机干预：检测自杀/自伤关键词 → 显示热线 |

### Phase 5：UI 打磨（预计 2-3 小时）

| 步骤 | 内容 |
|------|------|
| 5.1 | 蝴蝶 CSS 动画：翅膀轻扇 + 悬浮光点 |
| 5.2 | 语音按钮脉冲动画 |
| 5.3 | Tab 切换过渡动画 |
| 5.4 | 暗色模式适配 |
| 5.5 | iPad/Desktop 响应式优化 |
| 5.6 | PWA safe-area 适配 |

---

## 五、文件清单

### 新建文件
```
web/app/src/views/ChatAssistantPage.vue       # AI助手主页面
web/app/src/views/AssessmentPage.vue           # 从 TrackerPage 提取
web/app/src/components/assistant/ChatPanel.vue # 聊天面板
web/app/src/components/assistant/VoiceCallPanel.vue  # 语音通话
web/app/src/components/assistant/CounselingModule.vue # 心理疏导
web/app/src/components/assistant/ButterflyMascot.vue  # 金斑蝶形象
web/app/src/components/assistant/QuickActions.vue     # 快捷操作
web/app/src/composables/useVoiceCall.ts        # 语音通话状态机
web/backend/services/counseling.py             # 心理疏导后端服务
```

### 修改文件
```
web/app/src/router/index.ts                    # 路由调整
web/app/src/constants/page-names.ts            # 页面名称
web/app/src/views/TrackerPage.vue              # → 重命名为 AssessmentPage
web/app/src/components/tracker/DigitalHuman.vue # 去除 panda 引用
web/app/src/api/chat.ts                        # 新增心理疏导 API
web/backend/services/rag.py                     # 可能新增心理疏导 prompt
web/app/public/cyber_panda.png                  # → 蝴蝶图片
```

---

## 六、风险与考量

| 风险 | 缓解措施 |
|------|---------|
| TrackerPage 拆分可能引入回归 | 保留原页面作为 AssessmentPage，确保 VASI 测评流程不受影响 |
| Web Speech API 浏览器兼容性 | 检测 + 降级提示（Safari/iOS 支持较好） |
| 语音通话体验不够流畅 | 先用方案 A 快速验证，Phase 2 再考虑 WebSocket 实时流 |
| 心理疏导的伦理边界 | 明确免责声明，非医疗建议，检测危机信号引导求助 |
| 大量新代码的 QA | 每个 Phase 独立构建部署验证 |

---

## 七、验证标准

- [ ] AI助手独立页面：`/` 显示蝴蝶 + 聊天面板
- [ ] VASI测评独立页面：`/assessment?view=assessment` 功能完整
- [ ] 聊天消息刷新不丢失（持久化到后端）
- [ ] 流式输出有打字机效果
- [ ] 语音通话：点击拨打 → 对话 → 挂断，全流程可用
- [ ] 心理疏导：心情记录 → 情绪趋势 → 疏导对话
- [ ] 移动端 + iPad + Desktop 全部响应式正常
- [ ] 微信内置浏览器兼容
- [ ] PWA safe-area 正确处理

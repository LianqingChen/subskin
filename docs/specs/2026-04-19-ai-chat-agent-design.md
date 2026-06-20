# 小白助手 Agent 模式设计文档

> 日期: 2026-04-19
> 状态: 已确认，进入实施

## 核心原则

**AI 自动生成，用户确认执行。** AI 帮用户免去重复操作，但保留/删除/分享等行为必须用户明确确认。

## 用户交互流程

```
用户在AI对话上传图片（白斑照片）
  │
  ▼
后端并行处理：
  ├─ 1. VASI 自动评估（评分、部位、分期）
  ├─ 2. 体检报告 OCR 解读（如果是文档）
  └─ 3. RAG 文献检索 + LLM 生成回答
  │
  ▼
AI 回复包含：
  ├─ 文字回答（基于上传内容+文献）
  ├─ 📊 VASI 评分卡片（评分 · 部位 · 分期）
  │     [✓ 保存到小白追踪]  [✗ 不保存]
  ├─ 📋 体检报告解读卡片（关键指标摘要）
  │     [✓ 保存到体检报告]  [✗ 不保存]
  └─ 📓 白白日记已自动生成草稿
        [✓ 存档（仅自己可见）]  [✓ 存档并分享到社区]  [✗ 不保存]
```

## 隐私设计（红线）

| 数据级别 | 规则 | 实现方式 |
|---------|------|---------|
| 🔴 病情照片 | **默认不保存，不分享** | 上传图片仅用于当次分析，不写入任何表，除非用户点"保存到追踪" |
| 🟠 体检报告 | **仅自己可见** | 保存到追踪时 is_private=true，分享到社区时二次确认弹窗 |
| 🟡 日记内容 | **用户选择公开/私密** | 默认 is_private=true，分享到社区需明确切换 |
| 🟢 AI回答文字 | **可公开** | 不含用户隐私，可显示在社区分享中 |

**关键**：上传的图片/文档**先当临时文件处理**，只在用户确认保存后才写入对应模块的数据库。

## Agent 工具定义

```python
tools = {
    "analyze_vasi": {
        "trigger": "用户上传白斑图片",
        "action": "调用视觉API评估VASI评分",
        "output": "VASI评分卡片（不自动保存）",
        "confirm_required": True
    },
    "interpret_report": {
        "trigger": "用户上传PDF/文档",
        "action": "OCR提取+LLM解读关键指标",
        "output": "报告解读卡片（不自动保存）",
        "confirm_required": True
    },
    "generate_diary": {
        "trigger": "对话中产生了追踪数据或报告解读",
        "action": "LLM汇总对话+追踪+解读，生成日记草稿",
        "output": "日记草稿（不自动保存）",
        "confirm_required": True,
        "privacy_default": "private"
    },
    "share_to_community": {
        "trigger": "用户在日记卡片点'分享到社区'",
        "action": "创建公开Post（不含原图/报告文件）",
        "output": "社区帖子",
        "confirm_required": True,
        "double_confirm": True,
        "data_filter": "remove_L3_data"
    }
}
```

## 前端 UI 组件设计

### ChatInput 新增附件按钮

```
┌──────────────────────────────────────────┐
│ 📎  │ 输入你的问题...              │ ➤ │
└──────────────────────────────────────────┘
  │
  ▼ 点击📎弹出：
  ┌─────────────┐
  │ 📷 拍照     │  ← 调用手机摄像头
  │ 🖼️ 相册选图  │
  │ 📄 上传文件  │  ← PDF/Word/TXT/MD
  └─────────────┘
```

### ChatMessage 新增行动卡片

```
┌─────────────────────────────────────┐
│ 🤖 AI回答文字...                     │
│                                     │
│ ┌─ 📊 VASI 评估结果 ────────────┐   │
│ │ 评分：23分（中度）              │   │
│ │ 部位：躯干  分期：稳定期        │   │
│ │ 面积占比：约15%                │   │
│ │                                │   │
│ │ [✓ 保存到小白追踪]  [✗ 跳过]   │   │
│ └────────────────────────────────┘   │
│                                     │
│ ┌─ 📓 白白日记草稿 ─────────────┐   │
│ │ 2026-04-19 病情日记            │   │
│ │ 今日AI评估躯干VASI评分23分...  │   │
│ │                                │   │
│ │ [🔒 仅自己存档] [🌐 分享到社区]│   │
│ │              [✗ 不保存日记]    │   │
│ └────────────────────────────────┘   │
└─────────────────────────────────────┘
```

## 数据模型扩展

### Message 扩展（前端）

```typescript
interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: Source[]
  attachments?: ChatAttachment[]    // NEW: 用户上传的附件
  actionCards?: ActionCard[]         // NEW: AI生成的行动卡片
  // ... existing fields
}

interface ChatAttachment {
  id: string
  type: 'image' | 'document'
  url: string
  name: string
  size: number
  mimeType: string
  thumbnailUrl?: string              // 图片缩略图
}

type ActionCard =
  | VASICard
  | ReportCard
  | DiaryCard

interface VASICard {
  type: 'vasi'
  vasiScore: number
  bodySite: string
  classification: string
  stage: string
  areaPercentage: number
  imageUrl: string                   // 临时URL，确认保存前不写入DB
  saved: boolean                     // 用户是否已确认保存
}

interface ReportCard {
  type: 'report'
  title: string
  summary: string                    // LLM生成的解读摘要
  keyFindings: string[]              // 关键指标列表
  fileUrl: string                    // 临时URL
  saved: boolean
}

interface DiaryCard {
  type: 'diary'
  title: string
  content: string                    // LLM生成的日记内容(HTML)
  date: string
  privacy: 'private' | 'public'
  saved: boolean
}
```

### 后端 API 扩展

```python
# 新增：带附件的提问
POST /api/rag/ask-stream
Content-Type: multipart/form-data

# 请求参数
question: str                        # 用户问题
conversation_id: str | None
images: List[UploadFile]             # 图片文件
documents: List[UploadFile]          # 文档文件

# SSE 事件扩展
{ type: "thinking", stage: "analyzing_image", message: "正在分析白斑图片..." }
{ type: "action_card", card: { type: "vasi", vasiScore: 23, ... } }
{ type: "action_card", card: { type: "diary", title: "...", content: "..." } }
{ type: "token", content: "..." }
{ type: "done", sources: [...] }

# 新增：确认保存行动卡片
POST /api/rag/confirm-action
{
  "conversation_id": "conv_xxx",
  "card_type": "vasi",              # vasi | report | diary
  "card_data": { ... },             # 卡片完整数据
  "action": "save"                  # save | share | discard
}

# 新增：临时文件上传（不写入模块DB）
POST /api/rag/upload-temp
Content-Type: multipart/form-data
file: UploadFile
→ returns { temp_url: "/uploads/temp/xxx.jpg", temp_id: "tmp_xxx" }
```

## 实施分期

| 阶段 | 内容 | 周期 | 交付物 |
|------|------|------|--------|
| **Phase 1** | 附件上传 + VASI/报告解读卡片 | 2-3天 | 用户能上传图片/文档，AI回答中显示分析卡片 |
| **Phase 2** | 确认保存 → 写入追踪/报告 | 1-2天 | 点击卡片按钮，数据写入对应模块 |
| **Phase 3** | 自动生成日记 + 存档/分享 | 1-2天 | AI自动汇总生成日记，用户确认后保存/分享 |
| **Phase 4** | Agent 工具链优化 | 后续 | 多工具编排、上下文记忆、更智能的触发 |

## Phase 1 详细任务清单

### 前端
1. ChatInput.vue - 新增 📎 附件按钮 + 文件选择弹窗（拍照/相册/文档）
2. ChatMessage.vue - 新增 ActionCard 渲染（VASI卡片、报告卡片）
3. types/index.ts - 扩展 ChatAttachment、ActionCard 类型
4. api/chat.ts - 支持带附件的请求（multipart/form-data）
5. stores/chat.ts - 支持 attachments 和 actionCards 字段

### 后端
6. rag.py - 新增带附件的流式接口（接收 images/documents）
7. rag.py - 新增临时文件上传接口 /rag/upload-temp
8. services/rag.py - 图片分析逻辑（调用 VASI 评估 API）
9. services/rag.py - 文档解析逻辑（PDF/Word/TXT → 文本提取 + LLM 解读）
10. models/rag.py - 扩展请求/响应模型（附件、行动卡片）

### 复用现有模块
- VASI 评估: 复用 `web/backend/services/vasi.py` 的评估逻辑
- 文件上传: 复用 `web/backend/services/community.py` 的 upload_file 方法
- 体检报告: 复用 `web/backend/api/medical_report.py` 的文件处理逻辑

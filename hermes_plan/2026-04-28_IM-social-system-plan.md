# SubSkin 用户社交 & IM 即时通讯系统规划方案

> 规划日期：2026-04-28  
> 参考平台：微信、抖音、小红书、微博  
> 当前阶段：Phase 1 规划（设计先行，分阶段落地）

---

## 一、现状盘点

### 1.1 已有能力 ✅

| 模块 | 已有内容 | 状态 |
|------|---------|------|
| 用户系统 | 注册/登录（手机/邮箱/微信/支付宝OAuth）、JWT认证 | 完整 |
| 社交关系 | 关注/取关、拉黑/解除拉黑、举报用户、公开资料页 | 完整 |
| 社区内容 | 帖子(图文/视频/长文/日记)、评论、点赞、收藏夹、书签、标签 | 完整 |
| 文件上传 | 图片/音频/附件上传、临时文件管理 | 完整 |
| 内容风控 | LLM审核(12类风险)、自动处罚(警告/禁言/封号)、管理员审核台 | 完整 |
| 通知系统 | 站内通知 + 短信通知 | 完整 |
| 审计日志 | 用户操作可追溯 | 完整 |
| AI聊天 | RAG问答（SSE流式）、多轮对话历史 | 完整 |
| 前端ChatPage | Vue SPA，ChatSidebar/ChatMessage/ChatInput组件 | 已有框架 |
| 实时追踪 | UserEvent行为事件、UserInteractionLog交互日志 | 完整 |

### 1.2 缺失核心能力 ❌

- **用户间IM私聊**：目前只有AI问答聊天，无用户间1对1消息
- **好友系统**：有"关注"（单向），无"好友"（双向确认）
- **群聊**：无群组创建/管理/群聊能力
- **消息级风控**：现有风控覆盖帖子/评论/资料，未覆盖私信
- **WebSocket实时通信**：无实时消息推送
- **内容分享到私聊**：无法将帖子分享给指定用户

### 1.3 数据库冲突注意 ⚠️

已有 `Conversation` 和 `Message` 表用于 AI RAG 对话，IM 相关表需要新命名以避免冲突。建议前缀 `im_`。

---

## 二、整体架构设计

```
┌─────────────────────────────────────────────────────────┐
│                     Frontend (Vue SPA)                    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐ │
│  │MessagesPg│ │ ChatRoom │ │ContactsPg│ │GroupInfoPg │ │
│  │(消息列表) │ │ (聊天室)  │ │(通讯录)  │ │(群资料)    │ │
│  └──────────┘ └──────────┘ └──────────┘ └────────────┘ │
│        │           │           │            │            │
│        └───────────┴─────┬─────┴────────────┘            │
│                          │                               │
│              ┌───────────┴───────────┐                   │
│              │   WebSocket /ws/chat  │ (实时消息)        │
│              └───────────┬───────────┘                   │
└──────────────────────────┼───────────────────────────────┘
                           │
┌──────────────────────────┼───────────────────────────────┐
│                    Backend (FastAPI)                      │
│                          │                                │
│  ┌───────────────────────┼───────────────────────────┐   │
│  │              IM API Routers                        │   │
│  │  /api/im/friends    好友系统                       │   │
│  │  /api/im/conversations  对话管理                   │   │
│  │  /api/im/messages   消息收发                       │   │
│  │  /api/im/groups     群聊管理                       │   │
│  │  /api/im/share      内容分享                       │   │
│  └───────────────────────┼───────────────────────────┘   │
│                          │                                │
│  ┌───────────────────────┼───────────────────────────┐   │
│  │             Services Layer                         │   │
│  │  im_service       消息业务逻辑                     │   │
│  │  im_moderation    消息风控（扩展content_safety）    │   │
│  │  websocket_mgr    WebSocket连接管理                │   │
│  └───────────────────────┼───────────────────────────┘   │
│                          │                                │
│  ┌───────────────────────┼───────────────────────────┐   │
│  │           Database (SQLite → PostgreSQL)           │   │
│  │  im_conversations / im_messages / im_friends       │   │
│  │  im_group_members / im_message_moderations         │   │
│  └───────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────┘
```

---

## 三、数据模型设计

### 3.1 好友关系 — `im_friends`

```sql
-- 好友关系表（双向确认制）
im_friends:
  id            INTEGER PK
  user_id       INTEGER FK → users.id      -- 发起方
  friend_id     INTEGER FK → users.id      -- 接收方
  status        VARCHAR(20)                -- pending / accepted / declined
  requested_at  DATETIME                   -- 请求发起时间
  accepted_at   DATETIME                   -- 接受时间
  UNIQUE(user_id, friend_id)
```

**与"关注"的区别**：
- 关注 = 单向（类似微博/Twitter），不需要对方同意
- 好友 = 双向确认（类似微信），需要发送请求→对方同意
- 两者共存：可以关注一个人但不是好友，也可以同时是好友和互相关注

**好友添加路径**（参考微信）：
1. 通过用户名/ID搜索添加 → Phase 1
2. 从社区帖子点击头像→发送好友请求 → Phase 1  
3. 二维码扫码添加 → Phase 2
4. 手机通讯录匹配 → Phase 3

### 3.2 私聊会话 — `im_conversations`

```sql
im_conversations:
  id            INTEGER PK
  type          VARCHAR(10)               -- private / group
  name          VARCHAR(100)              -- 群名称（group时必填）
  avatar        VARCHAR(500)              -- 群头像URL
  owner_id      INTEGER FK → users.id    -- 群主（group时）
  announcement  TEXT                      -- 群公告
  created_at    DATETIME
  updated_at    DATETIME                  -- 最后消息时间（排序用）

im_conversation_members:
  id              INTEGER PK
  conversation_id INTEGER FK
  user_id         INTEGER FK
  role            VARCHAR(10) DEFAULT 'member'  -- owner/admin/member
  mute_until      DATETIME                      -- 个人免打扰截止
  nickname_in_group VARCHAR(50)                 -- 群内昵称
  joined_at       DATETIME
  UNIQUE(conversation_id, user_id)
```

**私聊特殊规则**（参考抖音）：
- 非好友之间可以发消息，但限制 **3条未回复消息** 后必须加好友才能继续
- 拉黑 → 无法发消息，已有的会话仍保留但不可见新消息
- 用户可设置 "仅好友可发私信"（隐私设置）

### 3.3 IM消息 — `im_messages`

```sql
im_messages:
  id                INTEGER PK
  conversation_id   INTEGER FK
  sender_id         INTEGER FK → users.id
  msg_type          VARCHAR(20)     -- text / image / video / file / voice / system / share_post
  content           TEXT            -- 文本内容（text类型时）
  metadata          JSON            -- 媒体元数据
  reply_to          INTEGER FK → im_messages.id  -- 引用回复
  status            VARCHAR(20)     -- sent / delivered / read
  recall_at         DATETIME        -- 撤回时间（2分钟内可撤回）
  created_at        DATETIME
  INDEX(conversation_id, created_at)

-- metadata JSON 结构示例:
{
  "image": {"url": "...", "width": 800, "height": 600, "thumbnail_url": "..."},
  "video": {"url": "...", "duration": 30, "thumbnail_url": "...", "size": 2048000},
  "file":  {"url": "...", "name": "报告.pdf", "size": 512000, "mime_type": "application/pdf"},
  "voice": {"url": "...", "duration": 15},
  "share_post": {"post_id": 123, "post_title": "...", "post_thumbnail": "..."}
}
```

### 3.4 消息已读追踪 — `im_message_reads`

```sql
im_message_reads:
  id            INTEGER PK
  message_id    INTEGER FK
  user_id       INTEGER FK
  read_at       DATETIME
  UNIQUE(message_id, user_id)
```

### 3.5 消息风控记录 — `im_message_moderations`

```sql
-- 扩展 ContentModeration，新增 content_type='im_message'
-- 或独立表：
im_message_moderations:
  id              INTEGER PK
  message_id      INTEGER FK
  sender_id       INTEGER FK
  content_snapshot TEXT
  risk_level      VARCHAR(20)
  risk_categories JSON
  auto_action     VARCHAR(20)      -- passed / flagged / blocked
  ai_reason       TEXT
  ai_confidence   FLOAT
  status          VARCHAR(20) DEFAULT 'pending'
  reviewed_by     INTEGER FK
  created_at      DATETIME
```

---

## 四、API 设计

### 4.1 好友系统 (`/api/im/friends`)

| 方法 | 路径 | 说明 | 参考 |
|------|------|------|------|
| POST | `/friends/request` | 发送好友请求 {user_id, message} | 微信 |
| GET | `/friends/requests` | 待处理请求列表(收到+发出) | 微信 |
| POST | `/friends/requests/{id}/accept` | 接受好友请求 | 微信 |
| POST | `/friends/requests/{id}/decline` | 拒绝好友请求 | 微信 |
| DELETE | `/friends/{user_id}` | 删除好友 | 微信 |
| GET | `/friends` | 好友列表（字母排序） | 微信 |
| GET | `/friends/search?q=xxx` | 搜索好友 | 微信 |

### 4.2 会话管理 (`/api/im/conversations`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/conversations` | 会话列表（按最近消息排序） |
| POST | `/conversations/private` | 创建/获取私聊会话 {user_id} |
| GET | `/conversations/{id}` | 会话详情 |
| POST | `/conversations/{id}/mute` | 免打扰设置 |
| POST | `/conversations/{id}/pin` | 置顶会话 |
| DELETE | `/conversations/{id}` | 删除/退出会话 |

### 4.3 消息收发 (`/api/im/messages`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/conversations/{id}/messages` | 消息历史（游标分页） |
| POST | `/conversations/{id}/messages` | 发送消息（文本/媒体） |
| POST | `/messages/{id}/recall` | 撤回消息（2分钟内） |
| DELETE | `/messages/{id}` | 删除消息（仅自己可见） |
| POST | `/messages/{id}/read` | 标记已读 |
| POST | `/conversations/{id}/read-all` | 全部标记已读 |

### 4.4 群聊管理 (`/api/im/groups`)

| 方法 | 路径 | 说明 | 参考 |
|------|------|------|------|
| POST | `/groups` | 创建群聊 {name, member_ids[]} | 微信 |
| PUT | `/groups/{id}` | 修改群资料 {name, avatar, announcement} | 微信 |
| POST | `/groups/{id}/members` | 邀请成员 {user_ids[]} | 微信 |
| DELETE | `/groups/{id}/members/{user_id}` | 移除成员 | 微信 |
| POST | `/groups/{id}/transfer` | 转让群主 {new_owner_id} | 微信 |
| POST | `/groups/{id}/leave` | 退出群聊 | 微信 |
| POST | `/groups/{id}/dismiss` | 解散群聊（群主） | 微信 |
| GET | `/groups/{id}/members` | 群成员列表 | 微信 |

### 4.5 内容分享 (`/api/im/share`)

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/share/post` | 分享帖子到会话 {conversation_id, post_id} |

---

## 五、WebSocket 实时通信

### 5.1 连接端点

```
wss://subskin.cn/ws/chat?token={jwt_token}
```

### 5.2 事件协议 (JSON)

```json
// 客户端 → 服务端
{"type": "ping"}
{"type": "typing", "conversation_id": 42, "is_typing": true}
{"type": "read", "conversation_id": 42, "message_ids": [1,2,3]}

// 服务端 → 客户端
{"type": "message.new", "data": {...完整消息对象...}}
{"type": "message.recall", "conversation_id": 42, "message_id": 5}
{"type": "message.read", "conversation_id": 42, "reader_id": 7, "message_ids": [1,2,3]}
{"type": "typing", "conversation_id": 42, "user_id": 7, "is_typing": true}
{"type": "friend.request", "data": {"user_id": 7, "username": "..."}}
{"type": "conversation.new", "data": {...会话对象...}}
{"type": "unread_update", "data": {"total_unread": 5}}
```

### 5.3 WebSocket连接管理

```python
# websocket_mgr.py
class ConnectionManager:
    active_connections: dict[int, WebSocket]  # user_id → WebSocket
    
    async def connect(user_id, websocket)
    async def disconnect(user_id)
    async def send_to_user(user_id, event)
    async def send_to_conversation(conversation_id, event, exclude_user_id=None)
    async def broadcast_unread_count(user_id)
```

---

## 六、风控体系设计

### 6.1 消息发送风控（实时拦截层）

```
用户发消息
    │
    ▼
┌─────────────────┐
│ 1. 基础校验      │ ← 账号状态（封禁/禁言）、好友限制、拉黑检查
├─────────────────┤
│ 2. 频率限制      │ ← Redis令牌桶：30条/分钟，新用户5条/分钟
├─────────────────┤
│ 3. 敏感词过滤    │ ← AC自动机 + 敏感词库（动态更新）
├─────────────────┤
│ 4. LLM语义审核   │ ← LLM实时判定（异步？可配置同步/异步）
├─────────────────┤
│ 5. 图片/视频审核  │ ← 火山方舟视觉API（NSFW检测）
├─────────────────┤
│ 6. 链接检测      │ ← 恶意URL库匹配
├─────────────────┤
│ 7. 反欺诈模型    │ ← 行为模式：新号群发、相同内容多发、夜间异常活跃
└─────────────────┘
    │
    ▼
通过 → 发送成功   拦截 → 消息不送达 + 记录风控日志 + 触发处罚
```

### 6.2 风控处罚阶梯（扩展已有系统）

| 违规次数 | 处罚 | 参考来源 |
|---------|------|---------|
| 首次低危 | 警告 + 消息标注 | 抖音/小红书 |
| 累计2次中危 | 禁言3天 | 微信 |
| 累计3次中危 | 禁言7天 | 已有系统 |
| 首次高危 | 禁言7天 + 限制发私信 | 抖音 |
| 累计2次高危 | 禁言30天 | 已有系统 |
| 首次严重 | 永久封号 + 手机号拉黑 | 所有平台 |

### 6.3 敏感词库分层

```
Layer 1: 静态词库（本地部署）
  - 政治敏感词（2000+）
  - 色情词汇（5000+）
  - 暴恐词汇（1000+）
  - 非法广告（2000+）
  - 变体/拼音/拆字（正则规则）

Layer 2: LLM语义审核（已实现，扩展至IM）
  - 现有 content_safety.py 的 check_content_safety()
  - 新增 IM 专用 prompt（更侧重私信场景）
  - 风险类别同现有：涉政/暴恐/色情/赌博/诈骗/毒品/枪支/自残教唆/辱骂歧视/人身攻击/引流广告/违反公序良俗

Layer 3: 图片审核
  - 火山方舟视觉模型（NSFW、OCR提取图片中文字再过敏感词）
  - 皮肤图像白名单：白癜风患处照片允许，但标记为医学内容，非违规

Layer 4: 行为风控
  - 同一内容发送超过5个不同会话 → 标记垃圾消息
  - 新注册24小时内发私信超过10条 → 限制
  - 深夜(2:00-6:00)异常高频 → 人工审核
  - IP/设备指纹关联的批量注册 → 批量标记
```

### 6.4 行业风控规则参考

| 规则 | 来源平台 | 适用性 |
|------|---------|--------|
| 陌生人私信仅3条→需加好友 | 抖音 | ✅ SubSkin适用 |
| 消息撤回2分钟窗口 | 微信/抖音 | ✅ 标准功能 |
| 举报后先隐藏再审核 | 小红书/微博 | ✅ 已有类似机制 |
| 敏感词变体检测（拼音/拆字/谐音） | 微博 | ✅ 必须实现 |
| 新用户行为限制 | 全平台通用 | ✅ 防批量注册 |
| 图片OCR提取文字审核 | 微信/抖音 | ✅ 火山方舟视觉 |
| 链接白名单（仅允许信任域名） | 全平台通用 | ✅ SubSkin需配置 |
| 举报处理SLA：2小时内响应 | 小红书/抖音 | SubSkin可参考 |

### 6.5 特殊场景：白癜风患处照片

SubSkin 作为白癜风社区，用户可能互发患处照片交流病情，这不应被误判为色情内容。  
**处理策略**：
- LLM prompt 中加入医学场景豁免规则
- 火山方舟视觉API结果需结合上下文（会话历史、用户角色）综合判断
- 建立"医学影像白名单"二次校验机制

---

## 七、前端规划

### 7.1 页面结构

```
BottomNav（底部导航）
├── 首页
├── AI问答
├── 发现（社区）
├── 消息  ← 新增（红点未读数字）
└── 我的

消息模块子页面：
┌──────────────────────────────┐
│  MessagesPage.vue            │  消息列表（类似微信聊天列表）
│  ├── 搜索框                   │
│  ├── 会话列表（最新消息预览）   │
│  │   ├── 私聊会话              │
│  │   └── 群聊会话              │
│  └── 顶部Tab: 消息 / 通讯录    │
├──────────────────────────────┤
│  ContactsPage.vue            │  通讯录
│  ├── 好友请求入口（红点）      │
│  ├── 好友列表（字母索引）      │
│  └── 添加好友入口              │
├──────────────────────────────┤
│  ChatRoomPage.vue            │  聊天室（私聊/群聊共用）
│  ├── 顶部栏（对方信息/群名）   │
│  ├── 消息列表（虚拟滚动）      │
│  ├── 消息气泡（文本/图片/视频/文件/帖子分享卡片）│
│  └── 输入区域（文字/表情/图片/文件/语音）│
├──────────────────────────────┤
│  GroupInfoPage.vue           │  群资料页
│  ├── 群头像/名称/公告         │
│  ├── 群成员列表               │
│  └── 群设置（免打扰/退出/解散）│
└──────────────────────────────┘
```

### 7.2 消息类型组件

| 类型 | 组件 | 说明 |
|------|------|------|
| 文本 | `TextBubble` | 普通文字 + emoji |
| 图片 | `ImageBubble` | 点击放大，支持多图 |
| 视频 | `VideoBubble` | 缩略图 + 播放 |
| 文件 | `FileBubble` | 文件图标 + 名称 + 大小 |
| 语音 | `VoiceBubble` | 波形动画 + 时长 |
| 帖子分享 | `PostShareCard` | 带帖子预览的卡片 |
| 系统消息 | `SystemMessage` | "XXX加入了群聊"等 |

### 7.3 技术选型

- 虚拟滚动：消息列表使用 `vue-virtual-scroller` 处理长列表
- 图片预览：`v-viewer` 或自建
- 语音录制：`MediaRecorder API`
- 文件上传：复用现有 `chatApi.uploadTemp()`
- 状态管理：`Pinia` store `useImStore`

---

## 八、分阶段实施计划

### Phase 1：核心私信（MVP，2-3周）

**目标**：两个用户可以1对1发文字消息

- [ ] 数据库：`im_conversations`, `im_conversation_members`, `im_messages`, `im_message_reads`, `im_friends`
- [ ] 后端：`/api/im/*` REST API 全部实现
- [ ] 后端：WebSocket `/ws/chat` 基础连接 + 消息实时推送
- [ ] 后端：消息风控集成（敏感词 + LLM审核）
- [ ] 前端：`MessagesPage` + `ChatRoomPage` 基础版（仅文本）
- [ ] 前端：WebSocket 客户端 + 实时消息接收

### Phase 2：好友系统 + 多媒体（2-3周）

**目标**：加好友、发图片/视频/文件

- [ ] 好友请求/接受/拒绝完整流程
- [ ] 通讯录页面 + 搜索添加好友
- [ ] 图片消息（拍照/相册）
- [ ] 视频消息（录制/上传）
- [ ] 文件消息（PDF、文档等）
- [ ] 帖子分享到私聊
- [ ] 消息撤回（2分钟窗口）
- [ ] 阅读状态（已读/未读）

### Phase 3：群聊 + 增强体验（2-3周）

**目标**：群聊、表情、搜索

- [ ] 创建群聊 + 邀请成员
- [ ] 群管理（群主/管理员/移除/转让）
- [ ] 群聊 @提及
- [ ] 语音消息录制发送
- [ ] 消息搜索（关键词、日期范围）
- [ ] 会话置顶/免打扰
- [ ] 图片审核（火山方舟视觉API）

### Phase 4：运营工具 + 深度风控（2周）

- [ ] 管理员 IM 审核台
- [ ] 批量消息举报处理
- [ ] 行为风控模型（反欺诈）
- [ ] 数据统计看板（消息量/活跃度/违规率）
- [ ] 图片OCR提取文字审核

---

## 九、关键技术决策

### 9.1 消息存储策略

| 方案 | 优点 | 缺点 | 结论 |
|------|------|------|------|
| SQLite（现状） | 无额外依赖 | 并发写性能差，不适合IM高频写入 | Phase 1可用，Phase 2迁移 |
| PostgreSQL | 高性能、成熟 | 需部署维护 | **推荐Phase 2采用** |
| MongoDB | 文档型天然适合消息 | 引入新技术栈 | 不推荐 |

### 9.2 实时通信方案

| 方案 | 适用场景 | 决策 |
|------|---------|------|
| FastAPI WebSocket | 原生支持，无额外依赖 | **Phase 1采用** |
| Socket.IO | 自动降级（WS→长轮询） | Phase 2考虑 |
| Redis Pub/Sub + WS | 多进程WebSocket广播 | Phase 3（水平扩展时） |

### 9.3 敏感词过滤引擎

| 方案 | 说明 | 决策 |
|------|------|------|
| AC自动机 | Python `pyahocorasick`，高效多模式匹配 | **静态词库过滤** |
| LLM语义 | 复用现有 `content_safety.py` | **语义理解兜底** |
| 火山方舟视觉API | 图片NSFW + OCR | **图片审核** |

### 9.4 消息推送（离线消息）

当用户不在线时：
1. 消息存入数据库
2. 如果用户有 `expo_push_token`（未来），发推送通知
3. 如果用户绑定了手机，重要消息（如好友请求）发短信通知
4. 用户重新上线后 WebSocket 连接，拉取未读消息

---

## 十、风险与注意事项

1. **SQLite并发瓶颈**：IM场景写入频繁，SQLite的单一写入锁可能成为性能瓶颈。Phase 2需评估迁移PostgreSQL。
2. **敏感词库维护**：需要持续更新，建议接入第三方词库服务或建立社区报告机制。
3. **隐私合规**：私信内容存储需符合《个人信息保护法》，需要用户协议明确告知。
4. **图片审核成本**：火山方舟视觉API按调用计费，需合理控制审核频率（低危场景可抽样）。
5. **医患沟通风险**：若未来引入医生认证，医生与患者的私信可能涉及"在线问诊"合规问题，需提前规划免责声明。
6. **PWA限制**：WebSocket在PWA后台运行时可能断开，需做好重连和消息同步机制。
7. **与现有Chat系统隔离**：现有ChatPage是AI问答，新增IM系统需明确区分（不同路由/不同store/不同API前缀），避免混淆。

---

## 十一、参考平台核心设计对比

| 维度 | 微信 | 抖音 | 小红书 | 微博 | SubSkin建议 |
|------|------|------|--------|------|------------|
| 好友机制 | 双向确认 | 互关即好友 | 关注+私信 | 单向关注 | **微信式双向确认** |
| 陌生人私信 | 需好友 | 限3条 | 可私信 | 可私信 | **抖音式3条限制** |
| 消息撤回 | 2分钟 | 可撤回 | 可撤回 | 不可撤回 | **2分钟窗口** |
| 已读回执 | 可选 | 默认有 | 默认有 | 无 | **默认开启，可关闭** |
| 群聊上限 | 500 | 100 | 100 | 无明确 | **初期50，后续扩展** |
| 添加方式 | ID/手机/二维码 | ID/推荐 | ID/推荐 | ID/搜索 | **Phase1用户名搜索** |
| 图片审核 | 实时+事后 | 实时 | 实时 | 事后 | **实时LLM+视觉API** |
| 内容分享 | 转发到聊天 | 分享到私信 | 分享到私信 | 转发 | **帖子卡片分享** |

---

## 十二、文件清单（预估）

### 新建文件

```
后端:
web/backend/api/im_friends.py          # 好友系统API
web/backend/api/im_conversations.py    # 会话管理API
web/backend/api/im_messages.py         # 消息收发API
web/backend/api/im_groups.py           # 群聊管理API
web/backend/api/im_share.py            # 内容分享API
web/backend/services/im_service.py     # IM业务逻辑
web/backend/services/websocket_mgr.py  # WebSocket连接管理
web/backend/services/im_moderation.py  # 消息风控（扩展content_safety）
web/backend/models/im_models.py        # IM Pydantic模型
web/backend/ws/chat.py                 # WebSocket端点

前端:
web/app/src/views/MessagesPage.vue     # 消息列表页
web/app/src/views/ChatRoomPage.vue     # 聊天室页
web/app/src/views/ContactsPage.vue     # 通讯录页
web/app/src/views/GroupInfoPage.vue    # 群资料页
web/app/src/stores/im.ts               # IM状态管理
web/app/src/api/im.ts                  # IM API封装
web/app/src/composables/useWebSocket.ts # WebSocket composable
web/app/src/components/im/TextBubble.vue
web/app/src/components/im/ImageBubble.vue
web/app/src/components/im/VideoBubble.vue
web/app/src/components/im/FileBubble.vue
web/app/src/components/im/VoiceBubble.vue
web/app/src/components/im/PostShareCard.vue
web/app/src/components/im/SystemMessage.vue
web/app/src/components/im/ConversationItem.vue

数据库迁移:
web/backend/database/migration_add_im_tables.py
```

### 修改文件

```
web/backend/database/models.py         # 新增IM ORM模型
web/backend/app/main.py                # 注册新路由 + WebSocket
web/backend/services/content_safety.py # 扩展IM消息审核
web/app/src/components/layout/BottomNav.vue  # 新增"消息"Tab
```

---

> **总结**：本方案在 SubSkin 现有基础上，以微信/抖音/小红书为参照，设计了一套完整的用户社交+IM系统。核心思路是"先私聊后群聊，先文本后多媒体，先人工审核后AI风控"，分Phase逐步落地，确保每个阶段都有可交付价值。

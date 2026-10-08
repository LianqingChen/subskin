# SubSkin 网站功能优化规划 — 对照整体规划的差距分析与实施方案

> 创建日期：2026-07-30
> 基于：`2026-07-30-subskin-ai-community-master-plan.md`
> 目标：梳理当前网站功能现状，明确新增/完善/修订/删除项，制定可落地的优化方案

---

## 一、当前功能全景图

### 前端页面（24个视图）

| 页面 | 路由 | 功能 | 状态 |
|------|------|------|------|
| ChatAssistantPage | `/` | AI问答（知识+心理陪伴双模式） | ✅ 可用 |
| AssessmentPage | `/assessment` | VASI白斑测评（3步流程） | ✅ 可用 |
| ReportPage | `/report` | 体检报告上传+AI解读 | ✅ 可用 |
| CommunityPage | `/community` | 白友圈（瀑布流+日记日历+同城） | ✅ 可用 |
| CommunityEditorPage | `/community/new` | 发帖（文本/图片/视频/长文） | ✅ 可用 |
| PostDetailPage | `/community/:id` | 帖子详情+评论 | ✅ 可用 |
| ProfilePage | `/profile` | 个人中心 | ⚠️ 需优化 |
| UserProfilePage | `/user/:userId` | 用户主页 | ✅ 可用 |
| EncyclopediaNewPage | `/encyclopedia` | 小白百科 | ✅ 可用 |
| MessagesPage | `/messages` | IM消息列表 | ✅ 可用 |
| ChatRoomPage | `/chat/:id` | IM聊天室 | ✅ 可用 |
| ContactsPage | `/contacts` | 联系人/好友 | ✅ 可用 |
| GroupInfoPage | `/group/:id` | 群信息 | ✅ 可用 |
| VasiDetailPage | `/assessment/vasi/:id` | VASI评估详情 | ✅ 可用 |
| VasiComparePage | `/assessment/compare` | VASI前后对比 | ✅ 可用 |
| ReportDetailPage | `/tracker/report/:id` | 报告详情 | ✅ 可用 |
| ReportComparePage | `/report/compare` | 报告对比 | ✅ 可用 |
| PhotoGuidePage | `/photo-guide` | 拍照指南 | ✅ 可用 |
| VoiceCallPage | `/voice-call` | 语音通话AI | ⚠️ 评估中 |
| DraftsPage | `/community/drafts` | 草稿箱 | ✅ 可用 |
| CollectionSharePage | `/collection/:slug` | 收藏夹分享 | ✅ 可用 |
| DashboardPage | `/dashboard` | 管理后台 | ✅ 可用 |
| PrivacyPolicyPage | `/privacy` | 隐私政策 | ✅ 可用 |
| TermsOfServicePage | `/terms` | 服务条款 | ✅ 可用 |

### 底部导航（5个Tab）

```
问答(/) | 测评(/assessment) | 报告(/report) | 白友圈(/community) | 我的(/profile)
```

### 后端API模块（30+路由）

user, content, comment, encyclopedia, events, rag, vasi, oauth, community, social, medical_report, audit, patient_profile, wechat, moderation, im_conversations, im_messages, im_friends, im_share, im_groups, im_admin, im_contacts, notifications, llm_config_admin, admin_general, content_generation_admin, image_label, medication, doctor, analytics, consent, files

### 数据模型（35+表）

User, PatientProfile, UserEvent, Post, PostImage, PostLike, PostComment, PostTag, PostAudio, PostAttachment, PostVersion, Collection, CollectionItem, Bookmark, UserInteractionLog, UserFollow, CommunityCategory, Tag, VASIAssessment, MedicalReport, MedicalReportFile, MedicationReminder, PushSubscription, ImFriendRequest, ImConversation, ImConversationMember, ImMessage, ImMessageRead, EncyclopediaArticle, EncyclopediaRevision, EncyclopediaComment, EncyclopediaVote, UserNotification, AdminGeneratedPost, ImageLabel

---

## 二、对照规划的差距分析

### 🔴 完全缺失（需新增）

| # | 功能 | 规划对应 | 重要性 | 说明 |
|---|------|---------|--------|------|
| 1 | **AI病情日记（对话式）** | Sprint 1 | P0 | 当前只有Post.diary_type简单标记，无独立日记模型、无AI结构化提取、无对话式界面 |
| 2 | **AI日记结构化提取** | Sprint 1 | P0 | 从自然语言提取：饮食/心情/用药/睡眠/压力/患处变化 |
| 3 | **AI周报生成** | Sprint 2 | P0 | 汇总日记+VASI数据，AI生成病情周报 |
| 4 | **诱因模式分析** | Sprint 2 | P1 | 分析日记数据发现潜在诱因关联 |
| 5 | **治疗时间线** | Sprint 3 | P0 | 个人治疗事件可视化时间轴 |
| 6 | **治疗事件自动提取** | Sprint 3 | P1 | 从日记/帖子中AI提取用药/光疗/手术/复诊事件 |
| 7 | **结构化治疗分享模板** | Sprint 3 | P1 | 发帖时引导填写方案/周期/效果/费用 |
| 8 | **相似病友推荐** | Sprint 3 | P2 | 基于病型+部位+方案+城市的匹配 |
| 9 | **群体疗效洞察** | Sprint 4 | P2 | 匿名聚合统计：同方案有效率 |
| 10 | **分享海报生成** | Sprint 4 | P1 | 一键生成"治疗100天对比"图片 |
| 11 | **PWA Push提醒** | Sprint 2 | P2 | 每日提醒记录日记（PushSubscription模型已有，前端未接入） |

### 🟡 已有但需完善

| # | 功能 | 当前状态 | 需完善内容 |
|---|------|---------|-----------|
| 1 | **AI问答个性化** | RAG问答无用户上下文 | 接入用户治疗档案，回答时引用"根据你的记录..." |
| 2 | **社区经验聚合** | 问答只引用文献 | 问答时聚合社区帖子经验（"有N位白友分享过..."） |
| 3 | **日记日历** | DiaryCalendar只显示帖子 | 需关联结构化日记数据，显示每日摘要/心情/用药 |
| 4 | **VASI→日记联动** | 测评后可手动生成草稿 | 应自动关联到日记时间线，无需手动操作 |
| 5 | **视频发帖** | VideoPostEditor存在 | 需优化：上传进度、封面选择、播放体验、压缩 |
| 6 | **用药提醒** | MedicationReminder模型+API已有 | 前端无入口！需在个人中心/日记中接入 |
| 7 | **患者档案** | PatientProfile有基础字段 | 需扩展：当前治疗方案、用药列表、光疗频率、病程阶段 |
| 8 | **百科SEO** | 有Schema.org标记 | 需SSR/预渲染，当前SPA对搜索引擎不友好 |
| 9 | **微信分享** | useWechatShare已有 | 需增加：周报/对比海报的分享卡片 |
| 10 | **通知系统** | 基础通知已有 | 需增加：日记提醒、周报推送、用药提醒 |
| 11 | **IM消息入口** | MessagesPage存在 | 底部导航无入口，需从"我的"或顶部进入 |
| 12 | **社区发帖引导** | 自由发帖 | 需增加"治疗分享"结构化模板引导 |

### 🟢 已有且良好（保持）

| 功能 | 说明 |
|------|------|
| VASI测评流程 | 3步流程清晰，AI识别+Mask编辑+结果解读 |
| AI问答双模式 | 知识模式+心理陪伴模式切换 |
| 社区瀑布流 | 推荐/关注/同城三Tab + 标签筛选 |
| 百科协作 | 文章+修订+评论+投票 |
| IM系统 | 私聊+群聊+好友+WebSocket |
| 管理后台 | 增长分析+内容审核+图片打标 |
| PWA | 可安装+自动更新 |

### 🔵 建议修订/删除

| # | 项目 | 当前状态 | 建议 | 理由 |
|---|------|---------|------|------|
| 1 | **VoiceCallPage** | 语音通话AI（362行） | ⚠️ 降级为辅助入口 | 使用率极低，占用路由，可改为问答页内的麦克风按钮 |
| 2 | **AssessmentWizard.vue** | 旧版5步向导 | 🗑️ 删除 | 已被AssessmentPage(3步)替代，代码冗余 |
| 3 | **AssessmentSection.vue** | 旧版评估组件 | 🗑️ 删除 | 已被新的Step组件替代 |
| 4 | **chat/目录组件** | ChatInput,ChatMessage等6个 | ⚠️ 评估合并 | 与assistant/目录功能重叠，可能是旧版残留 |
| 5 | **ProfilePage模糊卡片** | 4个blur-sm预览卡片 | 🗑️ 删除 | 无实际功能，占空间，改为真实功能入口 |
| 6 | **BottomNav"报告"Tab** | 独立Tab | ⚠️ 评估合并 | 报告使用频率低于测评，可合并到测评页或"我的" |
| 7 | **ButterflyMascot** | 蝴蝶吉祥物组件 | ⚠️ 评估 | 仅VoiceCall使用，若删除VoiceCall则一并清理 |
| 8 | **BreathingExercise** | 呼吸练习组件 | ✅ 保留 | 心理陪伴有价值，但需提升入口可见性 |

---

## 三、导航架构优化方案

### 当前导航问题

1. 底部5个Tab中"报告"使用频率低，占用黄金位置
2. "消息"无底部入口，用户找不到IM
3. "百科"无底部入口，需从其他页面跳转
4. "日记"（规划核心功能）无独立入口

### 建议新导航（对照规划调整）

```
方案A（推荐）：保持5Tab，调整内容
─────────────────────────────────────
问答(/) | 日记(/diary) | 测评(/assessment) | 白友圈(/community) | 我的(/profile)

- "报告"合并到"测评"页内（作为子Tab）
- "日记"成为核心Tab（规划第一优先级）
- "消息"从顶部Header进入（保持现状）
- "百科"从问答页/白友圈进入

方案B：6Tab（如果日记和报告都重要）
─────────────────────────────────────
问答(/) | 日记(/diary) | 测评(/assessment) | 报告(/report) | 白友圈(/community) | 我的(/profile)
```

---

## 四、分阶段实施方案

### Phase 1（第1-2周）：AI病情日记核心 + 导航调整

#### 1.1 后端：日记数据模型（新增）

```python
# web/backend/database/models.py 新增

class DiaryEntry(Base):
    """AI病情日记"""
    __tablename__ = "diary_entries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    profile_id = Column(Integer, ForeignKey("patient_profiles.id"), nullable=True)

    # 原始输入
    raw_text = Column(Text, nullable=False)  # 用户原始输入
    input_type = Column(String(20), default="text")  # text/voice/quick

    # AI结构化提取结果
    mood = Column(String(20), nullable=True)  # 心情: good/neutral/bad/anxious/hopeful
    sleep_quality = Column(String(20), nullable=True)  # good/fair/poor
    diet_notes = Column(Text, nullable=True)  # 饮食记录
    medication_taken = Column(Text, nullable=True)  # 用药记录 JSON
    stress_level = Column(Integer, nullable=True)  # 压力 1-5
    skin_condition = Column(String(50), nullable=True)  # 患处变化: stable/improving/spreading/new_spots
    treatment_events = Column(Text, nullable=True)  # 治疗事件 JSON
    ai_summary = Column(Text, nullable=True)  # AI生成的日记摘要
    ai_extracted_json = Column(Text, nullable=True)  # 完整AI提取结果

    # 关联
    vasi_assessment_id = Column(Integer, ForeignKey("vasi_assessments.id"), nullable=True)
    is_public = Column(Boolean, default=False)  # 是否公开到社区
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=True)  # 关联的社区帖子

    entry_date = Column(Date, nullable=False, index=True)  # 日记日期
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)
```

#### 1.2 后端：AI日记解析API（新增）

```
POST /api/diary/entries          — 创建日记（触发AI提取）
GET  /api/diary/entries          — 日记列表（按日期）
GET  /api/diary/entries/:id      — 日记详情
PUT  /api/diary/entries/:id      — 更新日记
DELETE /api/diary/entries/:id    — 删除日记
GET  /api/diary/calendar         — 日历视图数据
GET  /api/diary/summary/weekly   — AI周报
GET  /api/diary/insights         — 诱因洞察
POST /api/diary/quick            — 快捷记录（心情/用药一键记录）
```

#### 1.3 前端：日记页面（新增）

- `DiaryPage.vue` — 日记主页（对话式输入 + 日历 + 最近记录）
- `DiaryChatInput.vue` — 对话式输入组件（聊天UI + 快捷标签）
- `DiaryEntryCard.vue` — 单条日记卡片（显示AI提取的结构化数据）
- `DiaryCalendarView.vue` — 日历视图（替代现有DiaryCalendar）
- `DiaryWeeklyReport.vue` — 周报卡片

#### 1.4 导航调整

- 底部导航：`问答 | 日记 | 测评 | 白友圈 | 我的`
- 报告功能合并到测评页（作为子Tab："白斑测评" | "体检报告"）

#### 1.5 清理工作

- 删除 `AssessmentWizard.vue`（已被AssessmentPage替代）
- 删除 `AssessmentSection.vue`（已被Step组件替代）
- 删除 ProfilePage 中4个模糊预览卡片
- 评估 `chat/` 目录组件是否为旧版残留

---

### Phase 2（第3-4周）：AI洞察 + 周报 + 提醒

#### 2.1 后端：AI周报生成

```
GET /api/diary/summary/weekly?week=2026-W31
```

- 汇总本周日记（心情/饮食/用药/睡眠/压力）
- 汇总本周VASI评估（如有）
- AI生成结构化周报 + 建议
- 返回可分享的JSON

#### 2.2 后端：诱因模式分析

```
GET /api/diary/insights?days=30
```

- 分析近30天日记数据
- 发现关联模式（如：睡眠差→白斑扩散、压力大→新发）
- 返回洞察卡片列表

#### 2.3 前端：周报 + 洞察UI

- `WeeklyReportCard.vue` — 周报卡片（可分享到朋友圈）
- `InsightCard.vue` — 诱因洞察卡片
- 集成到日记页面和个人中心

#### 2.4 PWA Push提醒

- 前端接入PushSubscription（模型已有）
- 每日20:00推送"今天记录日记了吗？"
- 用药提醒推送（MedicationReminder已有后端）

---

### Phase 3（第5-6周）：治疗档案 + 社区增强

#### 3.1 后端：治疗事件模型（新增）

```python
class TreatmentEvent(Base):
    """治疗事件"""
    __tablename__ = "treatment_events"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    profile_id = Column(Integer, ForeignKey("patient_profiles.id"), nullable=True)

    event_type = Column(String(30), nullable=False)  # medication/phototherapy/surgery/consultation/diagnosis
    event_date = Column(Date, nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)

    # 结构化字段
    medication_name = Column(String(100), nullable=True)
    dosage = Column(String(100), nullable=True)
    body_site = Column(String(50), nullable=True)
    doctor = Column(String(100), nullable=True)
    hospital = Column(String(200), nullable=True)
    cost = Column(Float, nullable=True)

    # 来源
    source = Column(String(20), default="manual")  # manual/diary_ai/post_ai/report_ai
    source_ref_id = Column(Integer, nullable=True)  # 关联的日记/帖子/报告ID

    created_at = Column(DateTime, default=_utcnow)
```

#### 3.2 前端：治疗时间线

- `TreatmentTimelinePage.vue` — 时间线页面
- `TreatmentTimelineItem.vue` — 时间线节点
- 集成到个人中心

#### 3.3 社区：结构化治疗分享

- 发帖时选择"治疗分享" → 弹出结构化表单
- 字段：治疗方案/持续周期/效果评价/费用/副作用
- 可关联VASI评估对比图

#### 3.4 患者档案扩展

- PatientProfile增加字段：
  - `current_treatment` — 当前治疗方案
  - `medication_list` — 用药列表 JSON
  - `phototherapy_frequency` — 光疗频率
  - `disease_stage` — 病程阶段（进展期/稳定期/恢复期）
  - `onset_age` — 发病年龄
  - `family_history` — 家族史

---

### Phase 4（第7-8周）：视频优化 + 增长

#### 4.1 视频发帖优化

- 上传进度条
- 自动压缩（前端ffmpeg.wasm或后端）
- 封面自动截取 + 手动选择
- 视频播放器优化（全屏/倍速）

#### 4.2 分享海报生成

- 治疗对比海报（VASI前后照片 + 数据）
- 周报海报（本周摘要 + 二维码）
- Canvas绘制 → 导出PNG

#### 4.3 SEO优化

- 百科内容预渲染（prerender或SSG）
- 社区精华帖预渲染
- sitemap.xml生成

#### 4.4 微信分享增强

- 周报分享卡片
- 对比海报分享
- 百科文章分享

---

### Phase 5（第9-12周）：生态完善

#### 5.1 AI问答个性化

- RAG问答接入用户治疗档案上下文
- 社区经验聚合引用
- "根据你的记录，你目前使用他克莫司+308激光..."

#### 5.2 相似病友推荐

- 基于PatientProfile + TreatmentEvent计算匹配度
- 社区首页"和你相似的白友"推荐
- IM快捷添加

#### 5.3 群体疗效洞察

- 匿名聚合统计API
- "同方案白友改善率"卡片
- 社区首页展示

#### 5.4 医生科普入驻

- 医生认证流程（DoctorVerification模型已有）
- 医生科普发帖标识
- 问答精华标记

#### 5.5 临床试验匹配

- 基于用户档案匹配ClinicalTrials.gov
- 数据Pipeline已有爬取能力
- 前端展示匹配结果

---

## 五、ProfilePage优化方案（重点）

### 当前问题

- 996行，仍然过大
- 4个模糊预览卡片无实际功能
- 用药提醒无入口
- 治疗时间线无入口
- 日记入口不明显

### 优化后结构

```
ProfilePage（精简为容器）
├── ProfileHeader.vue          — 头像/昵称/UID/编辑
├── PatientProfileSection.vue  — 患者档案（已有）
├── TrackingSummaryCard.vue    — 测评摘要（已有逻辑）
├── DiarySummaryCard.vue       — 日记摘要（新增：连续天数/本周记录）
├── MedicationSection.vue      — 用药提醒（新增：接入已有API）
├── TreatmentTimelineCard.vue  — 治疗时间线入口（新增）
├── CommunityStatsCard.vue     — 社区统计（已有）
├── SettingsSection.vue        — 设置（隐私/照片/通知/安装）
└── SecurityModal.vue          — 安全设置（已有）
```

---

## 六、技术债务清理清单

| # | 项目 | 操作 | 优先级 |
|---|------|------|--------|
| 1 | `AssessmentWizard.vue` | 删除 | P1 |
| 2 | `AssessmentSection.vue` | 删除 | P1 |
| 3 | ProfilePage模糊卡片 | 删除 | P1 |
| 4 | `chat/`目录6个组件 | 评估是否旧版残留 | P2 |
| 5 | `VoiceCallPage` | 降级为问答页内按钮 | P2 |
| 6 | `ButterflyMascot` | 若VoiceCall降级则清理 | P3 |
| 7 | Post.diary_type | 迁移到DiaryEntry后废弃 | P2 |
| 8 | `/tracker` redirect | 清理旧路由 | P3 |
| 9 | `/chat` redirect | 清理旧路由 | P3 |

---

## 七、数据模型演进图

```
当前                              新增
────                              ────
User                              DiaryEntry (AI日记)
  ├── PatientProfile (基础)         ├── mood/sleep/diet/medication/stress
  ├── VASIAssessment                ├── ai_extracted_json
  ├── Post (社区帖子)                ├── vasi_assessment_id (关联)
  ├── MedicalReport                 └── post_id (关联)
  ├── MedicationReminder          
  ├── ImConversation              TreatmentEvent (治疗事件)
  └── UserNotification              ├── event_type/date/title
                                    ├── medication/phototherapy/surgery
Post (社区帖子)                      └── source (manual/diary_ai/post_ai)
  ├── diary_date (简单标记)       
  ├── diary_type (简单标记)       WeeklyReport (周报缓存)
  └── ...                           ├── user_id/week
                                    ├── summary_json
VASIAssessment                      └── share_image_url
  ├── vasi_score/area_percentage  
  ├── body_site/classification    DiaryInsight (诱因洞察缓存)
  └── ...                           ├── user_id
                                    ├── insight_type
                                    └── description_json
```

---

## 八、关键指标（对照规划）

| 阶段 | 核心指标 | 目标 |
|------|---------|------|
| Phase 1 | 日活日记创建数 | >50条/天 |
| Phase 2 | 7日留存率 | >40% |
| Phase 2 | 周报生成率 | >60%活跃用户 |
| Phase 3 | 治疗分享帖占比 | >20%新帖 |
| Phase 4 | 分享海报生成数 | >20张/天 |
| Phase 5 | 病友匹配成功率 | >30%接受 |

---

## 九、风险与注意事项

1. **后端共享**：所有后端修改立即影响生产环境，需严格遵循staging→production流程
2. **数据库迁移**：新增表使用Alembic，仅做additive操作
3. **LLM成本**：AI日记提取每次调用LLM，需设置频率限制（每用户每天≤10条）
4. **隐私**：日记数据默认私密，公开需用户明确授权
5. **向后兼容**：Post.diary_type暂时保留，新旧并行，后续迁移

---

## 十、总结

### 最核心的3件事

1. **建AI日记** — 这是规划的第一优先级，是留存引擎，是当前完全缺失的
2. **调导航** — 把"日记"放到黄金位置，把"报告"合并，让用户感知到核心价值
3. **清债务** — 删除旧组件、模糊卡片，让代码库干净，为新功能腾出空间

### 不需要做的

- 不需要重构现有VASI测评（已经很好）
- 不需要重构社区基础功能（帖子/评论/点赞已完善）
- 不需要过早优化技术架构（SQLite单机够用）
- 不需要做微信小程序（PWA先跑通）

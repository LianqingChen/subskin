# SubSkin 产品精简与打磨 — 文件级改动触点调研报告

- 日期：2026-08-03
- 目的：为后续任务 #3（导航精简+报告合并+债务清理）、#4（日记周报卡片与分享）、#5（AI问答个性化）、#6（结构化治疗分享）提供精确文件级上下文。
- 结论速览：三项任务假设与现状不符 —— (a) ProfilePage 的"模糊预览卡片"已不存在；(b) AssessmentWizard/AssessmentSection 组件已不存在；(c) TreatmentEvent 表无任何写入方。

## 1. 导航与路由

### 1.1 BottomNav.vue（5 Tab → 4 Tab）
文件：/root/subskin/web/app/src/components/layout/BottomNav.vue（188 行）
- 第 10-18 行 navItems：现为 问答(/)、日记(/diary)、测评(/assessment)、白友圈(/community)、我的(/profile)。日记已在 Tab 中，改 4 Tab 只需删除第 16 行"我的"条目。
- 第 20-37 行 isActive()：第 33-35 行 /profile 分支可一并删除；第 31 行已把 /report、/tracker 视为"测评"激活态，报告合并为测评子 Tab 后可沿用。
- 渲染：第 66-78 行循环输出 router-link，每项带 data-track-id（bottom_nav_我的 将消失，影响 UserEvent 埋点口径）。
- 组件在 App.vue 第 12 行全局挂载；≥768px 时隐藏（样式第 182-186 行），桌面端导航依赖 AppHeader。

### 1.2 AppHeader.vue（桌面导航 + "我的"替代入口）
文件：/root/subskin/web/app/src/components/layout/AppHeader.vue（226 行）
- 桌面 nav 第 102-123 行：问答/测评/报告(111-114)/白友圈/我的(119-122)。对齐 4 Tab 需删除"报告"与"我的"链接、新增"日记"链接；isNavActive() 第 25-31 行与 shareTitle 第 66-75 行需同步修正。
- "我的"从 Tab 移除后入口已存在：登录态右上角头像按钮（第 153-161 行）→ 下拉菜单（第 162-176 行）含"个人中心"router-link /profile（第 167 行）、隐私政策、退出登录。未登录访客仅显示登录按钮（第 145-152 行），profile 本就需登录。
- 结论：移除"我的" Tab 不产生死路。

### 1.3 router/index.ts 相关路由
文件：/root/subskin/web/app/src/router/index.ts（169 行）
- /report：第 49-53 行（ReportPage.vue）
- /report/compare：第 60-65 行（ReportComparePage.vue）
- /tracker/report/:id：第 44-48 行（ReportDetailPage.vue；由 ReportUploader.vue 第 127、155 行跳转）
- /chat：第 21-24 行，仅 redirect 到 '/'，可直接删除
- /voice-call：第 16-20 行（VoiceCallPage.vue，全站无任何导航入口）
- 注意：/chat/:id（第 138-142 行，ChatRoomPage）是 IM 私聊路由，与 AI 问答无关，清理时勿误删。
- 联动点：App.vue 第 59 行 pageTitles['/report']；services/rag.py 系统提示词导航表（第 564-597 行）硬编码了 /report、/messages、/contacts 等模块路径，导航精简后需同步更新文案，否则 AI 引导会指向旧导航。

### 1.4 报告页合并进测评页的可行性
- ReportPage.vue（views/，42 行）：极薄壳 —— 固定熊猫（DigitalHuman，第 21-25 行）+ 滚动卡片内嵌 ReportUploader（第 37 行）。
- ReportUploader.vue（components/tracker/，307 行）：自包含（上传/列表/AI解读/对比模式），仅依赖 medicalReportApi 与 router，可直接复用到子 Tab。
- AssessmentPage.vue（views/，471 行）：全屏 3 步向导（拍照→标注→结果），自有 sticky header（第 284-327 行），桌面历史侧栏 + 移动端 bottom sheet；header 第 310-316 行已有"体检解读"快捷按钮 router.push('/report')。
- 可行性结论：可行。建议：AssessmentPage 增加子 Tab 切换（测评/体检解读），解读 Tab 直接复用 ReportUploader（熊猫布局可简化或舍弃）；/report 路由改为 redirect 到 /assessment?tab=report，保住存量入口（ProfilePage 第 631 行、ReportComparePage 第 198、216 行）。
- 风险：wizardStep/history 为页面级状态，Tab 切换需避免重置向导；AssessmentPage 为 min-h-[100dvh] 全屏布局，嵌入 ReportUploader 需处理滚动容器；/report/compare 与 /tracker/report/:id 保留不动。

## 2. 待清理组件引用关系（安全删除判定）

### 2.1 AssessmentWizard.vue / AssessmentSection.vue
- 两文件均不存在（src 下仅有 components/tracker/AssessmentStep1Capture/Step2Analyze/Step3Result/AssessmentHistoryPanel 与 views/AssessmentPage.vue）。仅两处注释残留旧名：composables/useVasiAssessment.ts 第 408 行、constants/bodySites.ts 第 3 行。
- 结论：无需删除（已不存在）；4 个现存 Assessment* 组件仅被 AssessmentPage.vue 引用（第 18-21 行 import）。

### 2.2 VoiceCallPage.vue
- 文件：views/VoiceCallPage.vue（361 行）。唯一引用：router/index.ts 第 16-20 行 /voice-call 路由。全站无任何 router-link/push 指向 /voice-call。
- 连带孤儿：components/assistant/ButterflyMascot.vue 仅被 VoiceCallPage 引用（第 9、210 行）；composables/useVoiceTrigger.ts 无任何引用方。
- 结论：可安全删除 VoiceCallPage.vue + /voice-call 路由；ButterflyMascot.vue、useVoiceTrigger.ts 随之成为死代码，可一并删除。
### 2.3 components/chat/ 目录 vs assistant/ 目录
- chat/ 6 个组件全部孤儿化：ChatOverlay.vue 内部引用 ChatMessage/ChatInput/SuggestionChips（第 8-10 行），但 ChatOverlay 本身无任何外部引用；KnowledgePanel.vue、ConversationList.vue 零引用。
- AI 问答已由 assistant/ 承载：ChatAssistantPage.vue 第 5-6 行引用 ChatPanel、CounselingPanel；CounselingPanel 第 6-7 行引用 BreathingExercise、MoodRecordCard。
- 附带发现：assistant/QuickActions.vue 也无任何引用方（孤儿）。
- 结论：components/chat/ 整个目录可安全删除。注意勿混淆：stores/chat.ts、api/chat.ts 是新助手聊天在用代码，不能删。
### 2.4 ProfilePage.vue 模糊预览卡片与 ButterflyMascot
- 文件：views/ProfilePage.vue（995 行）。全文检索 blur-sm/blur-md/预览/解锁/VIP 均无命中；唯一的 "blur" 是第 900 行昵称输入框的 @blur 事件处理器（checkNicknameAvailability）。
- ButterflyMascot 在该文件无任何引用（全项目唯一引用在 VoiceCallPage.vue）。
- 结论：「模糊预览卡片」为过时信息，当前代码不存在该代码块，无需删除；若产品要求新增模糊引导卡片则属新需求。ProfilePage 现有结构：头部用户卡（未登录引导第 597-609 行）、四宫格快捷入口（第 612-649 行，含 /report 入口第 631 行）、PatientProfileSection（第 652-658 行）、追踪数据卡（第 660 行起）。
## 3. 日记功能现状

### 3.1 现有 UI
- DiaryPage.vue（views/，660 行）：对话式输入框（第 248-276 行）、快捷记录 DiaryQuickPanel（第 243-245 行）、折叠日历 DiaryCalendarMini（第 225-231 行）、条目列表 DiaryEntryCard（第 292-299 行）、统计条（第 208-221 行：总记录/连续天数/本周）。未登录守卫完备（第 163-169 行避开 401 死循环，符合历史踩坑记忆）。
- components/diary/ 仅 3 个组件：DiaryEntryCard.vue（249 行）、DiaryCalendarMini.vue（227 行）、DiaryQuickPanel.vue（295 行）。
- api/diary.ts（128 行）：CRUD、quick、calendar、weekly、stats 函数齐全。
### 3.2 周报：后端就绪，前端零 UI
- 前端 getWeeklyReport() 已定义于 api/diary.ts 第 116-118 行（GET /api/diary/summary/weekly），WeeklyReport 类型第 62-69 行（week_start/week_end/entry_count/mood_distribution/ai_summary/insights），但全项目零调用 —— 周报没有任何展示 UI。
- 后端 api/diary.py 第 390-444 行 get_weekly_summary：返回心情分布与 insights；insights 为规则文案（第 418-428 行），ai_summary 仅拼接前 5 条日记摘要（第 430-435 行，注释自述"后续可升级为LLM生成"）。
- 任务 #4 缺口清单：① 周报卡片组件（components/diary/ 下新建）；② 周报 ai_summary 升级为 LLM 生成（可选）；③ 分享能力 —— 日记侧目前无任何分享/海报功能，仅 components/common/ 有通用 PageShareSheet.vue/PageSharePoster.vue（只被 AppHeader 全局分享使用），需新建周报分享海报或复用。

### 3.3 streak 连续记录天数
- 已存在。后端 api/diary.py 第 450-498 行 GET /diary/stats：从今天向前逐日回溯计算 current_streak（第 463-480 行），另返回 total_entries、week_count。
- 前端：api/diary.ts 第 121-127 行 getDiaryStats；DiaryPage.vue 第 213-216 行展示"连续天数"。
- 已知口径缺陷：回溯从今天开始，今天未记录则 streak=0（即使昨天连续记录）。做"打卡激励"打磨时需确认是否放宽为"昨天有记录也算连续"。

### 3.4 TreatmentEvent 数据缺口（重要）
- TreatmentEvent 模型已存在（models.py 第 1197-1228 行），但全项目无写入方：services/diary_ai.py 只更新 DiaryEntry 字段不写事件表；api/diary.py 第 17 行 import 了 TreatmentEvent 却未使用；DiaryEntry.treatment_events_json 字段从未被赋值。
- 影响：任务 #5 可用的"治疗档案"数据源目前恒为空表；建议由 #4 或 #6 顺带让日记 AI 提取落库 TreatmentEvent（source=diary_ai）。
## 4. AI 问答个性化注入点（后端）

### 4.1 问答主流程与注入位置
文件：/root/subskin/web/backend/services/rag.py（1321 行）
- 提示词构建：_build_knowledge_prompt() 第 515-619 行（智能问答模式）；_build_companion_prompt() 第 622-683 行（知心陪伴模式）。
- 消息拼装（核心注入点①）：_build_llm_messages() 第 686-712 行 —— system prompt + 参考资料 + 用户问题，conversation_history 插在 system 与 user 之间。可新增 user_context 参数注入个人上下文块。
- 同步链路：answer_question() 第 1139-1209 行（签名已含 db、user_id）→ generate_answer() 第 1050-1087 行。
- 流式链路（前端主路径，核心注入点②）：answer_question_stream() 第 1089-1136 行；第 1111-1113 行已有"向 messages[0] 动态追加说明"的先例（has_attachments），用户上下文可用同样模式注入。
- API 层：/root/subskin/web/backend/api/rag.py —— /ask-stream 第 529-560 行 → _stream_rag_response() 第 627-637 行（签名已含 db、user_id）；/ask 第 241-265 行；访客路由 /ask-public（268-325 行）与 /ask-public-stream 传 user_id=None，注入自动跳过。
- 前端佐证：api/chat.ts 第 75-90 行，登录用户走 /rag/ask-stream（streamAsk/streamAskWithAttachments），访客走 /rag/ask-public-stream。故任务 #5 主战场是 _stream_rag_response → answer_question_stream。
- 隐私提示：_build_knowledge_prompt() 第 603-612 行"数据保护"段落明确要求不查询/透露个人信息 —— 注入本人档案/日记时必须同步改写该段（限定"仅使用当前用户自己的数据、绝不跨用户"），否则提示词自相矛盾。

### 4.2 可注入的数据模型字段
文件：/root/subskin/web/backend/database/models.py
- PatientProfile（第 182-200 行，表 patient_profiles）：user_id、name、relationship（本人/父母/伴侣…）、gender、birth_date、diagnosis_date、vitiligo_type、notes、is_self。User 另有 patient_relation（第 115-117 行）与 default_*_profile_id（第 118-126 行）。
- DiaryEntry（第 1158-1194 行，表 diary_entries，索引 idx_diary_user_date）：raw_text、input_type、mood、sleep_quality、diet_notes、medication_taken、stress_level(1-5)、skin_condition、treatment_events_json、ai_summary、ai_extracted_json、vasi_assessment_id、is_public、post_id、entry_date。
- TreatmentEvent（第 1197-1228 行，表 treatment_events）：event_type(medication/phototherapy/surgery/consultation/diagnosis)、event_date、title、description、medication_name、dosage、body_site、doctor、hospital、cost、source、source_ref_id。当前无写入方（见 3.4）。
- 建议注入方案：按 user_id 取默认 PatientProfile（User.default_diary_profile_id，无则首条）+ 近 7 天 DiaryEntry + 最近 N 条 TreatmentEvent，格式化为"用户病情档案"文本块，经 _build_llm_messages 新参数或 messages[0] 追加方式注入；注意控制 token 量并只取本人数据。
## 5. 社区发帖结构化（任务 #6）

### 5.1 前端发帖入口与表单
- CommunityEditorPage.vue（views/，37 行）：纯分发器，按 route.query.type 选编辑器 text/image/video/long（默认 long），无业务逻辑。
- LongPostEditor.vue（components/community/Editor/，293 行）：现有字段 —— title、content/contentJson（RichEditor/Tiptap）、categoryId（默认选中"治疗分享"分类，第 83-88、164 行）、mood（MOOD_OPTIONS 第 48-53 行：💪坚持中/😔低落/🎉好转/🤔疑问）、tags、city+经纬度（CityPicker/useGeolocation）、isPrivate；草稿自动保存第 57-79 行，夸大宣传检查第 90-100 行。
- 发布 payload：handlePublish() 第 160-196 行，未传 diary_type/diary_date；结构化治疗字段（方案/时长/效果/费用）完全没有。
- 前端类型：api/community.ts createPost 第 83-86 行；PostCreateRequest 在 types/index.ts 第 228-246 行（已含 diary_date/diary_type 可选字段，加新结构化字段需同步扩展）。

### 5.2 后端创建帖子链路
- API：api/community.py create_post() 第 201-241 行起 —— 校验封禁/禁言/限速后调 CommunityService.create_post，已透传 diary_date/diary_type/mood/content_json（第 233-235 行）；后续接夸大宣传标记与异步内容审核。
- Pydantic：models/community.py PostBase 第 73-86 行、PostCreate 第 89-91 行（title/content/content_json/post_type/category_id/is_private/diary_date/diary_type/mood/is_anonymous/city + images/tag_names）。
- Post 模型：models.py 第 312-343 行。与治疗分享相关字段已存在：diary_type（第 335 行，枚举 medication/phototherapy/mood/diet/general）、mood（336）、diary_date（334）、content_json（321，Tiptap JSON 通用结构化槽位）、is_private、city。
- 服务层：services/community.py create_post() 第 67-85 行（签名同上）。
- 建表机制：app/main.py 第 74 行 Base.metadata.create_all 只建新表不加列 —— 给 posts 加列必须写 SQLite ALTER TABLE 迁移脚本，参考 /root/subskin/scripts/migration_add_content_json.py、migration_add_tags_attachments.py 等既有模板。

### 5.3 新增结构化字段方案与风险
- 方案 A（轻量，推荐起步）：posts 表新增 1 个 structured_json TEXT 列存治疗分享模板 JSON（方案名/疗法/部位/时长/效果/费用/VASI对比图），前端新增"治疗分享模板"表单组件填充；迁移脚本加列即可。
- 方案 B（重）：新建 post_treatment_profiles 表做结构化治疗档案，利于后续群体疗效聚合统计；改动面更大。
- 风险：① 后端共享（无 staging backend），schema 变更立即影响生产，必须只增列、不改不删（AGENTS.md 红线；历史教训：diary_type 缺列曾致社区 API 500）；② 新字段需同步改 6 处：models.py → models/community.py(PostBase/Create/Update) → api/community.py → services/community.py → 前端 types/index.ts → 编辑器组件与 PostDetailPage 展示；③ diary_type 现有枚举与索引不可变更；④ 后端改动需 systemctl restart subskin-backend 并走 DEPLOY_LOG 流程。

## 6. 通用风险清单（适用全部实施任务）
1. 部署流程零容忍：任何改动先 staging（npm run build），生产推送需用户明确确认；后端 .py 改动重启即影响生产（AGENTS.md）。
2. 前端删除组件后必须 npm run type-check（vue-tsc-guard skill）+ npm run build 双重验证，防止隐藏引用。
3. rag.py 系统提示词内的导航表（第 564-597 行）与 App.vue pageTitles 均为硬编码，导航精简需同步。
4. 埋点 data-track-id 随导航变化失效，属预期行为，无需修复但需知会。
5. 日记/问答涉及医疗内容，新增文案保留"仅供参考、遵医嘱"免责提示。

## 附录：关键文件清单（绝对路径）
### 前端 /root/subskin/web/app/src
- 导航：components/layout/BottomNav.vue、components/layout/AppHeader.vue、App.vue、router/index.ts
- 测评/报告：views/AssessmentPage.vue、views/ReportPage.vue、views/ReportDetailPage.vue、views/ReportComparePage.vue、components/tracker/ReportUploader.vue、components/tracker/AssessmentStep1Capture|Step2Analyze|Step3Result|AssessmentHistoryPanel.vue
- 日记：views/DiaryPage.vue、components/diary/DiaryEntryCard.vue、DiaryCalendarMini.vue、DiaryQuickPanel.vue、api/diary.ts
- 问答：views/ChatAssistantPage.vue、components/assistant/ChatPanel.vue（第 24-26 行调 /rag/ask-stream）、CounselingPanel.vue（第 32 行）、api/chat.ts、stores/chat.ts
- 社区：views/CommunityEditorPage.vue、components/community/Editor/LongPostEditor.vue、api/community.ts、types/index.ts
### 后端 /root/subskin/web/backend
- 问答：services/rag.py、api/rag.py
- 日记：api/diary.py、services/diary_ai.py
- 社区：api/community.py、services/community.py、models/community.py
- 模型：database/models.py（app/main.py 第 74 行 create_all）
- 迁移脚本模板：/root/subskin/scripts/migration_add_*.py

### 可安全删除清单（任务 #3）
| 文件 | 理由 |
|------|------|
| /root/subskin/web/app/src/views/VoiceCallPage.vue | 仅 router 引用，无导航入口 |
| router/index.ts 第 16-20 行 /voice-call 路由 | 同上 |
| router/index.ts 第 21-24 行 /chat redirect | 无引用 |
| /root/subskin/web/app/src/components/chat/（整目录 6 文件） | 全部孤儿 |
| /root/subskin/web/app/src/components/assistant/ButterflyMascot.vue | 唯一引用方 VoiceCallPage 被删 |
| /root/subskin/web/app/src/components/assistant/QuickActions.vue | 零引用 |
| /root/subskin/web/app/src/composables/useVoiceTrigger.ts | 零引用 |

（报告完）

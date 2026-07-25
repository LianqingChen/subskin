# SubSkin Deployment Log

> This file tracks all staging and production deployments.
> **Staging changes accumulate here until explicitly pushed to production.**
> **When user says "推送到正式环境" / "更新到正式环境", it means FULL SYNC — ALL pending items since the last production push will be deployed together, not just the latest change.**

## Pending Changes

| 日期 | 模块 | 变更描述 | buildTime |
|------|------|---------|-----------|
| (无待推送变更) | | | |

## Production Deployment History

> Latest: 2026-07-24 — buildTime: 1784912961105
| 2026-07-24 | 全量同步（5项） | **全量同步 staging → production**，累积推送 2026-06-21~2026-07-24 全部变更：①导航栏简化+问答页精简+tab改名+白友圈500修复；②Phase3～4功能升级(日记/对比/用药/时间线/向量/医生/监控)；③Embedding手动触发；④代码审查20项整改；⑤VASI白斑识别增强 | 1784912961105 |
| 2026-07-24 | 前端·导航+问答页+社区修复 | **5项修复**：①导航栏简化——去掉"小白"前缀，改为问答/测评/报告/白友圈/我的；②问答页面精简重设计——移除价值主张卡片和今日必读堆砌，改为简洁科技感布局（渐变图标+精简文案）；③第3个tab从"小白百科"改为"报告"（实际是体检报告解读页）；④白友圈帖子消失修复——diary_type列缺失导致社区API 500，已补充数据库列；⑤AI问答服务不可用——确认为阿里云DashScope账户欠费(Arrearage)，非代码问题，需充值。 | 1784912733081 |
| 2026-07-24 | 全栈·Phase3+Phase4功能升级 | **Phase 3～4 全量功能升级，staging 重建 + 后端重启**。⚠️后端改动已随 `systemctl restart subskin-backend` 立即生效于全环境。**Phase 3**：①治疗日记增强（Post模型新增diary_type字段+日历视图组件DiaryCalendar.vue+API /diary-calendar）；②白斑同部位对比增强（VasiComparePage自动同部位匹配建议）；③今日必读模块（ChatAssistantPage每日研究摘要卡片+/api/content/daily-briefing）；④PostgreSQL迁移准备（Alembic配置+基线迁移+diary_type迁移脚本）；⑤后端核心测试补充（diary_type+calendar+briefing测试）。**Phase 4**：①用药提醒（MedicationReminder模型+CRUD API+Web Push订阅+前端接口medication.ts）；②研究进展时间线（ResearchTimeline.vue+/api/content/timeline按月聚合）；③RAG向量数据库升级准备（vector_store.py抽象层，支持SQLite/pgvector/Qdrant三后端）；④医生认证体系（DoctorVerification+DoctorInvitation模型+申请/审核/邀请码API）；⑤监控告警体系（monitoring.py: Sentry错误追踪+Prometheus指标收集+健康检查增强）。 | 1784911321467 |
| 2026-07-22 | 管理后台+调度器 | **文献 Embedding 从自动改为手动触发**。⚠️后端/调度器改动已立即生效于全环境。①调度器 `update_scheduler.py` 的 `add_document` 调用改为 `compute_embedding=False`，新爬取文献不再自动向量化；②停用并禁用 `subskin-monthly-embed.timer` systemd 定时器（原每月1号03:00自动批量向量化）；③管理后台「系统监控」页新增「知识库向量化」卡片，支持手动触发增量 embedding（调用已有 `POST /api/admin/embed-batch` 端点），含确认弹窗、执行状态、结果统计。 | admin面板直接部署 |
| 2026-06-29 | 全栈·代码审查整改（20项） | **代码审查报告全量整改，staging 重建 + 后端重启**。⚠️后端改动已随 `systemctl restart subskin-backend` 立即生效于全环境（共享后端，无 staging 后端）。**P0（8项）**：①统一文件服务鉴权（VASI图片/社区上传/RAG临时附件均做 owner 校验，防 IDOR）；②手机号 allowlist 移至环境变量、移除管理员自动提权；③SMS/邮箱 OTP 日志脱敏（`_mask_phone`/`_mask_email`）；④VASI mock 失败时 fail-closed（不再返回伪造分数）；⑤新增 VASI finalize/abandon 端点；⑥VASI 自进化工厂禁用时返回 503；⑦社区帖子/评论/点赞/版本统一鉴权；⑧RAG 会话归属校验 + 临时附件归属校验。**P1（鉴权6项）**：WebSocket JWT→username 匹配 + 读回执校验；banned/inactive 用户在统一 JWT 层拦截；`PUT /me` 移除直接改手机号/邮箱（强制 OTP 绑定）；短生命周期 file-scoped token；admin 列表脱敏 + admin SPA 路由强制；`AuditLogService.log` 修复 + follow/like/share 审计 + 审计 target IDOR 防护；前端 logout 调后端撤销 + 重置密码撤销会话。**P1 VASI 14项**：lesions 过滤后写回、body_site 一致性、VLM ensemble union fallback、自适应 bbox 阈值、`_quality_reject_response` 调用、history/trend 过滤 draft 并用 `final_vasi_score`、`/check-photo-quality` 加鉴权+大小限制、magic byte 校验、批量删除归属校验、RL 图片路径修正、`GET /assess/{id}` 字段对齐、`startPreciseAssessment` 前放弃旧 draft。**P1 社区**：`create_post` NameError 修复、`my-diaries` 过滤私有非屏蔽、`PostLike` 唯一约束+幂等迁移、`add_to_collection` 校验可访问性、上传 size/扩展名/magic byte 校验、N+1 批量预取（`posts_to_models`）、DOMPurify 防 XSS、游标分页（前端+API）。**P1 RAG**：聊天速率限制（登录用户按 user_id）、guest 流式失败退款、危机消息绕过主题过滤、`SITE_FEATURE_KEYWORDS` 对齐 AGENTS.md 命名、历史轮数封顶 20、`add_document` 默认算 embedding、`cosine_similarity` 维度不匹配返回 0、统一 `get_llm_config`。**P2 batch**：PWA Workbox 对 `/api/*` 和 `/uploads/*` 设 NetworkOnly、schema helper 异常改 `logger.exception`、`start.sh` 默认 127.0.0.1 + 受控 reload、`.gitignore` 覆盖大二进制+临时文件、清理 `.bak`、admin 服务控制仅 start/restart + 审计、events API IP 限流 + 批量上限、nginx 安全头模板。**测试修复**：backend 测试套件 197 全绿（修复 test_auth/test_sms/test_credential/test_rag/test_vasi/test_analytics/test_comment/test_files，新增 test_audit 回归测试，安装 pytest-asyncio + 配置 asyncio_mode=auto + conftest 预置 SECRET_KEY）；修复 analytics 后端 3 个真实 bug（`_excluded_uid_filter` 保留匿名事件、`_real_user_filter` 保留 NULL phone 用户并排除 admin、`_load_excluded_uids` 排除 admin uid）。前端 `npm run type-check` 通过。 | 1782744700731 |
| 2026-06-21 | 后端·VASI白斑识别 | **⚠️共享后端，已立即生效于全环境**。增强白斑范围与边缘识别精准度，3步改动：①重写VLM静态prompt(vasi.py)——恢复输出bbox+edge_points+skin_region，注入色素脱失量化标准(0级<0.10/1级0.10-0.20/2级0.20-0.40/3级>0.40)、Fitzpatrick肤色自适应提示、非白斑反例约束(高光/疤痕/白化痣/参考卡)、边缘几何约束(edge_points紧贴bbox内)；修复旧prompt"bbox已不再需要"与SAM代码优先用bbox的矛盾。②接通edge_points——vasi.py主流程重建lesion_edge_points并传入segment_vitiligo_guided；vasi_segmentation.py签名新增参数，在VLM bbox盒提示基础上叠加edge_points作为SAM正提示点(box+points组合提示)，精修不规则边缘。③超参可调——temperature/max_tokens/timeout改为环境变量读取(VASI_VLM_TEMPERATURE=0.0/VASI_VLM_MAX_TOKENS=8192/VASI_VLM_TIMEOUT=120，原硬编码0.1/4096/90)，边缘定位更确定性、大图多斑不截断。④VLM模型qwen-vl-max→qwen3-vl-plus(.env+DB llm_module_configs双改)。离线验证：样本图返回4个病灶，每个含bbox+6-7个edge_points+boundary_type，JSON一次解析成功。无DB schema变更。 | 后端重启即生效 |

## Staging Deployment History (Archived)

> Previous: 2026-06-21 — buildTime: 1782032198708
| 2026-06-21 | 测评页+部署脚本（全量同步3项） | **全量同步 staging → production**，累积推送 2026-06-19~2026-06-21 全部 staging 变更：①修复 staging 403 Forbidden——`post-build-staging.sh`/`post-build.sh` 末尾追加 `chmod -R a+rX`，防止构建环境 umask 0077 导致产物 0600、nginx 无法读取；②测评页 Step1 上传照片后"开始AI分析"按钮自动上滑——watch 改 `flush:'post'` + 用 `scrollIntoView(block:'center')` 自动定位滚动容器（并修复 requestAnimationFrame 回调签名 TS2345：r → () => resolve()）；③分享帖子封面改为标注合成图(原图+皮肤蓝层+白斑粉层)作首图 + 原图作次图，滚动目标指向按钮本身 | 1782032198708 |
| 2026-06-19 | 测评页 | **2项UI修复同步生产**：①DigitalHuman身体部位注释字号 72→52（SVG单位），解决测评页注释字体偏大与页面不协调；②修复上传照片后未自动上滑——根因为 imagePreview 是 FileReader 同步设置的 base64，`<img>` 解码是异步的，首次 nextTick 时高度为 0 导致 scrollTo 目标偏小、按钮未入屏；改为先 `Image.decode()` 预解码 + 双 RAF + nextTick 等待布局稳定后再滚动到"开始AI分析"按钮 | 1781831937868 |
| 2026-06-18 00:23:37 | 测评页全量同步（18项） | **全量同步 staging → production**，累积推送 2026-06-14~2026-06-17 全部 staging 变更。核心：①功能1-上传照片后自动滚动到"开始AI分析"按钮；②功能2-分享时标注合成图(原始+AI图层)+原图作为双封面，修复data URL先上传服务器再存草稿；③MaskEditor 12轮性能/卡死修复(Canvas 1024px封顶、84K draw call→2个、zoomToFit死循环修复、60fps→12fps、Vue响应式优化、初始化5步异步)；④Step2标注画布可见性/工具栏/确认按钮；⑤UI一致性(背景#F5F7FA、数字人响应式)；⑥后端VLM视觉特征fallback(已即时生效) | 1781713417044 |
| 2026-06-13 01:10:21 | 测评页重构 v3 + VLM优化 | **测评页面全面重构**：①前端3步极简流程(拍照→AI分析+画布→结果)替换原5步，组件从2个超标文件(1368行)拆分为8个合规文件(全部在limit内)；②评估历史独立为桌面侧边栏+移动端底部sheet；③删除VisualFeatures阻断页、简化进度条、统一布局；④后端6个自进化文件优雅禁用(数据不足)；⑤VLM prompt从~250行精简到~70行(提高响应可靠性和速度)；⑥MaskEditor TS修复 | 1781284199040 |


| 日期 | 模块 | 变更描述 | buildTime |
|------|------|---------|-----------|
| 2026-06-10 | 测评页 | **2项合并推送**：①修复DigitalHuman身体部位标签被截断（SVG viewBox 1280→1400、所有x坐标+60、阈值640→700、overflow-hidden→overflow-visible）；②VASI测评步骤4界面简化（工具栏移入视口底部悬浮、面积占比改为badge、新手引导8秒自动关闭、信息栏紧凑单行+可折叠、移除冗余统计/提示/按钮） | 1781069684404 |

| 日期 | 模块 | 变更描述 | buildTime |
|------|------|---------|-----------|
| 2026-06-09 | 测评页+UX重构 | **2项合并推送**：①评估历史分页（useVasiAssessment composable新增分页API + AssessmentSection删除加载更多、新增分页条）；②VASI测评模块全面UX优化——架构统一(TrackerPage裁剪+路由修复+6文件路径更新)+5步向导流程(AssessmentWizard新建)+画笔简化(默认白斑画笔+新手引导+面积进度条)+AI辅助(部位确认牌+信心度徽章)+结果展示(sparkline趋势图+对比箭头) | 1780980449779 |
| 2026-06-09 | 测评页 | **VASI"灰色方框"双修推送（合并2条pending）**：①真正根因修复——MaskEditor.vue template transform 嵌套 bug：外层 `absolute top-1/2 left-1/2` + 内层 `translate(-50%, -50%)` + scale(zoom)，`translate(-50%)` 按图片**自然尺寸**算偏移，3000×4000 图在 zoom<0.5 时被推到 -1500px/-2000px 渲染在 viewport 外，只剩 `bg-gray-300` 灰底。改为 `absolute inset-0 flex items-center justify-center` flex 居中容器，内层只保留 scale + pan transform。②首轮 zoomToFit/minZoom 改动也带上：`minZoom 0.15→0.05`，独立 `fitFloor=0.02`，`onImgLoad` 加 `nextTick + requestAnimationFrame`，`watch(imageUrl)` 改 async 并对 cached blob 主动触发 onImgLoad，新增 `watch([skinLayer,lesionLayer])` 在 AI 图层后到达时重画 canvas。③修复 prod build TS2322——watch oldValue 默认值与 `MaybeUndefined<T,Immediate>` 类型冲突，去掉默认值（非 immediate watch 必有 oldValue） | 1780961725111 |
| 2026-06-09 | 社区+测评+登录 | **5项合并推送**：①发现页帖子卡片Footer简化（仅昵称+爱心，移除多余按钮）；②关注按钮从加号图标改为文字"关注"/"已关注"按钮（FollowPlus.vue重写）；③帖子详情页头像改为真实图片+私信按钮（PostDetailPage.vue）；④登录闪跳修复——PWA controllerchange不再强制刷新打断输入，showLoginModal持久化到sessionStorage（usePWA.ts+auth.ts），统一全局LoginModal（CommunityPage+PostDetailPage移除本地LoginModal）；⑤VASI测评结果页照片不再被隐私模式blur-lg模糊覆盖（用户自己的医疗照片不应对自己模糊），添加图片加载失败容错 | 1780940088791 |
| 2026-06-08 | 测评页 | **修复VASI测评3项Bug**：①VisualFeaturesCard特征分析描述文字移除`truncate`类改为自动换行（原超出屏幕显示省略号）；②`useVasiAssessment`的`loadImagePreview`从`URL.createObjectURL`(blob URL)改为`FileReader.readAsDataURL`(data URL)，修复MaskEditor灰色区域问题（blob URL在上传后可能失效导致图片不渲染）；③MaskEditor取消按钮行为修复——新增`cancelAssessment`函数：取消测评→终止draft(调用abandonAssessment)→重置状态→回到上传步骤，不再显示"测评完成"结果和"分享至发现"按钮；④特征分析步骤(Step 3)和VASI测评步骤(Step 4)添加"取消测评"和"返回特征分析"按钮，允许用户返回上一个操作 | 1780850708209 |

| 日期 | 模块 | 变更描述 | buildTime |
|------|------|---------|-----------|
| 2026-06-07 | 社区+后端 | **4项合并推送**：①恢复同城分享功能（CityPicker+useGeolocation+CommunityPage三Tab+4个发帖Editor+TS错误修复）；②RAG向量化改为每月增量执行（batch_embed+embed-batch端点+monthly_embed脚本+systemd timer）；③同城定位速度优化（IP优先+GPS异步升级，6-13秒→<1秒）；④同城Tab改为动态城市名+城市切换器（省份→城市层级选择+搜索） | 1780847821604 |

| 日期 | 模块 | 变更描述 | buildTime |
|------|------|---------|-----------|
| 2026-06-06 | 个人中心 + 全局文本 | **修复个人中心残留深色背景 + 全局文本可见性**：①ProfilePage移除所有功能性区块`dark:bg-gray-800/700/700-40/700-50`（选项栏、列表项、输入框、标签组、空状态、凭证卡片、信息框等10+处）；②5个profile弹窗移除`dark:bg-gray-800`；③全局移除已修改页面的`dark:text-gray-100/200/300`（覆盖ProfilePage, AssessmentPage, ReportPage, DashboardPage, CommunityPage及社区子组件），确保白色背景文字可读 | 1780761601399 |

| 日期 | 模块 | 变更描述 | buildTime |
|------|------|---------|-----------|
| 2026-06-06 | 个人中心 + 全局文本 | **修复个人中心残留深色背景 + 全局文本可见性**：①ProfilePage移除所有功能性区块`dark:bg-gray-800/700/700-40/700-50`（选项栏、列表项、输入框、标签组、空状态、凭证卡片、信息框等10+处）；②5个profile弹窗移除`dark:bg-gray-800`；③全局移除已修改页面的`dark:text-gray-100/200/300`（覆盖ProfilePage, AssessmentPage, ReportPage, DashboardPage, CommunityPage及社区子组件），确保白色背景文字可读 | 1780761601399 |
| 2026-06-06 | 全页面 | **移除功能模块卡片暗色背景**：①全局`.card`类移除`dark:bg-gray-800`（根治）；②测评/体检页移除panda背景`dark:bg-gray-900`和底部卡片`dark:bg-gray-800`；③ProfilePage移除10+处卡片`dark:bg-gray-800`；④DashboardPage移除标签栏`dark:bg-gray-800`；⑤CommunityPage移除筛选按钮/搜索栏/下拉面板/骨架卡片`dark:bg-gray-800`；⑥所有帖子卡片组件(PostCard/LongPostCard/ImagePostCard/TextPostCard)移除`dark:bg-gray-800`；⑦社区编辑器和弹窗(TagEditor/CreatePostSheet/4个Editor)移除暗色背景 | 1780761090364 |
| 2026-06-06 | 页面背景 | **修复正式环境页面深色背景**：移除`App.vue`根容器`dark:bg-gray-950`、`AssessmentPage.vue`和`ReportPage.vue`根容器`dark:bg-gray-900`，确保测评/体检/发现/我的页面在正式环境中始终白色/浅色背景 | 1780760210605 |
| 2026-06-06 | 导航栏 | **修复正式环境导航栏暗色背景**：移除`AppHeader.vue`生产环境header全部`dark:`变体类，正式环境导航栏在所有主题下均白色背景 | 1780758984304 |
| 2026-06-06 | 管理后台 + 后端 | **修复暂存标注回显Bug**：①后端新增3个端点（`/annotations` 回显管理标注、`/user-annotations` 预填充用户数据、`/annotated-image` 返回合成图）；②前端`openEditor()`重构为顺序加载（先加载标注数据+合成图URL，全部就绪后再显示编辑器，消除异步时序问题）；③修复暂存后重新打开编辑器标注丢失的核心缺陷 | 1780757327962 |
| 2026-06-06 | 管理后台 | **图片打标模块重大升级**：①用户填涂结果自动预填充到管理后台画布（无需从零开始）；②保存草稿功能（随时保存进度，避免数据丢失）；③管理员标注与用户原始数据严格分离（管理员数据仅作AI训练，不修改用户测评记录） | 1780757327962 |
| 2026-06-06 | 管理后台 | **保存草稿修复**：移除重复取消按钮；enhance save/submit to capture canvas data directly | 1780757327962 |
| 2026-06-06 | 前端 + 后端 | **修复个人中心"账号凭证加载失败"**: ①前端`client.ts`追加singleton `refreshPromise`去重并发refresh-token请求(减少重复token刷新)；②后端`user.py`和`oauth.py`的login/me端点追加`_sync_legacy_user_fields`同步，login/me响应中phone/email字段不再缺失 | 1780757327962 |
| 2026-06-06 | 后端 | **修复分析模块500**：`analytics.py:623`中`UserEvent.user_id`→`uid`(attribute typo) | 1780757327962 |
| 2026-06-05 | 测评页 | **修复桌面端上传文件框宽度**：移除两列布局中的`selectedPart`触发条件，上传照片区域恢复全宽居中，仅在AI评估后激活轮廓编辑器时使用左右分栏 | 1780668224574 |
| 2026-05-23 | 全站 | **发现页推荐优化**：无位置→热门(7天热榜)；AI助手优化(移除预设卡片+修复语音)；全站15项缺陷修复 | 1779537518850 |
| 2026-05-23 | 测评页 | **白斑视觉特征分析（新功能）**：上传照片后6维特征分析(可见性/颜色/边缘/形态/表面/分布)、科普参考卡片、结论前置、就医建议、VLM prompt合并、qwen-vl-plus-latest模型、JSON尾逗号修复、倒计时替代固定等待、线性用户路径(①上传→②评估→③特征→④VASI结果→⑤分享)、页面状态互斥防重复评估 | 1779537518850 |

> **注**：管理后台(admin.subskin.cn)没有正式/测试环境区分，每次构建即上线。

---

## Environment Sync Baseline

> **🔴 2026-06-09 SYNC POINT — LATEST**: Staging and Production are EXACTLY identical in code content.
> This is the current baseline. All future changes start from this sync point.
> **The ONLY intentional differences between staging and production are:**
> 1. Nav bar color: staging = 深蓝 `bg-slate-800`, production = 白色 `bg-white`
> 2. PWA app name: staging = "SubSkin [STAGING]", production = "SubSkin更懂你"
> 3. version.json `env` field: staging = `"staging"`, production = `"production"`
> 4. Update banner text: staging = "测试环境有新版本可用", production = "有新版本可用"
>
> **Everything else (功能、页面、组件、逻辑、API) is 100% identical.**
> **Any new change MUST go to staging first, then FULL sync to production after user confirmation.**

| | Staging | Production |
|---|---------|------------|
| BuildTime | 1780940124396 | 1780940088791 |
| Source code | ✅ Identical | ✅ Identical |
| Nav bar | Dark blue (`bg-slate-800`) | White (`bg-white`) |
| PWA name | SubSkin [STAGING] | SubSkin更懂你 |
| __APP_ENV__ | `'staging'` | `'production'` |
| Update banner | "测试环境有新版本可用" | "有新版本可用" |
| Everything else | ✅ Identical | ✅ Identical |

---

## Production Deployment History

| Date | BuildTime | Changes Pushed |
|------|-----------|----------------|
| 2026-05-23 | 1779469587330 | 🤖 **AI助手模式角色分离**：智能问答与知心陪伴后端mode参数分离，knowledge模式temperature=0.3（严谨医学顾问），counseling模式temperature=0.7（温暖心理陪伴），含CBT认知重构框架和自杀危机干预机制 |
| 2026-05-22 | 1779405915621 | 🎛️ **管理后台+主应用合并推送**：①管理后台移动端适配(ECharts响应式/Tab切换/底部导航栏) ②LLM配置逐模块预设+始终可编辑面板 ③图片打标模块(行内布局+AI/人工标注+Tab分离+鉴权修复+导出) ④主应用移除头像菜单「管理员页」入口 |
| 2026-05-21 | 1779376709422 | 📐 **聊天页高度修复**：改用 `h-[calc(100dvh-3.5rem)] pb-14 md:pb-0`，与小白助手保持一致，输入框精准停在底部导航栏上方 |
| 2026-05-21 | 1779368911912 | 💬 **私信功能 + 布局 + 通知（4项合并）**：①用户主页新增「私信」按钮+布局三层优化 ②取消关注确认机制 ③聊天页底部导航遮挡修复 ④私信通知（接收方收到"发来一条私信"，消息页可点击跳转） |
| 2026-05-21 | 1779326495672 | 🐛 **修复帖子详情关注按钮**：后端 `post_to_model` 增加 `is_followed` 字段（查 `UserFollow` 表），前端 `FollowButton` 正确传入 `initialFollowed`，已关注作者显示"已关注" |
| 2026-05-21 | 1779323885784 | 🎨 **发现页大改版（8项合并）**：①帖子卡片改版（仅昵称+小红心，移除收藏/评论按钮）②时间+城市显示 ③移除匿名发布 ④昵称唯一性校验 ⑤实名认证盾牌图标 ⑥移除帖子标签显示+主题筛选仅保留默认分类 ⑦修复点赞按钮误触跳转（`@click.prevent.stop`）⑧头像/昵称直接跳转发帖人主页 |
| 2026-05-20 | 1779236059530 | 🚀 **VASI Phase A+ Box Prompt + 图片打标 + 语法修复（3项合并）**：①核心突破：VLM estimated_size_percent → SAM box prompt，白斑分割从 1块99%→5块0.5-3%（面积14.2%），跳过精炼防止膨胀，tiling集成4级回退 ②图片打标模块（三级标注+隐私脱敏+训练导出） ③vasi_segmentation.py 语法修复 |
| 2026-05-20 | 1779209706351 | 🐛 **Bug修复合集 + 分类更名**：①同城tab显示城市名可切换城市 ②移除同城距离筛选 ③帖子封面图片滑动切换+防误触 ④搜索刷新按钮反馈+防持续高亮 ⑤帖子详情图片黑框→页面背景色+计数器适配 ⑥帖子详情图片滑动切换+防误触 ⑦我的发布跳转→用户主页 ⑧分类"最新资讯"→"科普百科"移至第2位 |
| 2026-05-19 | 1779152495412 | 🐛 VASI草稿隐私修复：`isPrivate: false→true`、serverId捕获、updatePost替代createPost、VasiDetailPage同理 |
| 2026-05-19 | 1779150659307 | ⚠️ 历史列表返回校准值：VASIHistoryItem 新增 final_* 字段，vasi_score/area_percentage 校准优先 |
| 2026-05-19 | 1779124708778 | 🔧 画笔双向替换：皮肤画笔挖白斑 + 白斑画笔挖皮肤，所有画笔默认为替换模式 |
| 2026-05-19 | 1779123813565 | 🔧✨ **VASI Phase A 精确度提升 + 前端优化（5项合并）**：1.VLM升级qwen3-vl-plus+Prompt重构+max_tokens 2000 2.SAM采样64→256+Pipeline重排(VLM→SAM guided) 3.前端AI识别来源徽标+白斑检测详情+API新字段 4.MaskEditor蚂蚁线动画(亮粉虚线+60fps) 5.移除皮肤虚线+文案缩短为40秒 |
| 2026-05-17 | 1778995389730 | 📐 帖子详情页布局优化（去重作者信息、标签合并一行）+ 🔔 通知系统修复（下拉框响应式定位+好友请求通知+关注/收藏容错） |
| 2026-05-17 | 1778994205162 | 🔒 安全修复合集（审计修订后）：NEW-1 PostComment导入缺失 / H-1 content_safety异常放行修复 / H-2 夸张疗效词强制标记flagged / NEW-3 SMS冷却 / C-1 指纹增强(完整SHA256) / NEW-7 RefreshToken String(128) / DB-4 refresh_tokens定期清理 / NEW-5 DB绝对路径 / moderation_status增加flagged / 🎨 NEW-2 BottomNav图标→RemixIcon / NEW-4 ChatAssistantPage图标→RemixIcon / F-3 AppHeader导航/tracker匹配 |
| 2026-05-17 | 1778991500796 | **批量推送 #1–#10（10 项变更）**：1.🖼️海报Logo直角+slogan更新+Tiptap格式解析 2.📐海报头部/底部放大 3.🔗海报网址与品牌名对齐+移至顶部+固定www.subskin.cn 4.📄海报页脚精简(去重复品牌+slogan) 5.📤帖子详情页顶部改造(头像+昵称+关注+分享) 6.🔔通知系统修复(markAllRead反向标记bug+路由跳转bug) 7.📤全局分享功能(PageShareSheet+PageSharePoster+AppHeader集成) 8.📱社区主题下拉框溢出修复(right-0) 9.🖼️海报截图等比缩放不变形(cover模式) 10.🔗所有海报QR码使用当前页面实际URL |
| 2026-05-17 | 1778983716271 | **批量推送 #1–#12（12 项变更）**：1.🖼️图片认证修复 2.📐测评详情布局优化 3.🔔通知修复(async→sync) 4.🏙️同城发帖修复 5.📍定位预加载 6.📝TS类型更新 7.📊VASI评分统一(用final_vasi_score) 8.🔤分型文字修复+仅供参考标签 9.👤头像编辑修复 10.🏷️社区筛选下拉框(主题) 11.📤测评详情发布按钮+草稿跳转 12.🔀评估结果按钮合并(分享至发现) |
| 2026-05-16 | 1778935637579 | **批量推送 #1–#21（21 项变更）**：1.PWA背景色修复 2.通知下拉框定位 3.铃铛staging样式 4.测评重构B1(bodySites枚举+VASI详情页+路由修复) 5.B2(拍照质量反馈) 6.B3(MaskEditor笔刷套索撤销栈) 7.B4(DigitalHuman双视图) 8.B5(BeforeAfterSlider对比页) 9.⚠️B6后端(VASI公式+5新列) 10.放宽肤色检测 11.拍前实时指导 12.1cm参考卡 13.语音拍照 14.未选部位拦截 15.⚠️G算法修复(两阶段白斑识别) 16.MaskEditor点击无响应修复 17.⚠️H面积分母修复(皮肤区域非整图) 18.🚨取消质量门禁 19.⚡AI点选式分割(SAM Promptable) 20.并发race修复+移除精确分析 21.🎨编辑器格式化不生效修复+草稿字段保存 |
| 2026-05-16 | 1778903354131 | 环境同步冷启动：staging深蓝导航栏 + 页面宽度统一max-w-6xl + 更新横幅环境区分 + 部署工作流规范 + DEPLOY_LOG追踪 + version.json lastProdBuildTime |

---

## Staging Deployment History

| Date | BuildTime | Changes |
|------|-----------|---------|
| 2026-06-21 | 1782031263057 | 测评页Step1自动上滑修复：watch flush:'post' + scrollIntoView 替代手动scrollTo |
| 2026-06-09 | 1780940124396 | 🔄 **环境同步**：staging rebuilt 与 production 完全一致（代码相同，仅环境标识不同） |
| 2026-06-08 | 1780939893026 | 社区+测评+登录修复：FollowPlus文字按钮+PostDetailPage头像/私信+LoginModal闪跳修复+VASI照片blur移除 |
| 2026-06-08 | 1780850708209 | 测评页3项Bug修复：VisualFeaturesCard自动换行+MaskEditor blob→dataURL+cancelAssessment取消行为 |
| 2026-06-07 | 1780847849864 | 🔄 **环境同步**：staging rebuilt 与 production 完全一致（代码相同，仅环境标识不同） |
| 2026-06-06 | 1780761444132 | 🎨 **个人中心+全局文本修复**：ProfilePage残留暗色bg移除+5个profile弹窗暗色bg移除+全局`dark:text-gray-100/200/300`移除(覆盖所有已修改页面) |
| 2026-05-16 | 1778945043533 | 🖼️ 图片认证修复 + 📐 布局优化 + 🏙️ 同城发帖修复 + 📍 定位预加载 + 📝 类型更新 |
| 2026-05-16 | 1778928302036 | 🔧 K 修复：移除"精确分析"按钮（CPU 必失败）+ 修复 SAM 并发 RuntimeError |
| 2026-05-16 | 1778926844597 | ⚡ J 改造：SAM Promptable Mode（用户点击 → AI 自动分割），替代失败的 AutoMaskGenerator |
| 2026-05-16 | 1778922709058 | 🚨 设计哲学反转：取消所有质量门禁，让 AI 适应用户的现实拍摄 |
| 2026-05-16 | 1778920569084 | ⚠️ H 修复：白斑面积比例分母改为皮肤区域（不再是整张图）+ 文案优化 |
| 2026-05-16 | 1778919335385 | 🔧 MaskEditor 笔刷/橡皮/套索完全不工作 bug 修复（hidden canvas 0x0 坐标问题） |
| 2026-05-16 | 后端 | ⚠️ G 算法修复：两阶段白斑识别（皮肤前景 + 相对亮度），解决"白色背景被识别为白斑"的核心问题 |
| 2026-05-16 | 1778916478756 | F1-F5 用户反馈合并：放宽 skin_ratio 检测 + 拍前实时指导 + 1cm 参考卡 + 语音拍照 + 未选部位拦截 |
| 2026-05-16 | 1778910274508 | 测评重构 B2-B6 合并：useCameraQuality + MaskEditor + 双视图 DigitalHuman + BeforeAfterSlider + VasiComparePage + 后端真实 VASI 公式（vasi_formula.py + 5 新列） |
| 2026-05-16 | 1778908280016 | 测评重构 B1：bodySites 枚举 + VASI 详情页 + 路由修复 + 相机部位对齐 + PhotoGuide 接通 + 进度条诚实化 |
| 2026-05-16 | 1778904349002 | 通知下拉框定位修复+铃铛按钮staging样式适配 |

## 2026-06-03 — 图片打标页面全面修复

### Staging Deploy (pending production)

**Build time**: TBD

**Changes:**
- **MaskEditor.vue 重写修复**:
  - 修复图片消失问题：img 标签去掉了 `w-full h-auto`，改用 `max-w-none` 防止 CSS 尺寸冲突；添加 `@error` 处理器显示错误状态
  - 修复画笔无响应：添加 `imageLoaded` 守卫，图片加载完成前禁用涂绘工具
  - 添加加载状态（spinner）和错误状态（友好提示）
  - 图片容器添加 `minHeight: 200px` 确保可见区域
  - 画布覆盖层 pos 修复：坐标换算兼容 zoom 变换
- **添加放大缩小全屏控制**：图片底部左下角显示 zoom in/out/fit/fullscreen 按钮
- **ImageLabelingPanel.vue 添加多边形圈选**：
  - 集成 VitiligoContour 组件作为"多边形圈选"工具
  - 工具切换：像素填涂 / 多边形圈选，互斥显示
  - 圈选结果保存为 annotations 随标注提交

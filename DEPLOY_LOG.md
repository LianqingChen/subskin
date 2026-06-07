# SubSkin Deployment Log

> This file tracks all staging and production deployments.
> **Staging changes accumulate here until explicitly pushed to production.**
> **When user says "推送到正式环境", ALL pending items will be pushed together.**

## Pending Changes

| 2026-06-07 | 全站 | **全局暗色背景/字体颜色修复**：从正式环境基线 `7784f18` 还原后，仅移除所有 `dark:bg-gray-*` 和 `dark:text-gray-*` 类。不涉及结构、布局、功能或组件变更。 | 1780765933687 |
| 2026-06-07 | 测评页 + 体检页 | **修复测试环境顶部图片变成熊猫的Bug**：从正式环境 `DigitalHuman-DYEA1R29.js` 反编译还原木头小人SVG身体部位图。①重写`DigitalHuman.vue`（324行，rain/wave模式，12正面+12背面身体部位，butterfly_mascot吉祥物，雨/波/帘动画）；②`AssessmentPage.vue`移除失效的`AssessmentSnapshot`类型导入；③`BodyPartPanel.vue`内联定义`AssessmentSnapshot`类型；④`BodyPartCamera.vue`扩展`captured`事件类型加`meta`参数；⑤`ChatInput.vue`修复早前color修复留下的未闭合字符串。构建产物`DigitalHuman.js` 9806字节 / `.css` 2592字节，与正式环境完全一致（正式版9816字节）。 | 1780790251510 |
| 2026-06-07 | AssessmentPage + CommunityPage | **回滚测试环境：删除多余的 dead code**：①`AssessmentPage.vue`删除无用的`@open-chat`/`@open-report`事件处理（DigitalHuman木头小人不发这些事件）；②`CommunityPage.vue`删除6个硬编码fallback Mock示例帖子（刘哥/李姐/陈姐/张哥/小王/赵姐等测试数据），用于正式环境不存在的数据。CommunityPage bundle 20.7KB → 16.8KB（-19%）。 | 1780826657997 |
| 2026-06-07 | 后端 | **git commit 后端代码**（commit `d27542a`）：103个文件，23,457行插入。仅提交到版本控制，不重启服务、不影响用户。包括：rag.py流式/3模式、vasi.py草稿评估流、recommendation.py新排序公式、sms.py阿里云号码认证、wechat_auth.py OAuth状态管理等。此前已在生产环境运行中。 | (不部署) |
| 2026-06-07 | 社区 | **删除测试环境的「同城分享」功能**（与正式环境对齐）：移除 useGeolocation composable + CityPicker 组件（共 261 行删除），从 CommunityPage 删除「同城」Tab + 城市筛选逻辑 + 城市选择弹窗，从 4 个发帖 Editor (Text/Long/Image/Video) 删除「显示城市」开关 + city/lat/lng 字段。后端接口仍接受 city 参数（向后兼容），前端不再传送。CommunityPage bundle 20.7KB→14.8KB（-29%），9个文件改动，净删除 386 行。Batch 1 反编译验证发现 vasi.ts/community.ts/medical-report.ts/useDrafts.ts/im.ts/moderation.ts 等源码与 prod bundle 一致——community.ts 补齐 2 个方法 (getPublicProfile/getUserPosts)，moderation.ts 改进类型定义。 | 1780830874264 |


## Production Deployment History

> Latest: 2026-06-06 — buildTime: 1780761601399

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

## Environment Sync Baseline

## Environment Sync Baseline

> **2026-05-16 Sync**: Both environments rebuilt from same source code.
> The ONLY difference is the staging nav bar color (dark blue `bg-slate-800` vs white `bg-white`).
> This is the cold start point — all future changes must follow the staging→prod workflow.

| | Staging | Production |
|---|---------|------------|
| BuildTime | 1778986869891 | 1778986691825 |
| Nav bar | Dark blue (`bg-slate-800`) | White (`bg-white`) |
| PWA name | SubSkin [STAGING] | SubSkin更懂你 |
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

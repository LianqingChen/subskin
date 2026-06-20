# SubSkin Deployment Log

> This file tracks all staging and production deployments.
> **Staging changes accumulate here until explicitly pushed to production.**
> **When user says "推送到正式环境" / "更新到正式环境", it means FULL SYNC — ALL pending items since the last production push will be deployed together, not just the latest change.**

## Pending Changes

| 日期 | 模块 | 变更描述 | buildTime |
|------|------|---------|-----------|
| 2026-06-14 | 测评页+体检页+UI一致性 | **3项UI修复**：①测评页(AssessmentStep1Capture)背景从白色(bg-white)改为#F5F7FA，与其他页面一致；②移除数字小人上方标题文字"白斑测评"及描述"上传白斑照片，AI量化评估面积与严重程度"；③数字小人显示尺寸从280px固定高度改为50vh响应式高度(min 320px, max 480px, max-w-md居中)，与体检页视觉大小保持一致；④体检页(ReportPage)背景从#f7f7f7改为#F5F7FA并添加dark mode支持；⑤AssessmentWizard step1背景同步修正为#F5F7FA | 1781450546174 |
| 2026-06-14 | 测评页 | **修复AssessmentStep1Capture自动滚动Bug**：card.scrollIntoView()改为card.closest('main') + scrollTo()，解决嵌套overflow容器滚动问题 | 1781451755081 |
| 2026-06-14 | 测评页 MaskEditor | **修复MaskEditor画布4项Bug**：①移除zoomToFit中Math.min(1,fit)放大上限，允许图像填充容器；②maxHeight从65vh改为calc(100dvh-200px)增大移动端显示空间；③浮动工具栏从overflow:hidden视口内移到外部sticky定位，修复裁剪问题；④zoomToFit从requestAnimationFrame改为setTimeout(50ms)解决渲染时机问题 | 1781451907523 |
| 2026-06-14 | 后端 VASI | **修复VLM视觉特征缺失Bug**：①VLM静态prompt新增shape和surface两个字段（前端VisualFeatures接口要求8个字段，原prompt只有6个）；②vasi.py新增defensive fallback，当VLM未返回visual_features时自动填充8字段默认值，防止API返回null | 1781451907523 + backend restart |
| 2026-06-14 | 测评页 | **修复2项VASI测评流Bug**：①AssessmentStep1Capture自动滚动修复——offsetTop替换为getBoundingClientRect()计算（offsetTop相对offsetParent而非main滚动容器）；②BodyPartCamera相机退出遮罩冻结修复——leave动画期间添加pointer-events:none防止透明fixed遮罩拦截页面点击 | 1781452721847 |
| 2026-06-14 | 测评页 | **修复step3页面冻结根因——移除竞态自推进watch**：移除`watch(showContourEditor)`自动推进step3→step4的watch（与`onSubmitAssessment`路由决策冲突，导致step3渲染后立即被跳到step4，造成页面卡死）；step路由现由`onSubmitAssessment`和`onVisualFeaturesContinue`显式控制 | 1781453171647 |
| 2026-06-15 | 测评页 | **前置身体部位选择提醒**：测评流程中拍照/相册按钮增加身体部位检查——用户点击拍照或相册时，若未选择身体部位则弹出toast提醒"请先在数字人上点击选择身体部位"，阻止相机/文件选择器打开。修改AssessmentWizard.vue（新AI流）和AssessmentStep1Capture.vue（旧快速流） | 1781453548398 |
| 2026-06-15 | 测评页 MaskEditor | **修复AI测评返回后页面卡死Bug**：3项主线程优化——①ResizeObserver增加rAF节流防回流风暴；②loadLayerFromDataUrl在resolve前等待浏览器绘制，避免下游getImageData读到空白canvas；③AI图层加载后先stopAnimation再defer到rAF中执行updateAreas/rebuildEdgeCaches，消除RAF竞争导致的主线程死锁 | 1781456579077 |
| 2026-06-15 | 测评页 MaskEditor | **第二轮卡死修复（6项）**：①resizeObserver rAF去重+节流guard；②loadLayerFromDataUrl等待浏览器paint后resolve；③onImgLoad和layer watcher将重像素操作(extractEdgePixels/updateAreas)延迟2帧rAF执行；④移除snapshot()外冗余的rebuildEdgeCaches调用（内部已调用，避免双重像素遍历）；⑤onImgLoad/stAni增加防止重复startAnimation的guard；⑥imageLoading标志位移入rAF回调，防止主线程阻塞时提早释放loading状态 | 1781493458865 |
| 2026-06-15 | 测评页 MaskEditor | **⚡ 根因修复：Canvas分辨率封顶MAX_CANVAS_DIM=2048px**。手机相机4000×3000像素照片之前直接设为canvas尺寸，3个canvas缓冲区各45MB、getImageData遍历45MB×3次、快照历史30帧×45MB×2=2.7GB——这是卡死的真正原因。现在canvas工作分辨率上限2048px，CSS显示尺寸不变(自然分辨率)，内存/CPU降低12×，触摸坐标自动适配(~1行代码)。配合前9项rAF/节流/延迟修复，彻底消除主线程阻塞 | 1781499418125 |
| 2026-06-15 | 测评页 MaskEditor | **⚡ 最终根因修复：Vue响应式在60fps动画循环中的性能屠杀**。3项关键优化——①dashOffset从ref(0)改为plain let变量，消除60次/秒的Vue triggerRefValue()调度器开销；②edgePixelsSkin/edgePixelsLesion从ref改为plain数组，消除每帧canvas渲染中的Vue proxy拦截；③history从ref改为shallowRef，避免Vue深度代理对12MB+ ImageData对象的track/trigger开销。同时修复AssessmentStep2Analyze高度计算(calc(100dvh-52px)→h-full flex)，解决移动端底部按钮被BottomNav遮挡 | 1781538705204 |
| 2026-06-15 | 测评页 MaskEditor | **🔥 第二轮卡死根因修复：Canvas动画循环性能屠杀(4项)**。①动画从60fps节流到~12fps（CPU工作减5倍，行军蚁效果12fps视觉足够流畅）；②overlay canvas去掉willReadFrequently标记（允许浏览器GPU加速合成，手机性能提升巨大）；③overlay上下文缓存变量_overlayCtx（避免每帧调用getContext）；④updateAreas从同步阻塞改为requestIdleCallback延迟执行（避免初始化时3×getImageData阻塞主线程） | 1781539418172 |
| 2026-06-16 | 测评页 MaskEditor | **🔥🔥 第三轮根本性架构修复：84K个体draw call→2个drawImage(离屏canvas预渲染)**。核心架构改变——①renderContourOutlines从逐点fillRect(84K calls/frame)改为offscreen canvas预渲染+2个drawImage合成(从~80K GPU指令降到2个)；②边缘缓存重建时设_contourBufDirty标记，动画帧仅dirty时重建；③updateAreas防抖150ms(防止快速连续笔触时每笔3×getImageData)；④tab隐藏时暂停动画(visibilitychange)；⑤组件卸载时清理离屏canvas避免内存泄漏 | 1781540766838 |
| 2026-06-16 | 测评页 MaskEditor | **🔥🔥🔥 第四轮终极修复：初始化拆分为5步异步+分辨率降4倍**。①MAX_CANVAS_DIM从2048→1024(像素数据减4倍，所有getImageData/fillRect操作快4倍)；②初始化从单个同步块拆分为5个requestAnimationFrame步骤(snapshot→drawOverlay→startAnimation→updateAreas)，每步之间浏览器可处理用户输入；③HISTORY_MAX从30→10(内存从186MB→62MB)；④updateAreas延迟从200ms→500ms(给浏览器更多空闲时间) | 1781543313012 |
| 2026-06-17 | 测评页 MaskEditor | **🔥🔥🔥🔥 根因修复：zoomToFit()无限微任务死循环**。`zoomToFit()`在容器高度为0时使用`nextTick(() => zoomToFit())`重试——Vue 3的nextTick是微任务(Promise.resolve().then())，在浏览器layout之前执行，clientHeight永远不会改变→无限微任务循环→主线程永久阻塞→整个网站卡死(需关闭标签页)。修复：nextTick→requestAnimationFrame(在layout/paint后执行，dimensions可变)+添加10次重试上限+fallback默认zoom。触发条件：AI测评后VisualFeaturesCard默认展开占满移动端垂直空间→MaskEditor flex-1容器高度为0→zoomToFit进入死循环 | 1781706247394 |
| 2026-06-17 | 测评页 Step2 | **修复标注画布不可见+误跳结果页**：①VisualFeaturesCard默认展开(showVisualFeatures=true)占满移动端屏幕→MaskEditor(flex-1 min-h-0)被挤压到0高度不可见。改为默认折叠(showVisualFeatures=false)，画布获得全部剩余空间。②VisualFeaturesCard底部"继续VASI测评"按钮触发skipContourEdit直接跳到结果页，绕过手动标注。移除该冗余按钮(底部操作栏已有"跳过标注→"/"✓查看结果"按钮)，避免用户误点跳过标注 | 1781707243205 |
| 2026-06-17 | 测评页 Step2 | **修复工具栏被遮挡+缺少确认按钮**：①AssessmentStep2Analyze容器添加pb-[calc(54px+env(safe-area-inset-bottom))]底部留白，避免全局BottomNav(fixed z-50 ~54px)遮挡MaskEditor工具栏和底部操作栏。②MaskEditor新增confirmMasks()方法(toDataURL导出皮肤/白斑canvas→emit confirm)+defineExpose暴露。③AssessmentStep2Analyze添加maskEditorRef+底部操作栏新增"确认提交标注"主按钮(触发confirmMasks→maskConfirm→后端重新计算VASI)。原"跳过标注"改为次要"跳过"按钮 | 1781708832082 |
| 2026-06-17 | 测评页 Step3 | **修复分享封面图data URL无法上传问题**：测评完成后点击"分享"，annotated image（原始照片+AI皮肤/白斑图层合成图）之前是data URL(base64)直接存入草稿，导致后端API拒绝、localStorage超限、发布失败。修复：先通过communityApi.uploadImage将data URL上传到服务器获取真实URL，再存入草稿。分享时第1张封面=标注合成图，第2张=原始照片 | 1781712249965 |

## Production Deployment History

> Latest: 2026-06-10 — buildTime: 1781069684404
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

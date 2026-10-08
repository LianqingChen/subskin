# 公益页单页动线重构设计（2026-09-17）

> 状态：用户已批准，进入实施。
> 背景：公益页（/hospitals）被反馈"凌乱、动线不清晰"。诊断见下，本设计为方案 A「单页动线 · 目录即首页」。

## 诊断（staging 实测 + 代码审查）

1. 巨型头部卡片在所有 tab 重复渲染（标题 + CTA + 统计条，占首屏 1/3），含"0 条已汇总经验"劝退统计。
2. 首屏零实质内容：桌面第一屏 = 头部 + 重型筛选面板；移动端滚近两屏才见第一张卡。
3. 三 tab 两个是死胡同：「病友经验」0 条内容；「体验评价」因 20 人门槛永不生成名次。
4. 卡片噪音重复：「平台收录·附官方来源」「地址待核实·资料核验日期」「还没有病友评价…」在 7 张卡上一模一样。
5. 每卡 5 个动作两行排（看就诊经历/想去/去过/医院资料/对比），无主次。
6. 7 家医院配重型筛选（搜索 + 4 下拉 + 2 复选 + 重置 + 排序）。
7. 出口过多：侧栏 5 项 + 页脚 3 链接 + 每卡 5 动作。

核心矛盾：标题承诺"看病友经验"但 0 条经验；现阶段真实价值是「权威医院目录 + 就诊信息」，动线应先给价值再引导贡献。

## 信息架构与路由

```
/hospitals              主页面（重写）— 单页单动线，无 tab
/hospitals/:key         医院详情页（新增）— 资料 + 该院经验 + 六维说明
/hospitals/treatments   治疗知识（不动）
/hospitals/rules        社区公约（不动）
/hospitals/appeal       评价申诉（不动）
```

- 旧链接 `?hospital=key` 重定向到 `/hospitals/:key`；`?write=1` 场景入口保留（无 key 开就地选择器，有 key 详情页直接开 composer）。

### 主页面动线（自上而下）

1. **紧凑头部**（一行 ~64px）：左「公益 · 找医院，看病友经验」，右「分享就诊经历」主 CTA；统计条删除。
2. **轻筛选条**（默认一行）：搜索框 + 省份 + 城市（选省后可用）；「更多筛选」默认折叠（区县/诊疗服务/只看标记/只看有评价 + 重置），桌面同样折叠。排序小控件放列表头右侧。「补充医院」移到列表底部 + 空态。
3. 收录口径一行小字：「目录由平台收录并附官方来源，核验日期见详情；找不到不代表当地没有诊疗服务，可补充。」
4. **医院卡片列表**（降噪后，见下）。
5. **病友经验区块**：仅当 reviewTotal > 0 时渲染（跨院最新 3-5 条 + 查看全部）；0 条不渲染，页面自然结束。
6. 页脚：治疗知识 / 社区公约 / 评价申诉 / 隐私 + 免责。

### 详情页动线

← 返回 + 医院名 → 标记（想去/去过）+ 对比 → 资料区（地址/科室/诊疗项目/官方来源/核验日期/就诊前 4 问）→ 经验区（该院列表 + 主 CTA「分享就诊经历」，空态 = "还没有经验，成为第一个分享的人"）→ 六维体验折叠（说明 + 有数据时的分布条；门槛不达不显示名次、不提门槛）→ 纠错入口（本机草稿）。

### 移除

- HospitalWorkspace 侧栏三 tab、「体验评价」顶级 tab、详情弹窗（改路由页）、头部统计条。
- HospitalExperiencePanel 组件整体下线（排名表 20 人门槛永不可用；说明文字迁入详情页折叠，git 历史可恢复）。

## 卡片降噪（HospitalCard 重写）

| 现状（每卡重复 ×7） | 新设计 |
|---|---|
| 「平台收录·附官方来源」徽章 | 删除，页面级一行小字统一说明；「病友补充·待核实」**保留**（差异信息） |
| 「地址待核实·资料核验日期」行 | 移到详情页 |
| 「还没有病友评价，欢迎分享…」 | 删除；有评价才显示「N 条病友评价」 |
| 5 动作两行 | 4 个一行：主按钮「查看详情」（整卡可点）+ ♡想去 + ✓去过 + ⚖对比 |

卡片保留：名称、省市·区县、医院类型、科室、诊疗项目 tags（≤3）、N 条评价（有才显示）。

## 数据流（零后端改动，复用全部现有 composable）

- 主页：`useHospitalRegistry` + `useHospitalDirectory`；`useHospitalReviews.load(null)` 仅当 reviewTotal>0 拉跨院流。
- 详情页：按 `:key` 从 registry 定位 → `loadReviews(hospital.id)`；六维 `useHospitalExperience` 折叠展开时才 load。
- 两页共用的评价交互（composer/举报/申诉/helpful/删除/草稿）抽为 `useHospitalReviewFlow` composable，避免 150 行重复。
- 联动：`site-modules.json` 的 公益 desc 删除"六维体验排序"表述（rag.py 启动时读取，需重启后端拾取，纯文本）。

## 空态与错误

- 0 经验：不渲染经验区块、不展示"0 条"统计；详情页空态正向引导。
- 目录加载失败保留 amber 提示条；离线目录保留一行小字；经验流失败给重试。
- 详情页 key 不存在：「未找到该医院」+ 返回目录。

## SEO

- 主页保留 CollectionPage JSON-LD；详情页加 Hospital JSON-LD（name/address/source），meta title = 「{医院名} · 公益」。

## 文件影响

- 重写：`HospitalReviewPage.vue` → 改名 `HospitalsPage.vue`（单页化）、`HospitalCard.vue`、`HospitalPicker.vue`
- 新增：`HospitalDetailPage.vue`、`composables/useHospitalReviewFlow.ts`
- 改：`router/index.ts`（+`/hospitals/:key`）、`web/shared/site-modules.json`（desc）
- 删：`HospitalWorkspace.vue`、`HospitalExperiencePanel.vue`、`HospitalDetail.vue`（内容迁入详情页）
- 不动：composer / report / appeal / compare / create / suggestion / treatments / rules、全部后端与 DB

## 验证

vue-tsc → build staging → 浏览器 375/768/1024/1440 × 明暗走查（主动线、详情直达/返回、写经验入口、对比、标记、空态）→ PWA/version.json → DEPLOY_LOG。

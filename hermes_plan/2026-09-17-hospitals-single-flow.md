# 公益页单页动线重构 — 实施计划（2026-09-17）

设计文档：`docs/specs/2026-09-17-hospitals-single-flow-design.md`（用户已批准）

## 步骤

1. [ ] 读齐依赖：composables（useHospitalRegistry/Directory/Reviews/Notebook/Experience）、types/hospital.ts、HospitalReviewBoard 全量、HospitalReviewCard、HospitalCompare、HospitalQuickReviewCta、composer/create/suggestion、router
2. [ ] 新增 `composables/useHospitalReviewFlow.ts`：composer modal、report modal、publish、helpful、remove、appeal、visitedPrompt、quickPicker（两页共用）
3. [ ] 重写 `HospitalCard.vue`（降噪：主按钮查看详情 + 想去/去过/对比；删重复徽章与文案）
4. [ ] 重写 `HospitalPicker.vue`（轻筛选条：搜索+省/市一行，更多筛选默认折叠，排序入列表头，补充医院沉底）
5. [ ] 新增 `HospitalsPage.vue`（紧凑头部 + 筛选 + 卡列表 + 条件渲染跨院经验区 + 对比 sticky bar + 页脚；?hospital=key 重定向、?write=1 保留）
6. [ ] 新增 `HospitalDetailPage.vue`（返回头 + 资料 + 该院经验 + 六维折叠 + 纠错；key 不存在空态；JSON-LD）
7. [ ] `router/index.ts`：`/hospitals` 指向 HospitalsPage，新增 `/hospitals/:key`
8. [ ] 删除 `HospitalWorkspace.vue`、`HospitalExperiencePanel.vue`、`HospitalDetail.vue`、旧 `HospitalReviewPage.vue`
9. [ ] `web/shared/site-modules.json`：公益 desc 去掉"六维体验排序"表述
10. [ ] vue-tsc → build staging → 重启后端拾取 site-modules（纯文本）→ 浏览器四屏宽×明暗走查 → PWA/version.json
11. [ ] DEPLOY_LOG 记录（Pending Changes + Staging History）

## 约束

- 纯前端（site-modules 为共享文本，重启生效，需告知用户）；无 DB 变更
- 遵循 AGENTS.md：max-w-6xl 容器、RemixIcon、primary-* 色、44px 触控、dark: 全覆、PWA 安全区
- 不展示任何平均分/排名（广告法口径，现状约束保留）

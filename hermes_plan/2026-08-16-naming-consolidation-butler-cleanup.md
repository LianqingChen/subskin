# 2026-08-16 命名统一 + 熊猫移除 + 百科下线 + 管家清理

> 决策来源：用户 2026-08-16 拍板（对小白管家设计评审的反馈）
> 关联：docs/specs/2026-08-14-floating-butler-assistant-design.md、hermes_plan/2026-08-16-butler-3d-creature-drag.md
> 状态：代码与文档已完成，待部署（staging build + 后端 restart）

## 用户三项决策

1. **彻底移除所有熊猫类形象**（小助手外观的 panda / cyber_panda 选项及其静态图）。
2. **命名正式改为新命名体系，永远与网站页面最新命名保持一致**：所有涉及功能命名的地方引用同一套（web/shared/site-modules.json），实时更新。
3. **小白百科真下线**：百科内容融入智能问答/小助手，不再向用户透出独立百科页面/入口。

## 命名单一事实来源（机制）

- **web/shared/site-modules.json** = 站点功能模块命名 + 路径 + 图标 + 关键词的唯一事实来源。
  - 后端 services/rag.py 的管家/知识提示词 + resolve_site_navigation 从它派生（已实现）。
  - 前端 ButlerPanel.vue 快捷入口已读它（已实现）。
  - 本次新增：BottomNav.vue / AppHeader.vue 主导航 label/icon 也改从它读取，去除硬编码命名。
- **web/shared/page-names.json** + constants/page-names.ts = analytics 埋点页面名映射，本次对齐新命名并移除百科条目。
- **AGENTS.md / .agents/skills/** 不再硬编码旧四件套名，改为指向 site-modules.json 并说明"以它为准"。

## 变更清单

### 前端 web/app/src
- [ ] types/index.ts：ButlerMascot 移除 panda/cyber_panda
- [ ] utils/butler.ts：BUTLER_MASCOT_SRC 移除 panda/cyber_panda
- [ ] components/butler/ButlerAppearancePicker.vue：移除熊猫/赛博熊猫选项；卡通3D→卡通形象
- [ ] components/butler/ButlerPanel.vue：text-green-600→primary；Enter 发送/Shift+Enter 换行；加医疗免责声明
- [ ] components/butler/ButlerChat.vue：来源链接无 url 时不渲染 <a href="#">
- [ ] components/butler/FloatingButler.vue：拆分（拖动→useButlerDrag，招呼/漫游→useButlerRoam），降到 ≤400 行
- [ ] components/layout/BottomNav.vue：label/icon 读 site-modules.json
- [ ] components/layout/AppHeader.vue：nav 读 site-modules.json（移除"日记"冗余项）；shareTitle 移除百科分支
- [ ] App.vue：pageTitles 移除 /encyclopedia
- [ ] router/index.ts：/encyclopedia、/encyclopedia/:slug 改为 redirect /
- [ ] constants/page-names.ts：对齐新命名，移除百科条目
- [ ] 删除：views/EncyclopediaNewPage.vue、components/encyclopedia/*（4 个）、api/encyclopedia.ts
- [ ] 删除静态资源：public/panda.png、public/cyber_panda.png

### 后端 web/backend（⚠️ 共享后端，restart 即影响生产）
- [ ] models/user.py：AssistantPreferenceUpdate.mascot Literal 移除 panda/cyber_panda
- [ ] database/models.py：UserAssistantPreference.mascot 注释更新
- [ ] services/analytics.py：移除「浏览百科」UV/PV 统计块（百科页面已下线）
- [ ] services/rag.py：管家提示词补充"个人上下文引用边界"

### 共享 / 文档
- [ ] web/shared/page-names.json：对齐新命名，移除百科条目
- [ ] AGENTS.md：命名表/图标表/AI导航同步改为引用 site-modules.json
- [ ] .agents/skills/ui-audit/SKILL.md：命名表同步
- [ ] docs/specs/2026-08-14-floating-butler-assistant-design.md：补 v2/v3 演进说明
- [ ] DEPLOY_LOG.md：Pending Changes 记录本次变更

## 部署注意

- 前端改动 → npm run build 部署 staging，用户确认后 deploy:prod。
- 后端改动（models/user.py、analytics.py、rag.py）→ systemctl restart subskin-backend，立即影响正式环境，需先提醒用户。
- DB 无 schema 变更（仅 Literal 白名单收紧 + 注释），无需迁移。

## 验收

- [ ] vue-tsc --noEmit 通过
- [ ] 后端单测通过
- [ ] 管家外观选择器不再出现熊猫类选项
- [ ] BottomNav/AppHeader/管家/AI 导航命名一致（问答/测评/白友圈/白斑报告/体检解读/个人中心）
- [ ] /encyclopedia 访问重定向到 /
- [ ] ⚠️ 服务器跑 `pytest tests/backend/services/test_analytics.py tests/backend/services/test_rag.py -x -q`：
  - `test_analytics.py` 的 `nodes` 排序 / `links` 索引 / `top_paths` 三个断言（新命名 + 百科（已下线））
  - `get_feature_usage` 返回 6 项（AI问答/追踪评估/上传体检报告/发帖/评论/点赞，已无「浏览百科」）

## 补充（第二轮，2026-08-16）

- [x] 删除 5 个孤儿熊猫 3D 资源（`panda_opt.glb`/`panda_compressed.glb`/`panda_resized.glb`/`panda_webp.glb` + `cyber_panda_2d.jpg`），保留通用 `draco/` 解码器
- [x] 全屏问答页 `ChatPanel.vue` 接入 `ActionCardView`（渲染 + confirm-action 落库，公开分享二次确认）
- [x] `ActionCardView.vue` 从 `components/butler/` 移至 `components/common/`（共享组件，符合依赖规范）

## 补充（第三轮，2026-08-16）

- [x] 外观选择器只保留金斑蝶、梅花鹿（删 Logo/蝴蝶/卡通3D/图标 + gradient 风格）
- [x] 后端 Literal 收紧 real/deer + circle/rounded，GET/PUT 增加存量旧值兜底
- [x] 金斑蝶翅膀扇动改非对称拍翅 + 前后翅相位差（更自然）
- [x] 梅花鹿提亮毛色 + 纤细体型 + 腿部动画（更灵动）

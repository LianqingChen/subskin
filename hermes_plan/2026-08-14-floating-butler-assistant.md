# 小白管家（漂浮 AI 助手）实施记录

> 日期: 2026-08-14
> 设计文档: `docs/specs/2026-08-14-floating-butler-assistant-design.md`
> 状态: P1-P5 全部完成，已部署 staging（buildTime 1786716785151），待用户验证

## 实施清单

### 后端（共享后端，已随 restart 生效）
- `web/backend/services/rag.py`
  - `_build_butler_prompt()` — 管家统一人格（知识/导航/陪伴/危机路由 + 隐私/政治/受控执行红线）
  - `SITE_ROUTE_MAP` + `resolve_site_navigation()` — 确定性站内导航（≤3 条）
  - `_build_llm_messages()` 新增 butler 分支（含 user_context 注入 + 隐私强调）
  - `_mode_temperature()` — knowledge 0.3 / butler 0.5 / counseling 0.7
  - `answer_question()` 非流式返回 `navigation`
  - 知识提示词导航表清理：移除已下线 IM 路由 `/messages` `/contacts`；`SITE_FEATURE_KEYWORDS`/`SITE_FEATURE_PHRASES` 同步清理
- `web/backend/api/rag.py` — `_stream_rag_response` 但 `mode=="butler"` 时 yield `{"type":"navigation","items":[...]}` SSE 事件
- `web/backend/models/rag.py` — `NavSuggestion` 模型；`QuestionResponse.navigation`
- `web/backend/database/models.py` — 新表 `user_assistant_preferences`（additive，create_all 自动建表）
- `web/backend/models/user.py` — `AssistantPreferenceUpdate`（Literal 白名单）/`AssistantPreferenceResponse`
- `web/backend/api/user.py` — `GET/PUT /api/user/assistant-preference`（auth 必需，字段级更新）

### 前端（web/app，已部署 staging）
- `src/types/index.ts` — `NavSuggestion`、`ButlerPreference` 及枚举类型
- `src/api/butler.ts` — 偏好读写 API
- `src/api/chat.ts` — `SSEStreamReader.onNavigation` 处理 `navigation` 事件
- `src/stores/butler.ts` — 面板开合/模式/导航建议/偏好（云端优先，localStorage 兜底）
- `src/composables/useButlerChat.ts` — 管家聊天（共享 useChatStore 会话；butler/counseling 模式；附件临时上传；confirm-action）
- `src/utils/butler.ts` — 形象素材/尺寸/样式映射
- `src/components/butler/FloatingButler.vue` — 全局 FAB（`/` 隐藏，移动端避让 BottomNav+安全区）
- `src/components/butler/ButlerPanel.vue` — 面板壳（头部/问候/常用入口/输入栏+附件）
- `src/components/butler/ButlerChat.vue` — 消息区（气泡/来源/导航芯片/行动卡片）
- `src/components/butler/ActionCardView.vue` — VASI/报告/日记行动卡片（公开分享二次确认）
- `src/components/butler/ButlerAppearancePicker.vue` — 外观选择器（形象默认 Logo、蝴蝶次选）
- `src/App.vue` — 挂载 `<FloatingButler />`
- `src/views/ProfilePage.vue` — 设置区新增「小白管家」入口

### 测试
- `tests/backend/services/test_rag.py` — 新增 8 项 butler 测试（提示词红线/过期路由清理/导航解析/温度/上下文注入），18 passed
- `vue-tsc --noEmit` 通过
- 冒烟：butler 导航回答 ✓、PII 引导个人中心 ✓、navigation 事件 ✓、政治词入口拦截 ✓、偏好接口鉴权 ✓、新表已建 ✓

## 遗留/后续
- 全屏小白助手（ChatPanel）尚未接入 `ActionCardView`（目前仅管家面板渲染行动卡片）
- `navigation` SSE 事件目前仅 butler 模式下发

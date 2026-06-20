# 通知系统 Plan

## Goal
- 替换 AppHeader 眼睛图标为铃铛图标
- 实现消息通知功能：评论、点赞、收藏、关注、网站通知、风控通知

## Phases

### 1. 后端：Notification 模型 ✅ → pending
- `notifications` 表：id, user_id, type, title, body, ref_type, ref_id, is_read, created_at
- 类型枚举：like, comment, follow, bookmark, collect, system, moderation
- API：GET /api/notifications (列表), GET /api/notifications/unread-count, POST /api/notifications/{id}/read, POST /api/notifications/read-all

### 2. 后端：触发通知 hook
- like: 点赞时通知帖主
- comment: 评论时通知帖主
- follow: 关注时通知被关注者
- bookmark: 收藏时通知帖主
- 风控/moderation: 用户被禁言/封禁时通知

### 3. 前端：API
- src/api/notifications.ts

### 4. 前端：AppHeader UI
- 小眼睛 → 铃铛
- 下拉面板：未读红点 + 列表 + 已读/全部已读

### Files to modify
- web/backend/database/models.py
- web/backend/api/notifications.py (new)
- web/backend/api/social.py
- web/backend/app/main.py
- web/app/src/api/notifications.ts (new)
- web/app/src/components/layout/AppHeader.vue

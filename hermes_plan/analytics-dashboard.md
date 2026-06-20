# Task Plan: Analytics Dashboard ("驾驶舱")

## Goal
Add an admin-only analytics dashboard tab to the Encyclopedia page, showing UV/PV, cumulative users, conversion funnels, feature usage metrics.

## Phases

### Phase 1: Backend — Admin permission + Analytics API
- **Status:** not_started
- **Goal:** Create analytics API endpoints gated by admin phone numbers
- **Files to create/modify:**
  - [ ] `web/backend/api/analytics.py` — new router with dashboard endpoints
  - [ ] `web/backend/app/main.py` — register new router
  - [ ] `web/backend/database/models.py` — add DailyAnalytics model for pre-aggregation
  - [ ] `web/backend/services/analytics.py` — aggregation query service
- **Success criteria:**
  - [ ] `GET /api/analytics/overview` returns total users, today UV/PV, new users today
  - [ ] `GET /api/analytics/page-views` returns UV/PV by page for date range
  - [ ] `GET /api/analytics/funnel` returns conversion funnel data
  - [ ] `GET /api/analytics/feature-usage` returns per-feature usage counts
  - [ ] `GET /api/analytics/trend` returns daily trend data (7d/30d)
  - [ ] All endpoints return 403 for non-admin users
  - [ ] Admin check uses phone-based allowlist

### Phase 2: Frontend — Admin detection + Dashboard Tab
- **Status:** not_started
- **Goal:** Add "驾驶舱" tab visible only to admin users
- **Files to modify:**
  - [ ] `web/app/src/views/EncyclopediaPage.vue` — add dashboard section + tab
  - [ ] `web/app/src/composables/useAdmin.ts` — new composable for admin check
  - [ ] `web/app/src/api/analytics.ts` — API client for analytics endpoints
- **Success criteria:**
  - [ ] "驾驶舱" tab only appears for admin users
  - [ ] Non-admin users see no trace of the dashboard

### Phase 3: Frontend — Dashboard Charts & UI
- **Status:** not_started
- **Goal:** Build ECharts-based dashboard with all metrics
- **Files to create:**
  - [ ] `web/app/src/components/analytics/AnalyticsDashboard.vue` — main dashboard component
  - [ ] `web/app/src/components/analytics/MetricCard.vue` — reusable metric card
  - [ ] `web/app/src/components/analytics/TrendChart.vue` — line chart for trends
  - [ ] `web/app/src/components/analytics/FunnelChart.vue` — funnel visualization
  - [ ] `web/app/src/components/analytics/PageViewChart.vue` — page view breakdown
- **Success criteria:**
  - [ ] Overview cards: total registered users, today UV, today PV, new users today
  - [ ] 7d/30d UV/PV trend line chart
  - [ ] Conversion funnel: visit → register → login → use feature
  - [ ] Per-feature UV bar chart (AI问答, 上传照片, 上传报告, 发帖, 评论, 点赞, 百科浏览)
  - [ ] Page view ranking table

### Phase 4: Deploy & Verify
- **Status:** not_started
- **Goal:** Build, deploy, and verify everything works
- **Success criteria:**
  - [ ] Backend restarts without errors
  - [ ] Frontend builds cleanly
  - [ ] Admin user sees dashboard tab
  - [ ] Dashboard loads real data

## Decisions Log
| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-04-21 | Phone-based admin allowlist (not DB is_admin) | Simpler, no migration needed, only 2 admins |
| 2026-04-21 | Pre-aggregate into DailyAnalytics table | UserEvent can grow large; daily rollup is efficient for SQLite |
| 2026-04-21 | ECharts (already in deps) | Already installed, capable, no new dependency |
| 2026-04-21 | Dashboard as tab in EncyclopediaPage | User requested "在白白百科后面再加一个tab页" |

## Architecture Notes

### Admin Check Strategy
Frontend: composable checks `authStore.user.phone` against allowlist
Backend: dependency `get_admin_user` checks user.phone against same allowlist

### Data Aggregation Strategy
- `DailyAnalytics` table: pre-aggregated daily metrics (date, metric_key, metric_value, dimensions_json)
- Populated by: (1) query on demand from existing tables, (2) future scheduled job
- For v1: query on demand from UserEvent + domain tables with date filters + indexed lookups
- UserEvent has indexes on: uid, session_id, event_type, element_id, created_at — sufficient for date-range queries

### API Design
```
GET /api/analytics/overview          → { total_users, today_uv, today_pv, new_users_today, active_users_7d }
GET /api/analytics/trend?days=30     → { dates: [...], uv: [...], pv: [...], new_users: [...] }
GET /api/analytics/page-views?days=7 → { pages: [{ path, uv, pv }] }
GET /api/analytics/funnel?days=30    → { steps: [{ name, count, rate }] }
GET /api/analytics/feature-usage?days=7 → { features: [{ name, uv, pv }] }
```

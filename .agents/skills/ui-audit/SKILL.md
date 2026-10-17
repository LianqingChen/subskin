---
name: ui-audit
description: "SubSkin UI/UX 一致性审计 — 布局、颜色、组件复用、命名规范检查"
---

# UI Audit Skill

> SubSkin UI/UX 一致性审计 — 布局、颜色、组件复用、命名规范、多端与分享海报检查
>
> **触发词**: UI审计、UI audit、设计审查、视觉一致性、design QA、UX review
> **权威规范文档**: `/root/subskin/docs/specs/2026-10-17-subskin-design-system.md`

This skill provides a standardized checklist and methodology for auditing the SubSkin web app's UI/UX consistency. Use this whenever you need to review UI quality, check for design violations, or verify that new features follow the **SubSkin Tech Design System (Cursor & GitHub Style + Clinical Warmth)**.

## Audit Dimensions

Run through each dimension below. For each, flag violations as P0 (blocking), P1 (must fix), or P2 (should fix).

---

### 1. Layout Container & Multi-Device Consistency

**Rule**:
- All content pages use `.page` (`72rem`), `.page-wide` (`80rem`), or `.page-narrow` (`48rem`) defined in `src/styles/main.css`.
- Fixed bottom bars MUST include `.app-fixed-x` (`left: var(--app-sidebar-w); right: 0;`) so they do not overlap `AppSidebar` on desktop (`≥1024px`).
- Mobile bottom sheets (`fixed inset-x-0 bottom-0`) MUST constrain width on desktop/tablet (`sm:max-w-md sm:mx-auto sm:bottom-6 sm:rounded-2xl`).

**Check**:
- Verify outer page containers use `.page`, `.page-wide`, or `.page-narrow` (never hardcoded `max-w-*` or `#f5f7fa` backgrounds)
- Check `fixed` bottom elements for `.app-fixed-x` or `sm:max-w-*`

### 2. Sidebar Consistency

**Rule**: Desktop in-page sidebars must be `w-52`, with collapse toggle button on the right edge. List items use `px-3 py-2.5 rounded-lg`.

**Check**:
- Sidebar width: `w-52` only (NOT `w-56`, NOT `w-64`)
- Active item: `bg-primary-50 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300 font-medium rounded-lg`
- Inactive item: `text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800 rounded-lg`

### 3. Theme Color & Dark Mode Compliance

**Rule**:
- NO hardcoded Tailwind native colors (`bg-blue-*`, `text-green-*`, `bg-purple-*`, etc.) for brand UI. Use `primary-*` CSS variables (`#0d9488` / `#14b8a6` / `#0f766e`).
- Global canvas is `#f6f8fa` (light) / `#0b0f17` (dark); primary surface is `#ffffff` (light) / `#111827` (`dark:bg-gray-900` or `.card`).
- Every text, border, input, card, and modal MUST have complete `dark:*` classes.

**Check**:
- grep for `bg-blue-`, `text-blue-`, `bg-purple-`, `bg-pink-`, `bg-cyan-`
- Medical semantic colors (`emerald-*` = good, `amber-*` = stable/warning, `rose-*`/`red-*` = danger) are exempt ONLY for clinical status/score displays
- Category badges MUST use `getCategoryColor()` from `@/utils/colors`

### 4. Icon Purity (RemixIcon Only) & Component Reuse

**Rule**:
- 100% of UI icons MUST use RemixIcon (`<i class="ri-*"></i>`). Zero inline `<svg>` icons (except anatomical body maps and mask canvas) and zero emoji icons (`✨`, `🔥`, etc.).
- Shared patterns must use the project's common components (`UserAvatar`, `ConfirmDialog`, `MedicalDisclaimer`, `EmptyState`, `LoadingSpinner`).

### 5. WebView & Cross-Browser Compatibility (WeChat & Huawei Browser)

**Rule**:
- `<input class="flex-1">` inside flex containers MUST have `min-w-0`.
- Custom `100dvh`/`100svh` rules MUST have a preceding `100vh` fallback.
- Canvas code MUST NEVER call `ctx.roundRect()` directly — always use `traceRoundedRect()` (`arcTo` implementation).
- Font stacks (including Canvas `ctx.font`) MUST include `"HarmonyOS Sans SC"` and `"PingFang SC"`.

### 6. Typography Hierarchy & Tabular Numerals

**Rule**:
- Page title (`h1`): `.page-title` (`text-lg md:text-xl font-bold tracking-tight`)
- Section title (`h2`): `.section-title` (`text-base md:text-lg font-semibold tracking-tight`)
- All numerical metrics, VASI scores, percentages, and dates MUST use `tabular-nums`.

### 7. Medical Disclaimer Presence

**Rule**: EVERY content page, report, and generated poster MUST include a medical disclaimer.

### 8. Naming Consistency (Single Source of Truth)

**Rule**: Module names must be consistent across ALL surfaces (nav, title, header, body, share sheets, posters). 命名唯一事实来源：`web/shared/site-modules.json` 与 `web/shared/page-names.json`。

| Module | Official Name | Route | Forbidden Legacy Names in UI/Posters |
|--------|---------------|-------|--------------------------------------|
| QA / AI Chat | 问答 | `/` | 小白助手 |
| Diary & Tracker | 日记（白斑日记 / 白斑记录 / 变化报告） | `/assessment` | 小白追踪、健康手账、手帐、测评、小白日记、AI病情日记 |
| Exam Report | 体检解读 | `/assessment/exam` | — |
| Community | 发现 | `/community` | 白友圈、小白社区、病友社区、小白知识库 |
| Hospitals | 就医经验 | `/hospitals` | 医评、公益 |
| Contribution | 同行 | `/contribution` | — |
| Care | 调养 | `/care` | 护理优选 |
| Profile | 个人中心 / 我的 | `/profile` | — |

### 9. External Share Pages & Generated Posters

**Rule**:
- `PageSharePoster.vue`, `SkinReportPoster.vue`, `DiaryWeeklyPoster.vue`, `SkinReportSharedPage.vue`, `CollectionSharePage.vue` must use the unified `#0f766e` → `#0d9488` header gradient, `#f8fafc` inner cards, `'SubSkin · 白癜风病友的AI记录和分享社区'` subtitle, official module names, valid QR code routes (never `/diary` or `/tracker`), and `traceRoundedRect`.

---

## Audit Execution

To run a full audit:

```
1. Check all dimensions above using grep, AST-grep, and manual code review
2. Flag violations with: Page → File → Line → Issue → Priority (P0/P1/P2)
3. Prioritize P0 (blocking) items for immediate fix
4. Reference this SKILL.md for the correct pattern to apply
```

## Shared Utilities Reference

- **Colors**: `@/utils/colors` — `getCategoryColor(name)`, `SCORE_COLORS`
- **Post Actions**: `@/composables/usePostActions` — `toggleLike(post)`, `toggleBookmark(post)`
- **Components**: See Component Reuse table above

## Design System Quick Reference

```
Container:  max-w-6xl mx-auto px-4  (pages)
            max-w-4xl mx-auto px-4  (details)
Sidebar:    w-52, collapse right-edge toggle
Card:       card p-5  (default)
Buttons:    btn-primary, btn-secondary, btn-ghost
Badges:     badge, badge-primary, badge-success
Headings:   section-title, section-desc
Dark mode:  ALL elements need dark: variants
Safe area:  safe-bottom for fixed-bottom elements
```

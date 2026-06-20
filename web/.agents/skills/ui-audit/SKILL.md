# UI Audit Skill

This skill provides a standardized checklist and methodology for auditing the SubSkin web app's UI/UX consistency. Use this whenever you need to review UI quality, check for design violations, or verify that new features follow established conventions.

## Trigger Phrases

- "audit the UI", "UI audit", "check UI consistency"
- "review design", "design audit", "UX review"
- "check visual consistency", "verify design system compliance"
- "pre-merge UI check", "design QA"

## Audit Dimensions

Run through each dimension below. For each, flag violations as P0 (blocking), P1 (must fix), or P2 (should fix).

---

### 1. Layout Container Consistency

**Rule**: All content pages use `max-w-6xl mx-auto px-4`. Detail pages (post detail, article) may use `max-w-4xl`.

**Check**:
- grep for `max-w-` on every view page
- Verify horizontal padding is `px-4` (NOT `px-3`, NOT missing)
- Detail pages should be `max-w-4xl mx-auto px-4`

### 2. Sidebar Consistency

**Rule**: Desktop sidebars must be `w-52`, with collapse toggle button on the right edge (`absolute -right-3 top-1/2`). List items use `px-3 py-2.5 rounded-lg`.

**Check**:
- Sidebar width: `w-52` only (NOT `w-56`, NOT `w-64`)
- Collapse button: small bar at sidebar right edge with chevron icon
- Active item: `bg-primary-50 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300 font-medium rounded-lg`
- Inactive item: `text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800 rounded-lg`

### 3. Theme Color Compliance

**Rule**: NO hardcoded Tailwind native colors (`bg-blue-*`, `text-green-*`, `bg-purple-*`, etc.). Use `primary-*` CSS variables instead.

**Check**:
- grep for `bg-blue-`, `text-blue-`, `bg-green-`, `text-green-`, `bg-purple-`, `bg-pink-`, `bg-cyan-`, `bg-yellow-`
- Medical semantic colors (green=good, red=danger) are exempt ONLY for score displays
- Category badges MUST use `getCategoryColor()` from `@/utils/colors`

### 4. Component Reuse

**Rule**: Shared patterns must use the project's common components.

| Component | File | Replaces |
|-----------|------|----------|
| UserAvatar | `components/common/UserAvatar.vue` | Inline avatar divs (initial + image + error fallback) |
| ConfirmDialog | `components/common/ConfirmDialog.vue` | Custom delete modals, browser `confirm()` |
| MedicalDisclaimer | `components/common/MedicalDisclaimer.vue` | Inline disclaimer text blocks |
| EmptyState | `components/common/EmptyState.vue` | Custom empty state UIs |
| LoadingSpinner | `components/common/LoadingSpinner.vue` | Inline "加载中..." text |

**Check**:
- grep for `w-* h-* rounded-full bg-primary-100` (inline avatar pattern)
- grep for `confirm(` (browser confirm dialog)
- grep for `bg-amber-50.*border.*amber-200` (inline disclaimer)
- All like/bookmark logic must use `usePostActions()` composable

### 5. Card Padding Consistency

**Rule**: All cards use `card p-5` by default. Use `card p-4` for compact lists, `card p-6` for content-heavy forms.

**Check**:
- grep for `card p-3`, `card p-4`, `card p-5`, `card p-6`
- Flag deviations from the expected pattern

### 6. Typography Hierarchy

**Rule**: Consistent heading sizes across pages:

| Element | Mobile | Desktop |
|---------|--------|---------|
| Page title (h1) | `text-2xl font-bold` | `text-3xl font-bold` |
| Section title (h2) | `text-lg font-semibold` | `text-xl font-semibold` |
| Card title (h3) | `text-base font-medium` | `text-base font-medium` |
| Body text | `text-sm` | `text-sm` or `text-base` |

**Check**:
- Verify headings follow the hierarchy on each page
- No `text-lg` for main page titles (too small)

### 7. Medical Disclaimer Presence

**Rule**: EVERY content page MUST include a medical disclaimer via `<MedicalDisclaimer />`.

**Check**:
- ChatPage ✅
- TrackerPage ✅
- CommunityPage ✅
- PostDetailPage ✅
- ProfilePage ✅
- HomePage ✅
- EncyclopediaPage (if it exists, it must have one)

### 8. Naming Consistency

**Rule**: Module names must be consistent across ALL surfaces (nav, title, header, body).

| Module | Correct Name | Wrong Names |
|--------|-------------|-------------|
| AI Chat | 小白助手 / AI助手 | — |
| Tracker | 小白追踪 / 手账 | 健康手账 (internal label OK) |
| Community | 小白社区 / 发现 | 病友社区 |
| Encyclopedia | 小白百科 | 白白百科 |
| Profile | 我的 | — |

**Check**:
- grep for "白白百科", "病友社区" — flag and replace

### 9. Interaction Flow Integrity

**Rule**: No broken interaction chains. User actions must have clear paths.

**Check**:
- ChatInput "健康手账" button → must navigate to `/tracker` (NOT do inline upload)
- ChatInput "体检报告" button → must navigate to `/tracker?tab=reports`
- Non-logged-in users see consistent login prompts across modules
- BottomNav scroll hide behavior works on all pages

### 10. Spacing Consistency

**Rule**: Vertical spacing between major sections is `space-y-6`.

**Check**:
- CommunityPage main container should have `space-y-6` (NOT `space-y-3`)
- All pages should use consistent vertical rhythm

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

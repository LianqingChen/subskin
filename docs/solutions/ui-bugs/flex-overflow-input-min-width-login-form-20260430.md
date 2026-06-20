---
module: Login Form
date: 2026-04-30
problem_type: ui_bug
component: frontend_stimulus
symptoms:
  - "\"获取验证码\" button pushed beyond right edge of other form fields on mobile"
  - "Verification code input row overflowed its flex container"
  - "Right edge of button visibly misaligned with other full-width inputs"
root_cause: config_error
resolution_type: code_fix
severity: medium
tags: [tailwind, flexbox, min-width, input, mobile-layout, browser-defaults]
---

# Troubleshooting: Flex Input Overflow Due to Browser Default min-width

## Problem

On the login modal (mobile view), the verification code input (`flex-1`) caused the flex container to overflow, pushing the "获取验证码" button past the right edge of other form fields. All other fields (`w-full`) were properly aligned within the modal.

## Environment

- Module: Login Form (`PhoneLoginForm.vue`, `EmailLoginForm.vue`)
- Framework: Vue 3 + Tailwind CSS (Vite)
- Affected Component: Verification code row (`<div class="flex gap-2">`)
- Date: 2026-04-30

## Symptoms

- "获取验证码" button pushed to screen edge, visually beyond the right edge of other form inputs
- Fixed `w-32` (128px) was too wide on narrow screens, `w-24` (96px) was too narrow
- Reverting to `flex-1` still caused overflow — the input refused to shrink below a certain width

## What Didn't Work

**Attempted Solution 1:** Changed `flex-1` → `w-32` (128px fixed width)
- **Why it failed:** On mobile (375px viewport, 295px usable width in modal), 128px + ~100px button + 8px gap = 236px fits, but the button appeared misaligned because there was ~60px empty space to the right. Not a real overflow, but visually wrong.

**Attempted Solution 2:** Narrowed to `w-24` (96px fixed width)
- **Why it failed:** Too short — left 132px of wasted space, making the input look disproportionately tiny.

**Attempted Solution 3:** Reverted to `flex-1` without `min-w-0`
- **Why it failed:** Browser's implicit `size=20` attribute on `<input type="text">` sets a minimum width (~280px for CJK characters), which exceeds the available space (193px) after the button + gap. The flex container overflowed past the modal boundary.

## Solution

Add `min-w-0` to the input's Tailwind classes. This sets `min-width: 0px`, overriding the browser's default minimum width derived from the implicit `size=20` attribute.

**Code changes:**

In `PhoneLoginForm.vue` line 95 and `EmailLoginForm.vue` line 96:

```html
<!-- Before (broken — flex container overflows): -->
<input class="flex-1 rounded-lg border ..." />

<!-- After (fixed — input can shrink below browser default): -->
<input class="flex-1 min-w-0 rounded-lg border ..." />
```

Full verification code row:

```html
<div class="flex gap-2">
  <input v-model="phoneForm.code" type="text" maxlength="6" placeholder="6位验证码"
    class="flex-1 min-w-0 rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm outline-none transition-colors focus:border-primary-500 focus:ring-2 focus:ring-primary-500 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100" />
  <button type="button" :disabled="countdown > 0"
    class="shrink-0 rounded-lg bg-primary-50 px-3 py-2 text-sm font-medium text-primary-600 ..."
    @click="sendPhoneCode">{{ countdown > 0 ? `${countdown}s` : '获取验证码' }}</button>
</div>
```

## Why This Works

1. **Root cause:** Browsers give `<input type="text">` an implicit `size=20` attribute by default, which translates to a `min-width` of approximately 20 characters. For CJK fonts at `text-sm` (14px), this is roughly 280px. In a flex container with `flex-1` (which sets `flex: 1 1 0%`), the input _tries_ to shrink but is blocked by this browser-imposed minimum width.

2. **Why the fix works:** `min-w-0` in Tailwind sets `min-width: 0px` via CSS, explicitly overriding the browser's implicit minimum. This allows the `flex-1` input to shrink to the actual available space (container width minus button width minus gap).

3. **Underlying issue:** Flexbox's `flex-shrink: 1` cannot override the browser's intrinsic `min-width` on form elements. The CSS `min-width` property must be explicitly set to `0` to allow the element to shrink below its content-based minimum.

## Prevention

- **Rule:** When using `flex-1` on `<input>`, `<select>`, or `<textarea>` elements in a constrained flex container, always add `min-w-0` to allow proper shrinking.
- **Pattern:** `<input class="flex-1 min-w-0 ..." />` — this should be the default pattern for any flex item that is an interactive form element.
- **Catch early:** If a flex layout looks correct on desktop but overflows on mobile, suspect browser-default `min-width` on form elements as the first thing to check.

## Related Issues

No related issues documented yet.

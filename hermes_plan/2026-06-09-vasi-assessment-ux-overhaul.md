# VASI Assessment Module UX Overhaul Plan

> Created: 2026-06-09
> Status: IN PROGRESS

## Problem Statement

The VASI assessment module has fragmented UX: users must scroll between scattered sections (body selector → upload → results), the brush tool is complex, and there's duplicate state management across TrackerPage (986 lines) and AssessmentSection (562 lines).

## Architecture Decisions

### Current State (Problems)
1. **TrackerPage.vue (986 lines)** — Dead code. `/tracker` redirects to `/assessment`, so this is never rendered. Contains duplicate logic with AssessmentSection.
2. **AssessmentSection.vue (562 lines)** — Over 400-line component limit. Mixes wizard UI, upload, mask editing, and history in one file.
3. **useVasiAssessment.ts (635 lines)** — Over 200-line composable limit. Contains ALL assessment state + history + upload + contour + quality check logic.
4. **MaskEditor.vue (854 lines)** — Over 400-line component limit. Raw canvas drawing without UX guidance.

### Target Architecture

```
AssessmentPage.vue (≤ 200 lines) - Layout shell + step orchestration
├── StepSelectBody.vue (≤ 200 lines) - Step 1: DigitalHuman body selection
├── StepUploadPhoto.vue (≤ 200 lines) - Step 2: Photo upload/quality check
├── StepAnalyzing.vue (≤ 150 lines) - Step 3: AI analysis progress
├── StepMaskEditor.vue (≤ 200 lines) - Step 4: Mask editing wrapper
│   └── MaskEditor.vue (refactored, ≤ 400 lines)
├── StepResult.vue (≤ 200 lines) - Step 5: VASI score + interpretation
└── AssessmentHistory.vue (≤ 200 lines) - History list with pagination

Composables (split from useVasiAssessment):
├── useVasiUpload.ts (≤ 200 lines) - Upload, quality check, body site
├── useVasiResult.ts (≤ 200 lines) - Assessment result, history, CRUD
└── useVasiMask.ts (≤ 200 lines) - Mask/contour editing state
```

## Implementation Phases

### Phase 1: Architecture Cleanup (A)
- [x] Analyze current codebase structure
- [ ] Strip TrackerPage.vue to minimal redirect
- [ ] Split useVasiAssessment.ts into 3 smaller composables
- [ ] Fix all import references

### Phase 2: Wizard Flow (B)
- [ ] Create AssessmentWizard.vue with step orchestration
- [ ] Extract StepSelectBody.vue from DigitalHuman + BodyPartPanel
- [ ] Extract StepUploadPhoto.vue from AssessmentSection upload area
- [ ] Create StepAnalyzing.vue for AI processing progress
- [ ] Extract StepMaskEditor.vue wrapping MaskEditor
- [ ] Extract StepResult.vue for VASI score display
- [ ] Extract AssessmentHistory.vue from AssessmentSection history section
- [ ] Update AssessmentPage.vue to use wizard flow

### Phase 3: Brush Tool Simplification (C)
- [ ] Add auto-brush selection (skin brush auto-selected after AI layers load)
- [ ] Add area progress indicator (X% of region is lesion)
- [ ] Add animated onboarding tooltip for first-time users
- [ ] Improve mobile touch: pinch-zoom vs draw gesture separation
- [ ] Split MaskEditor into MaskEditorCore (canvas logic) + MaskEditorToolbar (UI controls)

### Phase 4: AI Enhancement (D)
- [ ] Add body part detection hint on photo upload
- [ ] Add "low confidence → guide to brush editing" auto-nudge
- [ ] Add "AI suggest fill" button in mask editor (for low-confidence areas)

### Phase 5: Result Display (E)
- [ ] Sticky result card at top after assessment
- [ ] Mini sparkline trend in history cards
- [ ] "Compared to last time" highlight in history
- [ ] One-tap diary creation from result

## File Changes Summary

### Delete/simplify
- `TrackerPage.vue` → Strip to redirect-only (< 10 lines)

### Split
- `useVasiAssessment.ts` (635 lines) → `useVasiUpload.ts` + `useVasiResult.ts` + `useVasiMask.ts`
- `AssessmentSection.vue` (562 lines) → `AssessmentWizard.vue` + 5 step components + `AssessmentHistory.vue`
- `MaskEditor.vue` (854 lines) → Split canvas logic and toolbar

### Modify
- `AssessmentPage.vue` → Use wizard layout
- `BottomNav.vue`, `AppHeader.vue` → Ensure `/tracker` and `/assessment` both show correct tab

### Route additions
- Add `/tracker/vasi/:id` route for VasiDetailPage (currently missing!)
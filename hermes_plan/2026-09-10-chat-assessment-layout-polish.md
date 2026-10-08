# Local layout polish

User-specified changes: conversation disclaimer flows below answers; remove space above body illustration; slim record controls; make record/recent panel scroll independently over illustration. Preserve current design and functional/measurement behavior.

Approach: normal document-flow disclaimer within answer content; native scroll overlay (not whole-card pointer interception), fixed body scene, compact visible controls with >=44px touch targets. Scope frontend only; staging deploy required, production unchanged.

1. Inspect layout constraints — complete.
2. Implement scoped layout changes — complete.
3. Regression/type/build/staging and asset checks — complete.

Final staging build: 1789000322846. Four frontend files changed. Existing 13 frontend regressions, type-check, build and public/PWA/health checks passed. Browser/device visual validation remains unavailable; no screenshot claim. Production frontend unchanged.

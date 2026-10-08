# 白斑双图对比与首页留白
## Goal
Small top inset for the body model; compact expanded-panel spacing; preselect body site before entering 白斑对比; exactly two photos or two saved same-site observations.
## Phases
- Inspect layout and all active photo/history comparison paths: complete.
- Implement body-site gate, two input methods and exact-pair validation; log/type-check/staging deployment: complete.
- Verify layout at 375/768/1024/1440, gate/redirect, pair limits, history filtering and submission; PWA/health/artifact integrity: complete.
## Decisions
- User-specified flow is approved; reuse existing comparison endpoints without backend changes.
- 8px body-model top inset on mobile; eliminate 16px gap below the panel toggle and reduce panel bottom padding.
- Reject oversized batches without silently truncating them. Keep single-photo journal capture available from the home gallery.

## Outcome
Completed and deployed to staging 1789487789740. Production unchanged. Browser/API checks and layout screenshots recorded in the verification report.

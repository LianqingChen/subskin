# Task Plan: Contour sticker interaction
## Goal
Implement the user-approved photo → reviewed contour → creative sticker reveal and reversible source comparison; deploy staging only.
## Phases
1. Inspect existing reviewed masks, poster rendering and source photo: complete.
2. Implement a dedicated responsive, accessible reveal component and reuse exact silhouette: complete.
3. Type-check, deploy staging immediately, verify interactions at 375/768/1024/1440px and reduced motion: complete.
4. Record version, health, PWA and production baseline verification: complete.
## Decisions
- Design is already approved in conversation; no repeated approval needed.
- Reuse current authorized image/mask pipeline; do not change shared backend, generation requests, or publishing behavior.
- All work logs stay in hermes_plan; staging pending changes must be preserved.

## Outcome
Completed and deployed to staging build 1789482956490. Review report: 2026-09-15-story-peel-verification.md. Production remains unchanged pending user testing and explicit later approval.

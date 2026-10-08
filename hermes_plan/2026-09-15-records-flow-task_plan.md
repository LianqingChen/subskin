# 手帐记录入口与默认镜头修正

## Goal
Implement the five explicit user requests: single bottom disclaimer, 发布到分享 wording, two concise history tabs, record-body navigation to the full saved result with artwork, and front camera preference for every new camera session.

## Phases
1. Inspect current history/detail/camera paths: complete.
2. Edit frontend and record pending changes, type check and deploy staging: complete.
3. Verify recent/all-history/detail/back flow, button isolation, camera preference/fallback/switch, responsive layout and PWA: complete.

## Decisions
- User explicitly requests just two tabs; use horizontal tabs on both mobile and desktop for this page, removing the previous sidebar/header repetition.
- Reuse VasiDetailPage and its existing saved AssessmentObservationResult/AssessmentStoryCard; no backend/data changes.
- Use exact user-facing constraint first, falling back to ideal only for missing/unsupported facing constraints so a single available camera still works. Reset preference on a new opening; preserve manual switches during that opening.
- Reuse local mirror + SFTP staging publishing verified earlier; production remains unchanged.

## Outcome
Completed: staging 1789485809276. Production unchanged. See verification report for browser/device coverage and limitations.

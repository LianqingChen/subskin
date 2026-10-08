# Continue-camera cancellation

## Goal
Canceling continued capture returns to the original recent/history/result page without losing its state; successful capture still opens the new photo confirmation flow.

## Plan
1. Keep pending baseline/site separate; defer destructive local form/result reset until a photo is captured.
2. Distinguish camera cancellation from successful completion; return query-based detail continuations to their detail route.
3. Type check, deploy staging, verify cancellation and successful capture with synthetic records and virtual camera.

## Status
Complete: staging 1789486666858. Type/build, seven browser flow checks and artifact/PWA/health checks passed. No backend or production changes.

# 就医地图第一版

## Goal
实现 SubSkin 就医地图交互首版并部署 staging，保留全部既有待发布变更。

## Phases
1. Context and design: complete. User explicitly authorized direct first version; proceed without a separate design approval gate.
2. Hospital sources and map design: complete.
3. Frontend implementation: complete.
4. Type check, staging build and PWA: complete. 9 regression checks pass. Responsive implementation complete, visual verification unavailable because browser control times out; document limitation.

## Decisions
- Frontend first preview: real hospital names with official sources; city-level map positions explicitly labeled, no fabricated reviews or scores.
- Province/city filtering, linked map/list, hospital detail, compare up to 3, local bookmarks and structured review drafts.
- No backend restart/schema changes. Public reviews and user-submitted hospitals need authenticated backend, moderation, immutable sharing audit in next phase.
- No production deploy.

## Errors
- Default SSH identity was denied. Try explicitly configured project server identity; mounted SFTP remains readable/writable.

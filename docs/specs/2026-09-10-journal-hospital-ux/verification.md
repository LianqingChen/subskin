# Verification — journal and hospital UX

Final staging buildTime: **1789049981840**. Production remains **1788097546229**.

## Passed
- `npm run type-check` and `npm run build` (all three implementation batches).
- `node --test tests/frontend/*.cjs`: **23 passed**, including 10 new regressions executing compiled Vue setup and template render output with synthetic data; no browser, network uploads, or patient data used.
- New regressions cover repeated change-hospital, guest selection, visible doctor/treatment requirements, optional fields remaining collapsed, invalid submit blocking, third-record selection retention, accurate filtered-empty wording, tag-filter pagination, absence of fabricated scores and capture readiness hints.
- HTTPS assessment/hospitals entry routes, version.json, manifest, sw.js and index JS/CSS return 200 and match deployed files by SHA-256.
- Manifest: staging name SubSkin [STAGING], short name SubSkin-STG, slate theme, white background, all 9 referenced icon files exist. Production retains its configured patient-facing name and teal theme.
- SW files: staging 24749 bytes, production 24276 bytes. This project uses injectManifest and bundles Workbox in SW; a separate workbox-*.js file is not required for this output.
- Staging update-banner wording present in compiled JS; actual banner display in an existing browser session remains unverified.
- Backend health: status=ok, service=subskin-backend. No backend restart or database mutation performed.
- Scoped views/components remain below project line-count limits; source remains in Vue/composable architecture with responsive layout and theme variants.

## Environment differences
Staging contains accumulated Pending Changes that production has not received. Assets: staging 68, production 61. AssessmentPage JS: 58335 vs 90054 bytes. HospitalReviewPage: 730584 bytes vs absent in this production snapshot; includes existing map dependencies. CommunityPage: 19854 vs 19824 bytes; ProfilePage: 72948 vs 71651 bytes. DigitalHuman has no standalone named chunk in either build. These are not claims of whole-environment equivalence. Production was deliberately not rebuilt or synchronized in this staging-only task.

Production version.json lacks lastProdBuildTime in its existing snapshot; this task leaves that production artifact unchanged.

## Pending visual acceptance
Browser connection timed out in both review and implementation. No claim of actual 375/768/1024/1440px screenshots, dark-mode visual acceptance, keyboard traversal, authenticated publishing, physical camera use, or refresh-banner display. Source and compiled-component tests cannot substitute for these checks. Please review the two staging pages on actual devices when available.

## Verification tooling notes
An early manifest read overlapped the final build replacing its output directory, and therefore failed temporarily. It succeeded after build completion. Initial icon validation incorrectly treated cache-busting query strings as filesystem paths; parsing the URL path confirmed all 9 icons exist. Neither issue required application changes.

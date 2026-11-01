# Diary responsive redesign and QA — 2026-10-31

## Outcome

Staging build `1793414478921`. Production remains `1793314103483`. This work changed only frontend source and did not restart the shared backend.

504 layout/state scenarios passed, plus 8 supplemental visual capture scenarios. No page errors were recorded in the final independent runs. This is not a claim that every browser/device or the real backend generation pipeline has been validated.

## Design rules implemented

- Normal diary and exam pages share `.page`, a shared 56px toolbar, and document scrolling. At 1440px, the previous 184px navigation/body offset (288 versus 472) is removed: both start at x=288.
- Below 1024px, the homepage is one column: capture action, recent records, then the quiet creative entry. At >=1024px, capture/story occupy the left column and recent records occupy the right. The existing app sidebar breakpoints remain in force.
- Focused capture and contour-review screens use `.page-narrow` for toolbar and body together. No independent inner max-width cap.
- One primary homepage action. Body-site/camera/gallery options appear after starting a record. New visible tab hit areas are 44px; decoration is reduced on phones.
- Exam upload is a keyboard-accessible button. History navigation no longer floats over the upload panel.

## Defects found and fixed

| Finding | Fix | Evidence |
|---|---|---|
| Desktop tab/body mismatch | Shared toolbar and shared container rule | Live DOM measurements; independent engine matrix |
| Inconsistent diary/exam sticky and scroll behavior | Shared toolbar and document scrolling | Live landscape history-scroll check |
| Dark selected tab used 28% translucent text | Opaque primary-300 text | Browser computed color changed to rgb(94,234,212); screenshot review |
| Phone report comparison bar overlapped BottomNav | Reserve 55px plus safe-area offset; wrap narrow controls; reserve content space | Comparison-mode matrix |
| Long report filenames escaped the card | min-width:0, max-width, truncation and wrapping file rows | Initial Chromium tests failed; final matrix passes |
| Long tags and small report controls | Break long tags; 44px targets; report title keyboard button | Long-data fixtures; visual review |

## Independent test matrix

The final deployed static bundle was copied to a local HTTP server. All API calls were intercepted with synthetic users, records, reports and image fixtures. Service workers were blocked in the independent matrix to prevent stale bundles. No real photographs were uploaded, and no live image-generation requests were made.

| Suite | Scenarios | Failures |
|---|---:|---:|
| Chrome / Chromium (156.0.8078.79) — light + dark | 128 | 0 |
| Firefox (157.0) — light + dark | 128 | 0 |
| WebKit (27.2) — light + dark | 128 | 0 |
| Empty history, all three engines | 36 | 0 |
| iPhone touch profile, WebKit, both orientations/themes | 28 | 0 |
| iPad touch profile, WebKit, both orientations/themes | 28 | 0 |
| Android/Pixel touch profile, Chromium, both orientations/themes | 28 | 0 |
| Total primary scenarios | 504 | 0 |

Desktop responsive widths: 320, 375, 390, 767, 768, 1023, 1024, 1279, 1280, 1440, 1920, and 844px landscape. Device profiles use the installed Playwright descriptors for iPhone 13 Mini, iPad Mini and Pixel 5 with portrait/landscape sizes.

Routes: `/assessment`, `/assessment/exam`, `/assessment/story`, `/assessment?view=records`. States include normal and empty history, long record/report titles, long filenames/tags, expanded capture controls, synthetic-photo preview, and report comparison mode.

Assertions cover page/interactive-element horizontal overflow, toolbar/body alignment, tab touch heights, and comparison-bar/BottomNav overlap. Screenshots were inspected for visual hierarchy and theme appearance. Internal component tests also cover login gating and saved/reviewed contour gating.

## Deployment sequence

| Staging buildTime | Change |
|---|---|
| 1793413026497 | Shared toolbar, layout/container consistency, upload entry |
| 1793413326154 | Responsive report comparison bar |
| 1793413607801 | Dark tab contrast and homepage heading hierarchy |
| 1793414478921 | Long filename/tag overflow, report touch and keyboard controls |

`npm run type-check`, `npm run build`, and `git diff --check` passed. Production was not deployed. Final version/PWA/health verification is recorded in DEPLOY_LOG.md.

## Boundaries

- WebKit automation is engine validation, not a physical iPhone/Safari certification. WeChat and Huawei physical browsers were not tested.
- Real camera permissions, OS photo pickers, virtual keyboard, hardware safe-area/notches and installed-PWA device behavior still require real-device acceptance.
- Independent API mocks verify presentation and frontend state, not backend authorization, model output quality, provider latency or billing.
- Other authorized work exists in the shared repository and staging deployment log; its changes were preserved.

## Evidence

Local artifact directory: `/home/liam/.codex/visualizations/2026/10/30/01a18da0-0bf5-77d3-8bf8-033afd2cc72b/diary-qa`.

- `layout-results-*.json`: final geometry/state results.
- `chromium-light-diary-desktop.jpg`: desktop light screenshot with synthetic records.
- `webkit-dark-diary-mobile.jpg`: mobile-width WebKit dark screenshot with synthetic records.
- `report-compare-mobile.jpg`: comparison-bar stress state with synthetic reports.
- `test-layout.mjs`: independent test runner (runtime dependencies and static snapshot under `/tmp/subskin-browser-qa`).

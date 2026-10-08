# Camera/device acceptance continuation

Staging build: **1788996117712**. Production frontend remains **1788097546229**.

## Completed engineering checks

`node --test tests/frontend/camera-lifecycle.cjs`: **10 passing** tests, executing the actual BodyPartCamera Vue script against deterministic media and DOM stubs. No physical camera or patient images used.

Four failures reproduced before fix: stale permission error overwrites a newer stream, play rejection leaves camera active, delayed toBlob emits after close, repeated shutter press creates multiple images.

Additional passing contracts: stop late-arriving streams, close/release on background and pagehide, retry null photo encoding, save full unmirrored frame without guide overlay, stop after successful capture, Escape cancellation. Dialog focus management and scroll locking implemented; actual keyboard/browser behavior not yet visually exercised.

`npm run type-check` and `npm run build` pass. Staging /assessment, /version.json, /manifest.webmanifest, /sw.js, /api/health all return 200. Manifest is SubSkin [STAGING], theme #1e293b, nine icons; service worker exists. No production frontend deployment or backend restart in this continuation.

## Real-device acceptance: still pending

The disconnected project mount was restored. Browser inventory works; CUA tab acquisition, documented claim/DOM reads and direct tab/screenshot requests time out. Troubleshooting documentation was consulted. No usable browser screenshot or interaction result has been obtained. No phone is exposed by the current tools.

User has been asked to reconnect the Chrome extension, keep staging open, and identify iPhone/iPad, Android or desktop camera. Do not mark the following accepted until observed on an actual connected device or explicitly reported by the tester:

| Case | Expected result | Status |
|---|---|---|
| 375/768/1024/1440px layouts | Both entries usable; no horizontal clipping; controls reachable | Not executed |
| Dark mode / large text / keyboard | Readable contrast, focus stays in camera, close returns focus | Not executed |
| Permission denied | Clear retry/gallery option, no frozen spinner or live stream | Not executed on hardware |
| Permission allowed | Correct camera preview and reachable shutter | Not executed on hardware |
| Switch camera | Stops previous camera, correct lens without stale error | Not executed on hardware |
| Capture / repeat / close during capture | One original frame, no stale photo injection, camera indicator ends | Unit contracts pass; hardware pending |
| Baseline overlay | Guide visible when requested, not burned into output photo | Unit draw contract checked; visual pending |
| App background / lock / return | Camera closes; stream stops; fresh reopening works | Unit contracts pass; hardware pending |
| Gallery/date confirmation | User supplies actual date; cannot submit missing/invalid date | Browser interaction pending |
| Orientation and PWA | Portrait/landscape, safe areas and installed PWA usable | Not executed |

Use a non-sensitive test target for camera preview. Testing need not upload medical photos. Uploading/saving an actual assessment should use an explicitly authorized test account and data, since staging shares the backend and database.

# Assessment validation and rollout

## Implemented on 2026-09-10

- Two equally visible journeys: first observation and ongoing tracking; shared private photo records, simplified capture, optional mask correction, current-result and detail pages.
- Capture context (position ID, view, confirmed date, baseline, optional patient notes) stored additively inside existing assessment details JSON. No schema migration or retrospective record overwrite.
- Complete unmirrored camera frame; EXIF orientation normalized before analysis; source image retained. No scene-wide contrast enhancement in measurement input.
- Large candidate boxes retained; one canonical mask supplies outlines/area. Candidates outside the skin ROI and partial frames are unavailable/partial rather than false precise measurements.
- Local visible-skin coverage explicitly distinct from clinical VASI. Corrected formula hand-unit scaling and missing foot aliases; old numerical fields retained for compatibility, new UI does not treat them as clinical scores.
- Optional user-selected reference segment with known millimetres and same-plane confirmation estimates planar cm²; it is not a curved-surface measurement or automatic reference-card detection.
- Comparison requires matching observation identity/view/date, same measurement version, complete masks, stable-skin feature registration, common visible ROI and alignment gates. Exact duplicates, zero/small baselines and missing evidence never imply clinical stability.
- Area, relative color and border-range availability are separate. Sensitivity interval models boundary uncertainty only; it is not a validated clinical confidence interval.
- Numeric comparison and preview heatmap use the same registration and mask differences. Cache fingerprints include image content, mask/context and measurement versions. Private generated files retain the existing owner-scoped naming convention.
- Old reports/history do not drive new clinical trends; raw database records remain unchanged. API serialization provides legacy-method labeling. Original legacy narrative data remains stored; current display does not reassert its unverified conclusions.
- Offline benchmark CLI: scripts/assessment_benchmark.py. Synthetic and in-memory API regressions: tests/assessment/.

Final staging buildTime: 1788974152768. Production frontend: 1788097546229 (unchanged).

## Validation completed

- `npm run type-check` on working copy and actual staging source.
- `npm run build`: staging only; service worker generated successfully.
- `PYTHONPATH=. .venv/bin/python -m pytest tests/assessment --confcutdir=tests/assessment -q --disable-warnings`: 22 passing tests. Includes full service orchestration with stubbed VLM/SAM, 81% large lesion, submitted body-site preservation, context round-trip, quality reject/finalize, alpha masks, common ROI, duplicate/no-evidence behavior, reference scale, benchmark patient-split leakage and private preview filename ownership, exact-duplicate rejection and camera-translation invariance.
- HTTPS responses for /assessment, /version.json, /manifest.webmanifest, /sw.js and /api/health: 200 on both staging and production during verification.
- Staging manifest name/theme correct; both manifests contain nine icons; injected service worker exists. No separate workbox file expected for the project's injectManifest build.
- Shared backend restarted and health OK. Production frontend build remains 1788097546229.

## Outstanding validation (do not claim complete)

- Browser automation timed out for both the in-app browser and Chrome. 375/768/1024/1440px screenshots, full authenticated browser flows, camera on real devices, 200% text zoom, dark mode and actual PWA update prompt still require user/device QA. HTTP 200 and successful build do not establish visual correctness.
- No real patient images were used in tests; no model accuracy percentage, clinical efficacy, diagnostic sensitivity/specificity or improved performance on patients has been established.
- No new trained segmentation model was promoted. Existing model interfaces were reused, and engineering defects/measurement gates were corrected. Expert-labeled authorized data is required for an independent baseline and model comparison.
- Automatic 3D surface measurements, clinical total-body VASI and reliable diagnosis from arbitrary smartphone photos are not provided.

## Dataset intake and benchmark workflow

Use a local JSON manifest with a `samples` array. Each row: `patient_id` (pseudonymous identifier only), `split` (train/validation/test), `ground_truth` (mask path relative to manifest), `prediction` (candidate mask path), `label_source` (`clinician` after actual clinician review), `consent` (true only after recorded authorization). Optional strata: `skin_tone`, `body_site`; repeatability: `repeat_group`, `unchanged`.

The script rejects cross-patient split leakage and unconsented/non-clinician labels. It evaluates held-out test masks, Dice/IoU, Boundary F1 at 2px, HD95, area error, strata and same-session area variation. It does not train a model or call a third party. Clinical sample-size planning, inter-rater annotation review, negative diagnoses, uncertainty bands and device-stratified external validation remain a clinician-led step.

Run on the server:

```bash
cd /root/subskin
.venv/bin/python scripts/assessment_benchmark.py --manifest /authorized/dataset.json --output /private/metrics.json
```

Never commit patient photos, paths containing personal identifiers or clinical manifests to Git. Keep raw/original/corrected masks versioned; user corrections and model pseudo-labels must not be labeled as clinician ground truth.

## Next production frontend release

All pending changes in DEPLOY_LOG.md must be reviewed and synced together only after the user tests staging and explicitly requests production deployment. Backend is already shared and active; no additional backend staging environment was created.

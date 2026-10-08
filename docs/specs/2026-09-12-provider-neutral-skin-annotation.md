# Provider-neutral skin annotation protocol: skin-outline-v1

User-approved scope: turn the demonstrated visual tracing workflow into a reusable journal workflow. The reference was assistant-drawn on one photograph, not automatic model performance. Do not embed that photograph or its coordinates in production, prompts, fixtures, or training data.

## Ownership of each step

1. Capture: original private photograph, EXIF orientation, selected body site/date. Existing photo-quality gate remains; it is not a guarantee of task suitability.
2. Vision adapter: configured `vasi` vision model proposes skin, exclusions, pale candidate and uncertain polygons. The versioned prompt is separate from changeable prose prompts. Text-only models are not a substitute.
3. Geometry renderer: accepts normalized finite coordinates, bounds polygon/vertex counts, rejects crossing/degenerate shapes, rejects substantive leakage beyond skin. No full-frame or color-only fallback is used in this opt-in pipeline.
4. Masks: skin minus exclusions; candidate inside skin minus exclusions and uncertainty; uncertainty remains independent. Skin is never expanded by a lesion prediction.
5. Measurement: only `measure_layers`, including current mask pixels, bounding width/height, outer-contour perimeter, same-image color reference, optional planar calibration. No model-supplied area, diagnosis, stage, efficacy or probability is accepted.
6. UI: original, skin, candidate and uncertainty views. Candidate outputs are pending. Manual review has an explicit acknowledgement and a working save action. The editor must use the same skin-only denominator and leakage gate as the backend.
7. Persistence: original AI masks/geometry preserved, user's corrected masks stored separately; review metadata and hash-linked revisions retained. These are ordinary application records, not a tamper-proof audit system. No automatic training export or auto-finalization of new protocol records.
8. Comparison: pending references cannot supply longitudinal quantitative changes. Existing common-ROI registration and quality gates still apply after user review.

## Transport and compatibility

`GET /api/vasi/annotation-protocol` advertises `skin-outline-v1` with manual review required. New journal requests explicitly send `annotation_protocol=skin-outline-v1` in the existing assess form. A missing capability stops the new request before an old server can silently ignore the protocol field. Existing production clients omit the field and retain their current assessment path. No schema migration or provider configuration change is included.

Response metadata is additive under `measurement.annotation`: protocol, review_state, dimensions, candidate/uncertain pixel counts, uncertain layer, excluded layer, and model provenance. Existing response models already accept a measurement dictionary. User review is submitted with the existing two-layer correction endpoint plus `uncertainty_reviewed=true`; the server rechecks masks before mutation, clears stale generated text, and finalization only succeeds after review.

## Limits and release criteria

Identical protocols standardize handling; they do not establish identical accuracy across models. Valid geometry is not proof of correct skin/disease classification. A candidate may still be wrong and requires human review. The current quality checker and overall detection performance require the wider Benchmark described in the audit. No claim of clinical accuracy or generalized improvement is made until held-out labeled cases pass.

Tests: invalid coordinates/NaN/self-crossing/oversized or empty geometry; exclusions and uncertainty; outside-skin rejection; explicit review; original evidence retention; mismatched image geometry; two fake provider adapters returning identical reference geometry; editor alpha/denominator/leakage consistency. Fake-provider equivalence is a contract test, not a real model accuracy comparison.

Staging-first deployment: type-check, build, protocol/correction smoke tests, responsive UI and PWA checks, record DEPLOY_LOG. Shared backend restart affects both environments and requires the project's explicit-impact confirmation. No production frontend deployment is authorized by this task.

# Findings
- Recent rows currently emit continue for every click. Full list thumbnails open detail, while most of the card lacks a details link and highlights continued capture.
- VasiDetailPage already loads saved measurements, masks and creative cards. Reuse this route.
- AssessmentPage and AssessmentObservationResult both render the same disclaimer; retain the page-level one.
- BodyPartCamera currently initializes facing=environment and does not reset on reopening.

- App.vue already renders GlobalFooter on /assessment/vasi/:id while excluding /assessment. Disclaimer deduplication therefore removes the detail-specific footer and keeps AssessmentPage's single inline bottom message.
- Ideal facing constraints can compete with resolution preferences. Exact facing first makes front selection deterministic when available; unsupported/missing facing can safely fall back without retrying permission denial.

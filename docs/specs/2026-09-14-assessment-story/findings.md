# Findings
- Current single-photo result is AssessmentObservationResult.vue, used in AssessmentPage.vue and VasiDetailPage.vue.
- Confirmed data includes measurement status, area percentage, regions, extent, optional color/border, and skin/lesion layers. handleTwoLayerConfirm updates the current result and layers from server response.
- useVasiShare currently creates a private community draft containing measurement text, an uploaded annotation composite, and original image. New creative sharing must not silently carry these photos forward.
- SkinReportPoster.vue implements a separate Canvas poster for multi-photo/periodic reports; reuse export patterns without conflating these reports with single-photo results.
- No image generation integration located in targeted frontend API/backend service search. First release can compose verified masks locally; generative personalization would require separate integration review.
- Repository is a GVFS remote mount. Broad git status is slow; avoid repeated broad scans.

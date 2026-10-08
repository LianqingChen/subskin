# Assessment reliability and two-journey design

Status: approved for implementation by user on 2026-09-10.

Source design: ../reviews/2026-09-10-assessment/review.md (sections 4–6).

- Equal first-discovery and repeat-monitoring entrances under existing 测评 navigation.
- Shared capture, quality gates, optional mask correction, private records, explicit observation context/date.
- Photo coverage is local image coverage, not clinical VASI; no scores or stable diagnosis on insufficient evidence.
- Pixel masks are canonical, large lesions supported, single-image and comparison measurements versioned, comparison requires common visible region and valid geometry.
- VLM describes appearance and limitations, never supplies a numeric change when quantitative evidence is unavailable.
- Independent area/color/border availability, consistent result/overlay/report, benchmark tooling with patient-separated expert ground truth and repeatability controls.
- Compatibility: preserve old routes/data/fields; old measurements retain provenance and never silently become clinical values.
- Validation: synthetic/regression/unit checks and staging PWA/responsive checks, with a separately documented expert clinical-validation requirement.

# Findings
- ComparisonViews uses needsAlign to disable three tabs and conditions their panels on aligned.
- BeforeAfterSlider and comparison overlays crop to square with object-fit: cover; use opt-in contain for comparisons while preserving other callers.
- Isolated manual backend candidate does no refinement of manual transforms; automatic matching uses the same strict <=2.5px criterion as measurement.
- Live backend is not yet using the prepared candidate. Backend activation affects both environments and requires explicit confirmation.

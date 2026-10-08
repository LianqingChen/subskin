# Findings
- ComparisonViews displays the same angle/distance diagnosis for every !aligned state, ignoring PairAlign.note and PairMetrics.reasons.
- compare_pair compares SHA-256 of resolved image bytes before registration. Equal bytes produce unavailable evidence with duplicate=true and a duplicate explanation.
- _merge_results retains that flag under merged.evidence.duplicate, while the frontend type currently only declares a historical top-level duplicate field.
- save_comparison_preview deliberately returns aligned=false and the actual capture_note for non-measured pairs. Duplicate photographs are not independent temporal observations; no 0% clinical change should be manufactured.

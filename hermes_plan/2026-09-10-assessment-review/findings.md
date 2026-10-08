# Findings

Source inspection in progress. Distinguish implemented functions from active integration and measured accuracy.

- User clarified first-detection guidance and diagnosed-user tracking are equally important.
- Current page combines body selection, single assessment, two photo-comparison sources, two history types and exam interpretation. Source uses absolute draggable panel, overflow hidden and 10–11px explanatory text.
- vasi_formula.compute_vasi_v2 multiplies regional hand units by depigmentation and 10; photo skin denominator is used as region coverage. Clinical VASI equivalence is not established.
- vasi.py discards VLM boxes over 25% (small body sites) / 45% (large sites): plausible cause of missed large lesions.
- spot_compare blends VLM area estimates with CV (45/55), with low-confidence flags rather than a universal cannot-compare gate. Existing canvas registration must be assessed before suggesting new registration.
- Browser first tab navigation timed out and reset runtime; retry with surface inventory.

- Existing canvas comparison obtains validity_a/validity_b but sums each full mask without common-valid-ROI intersection (spot_compare.py:810–822). This differs from photo_align heatmap gating.
- Scalar formula checks executed without importing service/database: hand-unit score multiplied by 10; left_foot gives 17.5 versus Chinese 左脚 90.0 for same 100%/fully depigmented synthetic input (missing Chinese mapping uses 9% default). Not patient accuracy testing.
- Main single-image input to VLM is gray-world white-balanced + CLAHE + sharpened + downscaled to 1024px. Enhanced images should not be sole colorimetric evidence.
- has_reference flag is persisted after assessment; it does not itself calibrate cm².
- Legacy feedback/evaluator factory functions return None (disabled); newer patient consensus path exists. Active weights/model performance not verified.
- Public browser title loaded but AX selection timed out twice. No claim of screenshots, four-width QA or authenticated flows.

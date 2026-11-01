# Autonomous vitiligo recognition: proposed acceptance and implementation design

Date: 2026-11-01. Status: research and offline implementation in progress; no release claim.

## User outcome

Users must not have to identify or paint lesions for the ordinary supported flow. Preserve the full goal: correct rejection, lesion identification, skin denominator, area proportion and visible overlay. Existing unconditional manual-review gating is not completion. Conversely, removing that gate without a validated model is not an accuracy improvement.

## Proposed 95% contract

These thresholds operationalize the request and are not current results. Freeze them before model selection; confirm the area interpretation with the user before final acceptance.

- Relevant-image gate: unrelated-image rejection >=95%, valid supported-photo false rejection <=5%. Report normal skin, unrelated objects, screenshots/documents, other hypopigmented disorders and ambiguous cases separately.
- Lesion identification: image-level sensitivity and precision >=95%; additionally report lesion-component recall for tiny/satellite lesions. No substitution of AUC or model confidence for accuracy.
- Pixel masks: independent subject-level macro lesion Dice >=0.95 and visible-skin Dice >=0.95. Positive and negative images reported separately. Empty-background agreement must not inflate lesion scores.
- Overlay boundaries: boundary F1 >=0.95 on a fixed normalized grid/tolerance, alongside native-resolution Dice and boundary-distance distribution. Do not increase tolerance after looking at test outcomes.
- Area: both absolute percentage-point error and relative ratio error must be recorded. Proposed joint criterion: <=1 percentage point absolute AND <=5% relative error on nonzero reference ratios for >=95% of applicable images. Near-zero/zero lesions need separately prespecified false-positive-area limits, not an arbitrary denominator epsilon that creates a passing score.
- Automatic completion: >=95% coverage on prespecified supported acquisition conditions, reported together with accuracy; rejected/abstained/failed cases remain in the denominator. Uncertain valid inputs request retakes rather than silently becoming manual labeling.
- Report patient-group bootstrap intervals and subgroup counts, device, body site, skin tone, lighting and lesion size. A point estimate from a tiny reused set cannot prove 95% generalization. Set final evidence/sample-size gates before testing.

## Measurement scope: two distinct deliverables

1. Visible-skin photograph ratio = predicted lesion pixels / predicted visible skin pixels (including lesion skin, excluding occlusion). Evaluate numerator and denominator jointly and independently.
2. Whole anatomical-region surface ratio: first establish complete body-region coverage and geometric area weights via standardized multi-view capture/reconstruction, or another independently validated acquisition protocol. A cropped hand/face image cannot prove whole-region surface area. This remains an explicit part of the requirement if the user means anatomical surface share; do not silently replace it with (1).

## Architecture and candidate comparison

A. Acquisition and semantic admission: photo decoding and quality checks; locally run image-domain/body-part/skin relevance classifier with hard negatives, including skin-coloured objects, documents, nonhuman skin and similar disorders. Reject explicit unrelated content; ask for retake on insufficient or ambiguous evidence. A disease classifier is not a definitive clinical diagnosis.

B. Joint anatomy/lesion segmentation: compare existing rule baseline, licensed specialist pretrained models, and self-supervised visual encoder plus multi-class decoder. Separate normal skin, depigmentation, background, occlusion and unreadable regions. Preserve small lesions and full-resolution spatial transforms.

C. Automatic prompting/refinement: region proposals can prompt a frozen segmentation model. Do not use image-specific human prompts in the automatic benchmark. Apply multiscale inference, uncertainty and ensemble disagreement as candidate signals; calibrate them on validation data rather than trust raw softmax.

D. Training/data efficiency: use consented or explicitly licensed existing datasets and weights only after provenance review. Synthetic counterfactuals and pseudo-labels are auxiliary material, not medical truth. No copying test labels or repeated tuning on the holdout. Keep patient and near-duplicate image groups together.

E. Measurement and output: same spatial grid for source, masks and overlay; independently test resizing/cropping/EXIF orientation; compute area server-side; return calibrated uncertainty and explicit unavailable/rejection states. Validate capture-to-result without manual edits.

F. Independent release evaluation: freeze model/checkpoint, preprocessing, thresholds and manifest; run locked real-image test with authoritative reference, negative/adversarial classes and subject-level splits. No deployment until joint gates pass. Existing reference datasets can avoid new manual labeling in the product workflow, but expert-referenced validation cannot be replaced by another AI's self-score.

## Concrete current evidence

- Registry enabled=false and automatic_measurement=false. Current policy unconditionally requires user review.
- Historical 13-image benchmark lesion Dice 0.5075, skin Dice 0.9157; not current clinical validation.
- Prior 78 synthetic rounds did not establish independent real-photo efficacy.
- Fresh offline generated-negative probe: checkerboard and text document returned review_required; skin-coloured rectangles produced 65,536 skin pixels and 17,458 uncertain pixels rather than semantic rejection. Uniform flat colour was caught by quality loss. This tests failure modes only, not dataset-level rejection rates.

## Primary evidence and candidate status

- https://www.sciencedirect.com/science/article/pii/S1361841525004669 — GloW-VSNet weak supervision uses physician scribbles. Potential low-label research baseline, not a no-label or clinically validated 95% guarantee. Published code link: https://github.com/YuhanZheng0327/Weakly-Supervised-Vitiligo-Lesion-Segmentation . License, weights, data access and inference prompting must be inspected before adoption.
- https://pmc.ncbi.nlm.nih.gov/articles/PMC13237307/ — automated clinical-photo measurement, reported 81% lesion accuracy and F-VASI ICC 0.91; controlled photography does not establish consumer-phone performance.
- https://pubmed.ncbi.nlm.nih.gov/38100337/ — distinction between patch-wise segmentation and clinical/full-region scoring.
- https://huggingface.co/nasskall/vitiligo — model card reports unknown training dataset and missing limitations/evaluation details; do not adopt based on name alone.

## Next executable work

1. Inspect specialist-repository licensing, available checkpoints, training/test splits and automatic inference requirements.
2. Inventory existing authorized evaluation manifests and negatives without exporting patient images or inventing data rights.
3. Establish baseline semantic rejection and joint measurement metrics on an independent benchmark; implement missing reusable evaluator terms as necessary.
4. Select and implement candidate screening + segmentation adapters offline; compare to the frozen baseline; then integrate the verified candidate and retake UX.

## User clarification (2026-11-01)

User explicitly permits existing legally authorized expert labels for training and independent evaluation. Users must not need manual labeling at inference. Required area scope is PHOTO-VISIBLE SKIN, not entire anatomical surface area. Whole-region 3D estimation is outside the clarified goal. Existing source-specific privacy and licensing checks still apply; this approval does not license unverified datasets.

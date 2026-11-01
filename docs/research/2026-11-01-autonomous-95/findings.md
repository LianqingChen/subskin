# Evidence audit

- Local GVFS workspace is unavailable in this session; authenticated SSH alias volc works.
- Registry currently enabled=false, automatic_measurement=false. Runtime uses parsed-skin/colour-reference fallback.
- measure_rgb explicitly blocks all unreviewed measurements. This is not an autonomous system today.
- 2026-10-25 historical 13-image grouped benchmark: lesion Dice 0.5075, skin Dice 0.9157. Historical baseline, not a newly executed generalization test.
- Existing 78-round synthetic study reports no validated real-image improvement and no candidate meeting its joint gates. Avoid repeating synthetic-only tuning and treating it as clinical validation.
- Current denominator is visible skin in the photograph. Full anatomical surface share requires complete acquisition or geometry; keep both requirements explicit rather than silently relabeling one as the other.

Primary research:
- https://pmc.ncbi.nlm.nih.gov/articles/PMC13237307/ — clinical trial cross-polarized images; reported lesion accuracy 81%, digital F-VASI ICC 0.91. Does not establish 95% consumer-photo segmentation.
- https://pmc.ncbi.nlm.nih.gov/articles/PMC11604898/ — differential hypopigmentation classification and segmentation; expert reference labels; skin types III/IV.
- https://pubmed.ncbi.nlm.nih.gov/38100337/ — patch-wise segmentation cannot directly stand in for full clinical scoring.
- https://arxiv.org/abs/2311.11096 — medical foundation-model OOD robustness and uncertainty; indirect evidence, not vitiligo validation.

Fresh generated-negative probe completed successfully. Three nonmedical patterns reached review_required instead of an explicit irrelevant-content rejection. The skin-coloured rectangle pattern produced a full-frame skin mask and 17,458 uncertain pixels. This establishes a semantic admission gap, not a measured population error rate.

User clarified: existing legitimately licensed expert labels may be used in training and independent validation; user-facing inference must be automatic. Area target is photo-visible skin, not anatomical whole-surface area.
Default data/rgb_segmentation/datasets contains zero dataset manifest exports; this does not establish that no annotated data exists elsewhere.
SigLIP local CPU probe completed: all four generated negatives ranked a nonmedical prompt highest. Approximately 0.52–0.57 sec/image in this isolated run, not a production latency guarantee. No calibrated accuracy claim.
Public dataset lead for provenance/mask inspection: SkinDis-India v2, https://data.mendeley.com/datasets/r7kdbj2wym/2, advertised CC BY 4.0 and an augmented clinical collection; do not use augmented siblings as independent test subjects. Actual annotation contents and source-specific permissions remain to be inspected.

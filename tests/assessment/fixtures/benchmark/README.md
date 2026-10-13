# Offline assessment benchmark

This fixture path is synthetic. It is not a clinical gold dataset and it is not a certification.

The report status is always `offline_benchmark_not_clinical_certification`.

## Run the synthetic fixture

From the repository root:

```bash
.venv/bin/python scripts/assessment_benchmark.py --write-fixture /tmp/subskin-bench
.venv/bin/python scripts/assessment_benchmark.py --manifest /tmp/subskin-bench/manifest.json --output /tmp/subskin-bench/metrics.json
```

`metrics.json` includes Dice, IoU, 2px boundary F1, and area error. Patients cannot appear in more than one split. Strata use `body_site` and `skin_tone` when those fields are present. Empty agreement is kept out of `positive_dice`.

Do not commit patient photos, real identifiers, or a clinical manifest.

## From admin reviewed masks

1. `label_sync` writes AI and user candidates onto the private labeling record. Those masks are not ground truth.
2. Admin review (`save_admin_reference`) stores a snapshot at `data/rgb_segmentation/admin_labels/{label_id}/{revision}/` with `lesion.png`, `total_skin.png`, and `metadata.json`.
3. Copy that snapshot, plus a separate prediction mask, onto a machine that is allowed to hold the authorized set. Keep the paths local.
4. Build one manifest row with `manifest_row_from_admin_snapshot`. Set `patient_id` to a pseudonym. Set `consent=true` and `label_source="clinician"` only after a clinician authorization is on record. Draft snapshots are rejected.
5. Write a `manifest.json` whose mask paths are relative to that file, then run the command above.

AI masks, user corrections, and unreviewed admin drafts must not be labeled clinician ground truth.

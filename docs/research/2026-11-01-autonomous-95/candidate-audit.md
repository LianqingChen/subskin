# Candidate audit — 2026-11-01

- GloW-VSNet public demo inspected via GitHub connector. demo.py blob dc824b4091936c834355ed5ed28b177c4c562c63 outputs 50 argmax cluster labels with random colours; SPANet.py blob 54146ad59051bdf47f604b46b13e6570812b8d6f confirms a 50-channel output. checkpoint.pth exists (~1 MB), but class-to-lesion semantics, training split/provenance and deployment permission remain unverified. Root web listing did not show a license. Do not treat this as a ready five-class model or choose the best label using test masks.
  Source: https://github.com/YuhanZheng0327/Weakly-Supervised-Vitiligo-Lesion-Segmentation/tree/master/demo
- arXiv:2512.11791 v2 is WITHDRAWN as of 2026-06-22, with experimental restructuring cited. Excluded as supporting validation evidence.
  Source: https://arxiv.org/abs/2512.11791
- Current evaluator distinguishes lesion pixel-count relative error from percentage-point error but lacked relative error of the actual lesion/skin ratio. Implemented a separate ratio metric and denominator reporting; this measures a required goal component, not model improvement.
- Existing dataset validator requires explicit training authorization even for evaluation and requires train/validation/test partitions. Evaluation-only independent cohorts need a scoped manifest workflow; do not fake training permission to pass validation.

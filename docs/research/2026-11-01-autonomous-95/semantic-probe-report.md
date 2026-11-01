# First local semantic relevance probe

Model: google/siglip-base-patch16-224, revision 7fd15f0689c79d79e38b1c2e2e2370a7bf2761ed. Weights SHA-256 verified against upstream LFS metadata: 2c63cb7d1f2e95ba501893cbb8faeb4ea9a3af295498d35097126228659c2af8.

CPU, two Torch threads, transformers 4.57.1, local safetensors; external inference disabled. No patient images. Fixed prompts were written before execution; no tuning after outcomes.

| Generated nonmedical input | Highest-scoring prompt | Best skin minus best other logit | Inference seconds |
|---|---|---:|---:|
| uniform_skin_coloured_surface | surface | -5.793 | 0.574 |
| checkerboard | checkerboard | -17.072 | 0.532 |
| generated_text_document | document | -12.693 | 0.526 |
| skin_coloured_rectangles | surface | -4.159 | 0.523 |

All four top prompts were nonmedical. The original fallback probe had routed three of these inputs to manual review; the skin-coloured rectangles generated a full-frame skin proposal. This is a useful candidate signal, not measured clinical performance: there are no real positive skin photographs, no independent OOD corpus, no calibrated threshold, and no disease/lesion segmentation validation. Do not call this 100% rejection accuracy or use these logits as probabilities.

Next: expand to legally authorized real skin photos, normal/lesional skin and hard negative objects, freeze development versus held-out sources, measure false rejections jointly with unrelated-image rejection, and compare routing policies without silently discarding abstentions. Keep the candidate offline until supported by that evidence.

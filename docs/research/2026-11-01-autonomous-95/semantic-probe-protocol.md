# Frozen first semantic probe

Candidate: google/siglip-base-patch16-224, Apache-2.0 model card. Resolve and record exact revision. Local CPU inference, safetensors only, no remote Python execution. No patient images or external inference calls. Dependencies installed in /tmp/subskin-semantic95-env, not the production venv.

Fixed 8 prompts and the same four generated nonmedical fixtures used in the existing fallback probe. Compare the strongest skin-photo prompt with strongest nonmedical prompt; record raw margin, never interpret sigmoid/softmax as clinical confidence. There are no real positives, so no specificity/sensitivity or 95% claims can follow. This run is a candidate viability/failure-mode check, not a release benchmark. Preserve unsuccessful outcomes as evidence; do not tune prompts on these four examples and call the outcome held-out accuracy.

Source: https://huggingface.co/google/siglip-base-patch16-224

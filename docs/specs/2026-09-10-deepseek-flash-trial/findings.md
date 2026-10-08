# Findings

- Official documentation retrieved today identifies DeepSeek-V4.1-Flash as `deepseek-flash`, supporting images. Old `deepseek-v4-flash` and `deepseek-v4-flash-vision-exp` route to the newer model. Sources: https://api-docs.deepseek.com/ and https://api-docs.deepseek.com/guides/vision/ . Search snippets were stale; opened primary pages are current.
- vasi._call_vision_model and spot_compare._call_pair_vlm both use get_llm_config("vasi"). Narrative generation uses separate skin_report config.
- Existing source already contains DeepSeek vision compatibility comments and a fallback vision-exp model; effective database configuration must be checked before assuming a provider switch is required.
- Pair cache uses common-roi-v1 plus fingerprint; verify which algorithm/call paths are active before promising a model change affects all comparisons.

- Credential exists in web/backend/.env; not in root .env. GET official /models succeeded and returned deepseek-flash and deepseek-v4-pro. No key value displayed.
- Effective vasi module already deepseek, chat=deepseek-v4-flash, vision=deepseek-v4-flash-vision-exp; skin_report and medical_report remain DashScope.
- Current spot_compare.compare_pair explicitly sets vlm=None; numeric comparison uses compare_registered_masks. Old _call_pair_vlm is not called by this path.
- Official deepseek-flash synthetic red-circle/blue-square two-image request: HTTP200, correct shapes/colors, 0.93s, 453 total tokens. No medical or patient data transmitted.
- User asked asynchronously whether to add independent visual observations to comparison or test single-image identification only. Existing model normalization is authorized; further comparison behavior awaits answer.

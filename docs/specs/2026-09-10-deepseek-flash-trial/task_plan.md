# DeepSeek Flash trial

Goal: Verify credentials/model support, prepare a reviewable model switch for journal assessments and photo comparisons, enable the user to assess recognition accuracy.

1. Read-only configuration, official model identity and image support — complete.
2. Synthetic image API validation and exact change scope — complete (two-image synthetic probe passed).
3. Existing DeepSeek alias normalization — complete; independent comparison visual observation awaits user choice.

Constraints: Never expose keys or patient photographs. No patient data is needed for connectivity checks. Backend is shared; changes affect production. Use existing module config, preserve unrelated modules and credentials. Do not infer medical accuracy from synthetic connectivity tests.

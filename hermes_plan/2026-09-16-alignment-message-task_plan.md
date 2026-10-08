# Identical-photo comparison message
## Goal
Stop falsely diagnosing angle/distance differences when a pair is duplicated, unavailable, legacy or otherwise not aligned. Surface the actual structured reason without inventing change measurements.
## Plan
1. Reproduce exact-byte duplicate output from the current backend functions using synthetic bytes and mocked I/O: complete.
2. Fix frontend interpretation of nested duplicate evidence and alignment reasons; isolate existing styles to retain component size standards.
3. Type check, staging deployment and real-component report regression across duplicate/failure/missing/success cases; verify PWA/health/production baseline.
No backend edits/restarts are planned if the duplicate branch already supplies the correct evidence.

## Outcome
Completed: frontend staging 1789490286086. No backend edits or production deployment were needed. Existing reports use the corrected presentation after updating the frontend.

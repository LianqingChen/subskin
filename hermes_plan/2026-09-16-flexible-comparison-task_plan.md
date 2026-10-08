# Flexible comparison

## Objective
All four visual comparison modes remain usable without pixel-perfect registration; automatically refine approximate manual geometry using stable image landmarks.

## Phases
1. Frontend viewing gates removed, contain full images, stage and verify — complete (1789518317753).
2. Isolated backend candidate: robust masked feature matching and bounded local refinement, keeping visualization independent from numeric measurement — complete.
3. Synthetic geometry/pipeline tests, Python 3.9 validation, reviewable manifest/diff — complete (36 tests on Python 3.9 and local runtime).
4. Shared backend activation — complete; user explicitly approved, deployed 10 files, restarted and verified both domains plus 36 live-source synthetic tests.

## Decisions
User has specified the implementation behavior; brainstorming's already-specified/bug-fix exception applies. Feature matching may use visible eye/skin texture corners, but do not force lesion contours to match or deform a changing lesion. Numeric measurement retains independent accuracy checks. No database migration.

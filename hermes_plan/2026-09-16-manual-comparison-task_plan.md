# Manual alignment and usable same-site comparison
## Phases
1. Inspect restriction/data/consent/deployment path; document design: complete.
2. Prepare isolated backend candidate and synthetic tests: complete.
3. Implement reusable frontend alignment controls and protected capability-aware requests; deploy staging: complete.
4. Validate geometry, backend contracts, UI and deployment; present shared-backend release for approval: complete.
5. Apply/restart shared backend: awaiting explicit user approval. Existing authenticated SSH control connection is available.
## Scope
No live backend edits, DB migrations or production frontend deployment before required approval. Candidate: /tmp/subskin-manual-alignment/backend; existing live source remains unchanged.

## Release
Candidate: data/release-candidates/manual-comparison-20260916. Frontend staging: 1789496068901. Manifest SHA-256: b927decc36baaba8f273f401cea51f587dc2b1c89130d7936f20593d0d714793. Backend is not enabled yet; do not mark this task fully complete before approval and activation.

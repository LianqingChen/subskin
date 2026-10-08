# Progress

- Context/skills reviewed; current staging version 1789517776353. Preparing frontend and isolated candidate only.

- Frontend build1789518317753 deployed and verified; 14 browser scenarios pass. PWA manifests/icons/SW/public paths/health checked.
- Backend candidate10 files frozen and dry-run verified. Local + server36 tests pass, including approximate translation/rotation/scale, wrong match fallback, lesion growth preservation and visual-vs-numeric tolerance.
- Test harness issues: copied synthetic duplicate fixture into new QA folder; isolated pytest invoked with addopts cleared because root full-project coverage config does not collect isolated candidate imports.
- Explicit shared-backend activation question is pending; do not apply/restart until answered.

## Activation 2026-09-16T00:33:23Z
- User confirmed shared backend activation. Verified frozen manifest and all before hashes; generating report count=0. Applied 10 files and restarted successfully.
- Health/capabilities successful on localhost and both public domains. Anonymous manual endpoint protected with401. Live-source tests36 passed; source hashes match all10 approved files.
- Initial read-only DB preflight failed due a relative DATABASE_URL; resolved against service WorkingDirectory and retried successfully, without DB writes.
- Production frontend unchanged; frontend users can refresh/retry capability check. Activation complete.

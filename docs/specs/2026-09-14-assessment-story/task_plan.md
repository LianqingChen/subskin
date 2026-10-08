# Assessment story report plan

## Goal
Create a concise illustrated assessment record and personal contour-based share poster.

## Phases
1. Context and design — complete.
2. User design approval — complete; includes contour/body-site/profile grounding and SubSkin QR.
3. Frontend implementation — complete; no shared-backend change.
4. Validation and staging — complete; build 1789319952437. Seven pure tests, fourteen browser checks, QR downscale decoding and HTTP/PWA verification passed.

## Decisions
- Exact confirmed-mask silhouette with deterministic art; no external generation service or patient-photo transmission.
- Explicit profile selection to avoid conflating a family member with the signed-in user.
- Export contains only art by default; optional original photo/measurement require visible opt-in.
- Public homepage QR; no private report identifier or credential.
- Production remains 1789178116492; pending release follows the usual user-confirmation workflow.

# Findings

- docs/research initially contains only four documents from the business-model analysis; restricting the archive to that directory would omit most historical plans.
- docs plus hermes_plan contain 226 Markdown files before this task's records; 109 are in hermes_plan, 55 in docs/specs, 19 in docs/plans. These are inventory counts, not counts of completed features or distinct projects.
- Admin is a standalone Vue 3 / Naive UI SPA under web/admin with hash routing, shared administrator-only APIs, and a mobile More drawer. It has no PWA service worker.
- web/app/vite.config.admin.ts is deprecated and must not be used. web/admin/vite.config.ts defaults to the live admin output directory, so staging build must explicitly override output/base.
- Recent DEPLOY_LOG records establish /admin-preview/ under staging for reviewing admin changes before production sync.
- Existing API authentication uses services.admin_auth.get_admin_user. Route guard alone is insufficient to protect document contents.
- No existing generic protected repository-document reader was found in inspected admin modules. A read-only allowlisted service and authenticated API are needed for automatic updates.
- A probe for web/backend/main.py failed because that file is absent; locate the actual API application entry point through FastAPI/include_router searches.
- Historical Markdown includes draft assumptions and claims. Display source date and document stage without treating an agent checkbox as proof of production deployment.

Implemented 2026-09-21: Date-and-subject keys now link matching documents across directories; live initial index was 222 documents / 118 topics before adding the verification report. Browser verification uses synthetic authentication and redacted snapshots; no patient account accessed. Shared backend restart succeeded, public read endpoints require authentication, and production frontend/admin hashes are unchanged.

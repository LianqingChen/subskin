# Consolidate host operations in DSH Console

Scope: move host metrics, service controls and system logs to DSH Console; remove the duplicate SubSkin terminal. Keep SubSkin content, moderation, users, LLM settings, training, planning and knowledge embedding maintenance.

- Add DSH-owned host monitor and allowlisted service/log API; inherit Harness dark appearance.
- Replace SubSkin SystemMonitor with SiteMaintenance (database storage + existing embedding action).
- Remove terminal Vue modules, xterm-only dependencies and backend terminal router/services. Retire /api/admin/system/* endpoints.
- Preserve the existing subskin tmux session under an independent systemd scope and expose a continuation session in DSH before restarting the shared backend.
- Typecheck/build admin only into subskin-admin; never touch user-facing app bundles or database data.
- Validate both applications, old route removal, actual host metrics, dark theme bootstrap and live session preservation; record deployment.

Repository standards: frontend-architect, backend-architect, vue-tsc-guard, deploy-verification. Admin is a standalone application with direct deployment; shared-backend impact has been communicated to the user.

## Execution and review

Completed and deployed. Host monitoring is served by the DSH admin process; the SubSkin backend no longer registers terminal or host-system routes. Website storage and embedding maintenance remain authenticated.

### Frontend review
- Passed: small SiteMaintenance view, composable/API separation, RemixIcon usage, responsive cards and44px actions, external DSH link without credential propagation.
- Schema: admin WebApplication JSON-LD added. Admin has no PWA; user-facing PWA and bundles were not changed.
- Typecheck and admin-only build passed; no type suppression or new circular dependency.

### Backend review
- Passed: storage-only website service, no framework dependency in the new service; host controls use a fixed allowlist in the separate DSH service.
- Terminal router/package exports removed; new boundary tests prevent regressions.
- No database migration or user-data modification. Monitoring logs redact common credentials and personal identifiers.
- Deployment startup reference issue was resolved; shared website health verified healthy afterward.

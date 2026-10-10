# Deployment Log — Deployment Execution

Executed 2026-10-10, ~12:55–13:00 +09:00, on the mac mini, against the frozen trunk revision `78944f76`. Approved by the human at the deployment-execution confirmation (`1101aaa8283023d66bfb7dd09ad44fa4573bcea583973624cd348e301df36596`).

## Timeline

| Step | Command / action | Result |
|---|---|---|
| 1. Before-health | `ops/server/docsurictl status` (12:50 capture) | web running (pid 1209); api stopped (exit 1, ENV-01); workers + tunnel up; web/public endpoints 200; disk 96% |
| 2. Production build | `NODE_ENV=production NEXT_PUBLIC_DOCSURI_REAL_API=1 NEXT_PUBLIC_DOCSURI_RESEARCH_AGENT_ENABLED=true NEXT_PUBLIC_ORCID_LOGIN_ENABLED=false npm run build` (frontend) | **Success** — Next.js standalone; shared first-load JS 103 kB; all routes compiled (identical shape to the Build-and-Test verified build) |
| 3. Rollout | `ops/server/docsurictl restart web` | `restarted web` — `dev.docsuri.web` reloaded; pid **1209 → 14643** |
| 4. Smoke tests | see `smoke-test-results.md` | local 200; public 200; asset branch 404 (contract); API-dependent BFF path 504 (expected — ENV-01) |
| 5. After-health | `ops/server/docsurictl status` | web running (14643); all other states unchanged; public 200; disk unchanged |
| 6. Rollback | not needed | would have been: rebuild previous revision + `docsurictl restart web` (runbook) |

## Deviations (recorded openly)

- **`pnpm` → `npm`:** the runbook/CI use pnpm; pnpm is not installed on the host (corepack would have downloaded it — a global toolchain mutation outside this approval). The executed `npm run build` is the same `next build` verified in Build and Test; no toolchain was installed.
- The brief seconds-long serving blip during the web restart was not independently timed; the post-restart smoke tests passed.

## Outcome

The mac-mini production surface now serves the frozen trunk revision's frontend build. The deployment introduced no new findings: the pre-existing operator items (ENV-01 API reconciliation, ENV-02 disk/logrotate, ENV-03 purge, ENV-04 status probe) remain exactly as recorded in `environment-provisioning/validation-report.md`.

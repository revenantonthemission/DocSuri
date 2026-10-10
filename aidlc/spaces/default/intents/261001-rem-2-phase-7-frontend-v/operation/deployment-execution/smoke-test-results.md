# Smoke Test Results — Deployment Execution

Executed 2026-10-10 immediately after the web-agent restart (pid 14643).

| Check | Command | Result | Interpretation |
|---|---|---|---|
| Local root (BFF web) | `curl -s -o /dev/null -w %{http_code} http://127.0.0.1:3000/` | **200** | The freshly built frontend serves locally |
| Public root (Cloudflare tunnel) | `curl -s -o /dev/null -w %{http_code} https://docsuri.rvnnt.dev/` | **200** | Ingress → tunnel → BFF is live end-to-end on the new build |
| Asset branch (bogus id) | `curl … http://127.0.0.1:3000/bff/api/papers/x/assets/y` | **404** | Contract behavior: denied/missing/non-image collapses to the empty no-store 404; the asset relay responds correctly |
| API-dependent BFF read (bogus job id) | `curl … http://127.0.0.1:3000/bff/api/content-jobs/00000000-…` | **504** | **Expected-degraded**: the gateways' upstream (API `127.0.0.1:8000`) is down under the open ENV-01 finding (`MigrationBlocked: NEEDS_RECONCILIATION`). Not a deployment defect; capability returns when the operator reconciliation completes |

## Notes

- Smoke coverage matched the approved plan; no test was skipped to make the deployment look green — the 504 is recorded as the honest consequence of the open operator finding.
- Post-deploy `ops/server/docsurictl status`: web 200, public 200, workers/tunnel unchanged; nothing else regressed.
- Rollback smoke steps (had they been needed) are the equivalent checks in `rollback-runbook.md`.

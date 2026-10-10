# Environment Provisioning — Consolidated Summary Confirmation

## Sources and Current Status

Read-only verification of the live mac-mini production environment on 2026-10-10 (12:50 +09:00), against `ops/server/README.md` and the deployment-pipeline records. The environment is mostly healthy — public ingress and the web/BFF stack serve — with real findings that need operator attention. **This stage makes no environment mutations.**

## Live observations (read-only)

- **launchd:** `dev.docsuri.web` (pid 1209), four workers (ingestion 1208, summarization 1199, evidence 1179, novelty 1190), tunnel (1184) — running. `dev.docsuri.api` — **stopped, last exit 1 (crash-looping)**. `dev.docsuri.logrotate` last exit 1; `dev.docsuri.worker-purge` last exit 1. `heartbeat`/`backup` idle, last exit 0.
- **Root cause of the API outage (from `~/Library/Logs/DocSuri/api.log`):** `backend.migrations.MigrationBlocked: schema readiness: NEEDS_RECONCILIATION; run explicit reconciliation` — the API refuses to start until the recorded schema reconciliation is executed. This is a deliberate safeguard, and reconciliation is an operator action tied to the already-recorded SQL/realm obligations (Q8-A boundary) — **not** something this workflow executes.
- **Endpoints:** web `http://127.0.0.1:3000/` 200; opensearch 200; minio 200; ollama 200; public `https://docsuri.rvnnt.dev/` **200**; api `127.0.0.1:8000/health` unreachable (agent down).
- **Containers/runtime:** Colima is **running** (Virtualization.Framework, docker socket present); `docsurictl status` nonetheless reports "docker unavailable" — a detection quirk in the status script worth fixing in the ops seam.
- **Disk:** 418 Gi used of 460 Gi — **96% full, 18 Gi free**; rotated logs are multi-GB (`api.log.2/.3` ~70 MB each, worker logs tens of MB), and `logrotate` last exited 1.

## Consolidated Summary Confirmation

- **Scope:** document the as-built environment inventory and validate it from live read-only evidence; surface the findings above; make no mutations and execute no reconciliation.
- **Artifacts to produce:** `environment-inventory.md` (agents, containers, endpoints, tunnel, logs, disk, environment manifests — as-built) and `validation-report.md` (observed state, findings, severity, and the operator actions required — reconciliation, logrotate/purge investigation, disk pressure, status-script docker probe).
- **Limits and authority:** the API's reconciliation, any service restart, log cleanup, or volume change are production mutations requiring explicit operator authorization; they are recorded as required actions, not performed here. The operation guardrails (security review for infra changes, rollback steps, quantified SLOs) are reflected in the artifacts.

Does this all look correct before I generate the environment-provisioning artifacts?

- Looks correct
- Request changes

[Answer]: Looks correct

# Deployment Strategy — DocSuri (mac-mini production)

Revised per the human decision (2026-10-09): everything is served on **this mac mini**; AWS is retired. Aligned with the team mandate (*deploy on merge; every commit passing CI auto-deploys*) and with the repository's production runbook (`ops/server/README.md`).

## Strategy

| Aspect | Choice | Grounding |
|---|---|---|
| Host | This Mac mini is the single production server | `ops/server/README.md` (AWS decommissioned 2026-08-17) |
| Cadence | Continuous deployment on merge: CI green → workspace update → rebuild/restart on the Mac | Team mandate; `ci.yml` + `docsurictl` seams |
| Release mechanism | `git pull` → `docker compose up -d` (data plane, if changed) → frontend standalone rebuild → `ops/server/docsurictl restart web` / `rebuild` | `docsurictl`, server runbook |
| Process supervision | launchd LaunchAgents (`dev.docsuri.*`): web, api (one worker), four workers, purge, logrotate, tunnel, backup | Server runbook |
| Ingress | Cloudflare Tunnel (outbound-only; TLS at the edge); only `127.0.0.1:3000` (the BFF) is published | Server runbook |
| Data plane | Colima containers: Postgres, Redis, OpenSearch, MinIO, ElasticMQ — all loopback-bound | Server runbook |
| Inference | Ollama on the same host (`127.0.0.1:11434`) | Server runbook |
| Rollback | Previous-good revision + `docsurictl` restart (see `rollback-runbook.md`); the daily pg_dump backup preserves data | Runbook + backup agent |
| Credentials | No cloud credentials in the pipeline; local environment manifests hold runtime configuration | Server runbook; u1 infrastructure record |

## Frontend specifics

- Next.js `output: 'standalone'` build served by launchd `dev.docsuri.web`; the BFF (`app/bff/[...path]/route.ts`) is the single ingress choke point and forwards to the loopback gateway (`DOCSURI_GATEWAY_URL`, server-side only).
- Same-origin asset delivery (`/bff/api/papers/{paperId}/assets/{assetId}`) with the backend's auth/license re-check; private 60 s cache; no presigned URLs.
- The frozen revision's verified evidence (build success, 86/494 tests, coverage floors) is the deployable basis; no deployment was executed in this stage.

## Operational notes

- `ops/server/docsurictl status` is the first-line health view (agents, containers, endpoints, tunnel, disk).
- Automatic login must remain enabled: Colima and Ollama live in the user GUI session; bare reboots must recover unattended.
- Single-host capacity/isolation and outage limits remain the explicit trade-off recorded in the u1 infrastructure design; no cloud failover exists by design.

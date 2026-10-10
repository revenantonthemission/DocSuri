# Deployment Execution — Consolidated Summary Confirmation

## Sources and Current Status

The deployment pipeline is revised for mac-mini production (AWS retired); the environment inventory/validation is approved and recorded, including the open High finding ENV-01 (API agent down pending the operator-gated schema reconciliation). This stage **executes** the deployment of the frozen trunk revision to the live mac-mini production surface — a real production action — and records the deployment log, smoke-test results and health-check report. Because executing it mutates production (frontend rebuild + web-agent restart), it proceeds only under this confirmation's approval.

## Consolidated Summary Confirmation

**Deployment plan to execute (on approval):**

- **Target revision:** the committed trunk state `78944f76` of this workspace (production runs from this Mac; the recorded release seams are `pnpm build` + `ops/server/docsurictl restart web`).
- **Steps:**
  1. `cd frontend && NODE_ENV=production NEXT_PUBLIC_DOCSURI_REAL_API=1 NEXT_PUBLIC_DOCSURI_RESEARCH_AGENT_ENABLED=true NEXT_PUBLIC_ORCID_LOGIN_ENABLED=false pnpm build` (the verified standalone build).
  2. `ops/server/docsurictl restart web` (reload `dev.docsuri.web` to serve the fresh build).
  3. Smoke tests: `http://127.0.0.1:3000/` 200; public `https://docsuri.rvnnt.dev/` 200; a paper page and the asset path (`/bff/api/papers/<id>/assets/<assetId>`) behave per contract; job stream endpoint reachable through the BFF.
  4. Health: `ops/server/docsurictl status` before/after; record the delta.
- **Expected effects:** brief web-serving blip during the restart (seconds); the API stays down until the operator reconciliation (ENV-01) — smoke results will say so explicitly rather than masking it; no other agent or container is touched.
- **Rollback (ready, not expected):** `cd frontend && pnpm build` from the previous good revision + `docsurictl restart web` (per `rollback-runbook.md`); nothing else changes.
- **Limits:** no reconciliation, no API restart, no docker/colima mutation, no log/disk cleanup, no secret inspection — the open operator findings remain as recorded.

Does this deployment plan look correct to execute?

- Looks correct
- Request changes

[Answer]: Looks correct

# CD Configuration — DocSuri (mac-mini production)

Revised per the human decision (2026-10-09): **"We're not using AWS anymore. Everything should be served in this mac mini."** This matches the repository's own production runbook: `ops/server/README.md` — *"This Mac is the production server (AWS decommissioned 2026-08-17). Everything runs here: data plane in Colima containers, app processes under launchd, inference on Ollama, public ingress through a Cloudflare Tunnel."*

## What changed in this revision

- **Retired:** `.github/workflows/cd.yml` (the AWS CD: OIDC role assumption, ECR image pushes, `cdk deploy`, ECS service updates). Deleted in this revision; the u1 infrastructure record already classified the CDK stacks as *historical, not deployment inputs*.
- **Adopted:** the repository's actual mac-mini release seams — `ops/server/install.sh` (launchd agents), `ops/server/docsurictl` (`status`, `logs`, `restart`, `rebuild`), `backend/docker-compose.yml` (data plane), and the frontend standalone build.

## Release path (deploy on merge)

1. A commit merges to the trunk; GitHub CI runs lint / typecheck / `test:coverage` / e2e / build (`ci.yml` — the CI Pipeline stage's coverage-gated job).
2. The mac mini updates the workspace to the merged revision (`git pull`).
3. Backend/data plane (only if changed): `docker compose -f backend/docker-compose.yml up -d` under the Colima runtime.
4. Frontend (only if changed): `cd frontend && NODE_ENV=production NEXT_PUBLIC_DOCSURI_REAL_API=1 … pnpm build` then `ops/server/docsurictl restart web` (or `ops/server/docsurictl rebuild` for the combined rebuild+reload).
5. Verify: `ops/server/docsurictl status` (agents + containers + endpoints + tunnel + disk) and the local smoke checks below.

## Runtime topology (as documented and configured)

| Piece | Mechanism | Exposure |
|---|---|---|
| Next.js standalone — the BFF | launchd `dev.docsuri.web` | `127.0.0.1:3000`, the ONLY port published through the Cloudflare tunnel |
| FastAPI monolith (one uvicorn worker by design) | launchd `dev.docsuri.api` | `127.0.0.1:8000` |
| Ingestion / summarization / evidence / novelty workers | launchd keepalive agents (ElasticMQ poll loops, graceful SIGTERM) | loopback only |
| Postgres · Redis · OpenSearch · MinIO · ElasticMQ | Colima containers via compose | `127.0.0.1` only |
| Inference (bge-m3, qwen3:8b) | Ollama brew service | `127.0.0.1:11434` |
| Ingress | Cloudflare Tunnel (`dev.docsuri.tunnel`, outbound-only, no inbound port open) | TLS at the edge → `http://127.0.0.1:3000` |
| Maintenance | `dev.docsuri.worker-purge` (daily), `dev.docsuri.logrotate`, `dev.docsuri.backup` (pg_dump → iCloud) | local |

Operating invariants from the runbook: LaunchAgents (not LaunchDaemons — Colima/Ollama live in the GUI session), automatic login must stay enabled for unattended recovery, logs in `~/Library/Logs/DocSuri/` (daily rotation, 50 MB, 3 generations).

## Verification boundary

- This stage executed no deployment and restarted no service; the commands above are the configured release seams as documented in `ops/server/README.md`.
- GitHub-hosted execution of CI remains the gate; the mac-mini step is local by design (no cloud credentials anywhere).

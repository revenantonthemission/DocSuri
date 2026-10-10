# Environment Inventory — DocSuri mac-mini production (as-built)

Captured 2026-10-10 12:50 +09:00 from live read-only checks plus `ops/server/README.md`. **No changes were made.**

## Host

- Single production server: **this Mac mini** (AWS decommissioned 2026-08-17). macOS, user session starts launchd **LaunchAgents** (not Daemons — Colima/Ollama live in the GUI session; automatic login must stay enabled).
- Disk: 460 Gi volume, 418 Gi used, **18 Gi free (96% full)**.

## launchd agents (`dev.docsuri.*`)

| Agent | State at capture | Role |
|---|---|---|
| `web` | running (pid 1209) | Next.js standalone — the BFF (`127.0.0.1:3000`) |
| `api` | **stopped — last exit 1** | FastAPI monolith (one worker by design), `127.0.0.1:8000` |
| `worker-ingestion` | running (1208) | ElasticMQ poll loop |
| `worker-summarization` | running (1199) | ElasticMQ poll loop |
| `worker-evidence` | running (1179) | ElasticMQ poll loop |
| `worker-novelty` | running (1190) | ElasticMQ poll loop |
| `worker-purge` | last exit 1 | daily GDPR grace-period sweep (one shot) |
| `logrotate` | last exit 1 | daily in-place truncation preserving launchd descriptors |
| `tunnel` | running (1184) | cloudflared (outbound-only) |
| `heartbeat` | idle, last exit 0 | health heartbeat |
| `backup` | idle, last exit 0 | daily pg_dump → iCloud |

## Runtime services

- **Containers (Colima, running — Virtualization.Framework, docker socket at `~/.colima/default/docker.sock`):** Postgres · Redis · OpenSearch · MinIO · ElasticMQ via `backend/docker-compose.yml`, all bound to `127.0.0.1`.
- **Inference:** Ollama (brew service), `127.0.0.1:11434` (bge-m3, qwen3:8b).
- **Ingress:** Cloudflare Tunnel (`dev.docsuri.tunnel`) → `http://127.0.0.1:3000` only; TLS at the Cloudflare edge; no inbound port open on the host.

## Endpoints observed

| Endpoint | Result |
|---|---|
| `http://127.0.0.1:3000/` (web/BFF) | 200 |
| `http://127.0.0.1:8000/health` (api) | unreachable (agent down) |
| `http://127.0.0.1:9200/_cluster/health` | 200 |
| `http://127.0.0.1:9000/minio/health/live` | 200 |
| `http://127.0.0.1:11434/v1/models` (Ollama) | 200 |
| `https://docsuri.rvnnt.dev/` (public) | 200 |

## Operational seams and artifacts

- Control: `ops/server/docsurictl` (`status`, `logs`, `restart`, `rebuild`); install: `ops/server/install.sh`; tunnel: `ops/server/tunnel-setup.sh`; heartbeat: `ops/server/heartbeat.sh`.
- Logs: `~/Library/Logs/DocSuri/` (daily rotation at 50 MB, 3 generations; currently holding multi-GB history).
- Environment manifests: `backend/.env` (production; secrets — values not inspected or copied); frontend runtime env (`DOCSURI_GATEWAY_URL`, `NEXT_PUBLIC_*` at build).

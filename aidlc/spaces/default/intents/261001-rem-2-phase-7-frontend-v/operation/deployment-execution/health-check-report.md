# Health Check Report — Deployment Execution

Before (12:50) vs after (~13:00) the web-agent rollout on 2026-10-10. Only the delivered change is expected to move; every other state is recorded unchanged.

| Item | Before | After | Delta |
|---|---|---|---|
| `dev.docsuri.web` | running, pid 1209 | running, **pid 14643** | Rollout (expected) |
| web endpoint `127.0.0.1:3000/` | 200 | 200 | Stable |
| public `https://docsuri.rvnnt.dev/` | 200 | 200 | Stable |
| `dev.docsuri.api` | stopped (exit 1) | stopped (exit 1) | Unchanged — ENV-01 open |
| api endpoint `127.0.0.1:8000/health` | unreachable | unreachable | Unchanged — ENV-01 open |
| workers (ingestion/summarization/evidence/novelty) | running | running | Unchanged |
| `dev.docsuri.worker-purge` | last exit 1 | last exit 1 | Unchanged — ENV-03 open |
| `dev.docsuri.tunnel` | running (1184) | running (1184) | Unchanged |
| OpenSearch / MinIO / Ollama endpoints | 200 / 200 / 200 | 200 / 200 / 200 | Unchanged |
| Disk | 418/460 Gi (96%) | 418/460 Gi (96%) | Unchanged — ENV-02 open |

## Assessment

- The deployment met its definition of done: the frozen frontend revision builds and serves on the live host through the public ingress; no service besides `web` was touched; no new finding was introduced.
- The one degraded capability observed (API-dependent BFF reads return 504) is the recorded consequence of ENV-01; it resolves when the operator executes the schema reconciliation and restarts the API agent — an authorized action outside this stage.
- Follow-up SLO framing (from the validation report): quantify availability targets for the public surface and API health, with alert thresholds below the SLO once the operator items are cleared.

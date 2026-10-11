# DocSuri v2 — Initial environment observations

Initial observations: 2026-10-11, approximately 07:26–07:27 Asia/Seoul
(2026-10-10 22:26–22:27 UTC). Follow-up metadata checks were performed during
the same feasibility session.

This is supporting discovery evidence, not a feasibility conclusion or an
approved migration plan. No services were started, restarted, or changed.

## Declared implementation and hosting

| Source | Observation | Limit |
| --- | --- | --- |
| `frontend/package.json` | Next.js 15.5.26, React 19, TypeScript, SWR, Tailwind; Vitest and Playwright tooling | Package declarations do not establish deployed versions or passing checks. |
| `backend/pyproject.toml` | Python 3.13+, FastAPI, SQLAlchemy/Postgres and Redis; local shared, discovery, summarization and operations packages | This is the current implementation, not a mandatory v2 technology choice. |
| `ingestion/pyproject.toml` | Python 3.11+; document parsing, AWS SDK, OpenSearch and Postgres dependencies | Dependency presence does not prove current use of each provider. |
| `ops/pyproject.toml` | Python 3.13+ operations package with shared/platform-integrity dependencies | Does not establish which jobs are currently running. |
| `ops/server/README.md` | Describes Mac-hosted production, Colima services, launchd application processes, Ollama and Cloudflare; records AWS decommissioning on 2026-08-17 | A historical runbook; deployment, limitations and backup health require live verification. |
| `ops/cdk/cdk.json` | Retains AWS deployment configuration | Configuration is not evidence that AWS resources still exist. |
| `backend/docker-compose.yml` | Declares full-local Postgres, Redis, OpenSearch, MinIO and ElasticMQ services | Existence of the file does not establish a running stack. |
| `ops/local-stack/colima-stack.compose.yaml` | Explicitly describes a local development stack, including SeaweedFS as an object-store stand-in | Development fixtures must not be treated as production data or production configuration. |

## Read-only local observations

| Check | Result | Interpretation |
| --- | --- | --- |
| `docker context ls` | Current context was `colima`; other listed contexts included default, desktop-linux and orbstack | Container observations below apply only to the current context. |
| `docker ps` | No running containers returned | No running containers in that context at the observation time. |
| `docker ps -a` | Five `docsuri-rem` services were stopped; two older Postgres test containers were also stopped | Stopped development/test containers remain. Their presence does not establish production users or data. |
| Selected `docker inspect` labels and mounts | All five `docsuri-rem` containers name `ops/local-stack` as their Compose working directory; database, cache, search and object-store mounts use the corresponding development volumes | This links the stopped services to the repository's development stack. No container environment variables or record contents were inspected. |
| `docker volume ls` filtered for DocSuri/rem3 | Postgres, Redis, OpenSearch and SeaweedFS volumes were listed under `docsuri-rem` | Persistent volumes exist; contents, age and authority have not been established. |
| `launchctl list` filtered for DocSuri | No matching rows in the caller's launchctl context | This is not an exhaustive check of all users or system service domains. |
| HTTP GET `http://127.0.0.1:8000/health` with five-second timeout | Connection failed; curl exit 7, HTTP 000 | The documented local backend endpoint was unavailable at that moment. |
| HTTP GET `http://127.0.0.1:3000/` | HTTP 200 | The frontend root responds; the complete paper journey has not been verified. |
| Frontend title and listener metadata | Page title is `DocSuri`; a Node process listens on loopback port 3000 | Confirms that the responding root page identifies itself as DocSuri; does not validate backend connectivity. |
| Directory metadata for `~/DocSuriData` and `~/Backups/docsuri` | Both directories exist | No private record contents were read; existence alone does not establish valid backups. |
| Directory metadata for `~/DocSuriData/minio` and `~/Backups/docsuri/postgres` | Both more specific directories also exist | Contents and restorability remain unverified. |

## Open evidence gaps

- Identify the authoritative currently served environment and reconcile it with
  the runbook, retained AWS configuration and stopped development stack.
- Establish aggregate existing-user counts and saved-data categories from that
  authoritative environment. These remain unknown; do not infer a fresh start.
- Verify backup dates, coverage and restorability before choosing continuity or
  migration. Merely finding volumes or backup directories is insufficient.
- Baseline the complete find → understand → save → revisit journey, including
  responsiveness, interruption recovery and defect reproduction.
- Establish current operating costs and external integration obligations.
- The user initially left the budget open, then explicitly set it to $0 with
  only free or local stacks. No fixed deadline, one human maintainer with coding
  agents, and no fixed technology choice remain confirmed. Estimate effort and
  verify resource sufficiency within the budget; evaluate free/local replacements
  against stability and repairability. The user
  also confirmed no known external commitments beyond current capabilities and
  directed investigation of uncertain policy requirements before hosting and
  data-handling choices. These answers are in `feasibility-questions.md`.

## Evidence method

Repository configuration and runbook files were read directly. Graph coverage
was checked at generation `2026-10-10T22:25:56Z`; the consulted configuration
paths had matching metadata with no recorded gap. This is a best-effort coverage
signal, not proof of exhaustive discovery. Local process, container, directory
and HTTP results are point-in-time observations. No live AWS inventory or
public production end-to-end verification has been completed in this stage.

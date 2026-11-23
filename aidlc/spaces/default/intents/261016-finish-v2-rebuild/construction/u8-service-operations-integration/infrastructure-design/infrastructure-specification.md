# Infrastructure Specification — U8 complete service operations and integration

Date: 2026-10-22 (Asia/Seoul)
Unit: u8-service-operations-integration (service). Sources:

- confirmed [infrastructure-design-questions.md](infrastructure-design-questions.md) (Q1, Q2 and the points settled from the records);
- this Unit's NFR design: [security](../nfr-design/security-design.md), [performance](../nfr-design/performance-design.md), [scalability](../nfr-design/scalability-design.md), [reliability](../nfr-design/reliability-design.md), [observability](../nfr-design/observability-design.md) and [logical components](../nfr-design/logical-components.md) (its § 6 is the hand-off this file answers);
- the [functional spec](../functional-design/functional-spec.md) (boundaries, Workflows 19 and 20) and [rules](../functional-design/rules.md);
- the [tech-stack decisions](../nfr-requirements/tech-stack-decisions.md) (names, folders and addresses, from Q23 of NFR Requirements);
- the component catalogue and the contract summary of the earlier record (`261010-docsuri-v2-rebuild/inception/domain-design/components.md` and `contract-design/contract-summary.md`), which this record's inception does not repeat;
- this Mac: Apple M4 Pro, 14 cores, 24 GiB of memory, macOS 27.0.1, FileVault on.

Everything runs on this one Mac. There is no cloud compute. The only outside services are Cloudflare (edge and tunnel), the providers (Google, ORCID, Resend, Notion), healthchecks.io and GitHub. How a release travels here is in [cicd-pipeline.md](cicd-pipeline.md), and what is watched is in [monitoring-design.md](monitoring-design.md).

## 1. Deployment

| Facet | Choice | Rationale |
|---|---|---|
| Compute model | Native processes under system launch jobs on this Mac, no containers for v2. OrbStack stays only for v1, until v1 retires | jobs start at boot without a login, and each runs as its own account (NFR Requirements Q18, Q19) |
| Long-running jobs | `org.docsuri.v2.host`, `.workers`, `.scheduler`, `.maintenance`, `.standing`, `.postgres`, `org.docsuri.models`, `org.docsuri.tunnel`, each with `KeepAlive`, `RunAtLoad` and `ExitTimeOut` 30 | reliability-design.md § 3 |
| Root jobs | `org.docsuri.v2.pf` (boot), `.backup-unlock` (boot and every 60 seconds), `.logrotate` (03:00) | reliability-design.md § 3 |
| Ingress | browser → Cloudflare's edge (TLS) → the tunnel, an outbound connection made by `_docsuri_tunnel` → `127.0.0.1:18200` (v2's host) or `:18201` (the maintenance server), over HTTP | no port on this Mac is open to the network. The scheme comes from the public host name (security-design.md § 4) |
| Egress | outbound HTTPS to Cloudflare (the tunnel), Google, ORCID, Resend, Notion, healthchecks.io and GitHub (the public check runs and release assets an install reads) | each call has its time limit (reliability-design.md § 10) |
| Local addresses | loopback only: 18200, 18201, PostgreSQL 15432, the model runtime 11434. On this Mac the composed realm uses 18109 and 15509 | the packet filter ties 18200, 18201, 11434 and 15432 to their listening accounts (security-design.md § 6.8) |
| Storage, internal disk | `/Library/DocSuri/` on the FileVault-encrypted data volume: the releases, the runtimes, the profile root, PostgreSQL's data, the models, the availability record, the evidence and the control folder | Time Machine excludes the whole folder (security-design.md § 6.7) |
| Storage, external drive | `DocSuri_Backup` (encrypted APFS, the backup account) and the new volume for v1's stores, for example `DocSuri_v1` (encrypted APFS, your login account) | NFR Requirements Q14–Q17, Q24 |
| Releases | one root-owned folder per release, `/Library/DocSuri/releases/<tag>/`, each with its own Python environment built at that path. `/Library/DocSuri/release` and `release-previous` are root-owned links to the installed release and the one before it | Q2 A; uv environments record absolute paths, so none is ever moved (cicd-pipeline.md § 5.3 and § 6) |
| Environments | each unit's synthetic realm, the CI lanes, the composed realm (CI and this Mac), the production profile in rehearsal mode (the soak), then live mode | cicd-pipeline.md § 7 |
| Infrastructure as code | every arrangement file is a template in the repository, rendered and installed by one idempotent installer, run in person as root, with a plan mode. Drift is caught by the isolation check's digests | § 4 |
| Sizing | memory: v2's host and workers under 4 GiB; PostgreSQL's 512 MiB of buffers; the models up to about 5.6 GiB. 50 database connections, 39 of them allocated. An 8 GiB storage budget. Internal-disk floors of 20 and 10 GiB, and a 64 GiB backup floor | performance-design.md § 3 and § 6; scalability-design.md § 3 and § 4 |
| Edge | Cloudflare's default edge for `docsuri.rvnnt.dev`. It caches only the public, content-hashed build files, under their own headers | security-design.md § 4 |

## 2. Infrastructure services

| Service | Role | Configuration | Notes |
|---|---|---|---|
| v2's PostgreSQL 16.14, with pgvector | database | `listen_addresses = '127.0.0.1'`, `port = 15432`, the private socket folder; SCRAM only (`pg_hba.conf` in security-design.md § 6.3); `shared_buffers = 512MB`, `max_connections = 50`, `work_mem = 16MB`, `maintenance_work_mem = 256MB`; `max_wal_size = 1GB`, `wal_keep_size = 0`, `archive_mode = off`, no slots or WAL senders; the server-log settings of security-design.md § 7.2; pgvector in `template1` and in each database | data in `postgres/data/` (0700, `_docsuri_v2_db`). Built from source with pgvector, both pinned |
| The database's roles | access | each owner's owner and login roles, every owner login with `CONNECTION LIMIT 4`; the disposable-databases role; the scheduler's login (member of the disposable role only); the backup agent's logins; the operator tool's logins, one of them the restore login with the owner-role memberships a restore needs; the operations login in `pg_monitor` | security-design.md § 6.3; scalability-design.md § 3.1 |
| Search indexes | search | an HNSW index (`vector_cosine_ops`, `m = 16`, `ef_construction = 64`) on `corpus.projection`'s `vector(1024)` column; a stored per-paper text column with its GIN index; the existing per-chunk `lexical` GIN index. A search transaction sets `hnsw.ef_search = 200` and pgvector's iterative index scan | performance-design.md § 2.4 |
| The model runtime, Ollama 0.40.7 | inference | `OLLAMA_HOST=127.0.0.1:11434`, `OLLAMA_MODELS=/Library/DocSuri/models`, `HOME=/Library/DocSuri/models-state`, `OLLAMA_MAX_LOADED_MODELS=2`, `OLLAMA_NUM_PARALLEL=1`. The models are `qwen3:8b` and `bge-m3:latest`, each pinned by its manifest digest | shared with v1. The search model is kept loaded (performance-design.md § 3.3) |
| The tunnel, cloudflared 2026.10.3 | ingress | run by name from its credentials file. Three registered configurations: v1's web (`127.0.0.1:3000`), v2's host (`127.0.0.1:18200`) and the maintenance server (`127.0.0.1:18201`). The last two set `httpHostHeader: docsuri.rvnnt.dev`. Each keeps the `ssh.rvnnt.dev` route and sets `no-autoupdate: true` and `loglevel: warn` | the active choice is a root-owned file, changed only by tunnel routing |
| Cloudflare's edge | TLS, DNS, cache | "Always Use HTTPS" on; minimum TLS 1.2; Rocket Loader, Email Address Obfuscation, automatic Web Analytics and Zaraz off | set by hand and recorded in the installation log |
| The packet filter | firewall | the anchor `/etc/pf.anchors/org.docsuri.v2`, loaded under `com.apple/*`, with the listener rules of security-design.md § 6.8 | enabled at boot by `org.docsuri.v2.pf` |
| The backup volume | backup storage | `DocSuri_Backup`, with U8's folder `docsuri-v2`: `archives/`, `staging/` and the agent's catalogue | only the backup agent reads or writes there (Workflow 19) |
| The maintenance server | static fallback | the backend's ASGI stack serving the notice and the static legal pages, `GET` and `HEAD` only, `no-store` | no application code or database |
| healthchecks.io | outside alerting | three checks: the heartbeat (5 minutes, 5-minute grace), the daily backup (1 day, 2-hour grace), the weekly restore verification (7 days, 6-hour grace) | free plan. The ping addresses are held only by the scheduler account |
| Resend | email | the free plan, within the shared count of 60, 90 and 2,700 | through the email-allowance port (security-design.md § 13) |
| Google, ORCID | sign-in | redirect URIs `https://docsuri.rvnnt.dev/sign-in/callback/google` and `/orcid` | security-design.md § 3.3 |
| Notion | export | each owner's own token | as U6 designed |
| GitHub | source, CI and releases | public repository; branch protection on `develop` and `main`; the CI lanes; `release.yml` | cicd-pipeline.md |

There is no cache server, message queue, search server or metrics server. The owners' job tables in PostgreSQL are the queue, as built, and search runs in PostgreSQL (Q5 of NFR Design). v1's Redis, OpenSearch and MinIO stay with v1 until it retires.

## 3. Shared infrastructure

| Shared Resource | Owner Unit | Consumer Units | Access Boundary |
|---|---|---|---|
| v2's PostgreSQL instance | U8 (the production profile) | U1–U7, each owner in its own schema | owner roles, SCRAM, the per-process connection gates |
| The model runtime | U8 (the arrangement) | DiscoveryCitations, PaperAssistance and ResearchWorkspace (U1, U3, U4), and v1 | the packet filter on its listener, the pinned digests, one v2 model job at a time |
| The tunnel | U8 | v1's web until settlement, v2's host, the maintenance server | routing only through the fixed command, in person |
| The operations ledger | U8 (ServiceOperations, through the ledger component) | PlatformControl (U7), through the ledger component's fixed command; the Resend adapters of AccountAccess (U2) and TopicsDigests (U5), through the email-allowance port | the ledger's lock, append-only |
| The backup volume | U8 (the backup agent) | PlatformControl's operations (U7) | the backup account only |
| The release folder | U8 (the release path) | every unit's code | root-owned; changed only in person |
| The GitHub repository and CI minutes | all units | all units | branch protection |

## 4. The installer

The installation of Workflow 20 is code: templates in the repository, rendered and installed by one installer you run in person as root.

| Phase | Installs | Workflow 20 step |
|---|---|---|
| Accounts | the five new non-login accounts, with their UIDs | 1 |
| Runtimes | PostgreSQL 16.14 with pgvector built from source, Ollama 0.40.7, cloudflared 2026.10.3 and the first release, each checked against its publisher's checksum and with `otool -L` | 2 |
| Folders and the database | the folders with their owners and modes; the Time Machine exclusions; PostgreSQL's initialisation, configuration, roles and `template1`'s extension; each password generated for production into its holder's file or the System keychain | 3 |
| Rule files | the packet filter anchor, the tunnel's registered configurations, the launch job definitions and the sudo rules (`visudo -c -f`) | 4 |
| Models and tunnel | the models' clones and their verification; the tunnel's move and the certificate's revocation | 5, 6 |
| Filter, volume and jobs | the packet filter's boot job; the backup volume's new passphrase and its unlock job; v2's jobs, stopped through service control | 7, 8, 9 |
| Restart and check | the authorized restart, then the isolation check | 10, 11 |

- **Plan mode.** It lists every file, account, setting and folder it would change, with the difference, and changes nothing.
- **Idempotent.** A second run changes nothing. Each phase checks its own result before the next starts.
- **Steps that stay by hand,** because they need your eyes or a login: the Cloudflare dashboard (certificate revocation, routes, the hostname's settings) and healthchecks.io's checks. Each is a checklist item the installer waits on and records, without the secret.
- **Drift.** The installer writes `control/arrangement-manifest.json`: the arrangement version and the digest of every file it put in place. The isolation check compares the installed files against that manifest every 5 minutes, whichever release is running (cicd-pipeline.md § 9).
- **On this Mac,** the composed realm uses its own throwaway PostgreSQL instance, initialised in `/tmp` from the root-owned 16.14 build as your login account at `127.0.0.1:15509`, and removed afterwards.

## 5. Cost

- Everything above is free or runs locally (NFR6.1). The only running cost is this Mac's electricity, which is not designed here.
- Capacity limits and their signals are in scalability-design.md § 7.

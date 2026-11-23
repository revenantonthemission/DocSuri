# Logical Components — U8 complete service operations and integration

Date: 2026-10-22 (Asia/Seoul)
Unit: u8-service-operations-integration (service). Sources:

- this stage's [security](security-design.md), [performance](performance-design.md), [scalability](scalability-design.md), [reliability](reliability-design.md) and [observability](observability-design.md) designs, and its confirmed [questions](nfr-design-questions.md) (Q1–Q6);
- the [tech-stack decisions](../nfr-requirements/tech-stack-decisions.md) (names, folders and addresses, Q23) and the [functional spec](../functional-design/functional-spec.md) (boundaries and integration points, Workflows 19 and 20).

This is the parts list of the running arrangement: what each part is, how the parts connect, where failures stop, what they share and how they are kept apart. It hands Infrastructure Design the list of things to configure (§ 6).

## 1. Component inventory

### 1.1 Long-running jobs

| Component | Launch job | Runs as | Listens on, or reaches | Holds or serves | Patterns applied |
|---|---|---|---|---|---|
| v2's host | `org.docsuri.v2.host` | `_docsuri_v2` | `127.0.0.1:18200` | every owner's routes, the workspace's build, the health routes | the browser boundary (security-design.md § 4), connection gates (performance-design.md § 3.1), request identifiers, latency summaries, the refused-start state (reliability-design.md § 4) |
| v2's workers | `org.docsuri.v2.workers` | `_docsuri_v2` | outward: the providers, the model runtime | the owners' job loops, the capability producers and the tolerance watcher | one model job at a time, leases, the producers' timers (observability-design.md § 3) |
| v2's scheduler | `org.docsuri.v2.scheduler` | `_docsuri_v2` | — | the application's own timed work, such as digest schedules and U6's housekeeping | its owners' schedules |
| The maintenance server | `org.docsuri.v2.maintenance` | `_docsuri_v2` | `127.0.0.1:18201` | the notice and the static legal pages | no application or database, `no-store` |
| The standing job | `org.docsuri.v2.standing` | `_docsuri_v2_sched` | outward: the public address, `127.0.0.1:18200`, healthchecks.io | the heartbeat, backups, verifications, disposals, the isolation check and housekeeping | one lane per task, catch-up at start (reliability-design.md § 11) |
| v2's PostgreSQL instance | `org.docsuri.v2.postgres` | `_docsuri_v2_db` | `127.0.0.1:15432` and its private socket | the production, rehearsal, import and scratch databases, with pgvector | SCRAM only (security-design.md § 6.3), the WAL bound, the connection budget |
| The model runtime, shared with v1 | `org.docsuri.models` | `_docsuri_models` | `127.0.0.1:11434` | the two pinned models | at most two loaded, one request per model, the search model resident (performance-design.md § 3.3) |
| The tunnel, shared with v1 | `org.docsuri.tunnel` | `_docsuri_tunnel` | outward: Cloudflare | the public address, routed to v1's web, v2's host or the maintenance server | root-owned registered configurations, `no-autoupdate`, `loglevel: warn` |

### 1.2 Root jobs

| Component | Launch job | Runs | Does |
|---|---|---|---|
| The packet filter's loader | `org.docsuri.v2.pf` | once at boot | loads `/etc/pf.anchors/org.docsuri.v2` under `com.apple/*` and enables the filter |
| The backup volume's unlock | `org.docsuri.v2.backup-unlock` | at boot and every 60 seconds | unlocks `DocSuri_Backup` with the System keychain's passphrase |
| The log rotation | `org.docsuri.v2.logrotate` | 03:00 daily | rotates and expires the fixed list of log folders |

### 1.3 Commands that run on demand

| Component | Runs as | Started by | Does |
|---|---|---|---|
| The backup agent | `_docsuri_r1t_backup` | the scheduler account (unattended commands) or you (in-person commands), through sudo | every write, read back and deletion on the backup volume, through its catalogue (Workflow 19) |
| The fixed commands | root, `_docsuri_v2` or `_docsuri_r1t_backup`, per command | you, with your password each time, or the scheduler account for its unattended set | service control, tunnel routing, the database operations, profile operations, copy disposal, v1 lifecycle, decisions, credential release (security-design.md § 5.2) |
| The operator tool (PlatformControl) | your login account | you | the bound operations, with their receipts, through the fixed commands |
| The ledger component | `_docsuri_v2` | the service in-process; the scheduler and you through its fixed command | appends to and copies the operations ledger, under its lock. It also implements the Resend adapters' email-allowance port (security-design.md § 13), so no owner calls ServiceOperations |
| The production environment tool | `_docsuri_v2` | you, in person | the units' operator commands against the production profile (BR6.9) |
| The migration tool | `_docsuri_v2` for its import phases, through its fixed command, so the owners' imports use the owners' own logins under trusted composition authority; its copies go through the backup agent's in-person commands | you, in person | dry runs and the final run (Workflow 9) |
| The runtime isolation check | root | the scheduler account, every 5 minutes | the arrangement's items (security-design.md § 6.8) |

### 1.4 Stores

| Store | Where | Owner and mode | Holds |
|---|---|---|---|
| The profile root | `/Library/DocSuri/profile/` | `_docsuri_v2`, 0700 | the operations ledger, the environment manifest, the private environment, the owners' credentials, the key folders, the artifact roots, the evidence folder (the installation log, latency summaries, reports) and `logs/` |
| v2's databases | the instance's data folder, `postgres/data/` | `_docsuri_v2_db`, 0700 | at most one production, two rehearsal, one import and one scratch database at once (scalability-design.md § 3.4) |
| The backup volume | `DocSuri_Backup`, folder `docsuri-v2` | `_docsuri_r1t_backup` | archives, staging and the agent's catalogue |
| v1's stores | the new encrypted volume (for example `DocSuri_v1`) | your login account | v1's object store, its dumps and the 2026-10-10 archive |
| The availability record | `/Library/DocSuri/availability/` | `_docsuri_v2_sched`, 0755, files 0644 | one line per 5-minute slot |
| The isolation evidence | `/Library/DocSuri/evidence/isolation/` | root, readable by every account | 14 days of results |
| The control folder | `/Library/DocSuri/control/` | root | `stops/` (stop records) and `logs/` (the root jobs' logs) |
| The configuration | `tunnel/config/`, `/etc/pf.anchors/org.docsuri.v2`, `/etc/sudoers.d/docsuri-v2`, `/Library/LaunchDaemons/org.docsuri.*.plist` | root | the registered origins, the filter's rules, the sudo rules, the job definitions (no secrets) |
| The runtimes and the release | `/Library/DocSuri/runtimes/`, `/Library/DocSuri/release/` | root | the pinned programs, pgvector included, and the release with its Python runtime and dependencies |
| The keychain items | the System keychain | root | the operator tool's database logins and the backup volume's passphrase |
| The accounts' own folders | `scheduler/`, `backup-agent/`, `models/`, `models-state/`, `tunnel/credentials/`, `tunnel/logs/` | each its account, 0700 | that account's logins, ping addresses, models, state, credentials and logs |

### 1.5 Outside this Mac

| Service | Plan | Used for |
|---|---|---|
| Cloudflare | free | the edge for `docsuri.rvnnt.dev` and the tunnel |
| Google, ORCID | free | sign-in |
| Resend | free | account mail and digests, within the shared count |
| Notion | free, through each owner's token | exports |
| healthchecks.io | free | the three checks |
| GitHub Actions | free for the public repository | CI, the complete verification's lane |

v1, until it retires, keeps its launch agents under your login account, its data plane in OrbStack and its Next.js application. It shares only the model runtime and the tunnel with v2.

## 2. How the components connect

| From | To | Over | Checked by | When it fails |
|---|---|---|---|---|
| A browser | v2's host, through Cloudflare and the tunnel | HTTPS to the edge, the tunnel's connection, then HTTP on loopback | the session cookie and CSRF, and the packet filter on the listener | the maintenance notice, or a not-ready answer |
| The host and the workers | v2's PostgreSQL | TCP on loopback | SCRAM with `require_auth` | busy answers, readiness false, retries with a growing wait |
| The host and the workers | the model runtime | HTTP on loopback | the packet filter on the listener, and the pinned digests | search by words only, model jobs wait |
| The workers | Google, ORCID, Resend, Notion | HTTPS | the providers' keys and tokens | the provider's capability is degraded or unavailable |
| The standing job | the backup agent | sudo, as `_docsuri_r1t_backup` | the scheduler account's unattended grant | the request fails, and an incident opens on storage.capacity |
| The standing job | the isolation check | sudo, as root | the unattended grant | the check is unknown, and an incident opens after 15 minutes |
| The standing job | the ledger component | sudo, as `_docsuri_v2` | the unattended grant | the ping reports `/fail` |
| The standing job | the public address and the local health route | HTTPS, and HTTP on loopback | — | the slot is down |
| The standing job | healthchecks.io | HTTPS, with no body | each check's secret address | the check goes late, and alerts after its grace |
| You, through the operator tool | the fixed commands | `sudo -k` | your password, every time | refused |
| The backup agent | the backup volume | the file system | the volume's ownership and encryption, and the catalogue | its status check fails |
| The backup agent | v2's instance, and v1's data plane for snapshots | TCP | SCRAM in v2's instance; a read-only login in v1's | the request fails |
| The unlock job | the System keychain, then `diskutil` | local | root | it retries every 60 seconds |
| ServiceOperations | PlatformControl's evidence | reading files | files every account can read | platform.status or platform.isolation becomes unknown |

## 3. Failure domains and blast radius

| Domain | Contains | Fails when | Blast radius | Containment |
|---|---|---|---|---|
| This Mac | everything | power loss, a macOS update, the hardware | the whole service | the 3-minute chain after the unlock, the external alert, backups on the external drive (reliability-design.md § 9) |
| The internal disk | the databases, the profile and the logs | it fills or fails | the service | the floors, the budget and closing admission; restore from the backup volume |
| The external drive | the backup volume, v1's stores and SSD01 | it is disconnected or fails | backups, and v1's stores | the start continues; writes are refused; a replacement on your decision |
| Cloudflare or the internet connection | public access and the providers | an outage | public access, and every provider | the service keeps its state; healthchecks.io alerts from outside |
| v2's PostgreSQL | all of v2's data | a crash or damaged data | the application | relaunch and crash recovery; production restore |
| The model runtime | embeddings and generation | a crash, or a digest differing from its pin | semantic search, research, novelty, assistance | search by words only; model jobs wait |
| A provider | its features | an outage, or its allowance used up | that provider's features only | its capability is degraded, with no fallback |
| v1 | v1 | anything | v1 only: its data plane and accounts are separate | v2 does not depend on v1 after the switch |
| The service account | the application | a compromise | the application's own data | no sudo grant; it cannot reach the backups, the operator's credentials or other accounts' folders |
| Your login account | the operator tool and v1 | a compromise | in-person steps still need your password (D4); your general sudo use is the residual risk (security-design.md § 17) | password every time; the credentials stay in the System keychain |

## 4. Shared resources and their bounds

| Resource | Shared by | Bound | Where designed |
|---|---|---|---|
| v2's PostgreSQL instance | v2's processes, the scheduler's login, the backup agent, the operator tool, the migration tool | 50 connections (39 allocated), the 8 GiB footprint | performance-design.md § 3.1, scalability-design.md § 3 |
| The model runtime | v1 and v2 | two models loaded, one request at a time per model; v2 runs one model job at a time | performance-design.md § 3.3 |
| The tunnel | v1 and v2 | one active origin at a time, changed only by the routing command | security-design.md § 6.4 |
| The internal disk | v2, v1, macOS and your own files | the 20 GiB threshold and the 10 GiB critical floor | scalability-design.md § 3.3 |
| The external drive's APFS container | the backup volume, v1's volume and SSD01 | the 64 GiB backup floor, read from the backup volume itself | scalability-design.md § 4 |
| The email allowance | account mail and digests | 60 a day for digests, 90 a day in all, 2,700 a month | security-design.md § 13 |
| healthchecks.io's free checks | v2's 3 and v1's 2 | 20 | observability-design.md § 5 |
| The CPU | everything | one password check at a time per process, one model job at a time | performance-design.md § 3 |
| The memory (24 GiB) | everything | v2's host and workers under 4 GiB; PostgreSQL's 512 MiB of buffers; the models up to about 5.6 GiB | performance-design.md § 6 |

## 5. Isolation strategy

- **Accounts per role.** Each part runs as its own non-login account, and only your login account and the scheduler account hold sudo grants, each for a closed set of fixed commands (security-design.md § 5).
- **Programs and files from root-owned folders only.** Nothing comes from a home folder or Homebrew's prefix, and the isolation check confirms it every 5 minutes.
- **Listeners tied to their accounts.** The packet filter lets each local address be served only by its own account's socket.
- **Data kept apart.**
  - Keys stay out of every backup.
  - Backups are reachable only through the backup agent, so the application cannot delete them.
  - v1's data stays in its own data plane and its own encrypted volume.
  - Time Machine excludes `/Library/DocSuri/` and OrbStack's data.
- **Owners kept apart in the database.** Each owner's schema has its own roles. The scheduler's login can drop only disposable databases.

## 6. What Infrastructure Design receives

The next stage turns these into exact files, values and steps:

- **Accounts, folders and modes:** the six accounts with their UIDs, and every folder of § 1.4 with its owner and mode.
- **Launch job definitions:** each label of § 1.1 and § 1.2 with its account, `KeepAlive` or schedule, `ExitTimeOut` of 30 seconds and its log paths, and no secret in any of them.
- **The sudo rules file:** the aliases and grants of security-design.md § 5.2, `timestamp_timeout=0` for the in-person aliases, and `visudo -c -f` at installation.
- **The packet filter:** the anchor's rules (security-design.md § 6.8) and its loader under `com.apple/*`.
- **PostgreSQL:**
  - the 16.14 build with pgvector, checksums and `otool -L`;
  - the settings of tech-stack-decisions.md and performance-design.md § 6;
  - `pg_hba.conf`;
  - the roles, each owner login's `CONNECTION LIMIT 4`, and `pg_monitor` for the operations login;
  - pgvector in `template1` and in each existing database;
  - the restore options (`--no-comments`; `--no-owner` with the disposable-databases role for scratch restores) and the operator tool's restore login with its owner-role memberships (security-design.md § 6.3).
- **The host's server settings:** Uvicorn with `proxy_headers=False` and no `forwarded_allow_ips`, and the outermost middleware that sets the public scheme (security-design.md § 4).
- **The model runtime:** `OLLAMA_HOST`, `OLLAMA_MODELS`, `HOME`, `OLLAMA_MAX_LOADED_MODELS=2` and `OLLAMA_NUM_PARALLEL=1`.
- **The tunnel:** the three registered configurations, with `httpHostHeader: docsuri.rvnnt.dev` for v2's host and for the maintenance server, and Cloudflare's settings for the hostname (security-design.md § 4).
- **Time Machine:** the two fixed-path exclusions.
- **The System keychain:** the operator tool's logins and the backup volume's passphrase.
- **healthchecks.io:** the three checks with their periods and graces (observability-design.md § 5).
- **The rotation job's folder list** (observability-design.md § 7) and the evidence folders' retention.
- **The release build:** precompressed files and the first-load size budget (performance-design.md § 2.2).
- **The complete verification:** its production-size synthetic corpus (performance-design.md § 11).

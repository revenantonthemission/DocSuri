# Tech Stack Decisions — U8 complete service operations and integration

Date: 2026-10-22 (Asia/Seoul)
Unit: u8-service-operations-integration (service). Sources:

- confirmed [nfr-requirements-questions.md](nfr-requirements-questions.md) (Q13, Q18, Q19 and Q22–Q25 above all);
- inception [requirements NFR6 and the constraints](../../../inception/requirements-analysis/requirements.md), as corrected by RC2 in the functional spec;
- the [technology stack](../../../../../codekb/DocSuri/technology-stack.md) (brownfield: Python backend, uv, pytest, Playwright, GitHub Actions);
- this Unit's [functional spec](../functional-design/functional-spec.md) (§ "What this design relies on", Workflow 20) and [rules](../functional-design/rules.md) (BR6.1–BR6.12, BR9.10);
- [security-requirements.md](security-requirements.md), which states the requirements these choices meet.

## Decision

U8 adds no new paid service, data store or framework. It assembles the built backend and workspace into one release, and runs it on this Mac as non-login accounts from root-owned, pinned copies of PostgreSQL, Ollama and cloudflared. [Q13, Q18, Q19, Q22]

| Area | Choice | Rationale |
|---|---|---|
| Application | The built Python backend (FastAPI on Uvicorn), started through the complete assembly's own entrypoint (BR1.7); every earlier assembly keeps booting alone | the established stack; one application against one database (BR1.4) |
| Browser application | The v2 workspace (Vite), built to static files inside the release and served by the v2 host. No Node.js runs in production. The Next.js application retires at settlement (RC2) | Q2 A; one browser application after the switch (BR5.7) |
| Python runtime | CPython 3.13.7 and every dependency installed by uv into the release folder from the lockfile (`uv sync --frozen`), each package checked against its lock hash | the backend's current runtime; nothing loads from a home folder or Homebrew (BR6.5) |
| Database | PostgreSQL 16.14 built from the PostgreSQL project's source release, without ICU or TLS, in `/Library/DocSuri/runtimes/postgresql-16.14/`, as v2's own instance run by `_docsuri_v2_db` | v1 runs 16.14 with the libc locale and no ICU collation; links only system libraries (Q22 A) |
| Model runtime | Ollama 0.40.7 from its official macOS release archive, run by `_docsuri_models` at `127.0.0.1:11434` and shared with v1. The release pins `qwen3:8b` and `bge-m3:latest` by manifest digest (ModelEvidence, BR6.11 (2)) | the models v1 and v2 already use; no second runtime on a tight disk |
| Tunnel | cloudflared 2026.10.3 from Cloudflare's official `darwin-arm64` archive, run by `_docsuri_tunnel` by name from its credentials file, with three root-owned registered configurations (v1 web, v2 host, maintenance server) | Cloudflare's free tunnel; no certificate left valid (BR6.11 (3)) |
| Supervision | launchd system daemons in `/Library/LaunchDaemons/`, each with a fixed label, its account and `KeepAlive`; started and stopped only through PlatformControl's service control, one fixed command per label | starts at boot without a login (BR6.11 (6)); a crash restarts within a minute (NFR7.2) |
| Local address isolation | A packet filter anchor, `/etc/pf.anchors/org.docsuri.v2`, loaded at boot by `org.docsuri.v2.pf`, matching each loopback port to its listening account (`user`) | no other account can serve v2's addresses (BR6.11 (4)) |
| Operations ledger | An append-only JSON Lines file in the profile root, chained with SHA-256, fsynced, with an atomically replaced head; Python's standard library only | Q13 A; survives emptying, restores and the mode change (BR6.10) |
| Maintenance server | A static server on the backend's ASGI stack at `127.0.0.1:18201`, run by the service account, serving only the notice and the static legal pages | Q13 A; no application or database dependency (BR9.10) |
| Backup agent | `pg_dump` and `pg_restore` from the 16.14 build, in custom format, and the earlier platform work's `write_archive` for the final write, run only as `_docsuri_r1t_backup` through fixed commands | Q14 A; the service cannot write or delete backups (BR4.3) |
| Time Machine | Two fixed-path exclusions set as root with `tmutil addexclusion -p`: `/Library/DocSuri/` as a whole, and OrbStack's data folder. The isolation check's backups item confirms them with `tmutil isexcluded` | Q25 A, widened from four folders to the whole tree, so that no private file or log can sit outside the exclusion (BR6.11 (8)) |
| Operator credentials | The operator tool's database logins sit in the System keychain, released only by its fixed command after you authenticate with your password | nothing your login account holds works unattended (NFR3.2) |
| Alerting | healthchecks.io's free plan, pinged by the standing job from the existing heartbeat script's probes | Q9 A; alerts even when the machine is down (NFR9.6) |
| Verification | pytest and Playwright on the composed synthetic realm at `127.0.0.1:18109` and `:15509`, in a new GitHub Actions lane on every change to develop | Q10 A; BR10.1–BR10.4 |

## Names, folders and addresses

These are the values of Q23, which BR6.11 and BR6.12 refer to.

| Item | Value |
|---|---|
| Service account | `_docsuri_v2` (UID and GID 610): v2's host, workers, scheduler and maintenance server |
| Scheduler account | `_docsuri_v2_sched` (611): the standing authority |
| Database account | `_docsuri_v2_db` (612): v2's PostgreSQL instance |
| Models account | `_docsuri_models` (613): the model runtime |
| Tunnel account | `_docsuri_tunnel` (614): the tunnel |
| Backup account | `_docsuri_r1t_backup` (607), unchanged, owner of `DocSuri_Backup` |
| Launch jobs | `org.docsuri.v2.host`, `org.docsuri.v2.workers`, `org.docsuri.v2.scheduler`, `org.docsuri.v2.maintenance`, `org.docsuri.v2.standing`, `org.docsuri.v2.postgres`, `org.docsuri.models`, `org.docsuri.tunnel`, `org.docsuri.v2.pf`, `org.docsuri.v2.backup-unlock`, and `org.docsuri.v2.logrotate` (root, added for NFR9.8) |
| Root-owned folders | `/Library/DocSuri/release/`, `runtimes/postgresql-16.14/`, `runtimes/ollama-0.40.7/`, `runtimes/cloudflared-2026.10.3/`, `tunnel/config/`, `control/stops/`, `control/logs/`, `evidence/isolation/` (readable by every account) |
| Account-owned folders (0700) | `/Library/DocSuri/profile/`, `postgres/data/`, `postgres/socket/`, `models/`, `models-state/`, `tunnel/credentials/`, `tunnel/logs/`, and `scheduler/`, which holds the scheduler's database login, its ping addresses and its logs. The backup agent's folder, `backup-agent/`, belongs to the backup account and holds its logins and `logs/`. The availability record's folder, `availability/`, belongs to the scheduler account with mode 0755, so every account can read it |
| Rule files | `/etc/sudoers.d/docsuri-v2` (0440) and `/etc/pf.anchors/org.docsuri.v2` |
| Addresses | v2 host `127.0.0.1:18200`, maintenance server `:18201`, PostgreSQL `:15432`, model runtime `:11434` |

## Configuration that is a requirement

- **PostgreSQL:**
  - Connections: `listen_addresses = '127.0.0.1'`, `port = 15432`, `unix_socket_directories = '/Library/DocSuri/postgres/socket'`, `unix_socket_permissions = 0700`, `ssl = off`.
  - Authentication: `password_encryption = scram-sha-256`. The superuser role has no password. `pg_hba.conf` holds, in order: one local line for the superuser over the socket, a `host` line that rejects the superuser, and `host all all 127.0.0.1/32 scram-sha-256`.
  - Server log: `logging_collector = on` into `log/` inside the data folder, with daily dated files (`log_rotation_age = 1d`), which the rotation job only deletes after 14 days and never truncates (NFR9.8), `log_min_messages = log`, `log_error_verbosity = terse`, `log_min_error_statement = panic`, `log_statement = 'none'`, `log_min_duration_statement = -1`, `log_parameter_max_length = 0` and `log_parameter_max_length_on_error = 0` (NFR3.9).
  - Write-ahead log: `max_wal_size = 1GB`, `wal_keep_size = 0`, `archive_mode = off`, `max_replication_slots = 0`, `max_wal_senders = 0`.
  - Memory and connections: `shared_buffers = 512MB`, `max_connections = 50`.
  - v2's databases, in production and in the composed verification realm, are created with `ENCODING 'UTF8'` and `LOCALE 'C'`. Sorting is then identical on macOS and in CI's Linux containers, and precomposed Hangul sorts by code point, which follows syllable dictionary order.
  - Every client connects with `require_auth=scram-sha-256`.
- **Ollama:** `OLLAMA_HOST=127.0.0.1:11434`, `OLLAMA_MODELS=/Library/DocSuri/models`, and `HOME=/Library/DocSuri/models-state`, where the runtime keeps its identity key. Allowed origins are left at their default.
- **cloudflared:** each registered configuration names the tunnel chosen at installation and its fixed credentials path, keeps the `ssh.rvnnt.dev` route, and sets `no-autoupdate: true`, because a root-owned copy changes only in person, and `loglevel: warn` (NFR3.9).
- **launchd:** each daemon sets `UserName` and `GroupName` to its account and `RunAtLoad` true, and writes standard output and error to its account's log folder (NFR9.8).
  - Long-running jobs set `KeepAlive` true: `org.docsuri.v2.host`, `.workers`, `.scheduler`, `.maintenance` and `.standing`, `org.docsuri.v2.postgres`, `org.docsuri.models` and `org.docsuri.tunnel`.
  - The standing job keeps its own schedule:
    - every 5 minutes: the backup agent's status check, the isolation check and the heartbeat;
    - 04:00 daily: the backup and its ledger copy;
    - 05:00: the restore verification, on Sundays and on any day an erasure waits for one;
    - after each scheduled backup: the disposal pass.
  - The three root jobs run without `KeepAlive`:
    - `org.docsuri.v2.pf` runs once at boot;
    - `org.docsuri.v2.backup-unlock` runs at boot and every 60 seconds (`StartInterval`);
    - `org.docsuri.v2.logrotate` runs at 03:00 daily (`StartCalendarInterval`) and rotates the logs in its fixed list of log folders, under the link rules of NFR9.8. It is the one job added to Q23's list.
  - A service-control stop disables and unloads the job, which then stays stopped across restarts (BR6.12).
- **Release folder:** a clone of the repository at a release tag on main, in `/Library/DocSuri/release/`, changed only by the release path with administrator rights (BR6.5).

## Rejected alternatives

- **Homebrew's PostgreSQL, Ollama and cloudflared.** Homebrew's folder belongs to your login account, and its Ollama loads libraries from it, so any program you run could swap them (BR6.11 (0)).
- **EDB's signed PostgreSQL installer (Q22 B).** It bundles ICU and OpenSSL, which a loopback-only, SCRAM-only instance does not need, and it adds a service account and a launch job that would then have to be removed.
- **v2's PostgreSQL in OrbStack or another container runtime.** It would run as your login account and start only at login (Q19).
- **Caddy or nginx for the maintenance notice (Q13 B).** It adds a dependency that the backend's own ASGI stack makes unnecessary.
- **Turning Time Machine off (Q25 B).** Your own files would lose their backups. A separate APFS volume for v2's data was also considered and rejected: it would add an unlock and a mount to every boot, when the only cost of local snapshots is a 24-hour tail that erasure evidence already adds to the date of every copy on the internal disk (NFR3.7).
- **Reusing v1's vectors (Q12 B).** Their producing model cannot be told from the code. Re-embedding costs nothing and removes the provenance check.
- **Keeping v1's stores on SSD01 (Q24 B).** Any account on this Mac could read them, and so could anyone who has the drive.

## Verification notes

- The installation log records, for every runtime, its publisher's checksum, the checksum of the downloaded file and the `otool -L` closure, with no secret (NFR3.9, NFR3.11).
- The runtime isolation check then confirms the programs, files, accounts, database, filter, volume, backups and boot items every 5 minutes (BR6.12).
- A runtime upgrade repeats the same checks and the performance measurements (NFR8.11).

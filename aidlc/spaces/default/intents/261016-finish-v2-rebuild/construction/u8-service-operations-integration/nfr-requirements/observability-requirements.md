# Observability Requirements — U8 complete service operations and integration

Date: 2026-10-22 (Asia/Seoul)
Unit: u8-service-operations-integration (service). Sources:

- confirmed [nfr-requirements-questions.md](nfr-requirements-questions.md) (Q1, Q2, Q8, Q9, Q21, Q23);
- inception [requirements FR4.1 and FR4.2](../../../inception/requirements-analysis/requirements.md);
- this Unit's [functional spec](../functional-design/functional-spec.md) (capability registry and Workflows 3 and 4) and [rules](../functional-design/rules.md) (BR3.1–BR3.11, BR6.12, BR10.5, BR10.7);
- the [technology stack](../../../../../codekb/DocSuri/technology-stack.md) and the existing `ops/server/heartbeat.sh`.

The inception requirements name no monitoring requirement, so **NFR9** is derived here from FR4.1 (continuous operation) and FR4.2 (real evidence). Capability states, incidents and the dashboard keep the behaviour the rules define; this file fixes their values and the signals and alerts around them.

## Service levels (NFR9)

- **NFR9.1** — Each objective has one indicator, recorded where it can be checked later:

| Objective | Indicator | Target | Alert well before a breach |
|---|---|---|---|
| Availability (NFR7.1) | up slots over every scheduled 5-minute slot of the month, a missing result counting as down, from the availability record (NFR9.13) | 99.0% a month | a missed heartbeat alerts within 10 minutes; the month's budget is about 7 h 18 min |
| Latency (NFR8.1–NFR8.5) | 95th percentile per measure | the targets in performance-requirements.md | measured in the complete verification and the soak, and shown with your switch-start decision |
| Backups (NFR7.6) | each day's set and ledger copy with integrity passed | every day | a missing daily ping alerts 2 hours after 04:00 |
| Restore verification (NFR7.8) | each Sunday's verification verified | every week | a missing weekly ping alerts 6 hours after 05:00 |

## Capability observations and incidents (NFR9)

- **NFR9.2** — Observation timing (BR3.2, BR3.3, BR3.7). A required capability that is unavailable opens an incident at once. [Q8, Q21]

| Capabilities | Renewal | Stale after | Incident after |
|---|---|---|---|
| Required (account, library, settings, usage, corpus, search, research, novelty, topics, export, operations ledger, storage, background work) | 60 s | 180 s | 10 minutes degraded, unknown or stale |
| Providers and platform.status | 5 minutes | 15 minutes | — (never required) |
| operations.cutover | 5 minutes | 15 minutes | 15 minutes unavailable |
| platform.isolation | 5 minutes | 15 minutes | 15 minutes failed, unknown or stale |

  Export shows degraded once its oldest unclear or accepted effect is older than 24 hours. Digests show degraded once the oldest pending delivery is 2 hours past its scheduled time (BR3.6). The error rate each records is failed over terminal effects in the last 24 hours.
- **NFR9.3** — An incident lives in the operations ledger. It opens, attaches new signals, and resolves only with evidence of one of its four resolution kinds (BR3.7), so a production restore never erases the incident that caused it.
- **NFR9.4** — 운영 shows administrators with current MFA every capability with its state, age and limitations, and the ledger's incidents, backups and recovery requests (BR3.8). It refreshes every 30 seconds and on demand. [Q8]
- **NFR9.5** — While any of the owner's jobs is unfinished, the 작업 list refreshes every 5 seconds. Live state still comes from the job event stream, with that refresh as its fallback (BR5.4). A job's own view keeps the project's rule for real-time job status: its event stream, with polling every 2 seconds when the stream fails (project.md § Mandated). [Q8]

## Alerts (NFR9)

- **NFR9.6** — Alerts use healthchecks.io's free plan, with three checks for v2 [Q9]:

| Check | Pinged | Period | Grace |
|---|---|---|---|
| Heartbeat | every 5 minutes, after probing the public address and the health route | 5 minutes | 5 minutes |
| Daily backup | after the 04:00 set and its ledger copy pass, or `/fail` when they do not | 1 day | 2 hours |
| Weekly restore verification | after the Sunday 05:00 verification, or `/fail` | 7 days | 6 hours |

  - The scheduler account's standing job, `org.docsuri.v2.standing`, sends the pings, reusing the probes of the existing `ops/server/heartbeat.sh`. Nothing of v2's runs as your login account (Q18).
  - The ping addresses are held only by the scheduler account.
  - Only the check name and pass or fail leave the machine, never error details (NFR3.10).
  - A missing or failed ping emails you.
  - v1's own heartbeat keeps its own checks until v1 retires.
  - If the machine is down, no ping arrives, so the heartbeat check alerts even then.

## Signals per component (NFR9)

- **NFR9.7** — Every component has one health signal and one error-rate signal:

| Component | Health signal | Error-rate signal |
|---|---|---|
| v2 host | health route (liveness, readiness) | share of 5xx answers per route class |
| v2 workers and scheduler | background.work, with lanes behind their deadline | failed jobs per lane over 24 hours |
| Maintenance server | answering on `127.0.0.1:18201` (heartbeat during maintenance) | failed requests |
| Standing job | its last successful run time | failed backups, verifications and disposals |
| v2's PostgreSQL instance | storage.capacity (footprint against the budget) | failed connections and transactions seen by the host |
| Model runtime | provider.models (reachable, digest equals the pin) | failed model jobs over 24 hours |
| Tunnel | the heartbeat through the public address; operations.cutover | failed heartbeat probes |
| Backup agent | its status check in platform.status | failed writes and disposals in its receipts |
| Runtime isolation check | platform.isolation | failed items per check (limitations) |
| Providers (Google, ORCID, Resend, Notion) | each provider's capability | refusals and over-limit answers |

## Logs and evidence (NFR9)

- **NFR9.8** — Logs [Q8, Q23]:
  - They carry only what NFR3.9 allows.
  - Each job writes into a folder its own account owns, all under `/Library/DocSuri/`, which Time Machine excludes (NFR3.7):

| Jobs | Log folder |
|---|---|
| v2's service jobs | `profile/logs/` |
| The standing job | `scheduler/logs/` |
| The backup agent | `backup-agent/logs/` |
| v2's PostgreSQL instance | `postgres/data/log/`, with the settings of NFR3.9 |
| The model runtime | `models-state/logs/` |
| The tunnel | `tunnel/logs/` |
| The root jobs (packet filter, backup volume unlock) | `control/logs/` |
  - Each log is rotated daily and kept 14 days, by one root job, `org.docsuri.v2.logrotate`, so no account needs a second job of its own:
    - It acts only inside a fixed, root-owned list of log folders: `profile/logs/`, `scheduler/logs/`, `backup-agent/logs/`, `models-state/logs/`, `tunnel/logs/` and `control/logs/`, plus `postgres/data/log/` for deletion only. It never touches the ledger, the availability record or any other file.
    - At 03:00 daily, it copies each log and then truncates it, so writers holding the file open lose nothing. Each copy gets its log's owner and mode 0600.
    - It deletes every rotated copy older than 14 days.
    - It never follows a link:
      - It reaches each log folder from `/Library/DocSuri/` one component at a time, opening every folder with `O_NOFOLLOW | O_DIRECTORY` and checking its owner: root above the account's folder, the account at and below it. It opens files only relative to the folder's descriptor (`openat` with `O_NOFOLLOW`), so a folder replaced by a link is refused like a file.
      - It acts only on a regular file with a single link, owned by that folder's account. It creates each copy with `O_CREAT | O_EXCL | O_NOFOLLOW` and sets its owner and mode on the open descriptor.
      - It truncates only through the descriptor it copied from, after checking that it is still the same file (device and inode).
      - A link, a directory or any other file is skipped and recorded with a fixed reason key in `control/logs/`. So a planted link can never make root truncate, copy or delete a file outside the logs.
    - PostgreSQL's server log rotates itself daily into dated files (`log_rotation_age = 1d`). The job never copies or truncates those files; it only deletes the ones older than 14 days, under the same link rules.
    - Its program and its list of log folders are root-owned, like every fixed command, and the runtime isolation check covers it with the arrangement's other jobs (BR6.12).
- **NFR9.9** — The runtime isolation check writes each result into `/Library/DocSuri/evidence/isolation/` and keeps 14 days of them, deleting older ones itself. The latest result is part of PlatformControl's read-only status (BR6.12). [Q21]
- **NFR9.10** — Evidence:
  - Readiness evidence records the running release tag and commit (BR6.5).
  - Every readiness or release claim needs a passed VerificationRun for that exact commit (BR10.5).
  - The installation log is kept in the profile's evidence folder and never holds a secret.
  - The soak's evidence holds the measurements of NFR8.1–NFR8.5.
- **NFR9.11** — There is no tracing system, because everything runs on one host. Each request carries a request identifier in its log lines and observations, so a single request can be followed across the host and workers.
- **NFR9.12** — The production probes U8 supplies for the Operation stages read liveness, capability readiness and a signed-out journey only. They never create work, sign in as a person or send anything (BR10.7).
- **NFR9.13** — The availability record (NFR7.1) [Q1, Q9]:
  - After every 5-minute probe, the standing job appends one line to an append-only JSON Lines record: the slot's start, up or down, and a fixed reason key. Each line is synced to disk.
  - The record lives in `/Library/DocSuri/availability/`, a folder the scheduler account owns with mode 0755 and files 0644, outside the scheduler's private folder. Every account, the operator tool included, can read it, only the scheduler account writes it, and it holds no personal data.
  - It keeps 13 months.
  - The month's figure is computed from it over every scheduled slot, with a missing slot counting as down. The operator tool reports the running figure and the remaining budget, and each closed month's figure is taken into the Operation stages' evidence.
  - healthchecks.io's alerts and downtime log are a second, independent view, not the record.

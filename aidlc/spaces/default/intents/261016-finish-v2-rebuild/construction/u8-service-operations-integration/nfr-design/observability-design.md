# Observability Design — U8 complete service operations and integration

Date: 2026-10-22 (Asia/Seoul)
Unit: u8-service-operations-integration (service). Sources:

- confirmed [nfr-design-questions.md](nfr-design-questions.md) (Q1–Q6 and the points settled from the records);
- [observability-requirements.md](../nfr-requirements/observability-requirements.md) (NFR9.1–NFR9.13), with the [reliability](../nfr-requirements/reliability-requirements.md), [performance](../nfr-requirements/performance-requirements.md) and [security](../nfr-requirements/security-requirements.md) requirements they measure, and the [tech-stack decisions](../nfr-requirements/tech-stack-decisions.md);
- the [functional spec](../functional-design/functional-spec.md) (the capability registry, Workflows 3 and 4, and the capability state derivation) and [rules](../functional-design/rules.md) (BR3.1–BR3.11, BR6.12, BR10.5, BR10.7);
- project.md § Mandated and § Forbidden, for real-time job status (the event stream, its polling fallback, the error boundary and the live region);
- the built code, read on 2026-10-22: the workers' control loop, `backend/control_runtime.py`, and the readiness read, `backend/local_observation.py`;
- the existing heartbeat script, `ops/server/heartbeat.sh`.

There is no metrics system and no tracing system. Capability observations are the metrics, the operations ledger is the record of incidents and recoveries, and plain files hold the logs, the availability record and the latency summaries. This file designs how each is produced, kept and shown, and what alerts you. What a log line may carry is fixed in [security-design.md](security-design.md) § 7.

## 1. Decisions at a glance

| ID | Decision | Source | Serves |
|---|---|---|---|
| O1 | Each capability has one producer, which records one safe observation per renewal. State is derived on every read | BR3.2–BR3.4 | NFR9.2 |
| O2 | Producers run on timers in the workers' control loop, observing once at start and then on their interval. The host times only its own error rates and latency | design | NFR9.2, NFR8.6 |
| O3 | A tolerance watcher in the same loop opens incidents in the ledger, one open incident per capability and environment | BR3.7 | NFR9.3 |
| O4 | The standing job pings three healthchecks.io checks. A down heartbeat slot reports a failure at once, and the next up slot clears it | Q9 | NFR9.6 |
| O5 | Logs go into per-account folders as registered JSON fields, and one root job rotates them | security-design.md D11 | NFR9.8 |
| O6 | A request's identifier travels into the jobs it starts | security-design.md D13 | NFR9.11 |
| O7 | The availability record is one JSON Lines file per Seoul calendar month, kept 13 months | NFR9.13 | NFR9.13, NFR7.1 |
| O8 | Latency summaries per route class, every 5 minutes | performance-design.md P10 | NFR8.3 |

## 2. Service levels (NFR9.1)

| Objective | Indicator | Target | Read from | Alert, well before a breach |
|---|---|---|---|---|
| Availability (NFR7.1) | up slots over every scheduled 5-minute slot of the month, a missing slot counting as down | 99.0% a month | the availability record (§ 12) | an outage alerts within 10 minutes (§ 5), while the month's budget is about 7 hours 18 minutes |
| Latency (NFR8.1–NFR8.5) | the 95th percentile per measure | performance-requirements.md | the latency summaries (§ 13) and browser timings | measured in the complete verification and the soak, and shown with your switch-start decision |
| Backups (NFR7.6) | each day's set and ledger copy, integrity passed | every day | the operations ledger | a missing or failed daily ping alerts within 2 hours of 04:00 |
| Restore verification (NFR7.8) | each Sunday's verification verified | every week | the operations ledger | a missing or failed weekly ping alerts within 6 hours of 05:00 |

운영 shows the month's running availability and the budget left (§ 4).

## 3. Observations and incidents (NFR9.2, NFR9.3)

### 3.1 Producers (O1, O2)

- **Where they run.** Each capability in the registry has exactly one producer, from its owner. Producers run in the workers process, on timers in the built control loop, so the host's request threads never wait for them.
- **The host's own.** The host's own error-rate counters (5xx answers per route class) are summarised by the host itself, which writes them as its observation.
- **The first observation.** Every producer observes once as soon as its process starts, then every renewal interval (§ 3.2).
- **What an observation holds:** the capability, its producer, an outcome (available, degraded, unavailable or unknown), the limitation keys, the time, and error-rate counts. Each value must be registered. Anything else, including private text, credentials, email addresses, titles or content, is refused (BR3.4).
- **Bounded buffering.** If the observation store is unavailable, each producer holds up to 60 observations in memory. Beyond that it drops the oldest and counts them, and 운영 shows the count as missing evidence. An observation that fails to record never changes a job, an effect or a request.
- **Housekeeping** deletes observations older than 14 days. Incidents keep their own evidence in the ledger.

### 3.2 Timing (NFR9.2)

| Capabilities | Renewal | Stale after | Incident after |
|---|---|---|---|
| Required: account, library, settings, usage, corpus, search, research, novelty, topics, export, operations ledger, storage, background work | 60 s | 180 s | at once when unavailable. After 10 minutes degraded, unknown or stale |
| Providers and platform.status | 5 minutes | 15 minutes | — (never required) |
| operations.cutover | 5 minutes | 15 minutes | after 15 minutes unavailable |
| platform.isolation | 5 minutes | 15 minutes | after 15 minutes failed, unknown or stale |

- **State.** It is derived on every read: the latest admitted observation, stale once it is older than its bound, and unknown when there is none (BR3.2).
- **Export** shows degraded once its oldest unclear or accepted effect is older than 24 hours.
- **Digests** show degraded once the oldest pending delivery is 2 hours past its scheduled time.
- **Error rates.** Each producer's error rate is failed effects over terminal effects in the last 24 hours.

### 3.3 The platform's capabilities

- **platform.status and platform.isolation** are pulled read-only through PlatformControl's evidence read (C10 `inspectEvidence`), never by running a platform operation (BR3.5).
- **platform.isolation** takes the newest file in `/Library/DocSuri/evidence/isolation/` (§ 8). A failed item makes it unavailable with the reason runtime-isolation-lapsed and the failed items as its limitations.
- **storage.capacity** also takes the backup agent's latest status check this way.

### 3.4 Incidents (O3, NFR9.3)

- **The watcher.** A tolerance watcher in the workers' control loop runs every 60 seconds over each capability's recent states and opens an incident by the rules of § 3.2. It does the same when a lane's job failures are correlated to a required capability, when a switch aborts, and when a rollback's copy cannot be completed (Workflow 4).
- **In the ledger.** Opening an incident appends it to the operations ledger. A capability that already has an open incident in the same environment gets the new signal attached instead, so one problem is one incident.
- **Resolving.** An incident moves through investigating and recovering, and resolves only with the evidence of one of its four resolution kinds (BR3.7).
- **Restores keep it.** Because incidents live in the ledger, a production restore never erases the incident that caused it.

## 4. Dashboards and job views (NFR9.4, NFR9.5)

**운영.** Only administrators with a completed second factor see it (NFR1.2). It shows:

- every capability with its state, age, limitations and error rate;
- open incidents first, then the resolved ones;
- the latest set per database, with retention;
- the latest restore verifications, each with its HNSW rebuild time against the 45-minute restore bound (scalability-design.md § 5);
- recovery requests;
- the month's availability figure and the budget left;
- the latest isolation result, with every stop record's expiry;
- the email allowance's day and month counts;
- the latest 5-minute latency summary per route class.

It refreshes every 30 seconds and on demand, each refresh one read (amendment A5, `readDashboard`).

**작업.** While any of the owner's jobs is unfinished, the list refreshes every 5 seconds, and it stops refreshing once none is. Live state comes from the job event stream (`EventSource`, resuming with `Last-Event-ID`), and the refresh is its fallback (BR5.4).

**A job's own view** follows the project's rules for real-time status:

- its event stream, with polling every 2 seconds whenever the stream fails;
- an error boundary around the view;
- an ARIA live region that announces each change of state.

## 5. Alerts (NFR9.6, O4)

| Check | Pinged by | Period | Grace | Reports a failure (`/fail`) when |
|---|---|---|---|---|
| Heartbeat | the heartbeat lane, every 5-minute slot | 5 minutes | 5 minutes | the slot is down |
| Daily backup | the backup lane, after the 04:00 set and its ledger copy | 1 day | 2 hours | the set or the ledger copy did not pass, or the run was skipped |
| Weekly restore verification | the verification lane, after the Sunday 05:00 run | 7 days | 6 hours | the verification failed, or was skipped |

- **When you hear.** A down slot pings `/fail`, so you hear within that slot, and the next up slot's ping clears it. Planned work, such as the switch or a production restore, therefore alerts too, as you would expect. Holding the failure back for a second slot was considered and rejected: the up ping after a single skipped slot would land at healthchecks.io's own deadline, so the alert would fire or not by chance. If the Mac or the standing job is down, no ping arrives, and the check alerts after its period and grace, within 10 minutes.
- **Each ping** is an HTTPS request with no body, to the check's own address, with a 10-second time limit. Only the check, through its address, and pass or fail leave the machine, never an error detail (NFR3.10). A ping that cannot be delivered makes the check late, which alerts after its grace.
- **The ping addresses** are held only by the scheduler account, in `scheduler/` (security-design.md § 6.1).
- **v1's own checks**, two of them, stay until v1 retires, which makes 5 of the free plan's 20 checks in use.

## 6. Signals per component (NFR9.7)

| Component | Health signal | Error-rate signal | Computed from |
|---|---|---|---|
| v2's host | the health route (liveness, readiness) | the share of 5xx answers per route class | the latency summaries' 5xx counts |
| v2's workers and scheduler | background.work: lanes behind their deadline | failed jobs per lane over 24 hours | the job records |
| The maintenance server | answering on `127.0.0.1:18201`, which the heartbeat's public probe reaches during maintenance | failed requests | its own log's counts |
| The standing job | the time of its last successful run | failed backups, verifications and disposals | the availability record's newest line, which every account can read, and the ledger's records |
| v2's PostgreSQL instance | storage.capacity: the footprint against the budget | failed connections and transactions seen by the host and the workers | their error-rate counts, reported with the operations observations |
| The model runtime | provider.models: reachable, with each digest equal to its pin | failed model jobs over 24 hours | the job records |
| The tunnel | the heartbeat through the public address, and operations.cutover | failed heartbeat probes | the availability record's reasons |
| The backup agent | its status check, in platform.status | failed writes and disposals | its receipts |
| The runtime isolation check | platform.isolation | failed items per check | its results (§ 8) |
| Google, ORCID, Resend and Notion | each provider's capability | refusals and over-limit answers | each adapter's counts |

## 7. Logs (NFR9.8)

What a line may carry, and how files are rotated without following links or blocking, are fixed in security-design.md § 7. Where each log lives:

| Jobs | Log folder | Owner |
|---|---|---|
| v2's service jobs (host, workers, scheduler, maintenance server) | `profile/logs/` | `_docsuri_v2` |
| The standing job | `scheduler/logs/` | `_docsuri_v2_sched` |
| The backup agent | `backup-agent/logs/` | `_docsuri_r1t_backup` |
| v2's PostgreSQL instance | `postgres/data/log/`, as PostgreSQL's own dated files | `_docsuri_v2_db` |
| The model runtime | `models-state/logs/` | `_docsuri_models` |
| The tunnel | `tunnel/logs/` | `_docsuri_tunnel` |
| The root jobs (packet filter, volume unlock, log rotation) | `control/logs/` | root |

- **v2's own processes** write `<process>.log` through Python's `WatchedFileHandler`. Every job's standard output and error go to `<label>.out.log` and `<label>.err.log` in its account's folder.
- **The rotation job**, `org.docsuri.v2.logrotate`, runs at 03:00 over a fixed list of these folders. The list is a root-owned file in the release. The job keeps 14 days:
  - it moves v2's own logs aside;
  - it copies and then truncates the files launchd holds open;
  - it only deletes PostgreSQL's dated files, after 14 days.
- **Its own record.** Each run writes one summary line to `control/logs/`: the folders done, the files moved or copied, the bytes written while a copy ran, and each skip with its reason key.

## 8. Isolation evidence (NFR9.9)

- **Each run** of the isolation check writes one JSON file to `/Library/DocSuri/evidence/isolation/`, named by its UTC start time. The file holds each item with pass or fail, the stop records found with their expiries, and the run's start and duration.
- **The folder** is written only by root and readable by every account.
- **Retention.** The check deletes its own files older than 14 days.
- **The latest result** is part of PlatformControl's read-only status (BR6.12).

## 9. Evidence (NFR9.10)

- **Readiness evidence** records the running release tag and commit, read from the release folder at start (BR6.5).
- **Claims.** Every readiness or release claim needs a passed VerificationRun for that exact commit (BR10.5).
- **The installation log** is kept in the profile's evidence folder and never holds a secret (security-design.md § 7.2).
- **The soak's evidence** holds:
  - the latency summaries for NFR8.1–NFR8.5;
  - the availability record's slots;
  - the backups and verifications from the ledger;
  - every incident.

## 10. Request identifiers (NFR9.11, O6)

- **One per request.** The host's boundary middleware gives each request a fresh identifier and keeps it in a context variable for that request. It never takes one from a header (security-design.md § 7.1).
- **Where it appears:**
  - every log line written while the request runs;
  - the error answer's `requestId`;
  - observations recorded during the request;
  - the record of any job the request starts, as its origin request.
- **Into the workers.** A job's log lines carry its `jobId` and that origin request's identifier, so one request can be followed from the host into the workers without a tracing system.

## 11. Production probes (NFR9.12)

The probes U8 supplies for the Operation stages read three things only:

- liveness;
- capability readiness;
- a signed-out journey: loading the shell, resolving navigation as an anonymous caller, and opening `/privacy`.

They never sign in, create work or send anything (BR10.7).

## 12. The availability record (NFR9.13, O7)

- **Where.** In `/Library/DocSuri/availability/`. The folder is the scheduler account's, mode 0755, and its files are 0644, so every account can read it and only the scheduler account writes. It holds no personal data.
- **Files.** One JSON Lines file per calendar month in Asia/Seoul, named `YYYY-MM.jsonl`.
- **One line per slot**, appended by the heartbeat lane and synced to disk, with three fields:
  - `slot`: the slot's start, in UTC, ISO 8601;
  - `up`: true or false;
  - `reason`: a fixed key: `ok`, `public-not-ready`, `local-not-ready`, `public-unreachable`, `local-unreachable`, `maintenance` or `probe-timeout`.

  If a slot ever has two lines, readers keep the first.
- **The month's figure.** Up slots over every scheduled slot of the month, a missing slot counting as down. The first month counts from admission opening.
  - The operator tool and 운영 show the running figure and the budget left.
  - Each closed month's figure goes into the Operation stages' evidence.
- **Retention.** The standing job's housekeeping deletes files older than 13 months.
- **A second view.** healthchecks.io's alerts and its log of down periods are an independent view, not the record.

## 13. Latency summaries (O8)

- **The host** keeps a fixed-bucket histogram per route class in memory. Every 5 minutes it appends one line per class to `evidence/latency/YYYY-MM-DD.jsonl` in the profile, holding:
  - the window's start;
  - the route class;
  - the count, the median, the 95th percentile and the maximum, in milliseconds;
  - the number of 5xx answers.
- **What it never holds:** an identifier, a path beyond the class's name, or a client or account.
- **Retention.** Files are kept 14 days, so they cover the 7-day soak.
- **Readers.** These summaries feed the host's 5xx signal (§ 6), 운영's latency panel (§ 4), the soak's evidence (§ 9) and the performance phase of the complete verification (performance-design.md § 10).

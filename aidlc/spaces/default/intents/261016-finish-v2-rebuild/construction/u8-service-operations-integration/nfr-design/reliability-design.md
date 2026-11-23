# Reliability Design — U8 complete service operations and integration

Date: 2026-10-22 (Asia/Seoul)
Unit: u8-service-operations-integration (service). Sources:

- confirmed [nfr-design-questions.md](nfr-design-questions.md) (Q1–Q6 and the points settled from the records);
- [reliability-requirements.md](../nfr-requirements/reliability-requirements.md) (NFR7.1–NFR7.19), with [performance-requirements.md](../nfr-requirements/performance-requirements.md) (NFR8.6, NFR8.9), [observability-requirements.md](../nfr-requirements/observability-requirements.md) (NFR9.13) and the [tech-stack decisions](../nfr-requirements/tech-stack-decisions.md);
- the [functional spec](../functional-design/functional-spec.md) (Workflows 1, 4–7, 12–14, 19 and 20, and the state machines) and [rules](../functional-design/rules.md);
- the built code, read on 2026-10-22: the owner transactions with their deadlines and retries, `backend/transactions.py` (`UnknownCommit`, the serialization retries); and the workers' control loop, `backend/control_runtime.py`.

There is one machine and no standby. This file designs how the service stays up, comes back and recovers its data within the requirements, and how each failure is contained. Monitoring and alerts are in [observability-design.md](observability-design.md). The map of parts and failure domains is in [logical-components.md](logical-components.md).

## 1. Decisions at a glance

| ID | Decision | Source | Serves |
|---|---|---|---|
| R1 | Availability is measured from the availability record's scheduled 5-minute slots, and a missing slot counts as down | NFR7.1, NFR9.13 | NFR7.1 |
| R2 | launchd relaunches each long-running job, and the host never exits on a missing dependency or a refused check, so a crash loop always means a real fault | settled | NFR7.2, NFR7.4 |
| R3 | The host retries its database with a growing wait, from 1 to 30 seconds | settled | NFR7.4, NFR8.6 |
| R4 | The standing job runs each task in its own lane, never overlaps a task with itself, and catches up a missed backup or verification when it starts | settled, with catch-up added here | NFR7.6, NFR7.8 |
| R5 | Each provider's capability state works as its circuit breaker, with fixed time limits and retries | settled | NFR7.12 |
| R6 | A production restore runs as bound steps, each with its time bound shown to you as it runs | NFR7.9 | NFR7.9 |
| R7 | Stops are graceful: launchd allows 30 seconds, the host drains for 10, and the workers leave unfinished items to lease recovery | settled | NFR7.2, NFR7.5 |
| R8 | The switch's 4 hours are counted from v1's stop. At the bound, the operator tool allows only the abort | NFR7.15 | NFR7.15 |

## 2. Availability (NFR7.1, R1)

- **The objective:** 99.0% per calendar month at `https://docsuri.rvnnt.dev`, from the time admission opens, planned work included. The error budget is 7 hours 12 minutes in a 30-day month and 7 hours 26 minutes in a 31-day month.
- **One probe per slot.** Slots start every 5 minutes on the clock (:00, :05 and so on). In each slot, the standing job's heartbeat lane runs two probes:
  - the public address's health route, `https://docsuri.rvnnt.dev/health/ready`. It goes out to Cloudflare and back through the tunnel, so it exercises the whole public path;
  - the local health route, `http://127.0.0.1:18200/health/ready`.

  The slot is up only if both answer ready within 10 seconds each.
- **Recording.** The lane appends the slot's line to the availability record (observability-design.md § 12), syncs it to disk, and then pings healthchecks.io.
- **A missing slot counts as down**, whether the Mac, the standing job or the service was down. So the figure never overstates availability.
- **Planned work counts too.** During the switch, a production restore or an installation's restart, the public address serves the maintenance notice, which is not ready, so those slots are down.
- **The budget is information, not a block.** 운영 shows the month's running figure and remaining budget, for your release and maintenance decisions. Nothing is held back automatically.

## 3. Supervision and restarts (NFR7.2, NFR7.3)

- **The long-running jobs:**
  - `org.docsuri.v2.host`, `.workers`, `.scheduler`, `.maintenance`, `.standing` and `.postgres`;
  - `org.docsuri.models` and `org.docsuri.tunnel`.

  Each sets `KeepAlive` and `RunAtLoad`. launchd relaunches a crashed job after its throttle interval of 10 seconds by default, well inside the 1 minute.
- **The root jobs** run without `KeepAlive`:
  - `org.docsuri.v2.pf`, once at boot;
  - `org.docsuri.v2.backup-unlock`, at boot and every 60 seconds;
  - `org.docsuri.v2.logrotate`, at 03:00.
- **No crash loops from dependencies.** The host never exits because a dependency is missing or a check refuses (§ 4). So a job that keeps crashing is a real fault. Readiness, background.work and their incidents show it.
- **A planned restart** uses an authorized restart (`fdesetup authrestart`). Every job of the arrangement starts at boot without a login, and the unlock job opens the backup volume. The whole chain is ready within 3 minutes of boot (performance-design.md § 2.6).
- **An unplanned restart**, after a power cut for example, waits at the FileVault unlock screen, and so can a macOS update. The heartbeat check alerts you within its grace period (observability-design.md § 5). From the unlock, the chain is ready within 3 minutes. The wait counts against the budget.
- **Stops persist.** A service-control stop disables the job, so it stays stopped across restarts until a start enables it again (BR6.12).

## 4. Starting without the database, and refused starts (NFR7.4, R2, R3)

- **The database doesn't answer yet.** This is typical at boot, when the host's job may start before PostgreSQL's. The host keeps `/health/live` answering and `/health/ready` answering not ready, naming `database`. It tries again after 1, 2, 4, 8 and 16 seconds, then every 30 seconds, and never exits. Once the instance answers through SCRAM with the expected identity, the assembly continues (Workflow 1).
- **A start check refuses**, because the root, the ledger, a key, a service secret, the schema or a restore's start authorization failed (Workflow 1). The process does not exit. It stays in a refused state:
  - it serves only the health routes, which name the failed check;
  - it serves nothing else, and starts no worker or producer.

  launchd then sees no crash and does not loop it. The heartbeat sees the service as not ready and alerts. Once the cause is fixed, the operator restarts the job through service control. A refused start is never retried by itself, because none of these causes fixes itself.

## 5. Planned work (NFR7.5)

- **Routing.** The public address moves to the maintenance server through PlatformControl's tunnel routing, in person.
- **The maintenance server** depends on no application code and no database. It is a long-running job of its own, so it is always ready to take the address.
- **No fixed window.** There is no fixed maintenance window. Each planned job's downtime counts against the month's budget (§ 2).

## 6. Backups (NFR7.6, NFR7.7)

**The daily run, at 04:00 Asia/Seoul,** after v1's 03:30 job:

1. The standing job's backup lane creates a backup request with origin schedule (Workflow 5).
2. Once admitted, PlatformControl runs it through the backup agent's unattended `backup` command, and a ledger copy goes beside the set.
3. The set counts only after its integrity check passes.
4. The disposal pass follows.
5. The lane pings healthchecks.io's daily check, or `/fail` if the set or the ledger copy did not pass.

- **Which database.** The rehearsal database during the soak, and the production database in live mode.
- **A day without a set.** On a day no set is taken, a ledger copy is still taken at 04:00, and the daily ping reports `/fail`.
- **Catch-up (R4).** If the Mac or the standing job was down at 04:00, the lane runs the missed backup as soon as it starts again, if the newest passed set is older than 24 hours. So writes lost to a failed disk stay within 24 hours plus any downtime.
- **Retention.** Daily sets and their ledger copies are kept 14 days, and Sunday's 8 weeks. The retention floor always keeps the newest passed set of each database that still exists and the newest verified ledger copy (BR9.17).

## 7. Restore verification (NFR7.8)

**When it runs.** Every Sunday at 05:00, and at 05:00 on any day an erasure is waiting, meaning a tombstone newer than the newest verified register head.

**Its steps:**

1. The standing authority checks the internal disk's free space (scalability-design.md § 3.3) and records the register head.
2. The backup agent's unattended `verify` command restores the newest passed live set into a new scratch database. During the soak, that is the newest rehearsal set.
3. Through the scheduler's database login, the checks run in this order:
   - integrity: every table in the dump's table of contents is present, with its rows;
   - the replay of every tombstone up to the head;
   - a check that every tombstoned owner is absent.
4. The scratch database is dropped, and the time of the drop is recorded.

- **Pass or fail.** It passes only when every check passes and the scratch database is gone. Then healthchecks.io's weekly check is pinged, or `/fail` on a failure.
- **The bound applies to the start.** A waiting erasure's verification starts at the next 05:00, within 24 hours of its tombstone, and completes within 60 minutes of that start (performance-design.md § 7.2).
- **Catch-up (R4).** If the Mac was down at 05:00, the lane runs a due verification as soon as it starts again. Only downtime can then push an erasure past its 24 hours, and its evidence shows the actual times.
- **Failures.** A failed check opens an incident. A scratch database that cannot be dropped is recorded as a retained copy with a 1-day backstop (Workflow 6).

## 8. Production restore and recovery requests (NFR7.9, NFR7.10, R6)

A production restore completes within 2 hours of the operator starting it on your decision, for a database within the 8 GiB budget. Its steps are bound operations, each with its receipt (Workflow 7):

| Step | Bound | Design |
|---|---|---|
| Route to the maintenance server and stop v2 | 5 minutes | tunnel routing, then service control per label |
| Pre-restore backup (skipped by a successor) | 25 minutes | the backup agent's in-person `backup` |
| Recreate the database and restore the chosen set | 45 minutes | `platform.database.recreate`, then the agent's `stream-back` into `pg_restore -j 2`, with `maintenance_work_mem = 1GB` and two parallel maintenance workers to rebuild the HNSW index (performance-design.md § 7.2) |
| Replay the tombstones and check integrity | 10 minutes | AccountAccess's restore evaluation, through the production environment tool |
| Post-restore backup | 25 minutes | the agent's in-person `backup` |
| Start v2, reach readiness and route back | 10 minutes | the start authorization first, then service control and tunnel routing |

- **Elapsed time.** The operator tool shows each step's elapsed time against its bound. A step past its bound is shown, never cut off automatically, because cutting a restore off midway leaves more to repair than letting it finish. Every failure path stays as Workflow 7 states.
- **Request expiry (NFR7.10).** A recovery request not admitted, or admitted and not started, within 24 hours expires. The standing job's housekeeping lane marks it in the ledger. A waiting request holds nothing (BR4.4).
- **Unknown outcomes.** One is reconciled from PlatformControl's receipt before any other production-affecting operation (NFR4.1).

## 9. Losing storage or the machine (NFR7.11)

- **A backup volume lost for good** is retired and replaced only on your decision. A backup and a ledger copy are then taken on the replacement at once (BR4.10).
- **If this Mac is lost,** the external drive's encrypted volumes can be read on another Mac with the passphrases kept in your password manager. What a rebuild needs survives:
  - the newest passed set and the newest verified ledger copy;
  - the release tag;
  - the installation procedure.

  No key is in a backup, by design (BR4.8), so a rebuild applies each key owner's own loss rule: U6's owners reconnect Notion, U2's keys go through key recovery, and replacing the verifier key ends every session. Rebuilding the service is an Operation-stage procedure.

## 10. Degradation, time limits and retries (NFR7.12, NFR7.13, R5)

No provider makes the service unready, and nothing switches to another provider or a paid one (BR3.11, BR7.2). Each provider's capability state works as its circuit breaker:

- **Open.** While it is unavailable, the features that depend on it say so and make no call.
- **The probe.** The provider's next observation is the test call.
- **Closed again.** When the probe finds the provider available, calls resume.

| Dependency | Time limit | Retries | While unavailable |
|---|---|---|---|
| Google, ORCID | 10 s per call | none: the person signs in again | its sign-in button shows unavailable; other sign-in methods work |
| Resend, account mail | 10 s per attempt | up to 3 attempts within 30 s, after a timeout, a 429 or a 5xx, with the same idempotency key | the message fails plainly, and its reservation follows security-design.md § 13 |
| Resend, digests | U5's own | U5's own retries and reconciliation, unchanged | digests wait |
| Notion | U6's budgets | U6's own, unchanged | exports wait or end as U6 designed |
| The model runtime, search | 2 s per embedding | none | search answers by words only, with semantic-search-unavailable |
| The model runtime, generation | the job's own deadline | the job's own | model jobs wait while provider.models is unavailable |
| v2's PostgreSQL | connect 3 s, statements 3–5 s, transactions 5–10 s (built) | serialization failures and deadlocks up to 3 times (built). A commit with an unknown outcome is reconciled by its operation key (`UnknownCommit`) | the host is not ready, and requests answer busy |
| The backup volume | the agent's status check | the unlock job every 60 seconds | the start continues (NFR7.13). storage.capacity is degraded, writes are refused, and deletions wait |
| A provider's capability probe | 5 s | the next renewal | its last state ages into stale |

## 11. The standing job (R4)

| Lane | When | Overlap rule |
|---|---|---|
| Heartbeat and availability record | every 5-minute slot | at most one probe pair, in under 25 seconds |
| The backup agent's status check | every 5 minutes | one at a time |
| The runtime isolation check | every 5 minutes | one at a time, within 60 seconds |
| Backup and its ledger copy, then disposal | 04:00, with catch-up at start | one at a time |
| Restore verification | 05:00 when due, with catch-up at start | one at a time |
| Housekeeping: request expiry, and pruning the availability record past 13 months | hourly | one at a time |

- **No lane waits for another.** A 25-minute backup or a 60-minute verification never delays the heartbeat, the record or the pings.
- **A turn that comes while its lane is still running** is skipped and recorded with the reason skipped-overlap, never run twice at once. A skipped backup or verification also pings `/fail`.
- **The job's own health.** It is a long-running job of its own, and its health signal is the time of its last successful run (observability-design.md § 6).

## 12. Cutover (NFR7.14–NFR7.16, R8)

- **Preconditions (NFR7.14).** At the switch's start, the operator tool checks each item's evidence:
  - a soak of 7 days clean on the release tag;
  - a verified rehearsal restore;
  - v1's restart rehearsal within the last 7 days;
  - a consumer inventory covering 14 days;
  - backup-volume free space of at least the 64 GiB floor plus the accepted dry run's measured snapshot and backup sizes;
  - isolation evidence passed within the last 15 minutes.

  If any item is missing, the switch does not start, and the tool names the item.
- **The 4-hour bound (NFR7.15).** The CutoverRecord stores the time v1 stopped. The operator tool shows the time left at every step. At 4 hours it refuses every forward step and offers only the abort, which is a bound operation. A failed step or your decline aborts too, and v1 serves again before anything of v2's is removed (BR9.4, BR9.5).
- **The rollback window (NFR7.16).** A rollback is possible for 14 days after admission opens. v2's withdrawals and erasures reach v1 through v1's own account code before v1 serves. v2's database is copied first unless your decision waives the copy (BR9.7, BR9.13).

## 13. Arrangement health (NFR7.17–NFR7.19)

- **Isolation lapses (NFR7.17).** A lapse in the runtime arrangement makes platform.isolation unavailable, and an incident opens once it lasts 15 minutes. An isolation check that stays unknown or stale for 15 minutes does the same. Such an incident keeps the soak from counting as clean and blocks the switch.
- **The disk floors (NFR7.18)** keep PostgreSQL's write-ahead log from running out of room. Below the critical floor, storage admission closes and restore verifications and imports stop before the disk fills (scalability-design.md § 3.3).
- **Planned stops (NFR7.19).** A planned stop's record is valid for 14 days.
  - You renew it in person before it passes, by stopping the job again through service control.
  - Every isolation check lists each record's expiry, and the operator tool shows it whenever it lists stops.
  - A lapsed record counts as an isolation lapse. So a stopped job nobody renews becomes an incident instead of staying hidden.

## 14. Failure modes

| Part | Failure | Detected by | Automatic response | Recovery |
|---|---|---|---|---|
| v2's host | crash | launchd | relaunch within 10 seconds | ready within 3 minutes |
| v2's host | refused start | its health route, and the heartbeat | stays refused, serving only health | you fix the cause and restart it through service control |
| v2's workers | crash | launchd | relaunch | leases return unfinished items |
| v2's PostgreSQL | crash | launchd, and the host's readiness | relaunch with crash recovery | the host reconnects with its growing wait |
| v2's PostgreSQL | damaged data | the integrity checks, an incident | none | a production restore (Workflow 7) |
| The model runtime | down | the models probe | research waits, and search answers by words only | relaunch |
| The model runtime | a digest differing from the pin | the models probe (model-evidence-mismatch) | no model is used | a new release, or the clones made again |
| The tunnel | down | the heartbeat, then healthchecks.io's alert | relaunch | — |
| Cloudflare | outage | the public probe, then healthchecks.io's alert | none | waiting |
| The internal disk | low or critical | storage.capacity | degraded, or admission closed and an incident | freeing space |
| The backup volume | missing or locked | the agent's status check | the unlock job retries every 60 seconds, and writes are refused | reconnecting the drive |
| The operations ledger | a broken chain | the ledger check | operations.ledger unavailable, an incident, and dependent writes stop | repair from the newest verified copy, in person |
| The arrangement | an isolation lapse | the isolation check | platform.isolation unavailable, then an incident | correcting the arrangement |
| The standing job | down | its pings stop, then healthchecks.io's alert | relaunch, with catch-up at start | — |
| The Mac | power loss, or an update stuck at the unlock | the heartbeat stops, then the alert | it restarts after power returns and waits at the unlock | you unlock it, and the chain is ready within 3 minutes |
| A provider | outage | its probe | degraded or unavailable, and its features say so | automatic once it is back |
| Email | allowance used up | the shared count | allowance-exhausted: digests wait, account mail fails plainly | the reset at 09:00 in Seoul |

## 15. Stopping and starting cleanly (R7)

- **launchd** sends SIGTERM and allows 30 seconds (`ExitTimeOut`) before it ends a job.
- **The host** stops accepting connections and finishes the requests under way, for up to 10 seconds. It closes its event streams with a retry hint, so browsers reconnect after the restart.
- **The workers** stop claiming work. Unfinished items keep their leases and are claimed again once those expire (built lease recovery).
- **The standing job.** A backup or verification cut off by a stop leaves its request's outcome unknown. It is reconciled from the backup agent's receipt before any other production-affecting operation, and the agent's next pass sweeps any staging file left behind (Workflow 19).
- **PostgreSQL** treats SIGTERM as a smart shutdown, which waits for open sessions. If a session, such as a running dump, outlasts the 30 seconds, launchd ends the server, and the next start replays the write-ahead log. That is safe and takes seconds, bounded by `max_wal_size`.

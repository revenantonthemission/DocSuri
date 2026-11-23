# Monitoring Design — U8 complete service operations and integration

Date: 2026-10-22 (Asia/Seoul)
Unit: u8-service-operations-integration (service). Sources:

- confirmed [infrastructure-design-questions.md](infrastructure-design-questions.md) (the points settled from the records: monitoring stays local);
- this Unit's [observability design](../nfr-design/observability-design.md), which this file puts on the platform, with the [reliability](../nfr-design/reliability-design.md), [performance](../nfr-design/performance-design.md), [scalability](../nfr-design/scalability-design.md) and [security](../nfr-design/security-design.md) designs whose numbers it watches;
- the [functional spec](../functional-design/functional-spec.md) (the capability registry, Workflows 3 and 4).

There is no metrics server. The watched numbers come from:

- the capability observations in v2's database;
- the operations ledger;
- the availability record;
- the 5-minute latency summaries;
- the isolation results;
- the backup agent's receipts.

운영 shows them, and healthchecks.io is the only outside service.

## 1. Metrics and KPIs

| Metric | Source | Threshold | Why it matters |
|---|---|---|---|
| Availability this month | the availability record | below 99.0% misses the objective; the budget left is always shown | NFR7.1 |
| Slot status | the heartbeat lane, every 5 minutes | a down slot | an outage, seen within its slot |
| Health route, 95th percentile | latency summaries, class health | over 200 ms | NFR8.1 |
| API reads, 95th percentile | latency summaries, class read | over 500 ms | NFR8.3 |
| Search, 95th percentile | latency summaries, class search | over 3 s | NFR8.4 |
| Accepting work, 95th percentile | latency summaries, class accept | over 1 s | NFR8.5 |
| 5xx answers per route class | latency summaries | over 1% in a 5-minute window, highlighted | NFR9.7 |
| Busy answers from the connection gates | the host's counters, in its summaries | any, shown with its count | NFR8.12 |
| Resident memory of the host and the workers | a line each of the two processes adds to the 5-minute summary file, with its own resident memory | together over 4 GiB, highlighted | NFR8.7 |
| Required capabilities | observations | unavailable opens an incident at once; degraded, unknown or stale for 10 minutes opens one | NFR9.2 |
| The capacity footprint | storage.capacity | degraded from 6.4 GiB; unavailable from 8 GiB less 256 MiB | NFR8.13 |
| Internal disk free | storage.capacity (`statvfs`) | degraded below 20 GiB; critical below 10 GiB, with an incident | NFR8.14 |
| Backup volume free | the backup agent's status check | below 64 GiB | NFR8.16 |
| Email counts | the shared count in the ledger | 60 digests a day, 90 messages a day in all, 2,700 a month | NFR6.2 |
| The isolation check | its results | any failed item makes platform.isolation unavailable, and 15 minutes opens an incident | NFR3.8, NFR7.17 |
| Stop records | the isolation results | each record's expiry is shown; a lapsed record is a lapse | NFR7.19 |
| The newest passed set | the ledger | older than 26 hours fails the daily check | NFR7.6 |
| The newest verification | the ledger | older than 7 days and 6 hours fails the weekly check | NFR7.8 |
| An index rebuild in a restore | each restore verification's record | projected past 45 minutes at the full budget, highlighted | NFR8.9 |
| A dry run's duration | the run's report | over 2 hours | NFR8.8 |
| Bytes written while a log copy ran | the rotation job's summary line | above 0, shown | NFR9.8 |

## 2. Alerts

| Alert | Condition | Severity | Routes to |
|---|---|---|---|
| The service is down | a down slot pings `/fail`, or no ping arrives for the 5-minute period plus 5 minutes of grace | P1 | healthchecks.io, then email to you |
| The daily backup failed or is missing | `/fail` after 04:00, or no ping by 06:00 | P2 | healthchecks.io, then email |
| The weekly verification failed or is missing | `/fail` after Sunday 05:00, or no ping by Sunday 11:00 | P2 | healthchecks.io, then email |
| A required capability is unavailable | readiness turns false, so the heartbeat's local probe finds the service not ready and the slot is down | P1 | the same heartbeat alert |
| An incident opens | the tolerance watcher's rules (observability-design.md § 3.4) | P2 for a required capability, P3 otherwise | 운영 |
| The internal disk is critical | storage.capacity unavailable | P1 | through readiness, the heartbeat alert, and 운영 |
| An isolation lapse | platform.isolation unavailable, with an incident after 15 minutes | P2 | 운영. It also blocks the soak and the switch |
| The email allowance is used up | provider.resend degraded with allowance-exhausted | P3 | 운영 |
| A model digest differs from its pin | provider.models unavailable with model-evidence-mismatch | P3 | 운영 |

- **Severity.** P1 emails you at once. P2 emails you, or shows as an open incident on 운영. P3 shows on 운영.
- **Not alerted outside: an isolation lapse,** because platform.isolation is not a required capability, so readiness stays true. It is visible on 운영, and it blocks the soak and the switch. If you want an email for it too, a fourth healthchecks.io check would carry it, and the free plan has room. That would be a change to NFR9.6's three checks, for your decision.

## 3. SLIs and SLOs

| SLI | SLO target | Measurement window |
|---|---|---|
| Up slots over every scheduled slot, a missing slot counting as down | 99.0% | a calendar month in Asia/Seoul |
| Health route, 95th percentile | under 200 ms | each 5-minute summary; over the soak's 7 days |
| Workspace first load and later navigation, 95th percentile | under 2 s and under 1 s | the performance phase of each install; the soak |
| API reads, 95th percentile | under 500 ms | each 5-minute summary; the soak |
| Search, 95th percentile | under 3 s | each 5-minute summary; the soak |
| Accepting work, 95th percentile | under 1 s | each 5-minute summary; the soak |
| Start to ready | under 3 minutes | each restart, crash or install |
| Daily backup passed | every day | per day |
| Restore verification passed | every week | per week |
| A waiting erasure's verification started | within 24 hours of its tombstone | per erasure |

## 4. Logs and tracing

- **No aggregation.** Each account writes JSON lines into its own log folder (observability-design.md § 7), and the 03:00 job keeps 14 days.
- **Reading logs, in person.** A fixed command, `docsuri-logs <component> [--since <time>] [--request <id>]`, reads one component's logs as root and prints them. It is in person, like every fixed command (security-design.md § 5.3). It writes nothing, and it filters by request identifier, so a single request can be followed from the host into the workers.
- **No tracing system.** The request identifier travels into logs, error answers, observations and the jobs a request starts (observability-design.md § 10).

## 5. Dashboards

| Dashboard | Shows | For |
|---|---|---|
| 운영 | capabilities, incidents, backups and verifications, recovery requests, the month's availability and its budget, the latest isolation result with stop expiries, the email counts, the latest latency summary per route class | administrators with a completed second factor, refreshed every 30 seconds |
| 작업 and a job's view | each owner's own jobs, live through the event stream | every signed-in person |
| healthchecks.io | the three checks and their history of down periods | you, from outside this Mac |
| The operator tool's status command | PlatformControl's read-only status: services, routing, the backup agent, isolation | you, in person |

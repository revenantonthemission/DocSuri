# U7 monitoring design

## Scope

Local, vendor-free monitoring for the U7 operator, implementing the
observability design (NFR9.x) without a hosted telemetry service. The primary
evidence is the durable receipt; monitoring reads it.

## Metrics & KPIs

| Metric | Source | Threshold | Why it matters |
|---|---|---|---|
| Receipt count by outcome (`succeeded`/`failed`/`unknown`) | `PlatformControl` receipt store | no fixed threshold (informational) | aggregate operation health |
| Unresolved `unknown` operations | receipt store (`reconciliationState = unresolved`) | **> 0 is a signal to reconcile** | an unresolved effect is unsafe; must stay visible (NFR3.7) |
| Operation duration distribution | receipt timestamps | baseline-deferred; flag exceedances of the per-protocol deadline | bounded execution (NFR2.2) |
| Refusal count by reason | CLI results | informational | authority/evidence/precondition breakdown (NFR4) |
| Evidence compatibility distribution (`current`/`stale`/`mismatched`/`missing`) | evidence store | informational | staleness/mismatch visibility (NFR1.1/NFR9.2) |
| Idle activity | operator process | expect zero background activity when idle | NFR8.6 |

No numeric SLI/SLO is selected; thresholds are baseline-deferred per the
requirements.

## Alerts

| Alert | Condition | Severity | Routes to |
|---|---|---|---|
| Unresolved unknown remains | an `unknown` receipt stays `unresolved` beyond its review cadence | operator-visible (not paged) | the operator's unresolved list / `status` output |

There is no always-on alert target for a local CLI; alerting is an
operator-visible list, not a paging integration (nfr-design Q4).

## SLIs / SLOs

| SLI | SLO target | Measurement window |
|---|---|---|
| Operation outcome truthfulness | 100% of operations report a truthful outcome (never `succeeded` on liveness alone) | per operation (invariant, not a percentage) |
| Range/percentile latency SLOs | **baseline-deferred** | to be agreed after a measured baseline |

## Logs & Tracing

- **Logs:** structured local logs with event name, correlation id and safe
  references only; no credentials or private source text (NFR5.3, NFR9.5).
- **Retention/access:** documented local retention and file-permission access
  limits; receipts retained until reconciled/archived (NFR9.5, NFR3.7).
- **Tracing:** no distributed tracing vendor; the **correlation id carried on the
  operation/receipt** is the trace key across CLI → guarded-store → executor
  (NFR9.4).
- **Dashboard:** a small local `status` view over the metrics above; no hosted
  dashboard (NFR9.3 coordination item noted).

## Sources

- [observability-design.md](../nfr-design/observability-design.md)
- [reliability-design.md](../nfr-design/reliability-design.md)
- NFR requirements: `../nfr-requirements/observability-requirements.md`

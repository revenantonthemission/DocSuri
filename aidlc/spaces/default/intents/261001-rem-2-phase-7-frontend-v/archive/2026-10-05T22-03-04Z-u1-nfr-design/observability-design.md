# U1 Observability Design

## Sources

`../nfr-requirements/observability-requirements.md`, `../nfr-requirements/reliability-requirements.md`, `../functional-design/functional-spec.md`, `../../../inception/contract-design/contract-summary.md` and confirmed `nfr-design-questions.md` govern signal scope. Reuse Sentry and existing backend monitoring, with no new dashboard product or invented uptime target.

## OD-1 — Safe Diagnostic Envelope

Allowlist action/task/outcome/error category and safe request/job/dispatch/connection correlation identifiers. Scrub cookies, credentials, input/parameter bodies, document/result text, provider/SQL exceptions and unnecessary user data before serialization. Capture delivered client render and async errors to Sentry; inspect the actual captured event in positive/negative fixtures. Diagnostic delivery uses a bounded nonrecursive failure path and cannot block visible status/recovery controls. Covers **NFR7.1**.

## OD-2 — Connection and Actual Job-Lifecycle Events

Use a unique connection-attempt ID with monotonic construction/open timestamps to report connection_latency_ms, open/drop/restoration and actual connection mode. Record initial_submit, explicit_same_key_recovery, receipt_observed and observed terminal outcome separately. A replacement ID is an observed identity change, not proof that dispatch failed or another execution ran; label cause only from authoritative evidence. Emit unchanged state/replay suppression rather than duplicate history-driven outcome announcements.

These are signal names/concepts to bind to existing adapters at implementation, not claims that current code emits them. Measure actual latency rather than populate a default. Covers **NFR7.2–NFR7.3**.

## OD-3 — Backend Operation and Freshness Evidence

Correlate dispatch_started/confirmed/rejected/unknown, invocation_grant, prepared_binding, terminal_publish, reconciliation_outcome and fenced_write. Include success/error counters or operation freshness for API/worker/maintenance and the actual queued/durable state evidence. A no-op enqueue or missing store configuration must not become a successful operation metric. Avoid sensitive/high-cardinality payload labels.

For maintenance record scheduled/start/finish time, pass counts, eligible/processed/remaining backlog, skipped-live/locked work, failures and oldest-expired-payload age. A failed query/run cannot report zero backlog or a healthy empty scan. Keep last-success age distinct from last-start time. Covers **NFR7.4**.

## OD-4 — Actionable Cleanup and Maintenance Alerts

| Signal | Starting threshold / effect | Owner and action |
|---|---|---|
| Oldest unpurged expired live payload | 12 hours warning | revenantonthemission checks failed runs/backlog/capacity before urgency |
| Same payload-age signal | 18 hours urgent | Escalate/recover guarded cleanup with 6-hour remaining deadline margin |
| Same payload-age signal | 24 hours breach | Report failed requirement; read denial remains enforced; retain actual breach/recovery evidence |
| No successful hourly cleanup run | 75 minutes warning, 120 minutes urgent | Inspect scheduler/permissions/store and reschedule safely; running invocation is not successful completion |
| Authority recovery cadence freshness | 90 seconds warning, 180 seconds urgent without successful 30-second pass | Inspect runner/store health and backlog; never blindly resend UNKNOWN work |
| Pre-effect SENDING/UNKNOWN dispatch age | Eligible at 120 seconds from recorded send-start; monitor eligible backlog and settlement lag | Verify evidence/fence-based acceptance or retained-binding uncertain failure, never a resend or key release |
| Diagnostic delivery failure | Bounded local safe error counter, no recursive reporting | Keep application usable and diagnose adapter readiness |

Thresholds are starting operational settings to qualify with scheduler latency/loaded-state tests. Silence/failed monitoring is unhealthy/unknown, not success. Infrastructure/observability setup binds a verified notification channel and runbook/escalation destination to the named owner before activation; no channel is invented here. Recovery is a guarded existing operation with proper access, not an alert-triggered generation retry. Covers **NFR7.4**, supporting **NFR11.5**.

## OD-5 — Retention and Evidence

Use actual existing diagnostic retention/access configuration; record it before claiming operation. Sample/limit normal diagnostic volume without suppressing required failure/deadline evidence. No raw content is retained as a debugging convenience. U1 supplies signals for its slice/backend guarantees and U2 exercises the wider UI/connection matrix. No runtime observation, Sentry project availability or delivery success is established by these patterns.

# U1 Observability Requirements

## Sources and Evidence Boundary

Inception NFR7, FR7.3, C8, U1 rules and confirmed Q1/Q2 govern diagnostic scope. Mandatory Sentry and the existing backend monitoring surface must operate for delivered behavior; a planned integration or console log is not evidence of reporting. No separate dashboard product or unprovided uptime commitment is introduced.

## Detailed Requirements

| ID | Requirement / pass-fail condition | Evidence |
|---|---|---|
| NFR7.1 | Delivered client errors reach Sentry with allowlisted safe context. Cookies, credentials, document/result bodies and arbitrary request/parameter content are absent from sent diagnostics. | Trigger render/async/input failures and inspect captured events, including failed telemetry delivery and error serialization; NFR7, AC8.1.1 |
| NFR7.2 | Connection opening, drops and restoration are observable, with latency in milliseconds from EventSource construction to open. Actual timings and safe job/context correlation distinguish live, polling and offline states. | Controlled connect/drop/restore fixtures and real staging timings; latency is a runtime metric in addition to the NFR9 benchmark; NFR7, AC8.1.2 |
| NFR7.3 | Initial submission, explicit same-key recovery, returned identity and observed terminal outcomes are distinguishable. Replacement/dispatch-failure cause is labeled only with authoritative evidence; unknown cause remains unknown. | Paired replay/replacement/uncertain fixtures and safe lifecycle events; no recovery-click-is-new-execution claim; NFR7, AC8.1.3 |
| NFR7.4 | Safe backend operation health/failure evidence covers dispatch, effect/binding/publication, reconciliation and cleanup. Monitoring detects threatened cleanup deadline before 24 hours and reports breach/failure without affecting correct read denial. Diagnostic-delivery failure cannot recursively crash or block the journey. | Test success/failure counters or readiness/freshness indicators on the existing monitoring surface, expiry-age/deadline alerts and failed-reporting behavior; NFR7, Q2, AC8.1.4 |

## Required Signal and Alert Handoff

NFR Design identifies concrete metric/event names, delivery paths, notification ownership and thresholds. Include current dispatch outcome, stale/expired authority requiring reconciliation, binding/publication failure, fenced late write, and oldest unpurged expired payload age. At least the cleanup warning threshold must be below its 86,400-second deadline, with an explicit monitoring/recovery margin; an alert only after breach is not an early warning.

Preserve request/job/dispatch correlation as safe identifiers, not raw payload logging. Health/failure evidence must distinguish a missing real queue/worker/store configuration from genuine success; a no-op enqueue cannot count as successful dispatch. Do not use high-cardinality sensitive input or raw content as metric labels. Retention and access to diagnostics follow actual existing project configuration; no generic framework log-retention example is silently adopted.

## Validation and Responsibility

U1 emits required signals for its implemented slice and backend guarantees; U2 closes the wider job connection/diagnostic matrix. Real Sentry/environment readiness is coordinated by revenantonthemission as recorded in Delivery Planning, not assumed available. Verify delivery/scrubbing through controlled failures and operation evidence; schema/traceability checks alone do not establish runtime reporting.

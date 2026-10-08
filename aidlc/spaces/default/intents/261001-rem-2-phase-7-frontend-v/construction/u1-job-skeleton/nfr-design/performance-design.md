# U1 Performance Design

## Sources

Current inputs are `../nfr-requirements/performance-requirements.md`, `../nfr-requirements/security-requirements.md`, `../nfr-requirements/scalability-requirements.md`, `../nfr-requirements/reliability-requirements.md`, `../nfr-requirements/observability-requirements.md`, `../nfr-requirements/tech-stack-decisions.md`, `../functional-design/functional-spec.md` and `../../../inception/contract-design/contract-summary.md`. Confirmed `nfr-design-questions.md` selects the bounded amendment and retained operational profile. These are implementation strategies and validation plans, not measured acceptance results.

Recovery/readiness follows `../../../inception/delivery-planning/bolt-plan.md` and `../../../verification/u1-isolated-postgres-bootstrap-plan.md`. Current source declarations, preserved partial work and document checks are inputs to qualification, not installed/deployed dependencies or real-store/browser acceptance.

## PD-1 — Measure Actual Browser Boundaries

Instrument EventSource construction and its successful open using the browser's monotonic performance clock; pair the timestamps with a safe connection-attempt identity. Measure requested status mount to first committed named status UI separately, with no await for the entire job. Preserve the approved staging profile: production frontend, real BFF/gateway, authenticated unthrottled desktop Chromium, same-region runner, one active job and 100 sequential samples per metric. Compute nearest-rank p95 at rank 95 of 100 successful durations and retain the complete attempt/error log.

Strict targets remain <300 ms connection and <200 ms committed status UI. Report failures, replacement samples and environment/cache/build/browser details; never count a quick error as a success or exclude network/gateway overhead. A failed run is a failed acceptance result, not a prompt to relax the budget. U3 owns the separate asset-decoding measure. Covers **NFR9.1–NFR9.3**.

## PD-2 — Narrow Queries and Short Authoritative Transactions

Keep state/event lookups independent of prepared payload retrieval: state selects safe identity/state/seq/error fields only; cursor resolves opaque ID inside the authorized job history and reads ordered seq batches; result selects the committed exact snapshot only after owner/state/expiry checks. Use existing job identity/owner indexes and job/seq event uniqueness, plus an owner/job prepared-binding lookup and expiry/purge-status cleanup index. Physical index/migration syntax belongs to implementation and Infrastructure Design.

Validate/canonicalize final payload outside the fenced write transaction; retain the required summary code/data strings exactly through canonical integrity hashing and serialization, without Unicode, whitespace or line-ending normalization. Lock/recheck owner/job/fence using fresh database time inside the short transaction; RD-4 specifies preparation and one-time completion-expiry metadata. Reserve a separate heartbeat control connection/task budget so a large snapshot write or generation-source lookup cannot starve renewal. Each control operation has a total 5-second deadline, including acquisition/lock/query/commit handling; actual adapter timeout support and resource reservations must be proved, not inferred from a connection-pool label. Lost commit acknowledgement invokes identity reconciliation, never regeneration.

Ordinary backend HTTP work uses an 8-second response budget inside the fixed 10-second BFF gateway hop. Set per-phase deadlines from remaining budget rather than accumulating full timeouts. If a first send cannot safely fit, return the actual committed SUBMITTED receipt and leave first dispatch to guarded maintenance; if send outcome is ambiguous, preserve binding and report actual durable/uncertain state. Do not mark unconfirmed dispatch accepted. SSE header acquisition retains 15 seconds; its healthy body has no fixed total timeout. Covers **NFR9.4** and supports C8/worker timing.

## PD-3 — Exact Snapshot Volume Qualification

Persist one immutable final owner-specific prepared result, not the shared translation base. Measure at least summary, typical translation and representative larger supported translation fixtures, documenting actual encoded bytes, source/input bounds, payload validation, write/read distributions, connection/lock wait and worker memory. Compare actual limits/resource use against the chosen database placement and per-phase deadlines. No fixture size is declared a product maximum and no unrelated 100 KiB image limit is applied to results.

Summary fixtures retain the shared required `{code: string, data: string}` object with no extra nested fields; include distinct allowed Unicode, decomposed characters, whitespace, escaping and empty strings. Compare values before capture, after canonical serialization/JSON round-trip and after actual persistence/read; equivalent JSON escaping is allowed, altered string content is not. Translation retains schema-valid bare DocModel and final personalized overlays, including validated provenance timestamps. Record encoded size rather than flattening reproducibility, stripping values or substituting a shared cache payload to improve measurements.

If measured supported data cannot fit these operational bounds, surface a concrete timeout/resource/placement change before execution readiness. Do not truncate content, drop personalized fields, extend a fixed UI budget or quietly swap to a generative cache read. Covers **NFR9.4**; CD-2 owns capacity reporting.

## PD-4 — View State Without Cache-Based Authorization

Use owner/job/context-generation keys for server-state views. Mark job snapshots stale on temporary network loss; known access loss invalidates protected state. Result opening and transient retry perform a fresh authorized result read, with private/no-store transport and query-only capabilities. Do not display a previous owner's/job's content from a stale cache while awaiting a new selection. Store captured request metadata only in the approved namespace; generated results never enter localStorage.

Motion is cosmetic and does not gate status commit. Apply semantic themes, in-flow fallback for constrained sticky status, accurate unknown-progress semantics and reduced motion. Exact layout/focus behavior follows the approved mockups and functional specification. Covers **NFR12.2**, supporting **NFR10.1–NFR10.2**.

## Validation Handoff

NFR Design supplies the patterns; Code Generation authors instrumentation and tests, and subsequent verification provides measured results. Connection-pool sizes, runtime versions and capacity findings are recorded from actual configuration; no production throughput/uptime promise follows from the single-job benchmark.

Meaningful application/store timestamp and expiry checks under RD-4 are separate from monotonic browser latency measurement. Contract Design R-03 remains Accepted risk: the original shape-check dependency set lacks active date-time validation. A new isolated checker experiment cannot recertify that helper or prove runtime expiry. Admitted registered SQL, current implementation/source-footprint authority and independently measured qualified PostgreSQL realm precede required real-store measurements; no live-test skip or mock-default build supplies this evidence.

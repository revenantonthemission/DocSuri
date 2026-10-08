# U1 Capacity and Resource-Isolation Design

## Sources

`../nfr-requirements/scalability-requirements.md`, `../nfr-requirements/performance-requirements.md`, `../nfr-requirements/tech-stack-decisions.md`, `../functional-design/functional-spec.md`, `../../../inception/contract-design/contract-summary.md` and confirmed `nfr-design-questions.md` govern this design.

## CD-1 — Real-Store Competing-Authority Qualification

Build isolated fixtures with deterministic barriers and server-time control around accept/dispatch claim, execution grant, renewal/reconciliation, prepare/publication and owner deletion. Use at least two claimants against actual authoritative storage. Assert one initial send/grant, consistent state/event seq, immutable exact binding, nonregressing terminal outcome and owner isolation. Exercise both ordering directions; a passing two-thread in-memory mock is not real-store proof.

Preserve the no-restart protocol: a durable effect intent is never deleted for another invocation; a reconciliation fence is publication-only. Concurrent backend records/query results are validated just as message inputs are. NFR11.6's correctness test load is not a production throughput commitment. Covers **NFR11.6**.

## CD-2 — Evidence-Led Resource Qualification

Record actual worker/store/queue configuration, concurrent jobs/claims tested, payload-byte distributions, read/write p50/p95, errors, memory/CPU and connection/lock wait. Use summary, typical translation and a documented larger supported translation fixture; preserve final rendered terms and metadata rather than replace them with a shared cache base. Measure cleanup throughput/backlog alongside foreground reads and renewals.

The initial browser benchmark is one active job. Initial test execution may use one generation slot per worker for controlled measurement; production slot count remains explicit environment configuration, not an imposed one-user product limit. Acquire actual execution capacity before receiving more work than can be supervised; do not prefetch ten messages into a serial loop with no visibility maintenance for waiting messages. Queue duplicates still require C7 authority and cannot silently become parallel invocations.

Set bounded resource reservations from measurements: heartbeat/supervisor control capacity is protected from child generation/snapshot encoding, API queries are isolated from maintenance batch pressure, and database limits are checked before allocating pools. Missing configuration/qualification blocks execution readiness, not a reason to invent available capacity. Covers **NFR11.7**, with PD-3 supporting **NFR9.4**.

## CD-3 — Scaling Within Existing Boundaries

Keep the existing API, worker and relational authority. Additional worker instances may contend safely only after the shared protocol and resource footprint are qualified; no application-local mutex is the final concurrency defense. Derive any concurrency/pool adjustment from tested configuration and report the range measured. No unprovided RPS, uptime, growth forecast, sharding, new database or new deployment target is selected.

U2 extends UI against U1's backend contracts and U3 owns assets. Shared parent/proxy changes remain serial as planned. If supported payloads or cleanup backlog cannot meet the selected placement/budgets, surface a concrete resource/placement/schedule decision before readiness rather than truncate content or claim unlimited scaling.

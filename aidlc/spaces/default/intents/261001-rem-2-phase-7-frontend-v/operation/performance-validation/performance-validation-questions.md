# Performance Validation — Consolidated Summary Confirmation

## Sources and Current Status

Grounded in the live mac-mini serving surface (post-deployment-execution) and the unit-level NFR evidence. Light read-only latency sampling was executed 2026-10-10 on the running production build; no load was applied and no configuration was changed.

## Executed samples (real, this session)

- **Local root (`http://127.0.0.1:3000/`), 5 requests:** 200; totals 8.3–16.5 ms (TTFB 7.7–15.1 ms) — server-side rendering is effectively immediate on-host.
- **Public root (`https://docsuri.rvnnt.dev/`) through Cloudflare + tunnel, 5 requests:** 200; totals 0.61–1.50 s (TTFB 0.43–1.50 s) — the edge+ingress round trip dominates and is variable.
- **Excluded by the open outage:** API-dependent flows (job creation/result reads) cannot be sampled meaningfully while ENV-01 keeps the API down; their local round trip would add to the ecosystem evidence once reconciliation lands.

## Consolidated Summary Confirmation

- **Scope:** author `load-test-plan.md` (a single-host-appropriate plan: light concurrency targets, what to watch — one-uvicorn-worker rate-limit design, disk, launchd respawns — owner-gated execution), `test-results.md` (the executed samples above, with conditions and limits), and `nfr-validation-matrix.md` (each applicable NFR mapped to its evidence: unit-suite verification vs live sample vs deferred-with-reason).
- **Evidence basis:** the executed samples; the unit suites' bounded measurement tests (stream/status readiness latencies, asset readiness); the accessibility locks (D1–D4) in the retained tests; the security review dispositions.
- **Limits:** no load test was run (a live single-user production host is not saturated without owner authorization); no performance budget is asserted as met beyond the sampled on-host latency; all numbers are single-client observations, not capacity claims.
- **Gate:** the human's decision at the stage gate.

Does this all look correct before I generate the performance-validation artifacts?

- Looks correct
- Request changes

[Answer]: Looks correct

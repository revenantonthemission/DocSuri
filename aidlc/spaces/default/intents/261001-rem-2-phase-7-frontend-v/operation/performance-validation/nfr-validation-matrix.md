# NFR Validation Matrix — DocSuri (feature scope)

Each applicable NFR mapped to its validation evidence and current status. "Verified" cites executed evidence in this workflow; "Sampled" cites the live observations; "Deferred" names why.

| NFR | Requirement (short) | Validation evidence | Status |
|---|---|---|---|
| NFR5 (resilience) | SSE fallback, reconnection, cursor resume, access-loss cleanup | u2 lane suites (`u2JobStatus`, `u2JobDiagnostics`, `u2JobState`); live smoke after deploy (stream endpoint reachable; 504 only from the down API) | Verified (unit) |
| NFR6 (storage/robustness) | Captured-original storage behaviors degrade safely | u1/u2 idempotency + submission suites | Verified (unit) |
| NFR7 (telemetry) | Bounded, scrubbed diagnostics; failing sender harmless | u1/u2/u3 diagnostics suites; new `asset` kind bounded | Verified (unit) |
| NFR9/NFR10 (a11y) | Keyboard reachability, live-region discipline, no traps, equivalents retained | D1–D4 locks in `docModelViewer`/`summaryModal`/`u2InteractionMatrix`/`u3ZoomPanControls`; named controls + no-trap tests | Verified (unit) |
| NFR11 (runner/CI) | Unit-scoped runners; CI gates | u1/u2/u3 configs + suite lanes; `ci.yml` coverage+e2e gates | Verified (commands) |
| NFR12 (regressions) | Existing suites stay green | Combined 86 files / 494 tests; per-lane figures | Verified (commands) |
| Performance (feature) | Serve without unreasonable latency on-host; bounds measurable | Live samples: local 8–17 ms; public 0.6–1.5 s (infra-dominated); unit-level bounded measurements | Sampled (live) — no capacity claim |
| SEC-8/SEC-9 | Same-origin asset delivery, no presigned, auth re-check, BFF-only job routing | Asset security review (READY); BFF C5 conformance tests; static no-presigned scans; CSP check | Verified (review + unit) |
| Availability SLO | Quantified targets + alerts | `observability-setup/slo-config.md` (proposed 99.5%/30 d; heartbeat thresholds below breach) | Proposed (owner adoption pending) |
| Client error tracking | Sentry per mandate | **OBS-01: not integrated** (dependency present, no init) | Deferred — owner decision required |
| API availability | API health for API-backed flows | Live: DOWN (ENV-01 `NEEDS_RECONCILIATION`); documented P2 with runbook RB-2 | Open (operator action) |

## Notes

- No row is upgraded beyond its evidence: unit-verified items cite executed suites; live items cite dated samples; deferred items name the exact blocker.
- The performance row does not assert a budget; budgets/SLOs remain proposals until the owner adopts quantified targets.

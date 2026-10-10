# Test Results — Performance Validation

Executed 2026-10-10 on the live mac-mini production build (post-deployment-execution). Single client, no load, no configuration changes.

## Samples

| Target | n | Codes | Total (s) | TTFB (s) |
|---|---|---|---|---|
| `http://127.0.0.1:3000/` | 5 | 200 ×5 | 0.0165, 0.0097, 0.0105, 0.0094, 0.0083 | 0.0151, 0.0086, 0.0093, 0.0086, 0.0077 |
| `https://docsuri.rvnnt.dev/` | 5 | 200 ×5 | 1.2045, 1.2218, 0.6074, 0.8682, 1.5021 | 1.0463, 1.0769, 0.4353, 0.4261, 1.5016 |

## Summary figures

- **Local (on-host):** ~8–17 ms total; TTFB 8–15 ms — the server answers effectively immediately; the on-host rendering cost is negligible at this scale.
- **Public (Cloudflare edge + tunnel + on-host render):** 0.61–1.50 s total; TTFB 0.43–1.50 s — dominated by the edge/ingress round trip and highly variable per request (home-network egress + Cloudflare). The delta is infrastructure latency, not application latency.
- **API-dependent endpoints:** excluded (ENV-01 keeps the API down; BFF reads return 504 — an availability fact, not a latency sample).

## Unit-level measurement evidence (already verified in the suites)

- Bounded stream/status latency and asset-readiness measurements (`jobDiagnostics` kinds; bounded 0–600000 ms; invalid dropped) — pinned by unit tests.
- Fixed 2 s fallback cadence and 10 s asset-gateway timeout constants — asserted in tests.

## Limits

- n = 5 per target, one client, one moment in time — these are observations, not capacity claims or SLO measurements. SLO targets and alert thresholds live in `observability-setup/slo-config.md`.

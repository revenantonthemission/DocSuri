# Load Test Plan — DocSuri (single-host mac mini)

Status: **plan + executed light sampling** (2026-10-10). No saturation load was applied — this is a live single-user production host, and load execution is owner-gated.

## What was executed (read-only sampling)

- 5 sequential requests to `http://127.0.0.1:3000/` and 5 to `https://docsuri.rvnnt.dev/`, recording HTTP code, total time and TTFB (numbers in `test-results.md`).

## Planned load profile (owner-gated, for when capacity evidence is wanted)

| Aspect | Plan |
|---|---|
| Tooling | `hey`/`k6` (install on the host or run from another machine against the public origin), or a scripted curl loop for micro-runs |
| Levels | 10 → 25 → 50 concurrent GETs on `/` and one paper page; short bursts (30–60 s) with cool-downs |
| Watch | `docsurictl status` (launchd respawns, disk), `top`/`vm_stat`, the web log, tunnel log; API-level rounds only after ENV-01 clears (one uvicorn worker by design — the rate limiter counts in-process; do not read multi-worker scaling into any result) |
| Guardrails | Never run saturation against the public origin without the owner watching; abort on 5xx rate > 1% or p95 degradation beyond 2× baseline; keep fake traffic identifiable (distinct UA) so logs stay interpretable |
| Success criteria | Home: `/` stays 200 with p95 under the sampled baseline ×5 at the chosen level; no launchd respawns; disk flat |

## What this plan deliberately does not do

- It does not assert throughput/capacity numbers: single-host, home-network egress and Cloudflare add variability that only a real run can characterize.
- It does not test API-backed flows until ENV-01 is reconciled — measuring a down dependency would be theater.

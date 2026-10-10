# Anomaly Configuration — DocSuri observability (proposals)

The as-built anomaly detection is the dead-man's-switch model: the *absence* of a healthy heartbeat is the anomaly, judged off-box. The additions below are **proposals** (nothing wired by this stage) chosen to be lightweight and local-first.

## As-built

- **Absence-of-ping:** heartbeat stops → healthchecks.io grace expires → external alert (covers machine death, total egress loss).
- **Explicit probe failure:** heartbeat POSTs `/fail` naming the broken link (api/web/public).
- **Visibility of red states:** `docsurictl status` shows crash states; no external paging for non-probe components.

## Proposed detectors (owner decision)

| Detector | Rule | Why |
|---|---|---|
| Disk trend | Free < 20% for 24 h → heartbeat `/fail` (new local check) | ENV-02 is live: 96% full with multi-GB logs; free space is the most likely next outage |
| Logrotate/purge exits | Non-zero last exit for `logrotate`/`worker-purge` on two consecutive runs → local check → `/fail` | Both currently exit 1; rotation failure feeds disk pressure |
| API restart-loop | > 3 respawns in 15 min (launchd ThrottleInterval context) → alert | Crash-loops are otherwise only visible in logs |
| Worker silence | No log write from a worker for > 10 min → alert | Workers are poll loops; silence = wedged process |
| Client error-rate (after OBS-01) | Unhandled error sessions > 1% over 7 days → alert | The Sentry-based SLI in `slo-config.md` |

## Restraint notes

- Every detector routes through the EXISTING alert path (heartbeat/healthchecks) — no new external service.
- Thresholds sit below the SLO breaches in `slo-config.md`; retune with the owner after the first quiet month of data.

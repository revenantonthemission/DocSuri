# SLO Configuration — DocSuri (proposed targets)

Status: **proposals for the team to adopt** (grounded in the as-built seams); no historical measurement is claimed. Operation guardrail: every SLO is quantified with a percentage and a time window, and alert thresholds sit below the SLO breach.

| Service | SLI (what is measured) | Proposed SLO | Measurement source | Alert threshold (below breach) |
|---|---|---|---|---|
| Public surface | `https://docsuri.rvnnt.dev/bff/health` reachable | **99.5% over 30 days** | Heartbeat public probe (300 s cadence) | 3 consecutive probe failures (≈15 min) or grace-period expiry |
| Web/BFF local | `127.0.0.1:3000/` 200 | 99.5% over 30 days | Heartbeat web probe | Same as above |
| API health | `127.0.0.1:8000/health` 200 | 99.5% over 30 days | Heartbeat api probe | Same; **currently breached** by ENV-01 until reconciliation |
| Heartbeat freshness | Ping received within 2× interval | ≤ 10 min silence | healthchecks.io grace | Off-box grace expiry (external alert) |
| Disk free | Free space on the data volume | ≥ 15% free sustained | `docsurictl status` disk line | Free < 20% for 24 h (proposed local check); **currently breached** (4%; ENV-02) |
| Backup recency | Daily pg_dump completed | 1 successful run per 24 h | launchd `dev.docsuri.backup` exit 0 + iCloud artifact | 2 consecutive missed days |

## Notes

- Cadence is one probe per 300 s; "3 consecutive failures" ≈ 15 minutes of outage before paging — tune only with the owner.
- The 99.5% target (≈ 3.6 h/month) is a starting proposal for a single-host, no-failover deployment; the u1 record already names single-host capacity/outage limits as the explicit trade-off.
- Once Sentry is integrated (OBS-01), add a client error-rate SLI (e.g., < 1% sessions with an unhandled error, 7-day window) with its own alert rule.

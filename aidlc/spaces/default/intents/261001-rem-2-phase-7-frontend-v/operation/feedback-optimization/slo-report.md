# SLO Report — DocSuri (closing stage)

Date 2026-10-10. Honest basis: the SLO targets are **proposals** from `observability-setup/slo-config.md` awaiting owner adoption; no historical measurement window exists yet. This report states observed facts.

## Observed facts (this workflow's session)

| SLI | Observation | vs proposed SLO |
|---|---|---|
| Public surface reachability (`https://docsuri.rvnnt.dev/`) | 200 in every sample taken (smoke + performance stages); heartbeat public probe green otherwise | Within the proposed 99.5%/30 d — on a 1-day observation, informational only |
| Web/BFF local | 200 in all samples; 8–17 ms local latency | Within target |
| API health | **DOWN** all session (`NEEDS_RECONCILIATION`, ENV-01) | **Breached** — P2 under the incident plan |
| Heartbeat freshness | Alive on 300 s cadence; correctly reporting the api probe failure | Within target mechanics |
| Disk free | 96% used / 18 Gi free — below the proposed ≥15%-free target | **Breached** (ENV-02) |
| Backup recency | `dev.docsuri.backup` idle with last exit 0; iCloud artifact path per runbook | Presumed within target; artifact recency not independently inspected |

## Actions to make this report real

1. Owner adopts (or edits) the proposed targets in `slo-config.md`.
2. Clear ENV-01 (operator reconciliation) → API health returns within target.
3. Clear ENV-02 (logrotate fix + bounded cleanup) → disk back within target.
4. After one full month, re-run this report against real history from the heartbeat + logs; then tune thresholds.

No target is claimed as met where evidence contradicts it; nothing was adjusted to make a row green.

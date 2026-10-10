# Alarms — DocSuri observability (as-built)

## Primary alarm: the dead-man's switch (configured, working)

- **Mechanism:** `ops/server/heartbeat.sh` (launchd `dev.docsuri.heartbeat`, every 300 s) probes `http://127.0.0.1:8000/health` (api), `http://127.0.0.1:3000/` (web), and `https://docsuri.rvnnt.dev/bff/health` (public chain). On success it pings a healthchecks.io check; on failure it POSTs `/fail` with the failing probe names; if the machine dies, pinging stops and the off-box grace period alerts. (No on-box monitor can report its own host's death — the alerting authority is the absence of a ping.)
- **Config:** outside the repo at `~/.config/docsuri/monitoring.env` (ping URL is a capability; values not inspected by this stage).
- **Current signal:** the api probe is failing because of the open ENV-01 (`NEEDS_RECONCILIATION`) — the alarm path is active and correctly reflects the outage. No alarm-tuning was performed.

## Secondary alarm states

| Signal | What it means today | Alarm status |
|---|---|---|
| launchd agent red (`api` exit 1; `worker-purge`/`logrotate` last exit 1) | Crash/one-shot failure | Visible in `docsurictl status`; **not** externally paged unless the heartbeat probe fails |
| Heartbeat "monitoring is blind" line | Ping URL unset — no alerts at all | Must never persist; treat as a configuration fault |
| Disk ≥ a near-full threshold | Disk pressure | Currently 96% (ENV-02); **no automated alarm wired** — proposed threshold in `anomaly-config.md` |

## Proposed additions (owner decision; nothing wired here)

1. Alert on `worker-purge`/`logrotate` non-zero exits (launchd state or a heartbeat extension).
2. Disk-free alarm below 20% (local check writing to the heartbeat `/fail` path).
3. After OBS-01 is resolved, Sentry alert rules for client error-rate spikes.

Alarms are not mutated by this stage; proposals above are recorded for the owner.

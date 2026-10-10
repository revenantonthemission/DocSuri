# Dashboards — DocSuri observability (as-built)

No external dashboard service exists on the mac-mini deployment (AWS CloudWatch dashboards retired with AWS). The observability "dashboard" is the host's own status surface, plus the log tails. This file is the canonical pane definition.

## Primary pane — `ops/server/docsurictl status`

Shows, in one screen: every launchd agent with state/pid (web, api, four workers, purge, logrotate, tunnel, heartbeat, backup), the container runtime probe, each loopback endpoint's HTTP code (api 8000, web 3000, opensearch 9200, minio 9000, ollama 11434), the public ingress code, and disk usage. Run it first, every time.

## Secondary panes

- **Heartbeat verdict history:** `tail -f ~/Library/Logs/DocSuri/heartbeat.log` — last probe set result per 300 s tick (`probes: all-ok` or `FAILED probes: …`), plus "monitoring is blind" when the ping URL is unset.
- **Public chain drill-down:** the heartbeat's public probe targets `https://docsuri.rvnnt.dev/bff/health` — the single end-to-end point that exercises Cloudflare edge → tunnel → web/BFF.
- **Per-service tails:** `~/Library/Logs/DocSuri/{web,api,worker-*,tunnel}.log` (rotated 50 MB × 3).
- **Disk:** `docsurictl status` line (currently 96% — see ENV-02).

## What a healthy pane looks like

web `200`, public `200`, tunnel running, four workers running, heartbeat `all-ok`, backup/heartbeat idle-with-exit-0, disk with a healthy free margin. api `200` is expected once ENV-01 (schema reconciliation) is cleared.

## Mapping to the operation guardrails

Every running component has at least one health signal above (HTTP probe and/or launchd state); error rate is read from the per-service logs via `log-queries.md`.

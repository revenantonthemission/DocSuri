# Validation Report — Environment Provisioning

Date: 2026-10-10 12:50 +09:00 · Method: live **read-only** checks (`docsurictl status`, `launchctl list`, `colima status`, endpoint probes, log tails) · **No mutations performed.**

## Findings

| ID | Severity | Location | Finding | Required action | Status |
|---|---|---|---|---|---|
| ENV-01 | High | launchd `dev.docsuri.api`; `~/Library/Logs/DocSuri/api.log` | API is down and crash-looping (exit 1): `backend.migrations.MigrationBlocked: schema readiness: NEEDS_RECONCILIATION; run explicit reconciliation`. The startup safeguard blocks until the recorded schema reconciliation is executed. Public web/BFF still serves 200, so browser flows degrade only where the API is required. | Operator executes the explicit schema reconciliation (the recorded SQL/realm obligation; a production mutation requiring operator authorization and its own change record), then `ops/server/docsurictl restart api` and verify `http://127.0.0.1:8000/health` + a BFF API round-trip. Not performed here. | Open |
| ENV-02 | Medium | Host disk; `~/Library/Logs/DocSuri` | Disk is 96% full (418/460 Gi; 18 Gi free); rotated logs hold multi-GB history (`api.log.2/.3` ≈ 53–70 MB each; worker logs tens of MB) and `dev.docsuri.logrotate` last exited 1. | Investigate the logrotate failure (its log is 1 KB at `~/Library/Logs/DocSuri/logrotate.log`), fix and run it; consider a one-time bounded log cleanup under operator authorization; keep ≥ an agreed free-space margin. | Open |
| ENV-03 | Low | launchd `dev.docsuri.worker-purge` | Last run exited 1 (daily one-shot). | Inspect the purge log at its next scheduled run; determine whether the exit reflects a data-state condition or a defect. | Open |
| ENV-04 | Low | `ops/server/docsurictl status` | Reports "docker unavailable" although Colima is running with a live docker socket — the status probe fails to find the CLI/socket context. | Fix the probe (socket path/PATH context) so `docsurictl status` reports the real container state. | Open |

## Passed checks

- Web/BFF on `127.0.0.1:3000` → 200; public ingress `https://docsuri.rvnnt.dev/` → 200; tunnel agent running (no inbound port published: only `:3000` reaches the tunnel).
- Four workers running; heartbeat and backup agents idle with last exit 0.
- OpenSearch, MinIO and Ollama endpoints 200; Colima VM running.
- LaunchAgent-based supervision matches the runbook (no LaunchDaemons); logs directory present and actively written.

## Authority and boundaries

- Every remediation above is a production mutation: it requires explicit operator authorization and is **not** executed by this stage. The workflow records the findings and the required actions only.
- Security posture: no security control was inspected as removed or bypassed; the loopback-only datastore binding and single-port ingress choke point remain as configured. Any infra change that follows must carry its security review and rollback steps per the operation guardrails.
- SLO framing for follow-up: availability of the public surface (current: up, 200) and API health (current: down) should be quantified with targets and alert thresholds below SLO breach when the team fixes the operator items above.

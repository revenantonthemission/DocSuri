# Observability Setup — Consolidated Summary Confirmation

## Sources and Current Status

Read-only survey of the mac-mini observability seams on 2026-10-10, against the operation guardrails (quantified SLOs with alert thresholds below breach; at least one health metric and one error-rate metric per component) and the live environment state. The host already has real, working monitoring seams; this stage documents them into the six required artifacts and records the gaps honestly. No alarm, dashboard or configuration is mutated.

## Ground truth observed (read-only)

- **Dead-man's-switch heartbeat (`ops/server/heartbeat.sh`, launchd `dev.docsuri.heartbeat`, 300 s):** probes `api /health`, `web /`, and the full public chain `https://docsuri.rvnnt.dev/bff/health`; pings healthchecks.io on success, posts `/fail` with the failing probe name on failure; a dead machine simply stops pinging and the off-box grace period alerts. Config lives outside the repo (`~/.config/docsuri/monitoring.env`; values not inspected).
- **Runtime status surface:** `ops/server/docsurictl status` (agents, containers probe, endpoints, tunnel, disk) and `~/Library/Logs/DocSuri/*.log` (rotated, 50 MB × 3).
- **In-app telemetry:** the frontend ships bounded/scrubbed diagnostics (`jobDiagnostics`: stream/status/asset/terminal/result-read) exercised by the unit suites; the backend carries an in-process `ObservabilityHub` (`backend/app.py`, `wiring.py`).
- **Gap found — Sentry:** `@sentry/nextjs` is a dependency and the project has an affirmed mandate (`ALWAYS integrate Sentry for client-side error tracking in Phase 7`), but **no `Sentry.init` / instrumentation exists in frontend source** — client error tracking through Sentry is not actually integrated. Recorded as OBS-01 with a required action.
- Live context: the API probe in the heartbeat is currently failing because of the open ENV-01 (`NEEDS_RECONCILIATION`) — i.e., the alarm path is active and correctly reflecting the outage.

## Consolidated Summary Confirmation

- **Scope:** document the as-built observability: `dashboards.md`, `alarms.md`, `slo-config.md`, `log-queries.md`, `tracing-config.md`, `anomaly-config.md` — each grounded in the seams above, marking proposals (SLO targets, thresholds) as proposals to adopt.
- **Findings to record:** OBS-01 (Medium) Sentry client error tracking not integrated despite the mandate (dependency present; no init); OBS-02 (Info) the heartbeat's api probe currently reflects the ENV-01 outage — alarm working as designed; ENV-02/03/04 cross-referenced (disk/logrotate, purge exit, status probe).
- **Limits and authority:** no alarm/dashboard/config mutation; the private monitoring config is not inspected; SLO numbers are proposed targets for the team, not measured history. The stage gate is the human's decision.

Does this all look correct before I generate the observability artifacts?

- Looks correct
- Request changes

[Answer]: Looks correct

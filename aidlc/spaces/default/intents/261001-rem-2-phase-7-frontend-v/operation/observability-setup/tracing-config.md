# Tracing Configuration — DocSuri observability (as-built)

## What exists

- **Backend, in-process:** the `ObservabilityHub` store (`backend/app.py`, `backend/wiring.py`, `backend/modules/summarization/src/summarization/real_wiring.py`) — request/operation signals recorded in process on the single-host API; consumed by its own endpoints. No external APM exporter is configured.
- **Frontend, in-app:** bounded, scrubbed diagnostics (`frontend/lib/jobDiagnostics.ts`): stream/status/asset/terminal/result-read events with bounded durations and allowlisted fields (no content, ids, parameters or stacks); sender seam installable for a host. Exercised by the unit suites.
- **Request logs:** launchd-redirected per-service logs (`web`, `api`, `worker-*`, `tunnel`) with the query recipes in `log-queries.md`.
- **No distributed tracing service** (no Jaeger/OTel collector/Tempo/Datadog on this host); spans across BFF → API are not correlated by a trace id today.

## Gap — OBS-01 (client error tracking)

The team mandate (`ALWAYS integrate Sentry for client-side error tracking in Phase 7`) is **not implemented**: `@sentry/nextjs` is a dependency, but no `Sentry.init`/instrumentation files exist in frontend source. Consequences: unhandled client errors are not captured/reported anywhere beyond the in-app diagnostics buffer.

**Required action (owner):** either integrate Sentry per the mandate (init files for browser/edge/server + DSN via environment; keep the existing scrubbing discipline: no content/ids/secrets in events), or revise the mandate with an explicit decision. Until then this remains an open observability finding.

## Proposal (smallest sufficient next step)

If full Sentry is revisited, scope it as: error capture only (no session replay, no PII), environment-tagged, sampled; dashboards/alerts flow into the healthchecks/SLO seams above. Nothing is added by this stage.

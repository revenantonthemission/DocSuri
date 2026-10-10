# Incident Plan — DocSuri

Grounded in the mac-mini environment, the working heartbeat alarm, and the operation guardrails (post-incident review required for P1/P2; escalation paths in every runbook).

## Severity classes

| Class | Definition | Examples | Response expectation |
|---|---|---|---|
| **P1** | Public surface entirely unreachable | heartbeat grace expiry; public probe failing after mitigations | Immediate owner response; mitigate via RB-1; incident record + post-incident review |
| **P2** | Public up but a core capability broken | API down for all API-backed flows (the current ENV-01 state); asset delivery broken for all papers | Same-day owner response; runbook (RB-2/RB-3); post-incident review if user-visible > 1 h |
| **P3** | Single non-critical component down | one worker stopped; tunnel flap; purge/logrotate exits | Next scheduled maintenance; monitoring entry |
| **P4** | Minor/observability defect | `docsurictl` docker-probe false negative (ENV-04) | Backlog fix |

## Flow

1. **Detect** — healthchecks.io alert (grace or `/fail` with probe names), or owner report.
2. **Triage** — `docsurictl status` + `heartbeat.log` + the named log queries (`observability-setup/log-queries.md`).
3. **Mitigate** — the matching runbook; prefer the least-invasive authorized action; rollback when a recent deploy is suspect.
4. **Communicate** — tell the owner what is broken, what was done, and current state; keep it factual (no invented ETAs).
5. **Resolve** — service verified (smoke checks per runbook).
6. **Review** — P1/P2 always; P3 when recurring. Record: timeline, root cause, what detected it (or why not), prevention action, and updates to runbooks/SLOs. The review artifact lives with the incident record in this intent's `operation/` tree.

## Current open items as live examples

- **ENV-01** (API `NEEDS_RECONCILIATION`): a P2 in progress — detected by the heartbeat's api probe; mitigation requires the owner's reconciliation (RB-2); the incident record should close when `/health` returns 200.
- **ENV-02** (disk 96%): a P3 trending to P2 if it fills; mitigation RB-3.
- **OBS-01** (Sentry gap): P4 observability debt — owner decision (integrate per mandate or revise).

## Interfaces

- Alarms/detectors: `observability-setup/alarms.md`, `anomaly-config.md`.
- Escalation: `escalation-matrix.md`.
- Rollback/restore: `deployment-pipeline/rollback-runbook.md`.

# Feedback Loop — DocSuri

How feedback enters, where it is worked, and what stays open after this workflow.

## Capture paths (as-built)

1. **Alerts:** the healthchecks.io dead-man's switch (heartbeat `/fail` names the broken link) — the primary automated path.
2. **Owner reports:** direct user observation → incident plan severities (`incident-response/incident-plan.md`).
3. **Logs:** the named queries (`observability-setup/log-queries.md`) for triage and trend reading.
4. **Workflow learnings:** AI-DLC's learnings ritual persists corrections into the project memory on future intents (the mechanism that captured this workflow's correction — "not AWS; serve on the mac mini" — applies to all future guidance).

## Loop

- **Daily/continuous:** alerts → triage → runbook mitigation.
- **Monthly (proposed):** re-run the SLO report against real history; review disk trend; confirm backups.
- **Per future intent:** the open-items backlog below rides into scoping; learnings updates happen at those gates.

## Open-items backlog carried forward (not claimed done)

| Item | Class | Source |
|---|---|---|
| ENV-01 — schema reconciliation, API restart | P2 / operator | environment-provisioning validation |
| ENV-02 — logrotate fix + disk cleanup + disk alarm | P3→P2 trend | validation; anomaly-config proposal |
| ENV-03 — purge exit investigation | P3 | validation |
| ENV-04 — docsuri ctl docker probe fix | P4 | validation |
| OBS-01 — Sentry integrate-or-revise decision | P4 | observability tracing-config |
| SLO adoption (targets + thresholds) | governance | observability slo-config |
| U3-SEC-02 — regenerate wire bindings wording | release task | security review |
| Traceability GAP upgrades; deferred real-origin E2E and real-integration evidence; Step 47-class gates | quality | unit summaries; build-and-test |

## What closes with this workflow

The feature scope's stages are complete and approved; the system is deployed on the mac mini and serving the frozen trunk build. The backlog above is the honest continuation set — each item keeps its recorded owner and evidence link.

# Escalation Matrix — u4-research-novelty

Escalation matrix for the u4-research-novelty unit. All escalation paths operate within the $0 budget constraint using local synthetic infrastructure only; no external incident management or paging service is provisioned.

## Escalation Matrix

| Severity | Condition | Escalation Path | Response Time | Owner |
|---|---|---|---|---|
| Critical invariant | Unauthorized data/effect, duplicate accounting, lost acknowledged state, corrupted published binding | Single human maintainer via local incident view; effect owner closes unsafe boundary | Immediate; stop affected new admission | Human maintainer |
| Error | Required capability unavailable (database, model, extraction, SSE stream) | Single human maintainer via local incident view; safe capability-specific user state | Human intervention | Human maintainer |
| Error | Recovery reserve at risk (shared capacity stop floor/cap reached) | Local incident with actual bytes/units, affected lane and owner runbook | Error; stop affected new admission | Human maintainer |
| Error | Accepted work needs intervention (reconciliation/retry budget exhausted, unknown admission outcome, stale claim) | Human's local incident queue with original identity references and bounded owner lookup/recovery procedure | Error; never auto-release merely because work is old | Human maintainer |
| Warning | Backlog, latency or capacity trend crosses human-agreed service threshold | Local incident view once policy/window selected; raw observations visible before selection | Warning/error according to approved policy | Human maintainer |
| Warning | Evidence stale or lost (required observation expires, counters report loss, sink full/unavailable, fallback freshness expires) | Local status and incident view when possible | Warning for optional diagnostics; error where required readiness evidence is missing | Human maintainer |
| Error | Restore/current-authority mismatch (restore lacks revocation/deletion evidence, coherent artifact binding, recovered key, valid claim treatment) | Local incident and isolated restore report for the human | Error; keep restored scope closed | Human maintainer |
| Error | Unapproved route or charge (provider/runner route exceeds evidenced free configuration or falls outside allowlist) | Local preflight report and incident view | Error; adapter/run disabled | Human maintainer |

## Escalation Procedure

### Step 1: Detection

1. Automated detection via bounded rule evaluation from observability setup alarms
2. Local observation facility detects condition class, capability, outcome and policy/build class
3. Incident recorded with correlation ID, first/last seen, occurrence count, responsible owner, protected evidence reference

### Step 2: Triage

1. Verify owner authority before reissuing any mutation
2. Verify current revocation/consent/withdrawal/erasure facts
3. Determine affected scope and blast radius
4. Classify severity: Critical invariant, Error, or Warning

### Step 3: Escalation

1. Escalate to single human maintainer via local incident view
2. No external notification service; no email/SMS/pager
3. Incident documented with correlation ID, owner identity references, bounded owner lookup/recovery procedure
4. No unattended paging or 24-hour response promise

### Step 4: Resolution

1. Resolve only after current owner checks and affected path pass
2. Acknowledgement means seen, not resolved
3. Recovery cannot erase the failed interval
4. Document final resolution with correlation ID and owner evidence references

## Escalation Guards

- No unattended paging or 24-hour response promise
- Human attention latency measured in local drill
- No automatic failover, replica or automatic host takeover
- Acknowledgement means seen, not resolved
- Recovery cannot erase the failed interval
- All escalation is read-only; no destructive actions without explicit owner confirmation

## Escalation Evidence

Each escalation record includes:

| Field | Description |
|---|---|
| Correlation ID | Opaque correlation identifier linking user-visible failure to job, dispatch and dependency evidence |
| First/Last Seen | First and last occurrence timestamps |
| Occurrence Count | Number of times the escalation has occurred |
| Responsible Owner | Owner ID responsible for the affected component |
| Protected Evidence Reference | Reference to protected evidence in owner store |
| Safe Next Step | Safe next step for resolution |
| Acknowledgement | Acknowledgement status (seen, not resolved) |
| Resolution Evidence | Evidence that current owner checks and affected path pass |

## Integration with Observability

- All escalations feed into observability setup alarms and dashboards
- Alarm conditions trigger escalation matrix
- SLO/SLI violations trigger escalation when thresholds are crossed
- Log queries support escalation investigation with bounded query patterns
- Tracing configuration provides causal trace links for escalation investigation
- Anomaly config provides anomaly detection rules for escalation detection

## Escalation Limits

- No unattended paging or 24-hour response promise
- No automatic remediation that could override owner authority
- No external notification service
- No paid incident response service or subscription
- All escalation is local synthetic only

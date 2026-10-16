# Incident Response Plan — u4-research-novelty

Incident response plan for the u4-research-novelty unit. All incident response procedures operate within the $0 budget constraint using local synthetic infrastructure only; no cloud incident management service is provisioned.

## Incident Response Strategy

**Strategy:** Single human maintainer handles all incidents; no automated incident response service; no external paging or notification service ($0 budget constraint).

**Scope:** All incidents affecting u4-research-novelty unit operations, including database connection failures, model inference failures, attachment extraction failures, SSE stream interruptions, tombstone/context deletion races, CAS conflicts, idempotency conflicts, policy-unresolved refusals, and artifact expiry events.

**Escalation Path:** Single human maintainer is the sole escalation path; no on-call rotation; no external incident response service.

## Incident Classification

| Severity | Definition | Examples | Response Time |
|---|---|---|---|
| Critical invariant | Unauthorized data/effect, duplicate accounting, lost acknowledged state, corrupted published binding | Isolation breach, data corruption, result-binding mismatch | Immediate; stop affected new admission |
| Error | Required capability unavailable, recovery reserve at risk, accepted work needs intervention, unapproved route/charge | Database connection failure, model inference failure, capacity limit reached | Human intervention; safe capability-specific user state |
| Warning | Evidence stale or lost, backlog/latency/trend trend | Collector gap, sink full, resource exhaustion | Local incident view; no automatic remediation |

## Incident Response Workflow

### Phase 1: Detection

1. Automated detection via bounded rule evaluation from observability setup alarms
2. Local observation facility detects condition class, capability, outcome and policy/build class
3. Incident recorded with correlation ID, first/last seen, occurrence count, responsible owner, protected evidence reference

### Phase 2: Classification

1. Classify severity: Critical invariant, Error, or Warning
2. Verify owner authority before reissuing any mutation
3. Determine affected scope and blast radius
4. Check current revocation/consent/withdrawal/erasure facts

### Phase 3: Response

1. Execute appropriate runbook from runbooks.md
2. For critical invariant: Stop affected new admission; effect owner closes unsafe boundary
3. For error: Safe capability-specific user state; local incident queue
4. For warning: Local status and incident view; no automatic remediation

### Phase 4: Communication

1. All communication through local incident view only
2. No external notification service; no email/SMS/pager
3. Incident documented with correlation ID, owner identity references, bounded owner lookup/recovery procedure

### Phase 5: Resolution

1. Resolve only after current owner checks and affected path pass
2. Acknowledgement means seen, not resolved
3. Recovery cannot erase the failed interval
4. Document final resolution with correlation ID and owner evidence references

## Incident Response Guarantees

- No unattended paging or 24-hour response promise
- Human attention latency measured in local drill
- No automatic failover, replica or automatic host takeover
- Acknowledgement means seen, not resolved
- Recovery cannot erase the failed interval
- All incident response is read-only; no destructive actions without explicit owner confirmation

## Incident Response Evidence

Each incident record includes:

| Field | Description |
|---|---|
| Correlation ID | Opaque correlation identifier linking user-visible failure to job, dispatch and dependency evidence |
| First/Last Seen | First and last occurrence timestamps |
| Occurrence Count | Number of times the incident has occurred |
| Responsible Owner | Owner ID responsible for the affected component |
| Protected Evidence Reference | Reference to protected evidence in owner store |
| Safe Next Step | Safe next step for resolution |
| Acknowledgement | Acknowledgement status (seen, not resolved) |
| Resolution Evidence | Evidence that current owner checks and affected path pass |

## Integration with Observability

- All incidents feed into observability setup alarms and dashboards
- Alarm conditions trigger incident response runbooks
- SLO/SLI violations trigger incident response when thresholds are crossed
- Log queries support incident investigation with bounded query patterns
- Tracing configuration provides causal trace links for incident investigation
- Anomaly config provides anomaly detection rules for incident detection

## Incident Response Limits

- No unattended paging or 24-hour response promise
- No automatic remediation that could override owner authority
- No external notification service
- No paid incident response service or subscription
- All incident response is local synthetic only

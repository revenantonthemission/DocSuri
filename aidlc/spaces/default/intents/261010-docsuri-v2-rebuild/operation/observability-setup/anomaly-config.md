# Anomaly Config — u4-research-novelty Observability

Anomaly detection configuration for the u4-research-novelty unit. All anomaly detection is local-only; no anomaly detection service or ML-based anomaly detection is provisioned ($0 budget constraint).

## Anomaly Detection Configuration

| Anomaly type | Detection method | Threshold | Action |
|---|---|---|---|
| Error rate spike | Error count exceeds baseline-derived threshold per 5-minute window | Baseline unset; report raw counts and full failure/timeout counts | Warning for optional diagnostics; error where required readiness evidence is missing |
| Latency anomaly | Completion duration exceeds baseline-derived percentile | Baseline unset; report completion distribution | Warning; no automatic remediation |
| Throughput drop | Admitted/completed work rate drops below baseline | Baseline unset; report offered/admitted/completed/failed/rejected counts separately | Warning; no automatic remediation |
| Error rate by operation | Error count per operation kind exceeds threshold | Baseline unset; report per-operation error counts | Warning; isolate affected operation |
| Collector gap | Collector heartbeat missing or freshness exceeds 90 seconds | 90-second deadline | Error where required readiness evidence is missing |
| Sink full | Optional observation sink reaches 64-event batch limit | 64-event maximum batch | Drop only eligible optional detail and mark a gap; no foreground transaction waits |
| Resource exhaustion | Resource usage reaches configured stop floor/cap | Per NFR8.1 capacity bounds | Error; stop affected new admission; preserve accepted responsibility |

## Anomaly Detection Guards

- No machine learning-based anomaly detection; all detection is rule-based with explicit thresholds
- No automatic remediation; all anomalies require human investigation
- No external anomaly detection service; all detection is local
- No paid anomaly detection service or subscription
- Anomaly detection is best-effort; missing or stale evidence is reported as unknown, never as healthy

## Anomaly Response Runbook

| Step | Action | Owner |
|---|---|---|
| 1 | Detect anomaly via bounded rule evaluation | Local observation facility |
| 2 | Classify severity (critical invariant / error / warning) | Human operator via protected ServiceOperations view |
| 3 | Correlate with owner evidence references | Human operator via protected read-only access |
| 4 | Determine affected scope and blast radius | Human operator via protected ServiceOperations view |
| 5 | Execute rollback runbook if deployment-related | Human operator via operation/deployment-pipeline/rollback-runbook.md |
| 6 | Record incident with first/last seen, occurrence count, responsible owner, protected evidence reference | Human operator via local incident view |
| 7 | Acknowledge (seen, not resolved) | Human operator |
| 8 | Resolve only after current owner checks and affected path pass | Human operator via authorized owner commands |

## Anomaly Detection Guards

- Acknowledgement means seen, not resolved
- Recovery cannot erase the failed interval
- No unattended paging or 24-hour response promise
- Human attention latency is measured in the local drill
- No automatic failover, replica or automatic host takeover

# Log Queries — u4-research-novelty Observability

Log query configuration for the u4-research-novelty unit. All queries are local CloudWatch Logs Insights-style saved queries against bounded local synthetic observation data. No cloud telemetry vendor is selected.

## Log Query Configuration

| Query name | Purpose | Query pattern | Retention |
|---|---|---|---|
| Research operation errors | Query all error-level research operation events by operation kind and outcome | `filter @message like /error/ \| stats count() by operation_kind, outcome_code` | 24 hours optional observation age |
| Admission/release tracking | Query admission and release events by owner and operation identity | `filter @message like /admission\|release/ \| stats count() by owner_id, operation_id` | 24 hours optional observation age |
| Tombstone events | Query tombstone creation and validation events | `filter @message like /tombstone/ \| stats count() by context_id, session_id` | 24 hours optional observation age |
| Usage reconciliation | Query usage reconciliation events by owner and operation | `filter @message like /usage_reconciliation/ \| stats count() by owner_id, operation_id, disposition` | 24 hours optional observation age |
| Collector health | Query collector heartbeat and drop/reset counters | `filter @message like /collector/ \| stats latest(@heartbeat), sum(@drop_count), sum(@reset_count)` | 24 hours optional observation age |
| Error rate by operation | Query error rate by operation kind over time window | `filter @message like /error/ \| stats count() by bin(5m), operation_kind` | 24 hours optional observation age |
| Capacity headroom | Query resource usage against configured limits | `filter @message like /capacity/ \| stats max(@usage_pct) by resource_type` | 24 hours optional observation age |

## Log Query Guards

- No secrets, prompts, private text, or credentials in any query pattern or result
- Labels use bounded vocabulary for component, capability, outcome and policy/build class only
- Owner IDs, job IDs, paper IDs, URLs, raw queries and hashes do not become query filters or labels
- Detailed opaque references exist only in restricted evidence
- Query results are bounded: at most 64 events per producer, 1 MiB per producer, at most 4 KiB per event
- Query timeout: 2-second deadline; observation expires after 90 seconds
- Sink retry: 64-event maximum batch, 100 ms attempt wait, at most two retries within a 2-second total deadline; after deadline drop only eligible optional detail and mark a gap
- No foreground transaction waits on sink recovery

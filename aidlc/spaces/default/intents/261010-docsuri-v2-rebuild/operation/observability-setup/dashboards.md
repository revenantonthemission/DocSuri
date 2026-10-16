# Dashboards — u4-research-novelty Observability

Local synthetic observability dashboard configuration for the u4-research-novelty unit. All dashboards are local-only; no cloud monitoring service is provisioned ($0 budget constraint).

## Dashboard Layouts

| Dashboard | Scope | Panels | Access |
|---|---|---|---|
| Research workspace readiness | Owner-scoped research operation readiness | Owner/context enforcement checks, admission/release status, tombstone state, artifact availability, eligibility revocation checks | Human operator via protected ServiceOperations view; owner via restricted read |
| Research workload | Research turn/novelty analysis/job processing | Accepted jobs, pending work, terminal states, usage reconciliation counts, dispatch obligations, completion facts | Human operator via protected ServiceOperations view; owner via restricted read |
| Error budget | Error rates by operation kind | UNAUTHENTICATED/FORBIDDEN/NOT_FOUND/CONFLICT/POLICY_UNRESOLVED/IDEMPOTENCY_CONFLICT/SOURCE_INELIGIBLE counts, error rate trend | Human operator via protected ServiceOperations view |
| Capacity headroom | Resource headroom vs limits | Upload bytes, queue depth, concurrency, retry counts, artifact retention, artifact expiry sweep | Human operator via protected ServiceOperations view |
| Observability health | Collection health, signal staleness, unknown/stale signals | Collector freshness, heartbeat, drop/reset counters, observation gaps | Human operator via protected ServiceOperations view |

## Dashboard Configuration

| Dashboard | Format | Retention | Access boundary |
|---|---|---|---|
| Research workspace readiness | Bounded local JSONL dashboard projection | 24 hours optional observation age | Owner-bound read-only; no public exposure |
| Research workload | Bounded local JSONL dashboard projection | 24 hours optional observation age | Owner-bound read-only; no public exposure |
| Error budget | Bounded local JSONL dashboard projection | 24 hours optional observation age | Owner-bound read-only; no public exposure |
| Capacity headroom | Bounded local JSONL dashboard projection | 24 hours optional observation age | Owner-bound read-only; no public exposure |
| Observability health | Bounded local JSONL dashboard projection | 24 hours optional observation age | Owner-bound read-only; no public exposure |

## Dashboard Guards

- No secrets, prompts, private text, or credentials in any dashboard value
- Labels use bounded vocabulary for component, capability, outcome and policy/build class only
- Owner IDs, job IDs, paper IDs, URLs, raw queries and hashes do not become labels
- Detailed opaque references exist only in restricted evidence
- Restricted drill-down follows opaque links to authorized owner evidence, with finite page and query bounds

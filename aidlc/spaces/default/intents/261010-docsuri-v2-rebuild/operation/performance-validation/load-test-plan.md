# Load Test Plan — u4-research-novelty Performance Validation

Load test plan for the u4-research-novelty unit. All load testing uses existing local synthetic infrastructure only; no cloud load testing service is provisioned ($0 budget constraint).

## Load Test Strategy

| Aspect | Decision | Source |
|---|---|---|
| Traffic pattern | Single human maintainer synthetic load only; no public traffic patterns | construction/u1-integrated-paper-journey/nfr-requirements/scalability-requirements.md (NFR8.1) |
| Test environment | Synthetic local realm, loopback PostgreSQL port 15479, HTTPS port 18079 | construction/u4-research-novelty/code-generation/code-summary.md |
| Model | Qwen3 8B candidate, one active model/call, finite context/output/deadline | construction/u1-integrated-paper-journey/infrastructure-design/infrastructure-specification.md (INFRA02) |
| Embeddings | BGE-M3 dense candidate, exact cached identity, revisioned chunk policy | construction/u1-integrated-paper-journey/infrastructure-design/infrastructure-specification.md (INFRA02) |
| Load generator | Local synthetic browser journeys and API calls within the application; no external load generator | construction/u4-research-novelty/code-generation/code-summary.md |

## Load Test Scenarios

| Scenario | Purpose | Measurement |
|---|---|---|
| Single complete P1/P2 journey | Establish useful-output and persistence correctness plus per-operation and full-task resource/time baselines | Query → understand → save → revisit; record model load separately from warm work |
| Mixed foreground/background use | Vary bounded simultaneous reading, search, save/revisit and assistance within the declared experiment limit; measure interactive latency while model work runs, accepted/completed/rejected throughput, queue age and CPU/memory/storage pressure | Query/list/revisit under load while model work runs concurrently |
| Admission spike and duplicate delivery | Increase arrival within safe bounds to each configured owner/global boundary; include concurrent reservations and same-key retry bursts; prove backpressure, finite retries and no extra accepted/accounting effects | Offered/admitted/rejected work, pending intents, retry load and bound enforcement without extra accepted/accounting effects |
| Record/corpus growth | Vary bounded permitted corpus/representation size, saved/history/job/result count and payload lengths; measure query/list/revisit cost, bytes per category, projection/cache/temporary growth and retention cleanup behavior | Query/list/revisit cost, bytes per category, projection/cache/temporary growth and retention cleanup behavior |
| Dependency outage and restart | Hold a required dependency unavailable within approved fault bounds, then restore; measure accumulated obligations, drain rate, worst queue age, memory/storage peak and recovery; require preserved identities and truthful foreground feedback | Accepted work recovery, drain rate, queue age, memory/storage peak, recovery time; verify preserved identities and truthful foreground feedback |
| Resource boundary | Use isolated quota/fault mechanisms to simulate low disk, exhausted queues, write failure, model unavailability and telemetry outage without filling or damaging the real workstation; verify safe refusal and successful recovery checks | Refusal under exhaustion, recovery checks, queue/deadline enforcement |

## Load Test Execution Parameters

| Parameter | Value | Source |
|---|---|---|
| Owner accounts | 2 synthetic accounts (A and B) | construction/u4-research-novelty/code-generation/code-summary.md |
| Papers | 2 fixture papers (P1: 1706.03762v7, P2: 2005.11401v4) | construction/u1-integrated-paper-journey/nfr-requirements/performance-requirements.md |
| Outstanding jobs | 2 accepted per owner / 4 global | construction/u1-integrated-paper-journey/infrastructure-design/infrastructure-specification.md (INFRA05) |
| Page size | 20 results / max 100 | construction/u1-integrated-paper-journey/infrastructure-design/infrastructure-specification.md (INFRA05) |
| Query size | 2 KiB | construction/u1-integrated-paper-journey/infrastructure-design/infrastructure-specification.md (INFRA05) |
| JSON request size | 16 KiB | construction/u1-integrated-paper-journey/infrastructure-design/infrastructure-specification.md (INFRA05) |
| Result size | ≤128 KiB | construction/u1-integrated-paper-journey/infrastructure-design/infrastructure-specification.md (INFRA05) |
| Source fixture size | ≤2 MiB each | construction/u1-integrated-paper-journey/infrastructure-design/infrastructure-specification.md (INFRA05) |
| Model context | 2,048 tokens | construction/u1-integrated-paper-journey/infrastructure-design/infrastructure-specification.md (INFRA05) |
| Model output | ≤224 tokens | construction/u1-integrated-paper-journey/infrastructure-design/infrastructure-specification.md (INFRA05) |
| Model generation deadline | 90 seconds | construction/u1-integrated-paper-journey/infrastructure-design/infrastructure-specification.md (INFRA05) |
| Embedding client deadline | 60 seconds | construction/u1-integrated-paper-journey/infrastructure-design/infrastructure-specification.md (INFRA05) |
| Statement timeout | 5 seconds | construction/u1-integrated-paper-journey/infrastructure-design/infrastructure-specification.md (INFRA05) |
| Idle-transaction timeout | 5 seconds | construction/u1-integrated-paper-journey/infrastructure-design/infrastructure-specification.md (INFRA05) |
| Lock timeout | 2 seconds | construction/u1-integrated-paper-journey/infrastructure-design/infrastructure-specification.md (INFRA05) |
| Database connections | 12 total (4 app pool, 2 worker, 1 observation, 1 maintenance, 2 spare) | construction/u1-integrated-paper-journey/infrastructure-design/infrastructure-specification.md (INFRA05) |
| Model execution permit | 1 active model/call | construction/u1-integrated-paper-journey/infrastructure-design/infrastructure-specification.md (INFRA02) |
| Memory-pressure free threshold | ≥35% before model start | construction/u1-integrated-paper-journey/infrastructure-design/infrastructure-specification.md (INFRA05) |
| Disk threshold | ≥8 GiB free before model start | construction/u1-integrated-paper-journey/infrastructure-design/infrastructure-specification.md (INFRA05) |

## Metrics to Collect

| Metric | Source | Unit |
|---|---|---|
| End-to-end journey latency | Browser harness | milliseconds |
| Search/query latency | Frontend/backend instrumentation | milliseconds |
| Save acknowledgement latency | Frontend/backend instrumentation | milliseconds |
| Acceptance latency | Acceptance → durable admission receipt | milliseconds |
| Job execution latency | Acceptance → first valid claim | milliseconds |
| Result retrieval latency | Result read → authorized prepared result | milliseconds |
| Revisit latency | Saved-work reopen → same intended paper/version | milliseconds |
| Recovery latency | Fault detection → verified recovery | milliseconds |
| Offered work count | Admission ledger | count |
| Admitted work count | Acceptance ledger | count |
| Completed work count | Terminal state ledger | count |
| Failed work count | Failure ledger | count |
| Rejected work count | Refusal ledger | count |
| Queue depth | Pending intents/reservations | count |
| Queue age | Oldest accepted intent age | milliseconds |
| CPU usage | Process/system monitoring | percent |
| Memory usage | Process/system monitoring | bytes/percent |
| Storage usage | Filesystem/database | bytes |
| Model load time | Model loader | milliseconds |
| Model execution time | Model inference | milliseconds |
| Error rate | Error ledger | count/percent |
| Retry count | Retry ledger | count |

## Load Test Execution Rules

1. Warm-up runs are declared before collection and retained as a separate set
2. Cold/warm cache, model loading, parallel-user/worker levels, fixture corpus size, network conditions and idle/busy hardware state are explicit strata, never silently pooled
3. Zero eligible samples/opportunities means unknown; do not drop failed, aborted, unexecuted, excluded-maintenance or unfinished cases from the recorded denominator
4. If adjusted availability is later useful, show its declared exclusions alongside the gross figure
5. Cross-process elapsed values require clock provenance and measured uncertainty; otherwise report unknown or an interval
6. Owner revisions order effects, not trace arrival time
7. Material model/runtime/configuration/data changes and later units require rebaselining before applying old targets
8. Numeric service targets are unset until baseline measured and human agreement; no numeric service target is invented here
9. Stop before headroom is consumed; simulate resource failures through isolated quotas/adapters instead of filling the real disk or exhausting the workstation
10. The exact runnable completion command remains separately approved

## Measurement Output

For each workload report:
- Offered, admitted, active, completed, failed, rejected work separately
- Duplicate deliveries and execution attempts separately
- Queue length alone cannot establish capacity: track age from original immutable acceptance, not latest retry
- Report unique intended identities alongside total arrivals so retries cannot inflate logical throughput
- Active and unresolved counts are timestamped states
- CPU pressure, sustained/resident memory, available allocated storage, data/log/temp growth and network use with units and sampling interval
- Estimate storage demand as measured category sizes and observed growth plus temporary publication/rebuild, recovery, backup/restore and safety headroom
- Retain assumptions and uncertainty; P1/P2 fixtures do not forecast public demand; model file size does not establish runtime memory or throughput
- Rebaseline after material model/runtime/configuration/data changes and each added unit's demand

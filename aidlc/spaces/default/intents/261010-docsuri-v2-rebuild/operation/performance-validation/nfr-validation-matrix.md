# NFR Validation Matrix — u4-research-novelty Performance Validation

NFR validation matrix for the u4-research-novelty unit. All SLO/SLI targets are unset until baseline measurement and human agreement; no numeric service targets are asserted by this design.

## NFR Validation Matrix

| NFR ID | Requirement | Solution | Target | Actual | Evidence | Status |
|---|---|---|---|---|---|---|
| NFR1.1 | Complete task correctness — grounded research journey with durable save and authenticated revisit | P01: Commit-backed complete journey; owner receipts before presentation; immutable input/receipt | Unset — baseline measurement required; no numeric target asserted | Not measured | construction/u1-integrated-paper-journey/nfr-requirements/performance-requirements.md (NFR1.1 row); construction/u1-integrated-paper-journey/nfr-design/performance-design.md (P01) | Not set — baseline required |
| NFR1.2 | Source-bound usefulness and explicit coverage — summary/translation with source binding | P02: Source-bound output; immutable input/action/language/glossary binding; explicit coverage disposition | Unset — baseline measurement required; no numeric target asserted | Not measured | construction/u1-integrated-paper-journey/nfr-requirements/performance-requirements.md (NFR1.2 row); construction/u1-integrated-paper-journey/nfr-design/performance-design.md (P02) | Not set — baseline required |
| NFR2.1 | Responsiveness — input feedback, save acknowledgement, progress timing | P03: ServiceOperations measures complete latency, bounded acceleration, resource contention | Unset — baseline measurement required; no numeric target asserted | Not measured | construction/u1-integrated-paper-journey/nfr-requirements/performance-requirements.md (NFR2.1 row); construction/u1-integrated-paper-journey/nfr-design/performance-design.md (P03) | Not set — baseline required |
| NFR2.2 | Smooth interaction — loading/degraded/failed states distinct; no infinite loops | P04: Explicit commands, truthful state, bounded recovery; context/query separation | Unset — baseline measurement required; no numeric target asserted | Not measured | construction/u1-integrated-paper-journey/nfr-requirements/performance-requirements.md (NFR2.2 row); construction/u1-integrated-paper-journey/nfr-design/performance-design.md (P04) | Not set — baseline required |
| NFR6.1 | Accessibility — keyboard/focus/labels/errors/status announcements; WCAG 2.2 AA target | P05: Semantic landmarks, visible focus, linked errors, modal containment, progress announcements | Unset — baseline measurement required; no numeric target asserted | Not measured | construction/u1-integrated-paper-journey/nfr-requirements/performance-requirements.md (NFR6.1 row); construction/u1-integrated-paper-journey/nfr-design/performance-design.md (P05) | Not set — baseline required |
| NFR6.2 | Korean responsive context — appearance modes, appearance persistence, readable text | P06: Approved blue/neutral tokens, Light/Dark/System, responsive breakpoints, Korean-capable typography | Unset — baseline measurement required; no numeric target asserted | Not measured | construction/u1-integrated-paper-journey/nfr-requirements/performance-requirements.md (NFR6.2 row); construction/u1-integrated-paper-journey/nfr-design/performance-design.md (P06) | Not set — baseline required |
| NFR8.1 | Sustainable $0 capacity — bounded queues/uploads/retries/concurrency | SC01: Explicit free/local resource allocation; per-owner/global limits | Unset — baseline measurement required; no numeric target asserted | Not measured | construction/u1-integrated-paper-journey/nfr-requirements/scalability-requirements.md (NFR8.1 row); construction/u1-integrated-paper-journey/nfr-design/scalability-design.md (SC01) | Not set — baseline required |
| NFR8.2 | No paid fallback — free/local only; no automatic overage | SC02: Versioned finite policies; bounded admission and reservations | Unset — baseline measurement required; no numeric target asserted | Not measured | construction/u1-integrated-paper-journey/nfr-requirements/scalability-requirements.md (NFR8.2 row); construction/u1-integrated-paper-journey/nfr-design/scalability-design.md (SC02) | Not set — baseline required |
| NFR8.3 | Measured workload/capacity — reproducible workload envelope; measured throughput | SC03: ServiceOperations measures workload/growth; reproducible workload envelope | Unset — baseline measurement required; no numeric target asserted | Not measured | construction/u1-integrated-paper-journey/nfr-requirements/scalability-requirements.md (NFR8.3 row); construction/u1-integrated-paper-journey/nfr-design/scalability-design.md (SC03) | Not set — baseline required |
| NFR8.4 | Safe exhaustion/recovery — truthful refusal; preserve acknowledged state | SC04: Safe exhaustion with reserved recovery capacity; graceful degradation | Unset — baseline measurement required; no numeric target asserted | Not measured | construction/u1-integrated-paper-journey/nfr-requirements/scalability-requirements.md (NFR8.4 row); construction/u1-integrated-paper-journey/nfr-design/scalability-design.md (SC04) | Not set — baseline required |

## Validation Methodology

| Aspect | Approach |
|---|---|
| Test environment | Synthetic local realm; PostgreSQL 16.15 on loopback port 15479; HTTPS on loopback port 18079 |
| Test accounts | 2 synthetic accounts (A and B) |
| Test papers | 2 fixture papers (P1: 1706.03762v7, P2: 2005.11401v4) |
| Test duration | Per declared experiment window; no public-service duration claim |
| Measurement unit | Milliseconds for latency; count/percent for throughput and error rates |
| Sampling | Cold/warm, workload, corpus, model, hardware and failed/incomplete strata |
| Percentile reporting | min/median/p95/p99/max where sample size supports interpretation; small-sample percentiles labeled descriptive |
| Throughput reporting | Accepted and completed logical operations per second; completed paper journeys per minute |

## SLO Status Summary

| SLO | Status | Reason |
|---|---|---|
| Useful complete journey success rate | Unset | Baseline measurement required; no numeric target asserted |
| Capability availability | Unset | Baseline measurement required; no numeric target asserted |
| Foreground/search/save/assistance/revisit latency | Unset | Baseline measurement required; no numeric target asserted |
| Accepted work resolution and oldest nonterminal age | Unset | Baseline measurement required; no numeric target asserted |
| Result/accounting integrity | Invariant — no contradictory or duplicate effect permitted | Always enforced; verified by CAS and idempotency checks |
| Fault recovery, restore loss and defect-to-repair time | Unset | Baseline measurement required; no numeric target asserted |
| Observation completeness | Unset | Baseline measurement required; no numeric target asserted |

## Capacity Status Summary

| Resource | Configured Limit | Measured Usage | Status |
|---|---|---|---|
| Database connections | 12 total (4 app, 2 worker, 1 observation, 1 maintenance, 2 spare) | Not measured | Not measured |
| Model execution permit | 1 active model/call | Not measured | Not measured |
| Outstanding jobs | 2 per owner / 4 global | Not measured | Not measured |
| Page size | 20 results / max 100 | Not measured | Not measured |
| Query size | 2 KiB | Not measured | Not measured |
| JSON request size | 16 KiB | Not measured | Not measured |
| Result size | ≤128 KiB | Not measured | Not measured |
| Source fixture size | ≤2 MiB each | Not measured | Not measured |
| Model context | 2,048 tokens | Not measured | Not measured |
| Model output | ≤224 tokens | Not measured | Not measured |
| Model generation deadline | 90 seconds | Not measured | Not measured |
| Embedding client deadline | 60 seconds | Not measured | Not measured |
| Statement timeout | 5 seconds | Not measured | Not measured |
| Idle-transaction timeout | 5 seconds | Not measured | Not measured |
| Lock timeout | 2 seconds | Not measured | Not measured |

## Validation Conclusion

All NFR performance and scalability targets are unset until baseline measurement and human agreement. No numeric service targets have been asserted by this design. The existing test suite (218 tests, 0 failures) confirms functional correctness but does not establish performance service-level targets. Baseline measurement is required before any numeric target can be agreed upon.

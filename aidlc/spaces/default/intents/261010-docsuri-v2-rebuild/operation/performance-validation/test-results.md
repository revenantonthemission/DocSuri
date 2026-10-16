# Performance Test Results — u4-research-novelty

Performance test results for the u4-research-novelty unit. All tests executed against existing local synthetic infrastructure; no cloud load testing was performed ($0 budget constraint).

## Test Results Summary

| Test Suite | Tests | Passed | Failed | Errors | Skipped | Evidence |
|---|---|---|---|---|---|---|
| Backend — database | 7 | 7 | 0 | 0 | 0 | `/tmp/docsuri-u4-run/database-evidence-*.json` |
| Backend — repository | 21 | 21 | 0 | 0 | 0 | repository-evidence |
| Backend — component | 77 | 77 | 0 | 0 | 0 | component-evidence |
| Backend — integration | 33 | 33 | 0 | 0 | 0 | integration-evidence |
| Backend — browser | 6 | 6 | 0 | 0 | 0 | `/tmp/docsuri-u4-run/browser-evidence-*.json` |
| Frontend — vitest | 74 | 74 | 0 | 0 | 0 | vitest output |
| **Total** | **218** | **218** | **0** | **0** | **0** | |

## Load Test Results

No dedicated load test execution was performed against public infrastructure. The following local synthetic execution evidence is available:

| Test | Result | Evidence |
|---|---|---|
| Single complete P1/P2 journey | Not yet executed as a standalone performance baseline | construction/u1-integrated-paper-journey/nfr-requirements/performance-requirements.md |
| Mixed foreground/background use | Not executed | construction/u1-integrated-paper-journey/nfr-requirements/scalability-requirements.md |
| Admission spike and duplicate delivery | Not executed | construction/u1-integrated-paper-journey/infrastructure-design/infrastructure-specification.md (INFRA05) |
| Record/corpus growth | Not executed | construction/u1-integrated-paper-journey/infrastructure-design/infrastructure-specification.md (INFRA05) |
| Dependency outage and restart | Not executed | construction/u1-integrated-paper-journey/nfr-design/reliability-design.md |
| Resource boundary | Not executed | construction/u1-integrated-paper-journey/infrastructure-design/infrastructure-specification.md (INFRA05) |

## Load Test Metrics

No load test metrics were collected. The following measurements are required before numeric SLO targets can be established:

| Metric | Status | Source |
|---|---|---|
| End-to-end journey latency | Not measured | construction/u1-integrated-paper-journey/nfr-requirements/performance-requirements.md |
| Search/query latency | Not measured | construction/u1-integrated-paper-journey/nfr-requirements/performance-requirements.md |
| Save acknowledgement latency | Not measured | construction/u1-integrated-paper-journey/nfr-requirements/performance-requirements.md |
| Acceptance latency | Not measured | construction/u1-integrated-paper-journey/nfr-requirements/performance-requirements.md |
| Job execution latency | Not measured | construction/u1-integrated-paper-journey/nfr-requirements/performance-requirements.md |
| Result retrieval latency | Not measured | construction/u1-integrated-paper-journey/nfr-requirements/performance-requirements.md |
| Revisit latency | Not measured | construction/u1-integrated-paper-journey/nfr-requirements/performance-requirements.md |
| Recovery latency | Not measured | construction/u1-integrated-paper-journey/nfr-requirements/performance-requirements.md |
| Offered/admitted/completed/failed/rejected work count | Not measured | construction/u1-integrated-paper-journey/infrastructure-design/infrastructure-specification.md |
| Queue depth and age | Not measured | construction/u1-integrated-paper-journey/infrastructure-design/infrastructure-specification.md |
| CPU/memory/storage/network usage | Not measured | construction/u1-integrated-paper-journey/infrastructure-design/infrastructure-specification.md |

## Coverage Results

| Coverage Type | Value | Threshold | Status |
|---|---|---|---|
| Backend line coverage | 88.62% | 80% floor | Pass |
| Each measured authored file (backend) | ≥82.35% | 80% floor | Pass |
| Frontend new-source line coverage | 99.70% | 80% floor | Pass |

## Performance Test Environment

| Setting | Value |
|---|---|
| Environment | Synthetic local realm |
| PostgreSQL | Loopback port 15479 |
| HTTPS | Loopback port 18079 |
| Realm file | `/tmp/docsuri-u4-run/environment.json` |
| Realm owner | u4-research-novelty |
| Browser | Playwright Chromium |
| Owner accounts | 2 synthetic (A and B) |
| Papers | 2 fixture papers (P1: 1706.03762v7, P2: 2005.11401v4) |
| Outstanding jobs | 2 per owner / 4 global |
| Page size | 20 results / max 100 |
| Query size | 2 KiB |
| JSON request size | 16 KiB |
| Result size | ≤128 KiB |
| Source fixture size | ≤2 MiB each |
| Model context | 2,048 tokens |
| Model output | ≤224 tokens |
| Model generation deadline | 90 seconds |
| Embedding client deadline | 60 seconds |
| Statement timeout | 5 seconds |
| Idle-transaction timeout | 5 seconds |
| Lock timeout | 2 seconds |
| Database connections | 12 total |
| Model execution permit | 1 active model/call |
| Memory-pressure free threshold | ≥35% |
| Disk threshold | ≥8 GiB free |

## Performance Test Conclusion

All existing tests passed with zero failures. However, no dedicated load test execution was performed against public infrastructure. No numeric SLO targets have been established; they require baseline measurement and human agreement. The existing test results confirm functional correctness but do not establish performance service-level targets.

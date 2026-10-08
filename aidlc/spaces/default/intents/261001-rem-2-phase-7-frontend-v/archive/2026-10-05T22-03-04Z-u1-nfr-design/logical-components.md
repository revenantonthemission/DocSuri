# U1 Logical Pattern and Failure-Domain Inventory

## Sources

`../nfr-requirements/performance-requirements.md`, `../nfr-requirements/security-requirements.md`, `../nfr-requirements/scalability-requirements.md`, `../nfr-requirements/reliability-requirements.md`, `../nfr-requirements/observability-requirements.md`, `../nfr-requirements/tech-stack-decisions.md`, `../functional-design/functional-spec.md` and `../../../inception/contract-design/contract-summary.md` are the actual upstream artifacts. Confirmed `nfr-design-questions.md` selects the timing/maintenance profile. This inventory applies patterns within approved components/runtimes, not a new deployment topology or duplicate entity ownership.

## LC-1 — Responsibilities and Resource Boundaries

| Logical area / existing owner | Patterns | Failure domain / isolation |
|---|---|---|
| Browser submission/recovery — ContentJobApi/JobSubmissionForm | SD-4, C4 attempt registry | Captured input and context guards isolate stale draft/preparation; backend auth remains authoritative |
| Browser tracking/result — JobStatus/SummaryModal/PaperDetailIsland | PD-1/PD-4, RD-5/RD-6, SD-5 | Separate job/connection/read state, current owner/job keys, stable authorized recovery checkpoint; no command capability in result view |
| BFF/controller/query — BffProxy/ContentJobController/ContentJobService | SD-1–SD-3, PD-2, RD-4 | Narrow query capabilities, configured upstream, cookie/redirect fidelity, safe owned-read failure; no pipeline invocation on reads |
| Durable job/result/effect authority — ContentJobService | Functional T1–T8, RD-1–RD-4 | Shared relational lock/fence/owner authority; exact immutable snapshot; no local-only concurrency defense |
| Existing worker supervisor/child execution — ContentJobWorker | RD-1, CD-1/CD-2 | Independent renewal/control capacity, one invocation grant, child generation cannot publish through stale authority |
| Existing scheduled maintenance seam | RD-2/RD-3, OD-3/OD-4 | Bounded guarded first dispatch/reconciliation/purge; separate scheduling from generation availability; no blind legacy re-enqueue |
| Existing queue and adapters | C6/C8, RD-1/RD-2 | At-least-once receipt; authority markers and compatible consumers prevent duplicate invocation/old-worker mutation |
| Existing diagnostics | OD-1–OD-5 | Safe allowlisted events, freshness/error evidence and bounded failure handling; no sensitive-data/debug payload coupling |

The shared relational database is a durability and resource failure domain. Control-plane reservation is verified against actual connection limits; a logical isolated task is not proof of reserved capacity. API, worker and maintenance failures remain observable separately. Queue visibility, database publication authority and browser presentation state are different mechanisms.

## LC-2 — Implementation Verification and Quality Floor

Implement the selected patterns under the existing stack, then author/run meaningful tests per component under test-after ordering. Preserve ≥80% new-code line coverage, current suites, strict type/lint and relevant contract/integration/browser checks. Use actual commands after reconciling the current package-script inventory; skipped live-dependency tests cannot prove real-store or skeleton behavior. Covers **NFR11.1**.

Validate configuration inequalities, adapters/deadlines, supported payload/resource limits, supervisor isolation, all declared races, scheduler cadence, cleanup drainage and notification readiness before actual operation. Schema/traceability checks alone do not prove these patterns. The real integrated check remains separately human-authorized before the Unit checkpoint.

## LC-3 — Infrastructure and Rollout Handoff

Infrastructure Design verifies actual existing API/worker/store/queue/runtime configuration, effective permissions/data protection, heartbeat and scheduler capacity, and compatible reader/worker activation before new-message/UI exposure. A minute-granularity scheduler needs the explicitly qualified bounded two-pass or other valid sub-minute strategy. Production-on-merge still requires compatible gated exposure, tested rollback and safe old-runtime drain/isolation; no atomic multi-runtime deploy is assumed.

Preserve exact readable records through rollback and do not reintroduce an old worker that grants ambiguous generation or writes coarse result references for new-protocol jobs. Proposed operational defaults are not assertions about the deployed environment. Additional services/architecture or changed product/placement limits require a concrete decision rather than a silent substitution.

## Upstream Findings

Functional Design's Minor R-05 (SubmissionDraft derived ER optionality) and NFR Requirements' Minor R-01 (explicit upstream source citations) remain in their recorded reviews for the U1 human checkpoint. Actual authoritative workflows and passed contracts supply the intended behavior. Explicit citations in these new documents do not retroactively resolve the earlier citation finding, and this stage does not edit either completed output set.

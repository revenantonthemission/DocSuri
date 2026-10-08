# U1 Logical Pattern and Failure-Domain Inventory

## Sources

`../nfr-requirements/performance-requirements.md`, `../nfr-requirements/security-requirements.md`, `../nfr-requirements/scalability-requirements.md`, `../nfr-requirements/reliability-requirements.md`, `../nfr-requirements/observability-requirements.md`, `../nfr-requirements/tech-stack-decisions.md`, `../functional-design/functional-spec.md` and `../../../inception/contract-design/contract-summary.md` are the actual upstream artifacts. Confirmed `nfr-design-questions.md` selects the timing/maintenance profile. This inventory applies patterns within approved components/runtimes, not a new deployment topology or duplicate entity ownership.

Recovery/readiness follows `../../../inception/delivery-planning/bolt-plan.md` and `../../../verification/u1-isolated-postgres-bootstrap-plan.md`. Current source declarations and preserved partial work remain qualification inputs, not installed/deployed, CI or operational receipts.

## LC-1 — Responsibilities and Resource Boundaries

| Logical area / existing owner | Patterns | Failure domain / isolation |
|---|---|---|
| Browser submission/recovery — ContentJobApi/JobSubmissionForm | SD-4, C4 attempt registry | Optional initial draft/tracking attempt links; captured input and context guards isolate stale preparation; backend auth remains authoritative |
| Browser tracking/result — JobStatus/SummaryModal/PaperDetailIsland | PD-1/PD-4, RD-5/RD-6, SD-5 | Separate job/connection/read state, current owner/job keys, stable authorized recovery checkpoint; no command capability in result view |
| BFF/controller/query — BffProxy/ContentJobController/ContentJobService | SD-1–SD-3, PD-2, RD-4 | Exact C2 object/bare DocModel and available instant checking; owner/state/known-expiry precedence; configured relay and no command side effects on reads |
| Durable job/result/effect authority — ContentJobService | Functional T1–T8, RD-1–RD-4 | Shared relational lock/fence/owner authority; exact code/data strings and final personalization; immutable T5 binding and one-time T6 expiry; no local-only concurrency defense |
| Existing worker supervisor/child execution — ContentJobWorker | RD-1, CD-1/CD-2 | Independent renewal/control capacity, one invocation grant, child generation cannot publish through stale authority |
| Existing scheduled maintenance seam | RD-2/RD-3, OD-3/OD-4 | Bounded guarded first dispatch/reconciliation/purge; separate scheduling from generation availability; no blind legacy re-enqueue |
| Existing queue and adapters | C6/C8, RD-1/RD-2 | At-least-once receipt; authority markers and compatible consumers prevent duplicate invocation/old-worker mutation |
| Existing diagnostics | OD-1–OD-5 | Safe allowlisted events, freshness/error evidence and bounded failure handling; no sensitive-data/debug payload coupling |

The shared relational database is a durability and resource failure domain. Control-plane reservation is verified against actual connection limits; a logical isolated task is not proof of reserved capacity. API, worker and maintenance failures remain observable separately. Queue visibility, database publication authority and browser presentation state are different mechanisms.

## LC-2 — Implementation Verification and Quality Floor

Implement the selected patterns under the existing stack, then author/run meaningful tests per component under test-after ordering. Preserve ≥80% new-code line coverage, current suites, strict type/lint and relevant contract/integration/browser checks. Use actual commands after reconciling the current package-script inventory; skipped live-dependency tests cannot prove real-store or skeleton behavior. Covers **NFR11.1**.

Validate configuration inequalities, adapters/deadlines, supported payload/resource limits, supervisor isolation, all declared races, scheduler cadence, cleanup drainage and notification readiness before actual operation. Schema/traceability checks alone do not prove these patterns. The real integrated check remains separately human-authorized before the Unit checkpoint.

Use complete-envelope positive/malformed content and timestamp fixtures plus exact Unicode/whitespace/escaping round-trips. Prove required RFC 3339 checker availability and fail its deliberately unavailable variant. Separately test actual capture/binding/publication/store/reads with fresh database time just before, at and after expiry, malformed/legacy metadata and no query side effects; synthetic shape/format probes are not that application acceptance. Coverage must bind all actually changed frontend/backend/controller/assembly/helper/shell/SQL sources rather than excluding difficult authority paths.

**Executed document checks (2026-10-05):** The seven original archive copies were compared byte-identical before revision. The read-only `validate_u1_nfr_design.py` helper in the approved temporary work directory verified all 35 mappings, the same 27 pattern IDs, 15 byte-identical unaffected pattern sections, unchanged traceability/profile bytes, timing inequalities and alert ordering. All 71 explicit Markdown references resolve and each prose output cites all eight inputs. Traceability, explicit eight-input coverage on each of the six prose outputs, required-section checks and whitespace checks passed with no findings.

A separate temporary `verify_u1_timestamp_evidence.py` experiment used jsonschema 4.26.0 with rfc3339-validator 0.1.4 and the unchanged approved C2/local schemas: six UTC/offset/fractional complete envelopes passed, 25 malformed timestamp envelopes across five branch/field paths failed, and deliberately absent checker support failed evidence admission. Without that admission guard, the five missing-checker malformed-field probes falsely passed, reproducing the annotation-only hazard. Eight code/data JSON round-trips retained exact strings and canonical integrity digests. These are synthetic document/format/serialization checks; they neither repair the original helper/application nor prove actual store expiry, races, environment qualification or the real integrated journey. No new JavaScript/TypeScript snippet is present for linter/type-check sensors.

## LC-3 — Infrastructure and Rollout Handoff

Infrastructure Design verifies actual existing API/worker/store/queue/runtime configuration, effective permissions/data protection, heartbeat and scheduler capacity, and compatible reader/worker activation before new-message/UI exposure. A minute-granularity scheduler needs the explicitly qualified bounded two-pass or other valid sub-minute strategy. Production-on-merge still requires compatible gated exposure, tested rollback and safe old-runtime drain/isolation; no atomic multi-runtime deploy is assumed.

Preserve exact readable records through rollback and do not reintroduce an old worker that grants ambiguous generation or writes coarse result references for new-protocol jobs. Proposed operational defaults are not assertions about the deployed environment. Additional services/architecture or changed product/placement limits require a concrete decision rather than a silent substitution.

Preserve partial application source and the original immutable dirty-source baseline. Reconcile current implementation-plan/source-footprint authority and supplemental original-byte capture before the narrow registered migration admission repair. Retain full-script identity/digest, same-connection current authority, locking, transaction/ledger and guarded commit; no raw rejected-SQL or blanket procedural exemption. Qualify concrete artifacts/runtime/launcher and separately authorize exact resources/rules/secret channel/rollback before independently measured protected PostgreSQL realm proof and mutation-capable preflight. Keep authority schema/race tests and the later adapted minimal-purge target distinct; required missing/wrong/expired proof and live-test skips do not pass. Required real-schema acceptance precedes later ordered implementation under the approved recovery handoff.

## Current Upstream Evidence

Current `../functional-design/reviews/review-03.md` independently resolves all five carried Functional Design findings, including draft optionality R-05; initial drafts and authorized known-job tracking may lack a captured attempt without fabricating identity/command authority. Current `../nfr-requirements/reviews/review-02.md` resolves its source-citation R-01 and reports no new architectural finding. These owning reviews supersede the older unresolved carry-forward descriptions without erasing their history; neither proves the partial implementation or completed integrated journey.

Contract Design R-03 remains Accepted risk: the original payload-shape checker lacks active date-time validation. RD-4 now specifies meaningful checker availability and actual application/store timestamp/expiry proof, not a claim that the old helper/runtime is fixed. Actual artifact/realm, deadline/resource/scheduler/notification, compatibility/rollback, coverage and browser acceptance remain separate evidence obligations. No resource/rule application or production operation is granted by this design amendment.

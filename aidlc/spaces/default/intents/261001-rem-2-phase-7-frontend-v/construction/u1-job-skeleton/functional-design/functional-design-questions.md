# Functional Design Questions — U1 Integrated Job Skeleton

## Sources

- [desc] Initial description: "Phase 7 frontend wiring for durable content jobs: wire JobStatus component with SSE, replace AssetViewer presigned redirect with same-origin delivery, route contentJobApi through BFF, mount components in detail page"
- [scope] Workflow-selected scope: `feature`; Standard depth/test strategy; U1 is a `service` Unit with required browser/server integration.
- Approved `../../../inception/units-generation/{unit-of-work,unit-of-work-story-map}.md` assigns U1 the integrated summarize journey and shared backend guarantees for summary and translation.
- Approved requirements, fifteen-component catalogue, ADR-013–ADR-016, and Contract Design C1–C4/C6–C8 govern ownership, errors, exact results, recovery and compatibility. Their paths are `../../../inception/requirements-analysis/requirements.md`, `../../../inception/domain-design/{components,decisions}.md`, and `../../../inception/contract-design/contract-summary.md`.
- Revised stories/refined mockups and the approved delivery plan supply acceptance slices, focus behavior and the real skeleton demonstration. U2 later completes translation UI/reload scenarios; U3 owns asset migration.
- Source observations: `backend/modules/summarization/migrations/002_create_content_jobs.sql`, `src/summarization/adapters/rds_jobs.py` and `adapters/s3_redis_store.py` under that module; `frontend/components/{JobStatus,SummaryModal}.tsx`. Observations establish design seams, not runtime readiness.

## Unit Design Scope

Create new U1-specific design artifacts. Older component-named Construction drafts remain historical inputs, not approved U1 designs; do not overwrite them or equate their folders with the approved Unit DAG.

Define detailed logical entities and validation, named business rules, submission/dispatch/worker/result workflows, recovery/stream/UI state machines, frontend input/state/capability boundaries, and per-AC traceability. Preserve ContentJobService as the single backend owner and ContentJobApi as the distinct client recovery owner. Produce `entities.md`, `rules.md`, `functional-spec.md` and `traceability.json`; include frontend design within the functional specification or a focused supplementary document as appropriate to U1's mixed scope. This stage writes design, not application implementations.

The following are already decided: additive preparedResult v1 envelope on the existing result route; bare DocModel validation; no generation on reads; retained-binding replay versus definite failed-dispatch replacement; fail-safe ambiguous generation without another invocation; pre-submit attempt handle and recovery lookup even without a job ID; native SSE/opaque cursor resolution and two-second fallback; stable-parent rendering containment and conditional focus continuity. Do not re-ask these policy choices.

## Q1. Exact Prepared-Result Persistence

The current durable-job store is relational and already uses transactions for job state/events. The existing artifact cache stores generated bases in object storage, including translation content that can be personalized at serve time; that cache is not the immutable final owner-specific job result. Where should the new exact prepared snapshot be persisted?

- A. **Snapshot in the existing relational database** — Add a separate job-bound prepared-result record alongside durable job/effect records. Store the final allowlisted payload and its immutable identity there. Binding/fence checks and later terminal publication use the same transactional authority. This simplifies crash reconciliation and account-deletion cleanup, at the cost of database storage/transfer for potentially large translation documents. Payload sizes and query behavior must be validated in subsequent NFR work; no silent result-size cutoff is introduced.
- B. **Immutable object-storage snapshot with database binding** — Store the final owner-specific prepared payload in the existing object-storage environment and retain its exact immutable object identity, digest and authorization/expiry binding in the relational database. Commit the binding only after durable payload storage, and publish completion only after the binding is committed. This keeps larger payloads out of the database but adds cross-store failure, orphan cleanup and account-deletion coordination. Do not reuse mutable/shared-base cache paths or expose storage URLs.
- X. Other (please specify)

Recommendation: A for the bounded first slice and a single transactional authority. Both alternatives retain the selected owner/TTL/read-only guarantees; the choice is persistence placement, not a new cloud platform or an exactly-once remote-generation claim. Record the trade-off and required crash/volume tests in the design.

[Answer]: A. Snapshot in the existing relational database

## Q2. Browser Recovery Record Contents

The mandated localStorage namespace remains `idempotency:{paperId}:{taskType}`. The key survives reload, but cannot reconstruct original parameters by itself. ContentJobApi owns immutable captured input and exposes the pre-job attempt/recovery interface from C4. What should its persisted record contain?

- A. **Key plus minimal original-request metadata** — Persist owner, paper/task, schema version, deterministic key, captured serialized input and known job identity when available. Original input is restricted to the existing non-secret identifier/parameter allowlist: paperId, version, targetLang, persona and scope. Never store session credentials, document text, generated results, arbitrary input fields or telemetry contents. Restore only after owner/schema/input/digest checks; quota/corruption failures remain controlled, and intact in-memory originals still support same-session recovery. U2 completes the wider reload UX/test matrix.
- B. **Key and identity only** — Persist owner/paper/task/key and known job identity, with original parameters held only in memory. After reload, an authorized known job may be tracked/read, but resend stays unavailable when the original request is not recoverable. Show the approved missing-original explanation; do not reconstruct by guessing current defaults. This minimizes stored parameters while limiting automatic reload recovery.
- X. Other (please specify)

Recommendation: A because the approved task input is a bounded parameter set, and preserving it enables verifiable unchanged-request recovery across reload. Neither option permits edited-draft recovery, another owner's record, forced key rotation or automatic POST on restore. Functional Design specifies record validation and attempt/context supersession; the saved key remains the exact original derivation rather than a substitute computed from new defaults.

[Answer]: A. Key plus minimal original-request metadata

## Remaining Design Work

- Specify a monotonic publication fence and durable effect-start decision before invoking generation. Reconciliation never issues another generation call once intent is ambiguous; it publishes from an exact durable prepared snapshot or fails safely after revoking expired authority. Pin transaction/cleanup behavior and all declared crash windows for the chosen persistence placement.
- Specify one authoritative dispatch operation and definite-versus-ambiguous send outcomes. Queue message delivery may duplicate; execution may not. Early messages cannot execute before acceptance is settled. Preserve legal lifecycle transitions and the current terminal protections.
- Specify owner-checked query precedence, result TTL initialization once, cursor-to-event lookup, state watermarks, old-job/context suppression and safe telemetry. Reads receive restricted capabilities and cannot use the existing generation-on-cache-miss path.
- Define U1 component interactions and validation for initial summary selection, prepare/submit/recover, status/replay/polling, result dialog and full-page render fallback. Preserve accessibility and focus rules for delivered behavior; no extra product states or actions are invented.
- Numeric lease/heartbeat/visibility tuning and performance/volume evidence belong to the applicable NFR stages. The functional protocol must already make renewal/fencing races explicit; implementation cannot proceed until required tuning is validated. The integrated verification command remains explicitly deferred until U1 supplies a runnable real check for separate approval.

## Historical Functional Design Confirmation

- **Prepared results (Q1: A):** Persist the immutable final owner-specific prepared payload and exact identity in a separate job-bound record in the existing relational database. ContentJobService owns it. A transaction checks current job/owner/fence and commits the exact snapshot binding; later terminal publication rechecks that committed binding and atomically commits state, event and fixed expiry. Reconciliation can publish from an existing durable snapshot without generation. Preserve the existing restriction that public resultRef is not advertised before completion. Repeated writes must match the same committed identity/content, not overwrite a prepared result. Account deletion prevents late resurrection and removes dependent prepared data through the same authoritative lifecycle; expiry denies reads even if physical cleanup has not yet run.
- **Worker authority and ambiguity:** Define durable effect-start intent before the worker invokes the existing pipeline, a monotonic publication fence, renewable server-time ownership, and atomic revocation/reconciliation. No new invocation after ambiguous effect-start; fail safely without releasing the key when no exact snapshot can be recovered. Preserve real outcome mapping, legal transitions and crash/redelivery cases from C7. Numeric lease/heartbeat/visibility tuning remains an explicit NFR-stage prerequisite, not an invented execution SLA.
- **Dispatch and identity:** Define one serialized authoritative dispatch operation per retained submission, distinguish confirmed queue rejection from ambiguous send outcome, and defer early queue messages until acceptance is settled. Only definite failed dispatch before generation may release its key for an explicit unchanged-request replacement. The UI adopts the actual returned job/state and never guesses the cause or restarts an old terminal job.
- **Browser record (Q2: A):** Under `idempotency:{paperId}:{taskType}`, persist a versioned record containing owner, paper/task, deterministic key, exact captured serialized input, original attempt identity and optional known job ID. Allow original input only from the approved paperId/version/targetLang/persona/scope set. Exclude credentials, document text, generated content and arbitrary fields. Treat stored data as untrusted: validate owner, namespace, schema, field allowlist and original digest before restore; never rewrite parameters from current defaults. Preserve memory-only operation with truthful warning on storage failure.
- **Attempt lifecycle:** preparation returns its retained handle before POST; availability lookup exposes the original recovery reference after a lost response without needing jobId. Editing the visible draft does not change the original attempt. A deliberately new attempt supersedes the prior active handle; owner/context/job changes and in-flight work are rechecked at action time. Restore performs no POST and cannot replace a newer active attempt. Missing/corrupt originals disable recovery with a persistent explanation. U1 establishes these interfaces and in-session protections; U2 completes the wider reload UX/test matrix.
- **Exact authorized reads:** Use a restricted service query capability, preserve C2's 401/indistinguishable 404/409/owner-only 410/422/transient 503 handling, and enforce TTL on both reference and content paths. Validate preparedResult v1, task/job consistency and bare DocModel translation content. Preserve final personalization despite later settings changes. Every read outcome has zero generation/enqueue, including unavailable legacy results and read retries.
- **Events and UI:** Specify authorized opaque cursor lookup, real SSE delimiters, per-job sequence/state watermarks and separate history reconciliation. Keep native EventSource, two-second non-overlapping fallback reads, terminal/context cleanup and old-job suppression. Preserve initial summary selection, command-free completed-result presentation, stable-parent containment, safe network failures, meaningful announcements and conditional focus continuity. Include U1 frontend props/state and capability composition in the behavioural specification without complete implementation code.
- **Artifacts and coverage:** Generate new U1 `entities.md`, `rules.md`, `functional-spec.md` and `traceability.json` with authoritative entity/rule YAML, workflows/state machines, derived ER/rule views, and explicit AC-to-business-rule mapping. Cover U1 primary stories and the U1 contributions to spanning stories without asserting later UI/asset or whole-release completion. Preserve single ownership and approved C1–C4/C6–C8 boundaries; old component-named drafts are historical, not current Unit evidence.
- **Verification/handoff:** Validate references, rule/AC coverage, diagrams and transaction/race scenarios, then obtain the required architecture review. Relational snapshot volume/performance and numeric worker timing are tested and tuned in NFR Design; do not introduce a silent result-size cap or weaken approved p95/coverage targets. Application generation remains Code Generation work with its own approved plan. The real integrated verification invocation remains deferred for separate human authorization before the skeleton checkpoint.

Does this all look correct before I generate the U1 functional-design artifacts?

- Looks correct
- Request changes

[Answer]: Looks correct

## Current U1 Design Revalidation

The human has approved the corrected C2 contract and revised Delivery Planning. The current pass revalidates the preserved U1 Functional Design against those inputs; it does not restart application implementation or produce designs for U2/U3. The earlier Q1 relational snapshot and Q2 minimal original-request metadata choices remain decided.

Current declared inputs are `../../../inception/units-generation/unit-of-work.md`, `../../../inception/units-generation/unit-of-work-story-map.md`, `../../../inception/requirements-analysis/requirements.md`, `../../../inception/domain-design/components.md` and `../../../inception/contract-design/contract-summary.md`. The approved `../../../inception/delivery-planning/{bolt-plan,team-allocation,risk-and-sequencing-rationale,external-dependency-map}.md` and `../../../verification/u1-isolated-postgres-bootstrap-plan.md` provide recovery/readiness handoffs, not runtime acceptance.

The existing design defines eleven entity shapes, twenty-five business rules, T1–T8 atomic authority boundaries and workflows for dispatch, worker outcomes, exact reads, original-request recovery and tracking/UI containment. Its map lists 124 acceptance criteria, with five explicit later-Unit deferrals. Those counts describe existing design content, not verified application behavior or whole-story completion. The partial U1 implementation and immutable dirty-source baseline remain preserved.

### Observed Changes and Remaining Design Inconsistency

- **C2 reproducibility:** The approved contract now references `shared/dtos/summarization.schema.json#/$defs/Reproducibility`, requiring exactly string `code` and `data`. The preserved entity model only describes prepared content as validated by C2; WF3/WF5 and the capture/result rules do not spell out that corrected nested object. Revalidation should make exact object preservation, malformed/legacy string handling and complete-envelope checks explicit without changing preparedResult v1, task scope or ownership/expiry/read-only semantics.
- **Unprepared draft relationship:** `SubmissionDraft.attemptId` is optional and WF1 opens a draft before preparation, but the derived ER diagram still makes every draft's IdempotencyKey parent mandatory. The prior review's R-05 identifies this minor mismatch. A draft should reference zero or one captured attempt; an attempt may be referenced by multiple drafts over time. Correcting that logical/derived relationship must not hash, submit or fabricate an idempotency record on mount.
- **Evidence limits:** Contract Design R-03 is Accepted risk from the approved contract: the original schema-validation dependency set lacks an active date-time checker. Its payload-shape passes do not establish malformed-timestamp rejection or runtime TTL correctness. Preserve that disposition and require meaningful application/store expiry evidence; this design pass does not rewrite the contract or repair the application validator.
- **Recovery prerequisites:** The approved delivery plan places current design/plan and narrow migration-admission/source-footprint reconciliation before the qualified real PostgreSQL schema lane and later implementation. Preserve T1–T8 and existing relational/captured-input choices. The isolated authority and later minimal-purge databases, trusted proof, artifact/runtime qualification and concrete resource/rule authorization are pending execution prerequisites, not new domain entities or a claimed environment.

### Proposed Bounded Modification

- Use `entities.md`, `rules.md`, `functional-spec.md` and `traceability.json` as the starting point, preserving their prior versions in the archive.
- Add resolving current input references and the exact C2 code/data object obligation to prepared-content constraints, capture/result rules and worker/read scenarios. Preserve successful strings exactly; malformed/missing/flattened data follows the existing safe protocol/unavailable outcome rather than guessed conversion or regeneration.
- Align the authoritative draft/attempt relationship and derived ER edge with the existing optional attempt reference and pre-preparation workflow. Keep the earlier resolved tracking-context optionality and all prior crash/supersession/legacy-bridge fixes intact.
- Retain all stable entity, rule and acceptance IDs, existing T1–T8 guarantees, legal terminal states, backend guarantees for both tasks, UI responsibility boundaries and five justified later-Unit deferrals. Refresh traceability/reference/diagram checks and obtain the current independent architecture review, carrying all prior finding IDs and actual dispositions.
- Carry the approved recovery/readiness handoffs and accepted timestamp-evidence limitation into verification expectations. Preserve application source, quality targets and separately deferred real integrated command; keep physical implementation, SQL admission and operational application with their owning later work.

## Q3. Existing U1 Functional Design Artifacts

How should we handle the existing U1 design while reconciling the approved C2 correction and optional draft relationship?

- A. **Modify (Recommended)** — Apply the bounded updates above to the preserved design, confirm the consolidated summary, then check the revised artifacts and obtain a fresh independent review.
- B. **Keep** — Retain the existing artifacts as-is and revalidate them against the current contract. The draft relationship finding and current conformance/evidence limitations remain visible for the applicable checkpoint.
- C. **Redo from scratch** — Regenerate U1's design from current approved inputs and recorded decisions, preserving the prior artifacts in the archive.
- X. Other (please specify)

[Answer]: A. Modify (Recommended)

The human replied exactly `Modify`. This selects the bounded design amendment above. The current summary below must be confirmed before revising the design outputs or requesting their independent review.

## Consolidated Summary Confirmation

- **Scope and outputs:** Modify the preserved U1 `entities.md`, `rules.md`, `functional-spec.md` and `traceability.json`, archiving their prior versions first. Add exact resolving current input references. Retain stable IDs, eleven logical shapes, twenty-five business rules and the existing acceptance allocation; design mappings do not claim application or whole-story completion.
- **Exact prepared content:** Keep Q1's separate immutable final-payload record in the existing relational authority, owned by ContentJobService. Explicitly require summary reproducibility to be the existing C2/shared object with required string `code` and `data`, no extra object fields and exact string preservation. Keep preparedResult v1 and bare DocModel translation, final prepared personalization, owner-first error precedence, fixed expiry and zero generation/enqueue on every read/retry. Missing, malformed or flattened reproducibility follows the existing safe capture/protocol or read-unavailable outcome; no coercion, guessed defaults or regeneration.
- **Atomic authority and worker behavior:** Keep T1–T8, separate T5 preparation/T6 terminal publication, current owner/fence/server-time rechecks, one durable whole-pipeline invocation grant, conservative ambiguous-effect reconciliation, truthful outcome mapping and deletion without resurrection. Retained replay and only proven pre-effect non-dispatch replacement remain distinct; no terminal restart or duplicate send. Preserve the prior first-dispatch recovery, guarded async preparation and legacy-authority bridge corrections.
- **Optional draft relationship:** State that each SubmissionDraft references zero or one captured attempt, while one attempt may be referenced by multiple drafts over time. Derive the corresponding optional-parent ER edge. An initial editable draft is valid before preparation and does not hash, submit or fabricate an idempotency record on mount. Keep the already optional TrackingContext attempt link and read-only tracking when originals are unavailable.
- **Browser recovery and UI:** Keep Q2's versioned minimal original-request metadata in the mandated namespace, with only owner/paper/task/key/attempt identity, captured allowlisted input and optional actual job ID persisted. Validate schema/owner/namespace/allowlist/digest before restore; no credentials, documents/results or arbitrary fields. Preserve handle-before-POST, captured A versus edited draft B, preparation supersession before async work, guarded publication, in-flight exclusion and no restore POST. Keep opaque stream cursors/state watermarks, two-second nonoverlapping fallback, stable-parent containment, query-only results and accessible conditional focus/announcements.
- **Acceptance and checks:** Keep U1's summarize end-to-end slice and shared backend guarantees for both tasks. Retain the four translation-UI deferrals AC1.2.1–AC1.2.4 and U3 asset-timing deferral AC8.2.2; do not transfer unfinished backend work. Recheck YAML shapes/relationships, actual diagram cardinality parity, all 124 acceptance rows and rule targets, current references and corrected complete-envelope scenarios. Obtain a fresh independent architecture review carrying prior IDs and actual dispositions; the reviewer, not this proposal, determines whether the draft relationship finding is resolved.
- **Evidence limits and implementation handoff:** Carry Contract Design R-03 as Accepted risk: the original payload-shape checker does not establish malformed-timestamp rejection or runtime TTL. Require actual application/store expiry evidence. Link the approved delivery recovery order and isolated PostgreSQL bootstrap plan, leaving migration admission, supplemental source footprint/current implementation authority, artifact/runtime qualification and measured realm/resource authorization as execution prerequisites. Preserve partial application source and the immutable baseline; this stage produces design only. Keep test-after ordering, at least 80% new-code coverage, current suites and accepted performance/accessibility targets. The real integrated verification command remains separately deferred for human authorization before the skeleton checkpoint.

Does this all look correct before I generate the artifact?

- Looks correct
- Request changes

[Answer]: Looks correct

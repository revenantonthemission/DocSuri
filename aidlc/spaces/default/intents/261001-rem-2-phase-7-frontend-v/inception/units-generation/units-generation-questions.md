# Units Generation Questions — Phase 7 Frontend Wiring

**Gate:** Architecture Reviewer (advisory)

## Sources

- [desc] Initial description: "Phase 7 frontend wiring for durable content jobs: wire JobStatus component with SSE, replace AssetViewer presigned redirect with same-origin delivery, route contentJobApi through BFF, mount components in detail page"
- [scope] Workflow-selected scope: `feature`.
- [memory:M1] `aidlc/spaces/default/memory/team.md#Walking Skeleton`: "Stance: ON — Build a thin end-to-end slice first"
- [memory:M2] `aidlc/spaces/default/memory/team.md#Testing Posture`: "Methodology: test-after, Ordering: Test-last per component"
- [memory:M3] `aidlc/spaces/default/memory/team.md#Deployment`: "Continuous deployment to production on merge"
- [memory:M4] `aidlc/spaces/default/memory/project.md#Mandated`: "ALWAYS route all content-job API calls through `/bff/api/content-jobs/*` (SEC-8)"
- [memory:M5] `aidlc/spaces/default/memory/project.md#Mandated`: "ALWAYS generate idempotency keys as SHA-256 hash"
- [memory:M6] `aidlc/spaces/default/memory/project.md#Mandated`: "ALWAYS wrap JobStatus in React Error Boundary"
- [memory:M7] `aidlc/spaces/default/memory/project.md#Mandated`: "ALWAYS use same-origin asset delivery via `/bff/api/papers/{paperId}/assets/{assetId}`"
- [memory:M8] `aidlc/spaces/default/memory/project.md#Mandated`: "ALWAYS integrate Sentry for client-side error tracking"
- [memory:M9] `aidlc/spaces/default/memory/project.md#Mandated`: "ALWAYS conduct security review mid-implementation (Week 2)"

---

## Questions for Units Generation

### 1. Unit Boundary Strategy
**Question:** How should the 5 domain components be grouped into deployable units?

- A. **Fine-grained (5 units)** — Each component is its own unit: ContentJobApi, IdempotencyService, JobStatus, AssetViewer, ErrorBoundary (+ ErrorBoundaryFallback + ZoomPanControls as part of AssetViewer)
- B. **Coarse-grained (2 units)** — API layer (ContentJobApi + IdempotencyService) + UI layer (JobStatus + AssetViewer + ErrorBoundary)
- C. **Three units (Feature-based)** — API (ContentJobApi + IdempotencyService), UI Core (JobStatus + ErrorBoundary), Assets (AssetViewer + ZoomPanControls)
- D. **Four units** — API (ContentJobApi + IdempotencyService), JobStatus (with ErrorBoundary), AssetViewer (with ZoomPanControls), Integration (PaperDetailIsland + SummaryModal + DocModelViewer)
- X. Other (please specify)

### 2. Unit Granularity
**Question:** What level of granularity is appropriate for Phase 7?

- A. **Fine-grained** — Each component is independently deployable (5+ units)
- B. **Medium** — 3-4 units grouped by feature/domain
- C. **Coarse** — 2 units (API + UI)
- X. Other (please specify)

### 3. Walking Skeleton — First Unit
**Question:** Which unit should be the walking skeleton (first implemented, end-to-end verified)?

- A. **API Unit** — ContentJobApi + IdempotencyService (BFF routing, job submission, idempotency)
- B. **JobStatus Unit** — JobStatus + ErrorBoundary + ContentJobApi (SSE progress, polling fallback)
- C. **Full Skeleton Unit** — All components integrated (ContentJobApi + IdempotencyService + JobStatus + ErrorBoundary + AssetViewer)
- X. Other (please specify)

### 4. Unit Kinds
**Question:** What kind is each unit?

| Unit | Kind Options |
|------|--------------|
| API Unit (ContentJobApi + IdempotencyService) | service / library |
| JobStatus Unit (JobStatus + ErrorBoundary) | ui / service |
| AssetViewer Unit (AssetViewer + ZoomPanControls) | ui / library |
| Integration Unit (PaperDetailIsland + SummaryModal + DocModelViewer) | ui / packaging |

- A. **API: library, JobStatus: ui, AssetViewer: ui, Integration: ui**
- B. **API: service, JobStatus: ui, AssetViewer: library, Integration: packaging**
- C. **API: library, JobStatus: ui, AssetViewer: library, Integration: ui**
- X. Other (please specify)

### 5. Dependency Ordering
**Question:** What dependency ordering constraints apply?

- A. **Strict topological** — No parallel development; strict DAG order
- B. **Parallel where possible** — Independent units can be developed in parallel
- C. **Walking skeleton first, then parallel** — First unit sequential, rest parallel
- X. Other (please specify)

### 6. Integration Contracts
**Question:** What are the key integration contracts between units?

- A. **ContentJobApi → JobStatus** — subscribeJobEvents(jobId, onEvent, lastEventId?) returns unsubscribe
- B. **ContentJobApi → IdempotencyService** — generateKey(userId, paperId, task, params) returns key
- C. **AssetViewer → BFF** — `<img src="/bff/api/papers/{paperId}/assets/{assetId}" />`
- D. **JobStatus → ContentJobApi** — submitJob(request) returns { jobId, state }
- E. **All of the above**
- X. Other (please specify)

### 7. Deployment Model
**Question:** What deployment model for Phase 7 units?

- A. **Monolithic deploy** — All units deployed together (single Next.js app)
- B. **Independent deploy** — Each unit independently deployable
- C. **Hybrid** — API units as library, UI units deployed together
- X. Other (please specify)

---

## Confirmation

**Please respond with your choices (A/B/C/D/X) for questions 1-7.**

[Answer]:
1. A
2. A
3. C
4. B
5. B
6. E
7. A

---

## Historical Summary Confirmation

**Summary of your choices:**

1. **Unit Boundary Strategy**: A — Fine-grained (5 units): ContentJobApi, IdempotencyService, JobStatus, AssetViewer, ErrorBoundary
2. **Unit Granularity**: A — Fine-grained (5+ units, each component independently deployable)
3. **Walking Skeleton**: C — Full Skeleton Unit (All components integrated end-to-end)
4. **Unit Kinds**: B — API: service, JobStatus: ui, AssetViewer: library, Integration: packaging
5. **Dependency Ordering**: B — Parallel where possible (independent units developed in parallel)
6. **Integration Contracts**: E — All of the above (ContentJobApi→JobStatus, ContentJobApi→IdempotencyService, AssetViewer→BFF, JobStatus→ContentJobApi)
7. **Deployment Model**: A — Monolithic deploy (All units deployed together as single Next.js app)

**Confirm** — Does this all look correct before I generate the unit artifacts?

- A. **Looks correct** — Generate the unit artifacts from these answers
- B. **Request changes** — Revise one or more answers before generation
- X. Other (please specify)

[Answer]: Looks correct

## Current Baseline and Reconciliation

The historical answers above predate the approved twelve-component catalogue and ADR-013 in `../domain-design/`. They are retained as history, not current generation authority. No unit definitions, dependency catalogue, story map, or traceability file exists in this stage yet.

The former choices conflict: one unit per component cannot itself deliver the confirmed integrated skeleton; an API client is not a separately deployed service; and the selected ContentJobApi subscription contract conflicts with JobStatus owning native EventSource. The current catalogue and approved stories supersede these obsolete interface descriptions.

Retain the selected single Next.js deployment. Unit boundaries represent testable delivery increments within that application, not new independently deployed processes. Preserve summarize and translate scope, pre-job recovery ownership in JobSubmissionForm, and read-only SummaryModal. Contract Design must settle BFF streaming/cursor and authorized resultRef-read prerequisites before implementation.

### Q8. Delivery Unit Boundaries

How should the approved components be grouped while keeping the first resolved DAG unit independently runnable as submit → SSE progress → COMPLETED → result?

- A. **Three capability increments** — U1 integrated job skeleton; U2 remaining job capabilities and resilience; U3 secure asset viewing. U1 includes real submit/BFF/idempotency/tracking/result integration and the containment, authorization, accessibility, and fallback needed for that slice. U2 completes remaining translation/recovery/replay/diagnostic cases and release evidence without being needed for the U1 demo. U3 delivers AssetViewer, ZoomPanControls, and DocModelViewer integration with secure BFF asset delivery. U2 and U3 depend on U1. Shared source edits need explicit responsibility and serialization; independent topology is not permission to edit the same files concurrently. Smaller increments improve checkpoint feedback, at the cost of carefully specified story/acceptance splits.
- B. **Two cohesive feature units** — U1 complete durable-job workflow, including all required recovery, translation, diagnostics, and result reading; U2 secure asset viewing. U2 depends on U1's shared integration. This reduces overlapping job-component work but makes the first unit materially larger than a thin skeleton, so the decomposition must explicitly reconcile that trade-off with the affirmed smallest-slice checkpoint before plan approval.
- X. Other (please specify)

Recommendation: A. Keep the established shared deployment and define narrow acceptance slices instead of equating each logical component with a unit. Unit kinds and exact story allocation will be presented with the decomposition plan; the mixed server/browser skeleton must retain its server-side design obligations. Remaining economic sequencing belongs to Delivery Planning, and current serial Construction execution is not changed by identifying topology-level independence.

[Answer]: A. Three capability increments

## Decomposition Plan

All units extend the same Next.js deployment. `service` below means work in the deployed executable, including server/browser integration; it does not create a microservice. Component entity owners from Domain Design remain unchanged. Each unit is a delivery increment with an explicit scope of edits, not an additional owner of shared component state.

| Unit ID | Directory | Kind | Deliverable | Direct dependencies |
|---|---|---|---|---|
| U1 | u1-job-skeleton | service | Working summarize submission through BFF, deterministic identity, live status, completed authorized result, and the containment/accessibility/fallback needed to operate that slice | None |
| U2 | u2-job-resilience | ui | Translation and remaining job/recovery/replay/result/diagnostic acceptance cases, extending U1's established frontend components | U1 |
| U3 | u3-secure-assets | service | Secure server-side asset proxy integration and browser asset viewing, including document composition and accessible zoom/pan/reset | U1 |

### Acceptance Boundaries

- **U1:** Establish PaperDetailIsland, JobSubmissionForm, ContentJobApi, IdempotencyService, JobStatus, SummaryModal, ErrorBoundary, ErrorBoundaryFallback, and the job-related BffProxy integration. Demonstrate the real summarize → SSE → COMPLETED → authorized readable result path, including initial parameter choice and read-only result opening. Include two-second fallback, terminal/context cleanup, cookie relay and trusted-identity boundaries, rendering containment, meaningful announcements/focus, scrubbed error reporting, and tests for everything delivered. Implement the in-session uncertain-submit recovery handoff from ADR-013 so a lost response has a safe owner before a job ID exists. No later unit is needed to execute the skeleton. Detailed replay/recreated-connection and reload-reconstruction cases are completed in U2, but the verified contract must already be known before U1 implementation.
- **U2:** Complete translate submission, reload recovery/storage-failure cases, replay deduplication and recreated-connection recovery, expanded result error/copy states, and remaining job telemetry/performance/accessibility acceptance. Preserve the existing in-session pre-job recovery boundary; extend its reload and unavailable-original cases rather than invent another owner. No security, accessibility, required polling, or tests for U1-delivered behavior are deferred to this unit. The story map must distinguish U1 contributions from U2's completion of spanning stories; neither a partial mapping nor a passing skeleton asserts full story/release completion.
- **U3:** Deliver AssetViewer, ZoomPanControls, DocModelViewer integration and asset-specific BffProxy changes, retaining server authorization/license recheck and private cache policy. Cover image load failures, existing text/table equivalents, minimap, keyboard zoom/pan/reset, context cleanup, decode timing and applicable accessibility tests. Authorized result asset-ID copy remains SummaryModal behavior in U2, not a new AssetViewer result-reading responsibility.
- **Shared-source coordination:** U1 establishes job API/proxy and parent composition. U2 extends job behaviors; U3 extends only asset proxy/document composition at the shared seams. Their lack of a capability dependency on each other does not authorize simultaneous writes to shared files. Preserve the selected serial Construction execution; Delivery Planning defines any later coordination and economic sequencing.
- **Prerequisites and checkpoints:** Contract Design verifies BFF streaming/cursor transport and authorized resultRef-to-content mapping before building U1. A demonstrated incompatible backend contract is escalated, not treated as ready. The first resolved DAG unit is U1; Delivery Planning specifies its demo and Construction later obtains an actual human-approved verification command and skeleton checkpoint. Delivery Planning retains the Week 2 security review obligation. Every unit carries test-after ordering and ≥80% new-code coverage plus the applicable existing checks.
- **Completeness:** Generate the four declared unit artifacts with all 26 active stories mapped at acceptance-slice depth, US4.3 explicitly excluded, and cross-cutting obligations assigned to every affected unit. Independent verification remains required; no current runtime or test success is claimed.

### Q9. Decomposition Plan Approval

Approve the three-unit boundaries, kinds, shared deployment and dependency structure above?

- A. **Approve Plan** — Use this decomposition for the unit artifacts, subject to the consolidated-summary confirmation.
- B. **Revise Plan** — Change the boundaries, kinds, or acceptance allocation before generation.
- X. Other (please specify)

[Answer]: A. Approve Plan

## Previous Approved Summary

- **Boundaries:** Three capability increments, using the approved twelve-component catalogue and ADR-013. Component entity ownership stays with its declared owner; delivery increments do not introduce duplicate owners.
- **U1 — `u1-job-skeleton`, `service`:** Independently runnable summarize → BFF → SSE progress → COMPLETED → authorized readable result. Include initial selection, deterministic identity, read-only result opening, two-second fallback, terminal/context cleanup, trusted identity and cookie relay, containment, accessible feedback/focus, scrubbed error reporting, and tests for the delivered slice. JobSubmissionForm owns in-session recovery before a job ID is known, using ContentJobApi's immutable original request and handing the recovered job to PaperDetailIsland before JobStatus mounts.
- **U2 — `u2-job-resilience`, `ui`:** Complete translation, reload/storage recovery, replay/recreated-connection cases, expanded result errors and authorized asset-ID copy, and remaining job diagnostics/performance/accessibility acceptance. U1's delivered security, accessibility, fallback, and tests are not deferred here.
- **U3 — `u3-secure-assets`, `service`:** AssetViewer, ZoomPanControls, DocModelViewer integration, and asset-specific BFF changes, including server authorization/license checks, private cache policy, image failures, existing text/table equivalents, minimap, keyboard navigation, context cleanup, and decode timing.
- **Dependencies and deployment:** U1 has no Unit dependency; U2 and U3 each depend on U1. All extend the same Next.js deployment. The service kind preserves server-side design obligations, not independent deployment. Retain serial Construction execution and explicitly coordinate shared proxy/parent files. Delivery Planning owns economic sequencing.
- **Prerequisites and verification:** Contract Design verifies streaming/cursor behavior and authorized resultRef resolution before U1 implementation; incompatible contracts require escalation. Delivery Planning retains the skeleton demo and Week 2 security review obligations. Construction requires the actual human-authorized verification command and skeleton checkpoint. Apply test-after ordering, ≥80% new-code coverage, and applicable existing checks per unit.
- **Outputs:** Generate unit-of-work.md, unit-of-work-dependency.md, unit-of-work-story-map.md, and traceability.json. Map all 26 active stories, distinguish partial acceptance contributions from story completion, assign cross-cutting obligations to affected units, and retain US4.3 as explicitly excluded.

Does this all look correct before I generate the unit artifacts?

- Looks correct
- Request changes

**Previous confirmation:** Looks correct

## Amended Decomposition Plan

Source authority: the approved fifteen-component Domain Design (ADR-014–ADR-016), amended requirements FR2.5/FR3.5 and the 28 active stories. Preserve the three selected increments and their stable IDs/directories. Earlier statements that all work is inside Next.js are superseded only by the explicitly authorized changes to the existing backend API/worker and their persistence adapters.

| Unit ID | Directory | Kind | Amended scope | Direct dependencies | Relative complexity |
|---|---|---|---|---|---|
| U1 | u1-job-skeleton | service | Integrated summarize journey plus shared backend controller/service/worker remediation, exact prepared results, truthful completion and protected read-only delivery | None | XL |
| U2 | u2-job-resilience | ui | Translation UI and remaining frontend recovery/replay/result/diagnostic cases, using U1's remediated shared backend contract | U1 | L |
| U3 | u3-secure-assets | service | Secure asset proxy/document integration and accessible viewer controls | U1 | M |

U1's larger relative size reflects real backend result persistence, outcome handling and effect-reconciliation work, not a new time commitment. It remains the narrow summarize end-to-end checkpoint; foundational backend behavior must support both approved task types so U2 does not conceal a second backend implementation. If detailed contract design demonstrates the slice cannot be delivered safely within this decomposition, surface that concrete gap before implementation rather than weaken the skeleton or quietly create another unit.

### Backend and Story Allocation

- **U1 owns backend remediation:** ContentJobController, ContentJobService and ContentJobWorker changes, including their required persistence/queue integration. ContentJobService remains the sole owner of durable job/binding/effect/prepared-result entities. Include real SSE delimiter correctness, result binding before completion, actual outcome mapping, all declared crash/redelivery windows, exact prepared personalization, owner/TTL-protected reads, legacy-reference failure and zero generation/enqueue on reads.
- **US2.6 and US3.4:** Assign primary ownership and backend acceptance to U1, including summary and translation fixtures at the service/worker boundary. U2 supplies translation UI integration and wider frontend state coverage; do not claim U1's tests prove later UI behavior. U1's delivered summarize result must already meet owner-checked 401/404/410, read-only and exact-identity guarantees; U2 is not a prerequisite for secure skeleton reads.
- **Recovery:** U1 verifies retained-binding replay, failed-dispatch key release/replacement and executed terminal failure through the actual backend, together with pre-job handoff and old-job response suppression in its delivered UI. U2 adds reload/storage/recreated-connection coverage. Old terminal jobs never restart; unknown recovery cause gets neutral feedback. U1-delivered protections and tests are never deferred to U2.
- **U2 remains ui:** Its scope is frontend adaptation and verification against the shared backend guarantees supplied by U1, not new controller/service/worker capabilities. A demonstrated new backend requirement needs explicit allocation and kind reassessment before work begins.
- **U3 remains bounded asset work:** Asset-specific BFF handling and document/viewer integration preserve the existing authorized asset service. U3 does not own job-result persistence or generation. Shared proxy/parent file edits remain serialized and regression-tested under the recorded serial Construction setting.

### Existing Runtime Boundaries and Delivery Handoff

The frontend and BFF remain in the existing Next.js deployment. U1 also changes the existing backend API and worker runtimes; these are coordinated changes to existing deployments, not a proposal to embed Python workers in Next.js or create new services. The worker's existing queue and persistence configuration remain dependencies. Contract Design pins cross-version compatibility and result-schema/persistence transitions; Delivery Planning and deployment stages own safe rollout/exposure, verification and rollback under the recorded production-on-merge practice. Do not assume multiple runtimes deploy atomically.

The Unit DAG remains U2 → U1 and U3 → U1. U1 is the first resolved DAG unit and has enough real implementation for submit → SSE progress → COMPLETED → exact readable result. No implementation order between U2 and U3 or economic critical path is selected here. All 28 active stories and excluded US4.3 must be mapped, with explicit cross-unit acceptance contributions and combined release evidence.

### Q10. Amended Decomposition Plan Approval

Approve the existing three-unit structure with backend result remediation and US2.6/US3.4 assigned to U1, the revised relative size, and the explicit existing-runtime deployment boundaries?

- A. **Approve Plan** — Use this amended decomposition, then confirm the consolidated summary before regenerating unit documents.
- B. **Revise Plan** — Adjust allocation, kinds or boundaries before generation.
- X. Other (please specify)

[Answer]: A. Approve Plan

## Consolidated Summary Confirmation

- **Structure:** Preserve U1/u1-job-skeleton (service), U2/u2-job-resilience (ui), and U3/u3-secure-assets (service). U1 is the sole root; U2 and U3 each depend on U1. Preserve serial Construction and shared-file coordination. Economic sequencing remains Delivery Planning work.
- **U1 scope and size:** XL relative complexity for the real summarize → BFF → SSE → COMPLETED → exact authorized result slice, including the existing frontend boundaries plus ContentJobController, ContentJobService, ContentJobWorker and their required persistence/queue integration. This is a qualitative estimate, not a time commitment. No later unit is required for the skeleton's secure, accessible and tested delivered behavior.
- **Backend acceptance:** U1 owns US2.6 and US3.4 backend guarantees for summary and translation fixtures: exact durable prepared content before completion, truthful outcomes, effect reconciliation across the declared crash/redelivery windows, prepared personalization, owner/TTL checks and required 401/404/owner-only 410 outcomes, controlled legacy references and zero generation/enqueue on reads. Detailed mechanisms require Contract/Functional Design and actual tests.
- **Recovery:** U1 includes retained-binding replay, failed-dispatch key-release replacement and retained executed-terminal failure, plus immutable request recovery before a job ID exists, actual identity/state handoff and old-job response suppression. U2 extends reload/storage and recreated-connection cases. Unknown recovery cause is not presented as proven dispatch failure; an old terminal job never restarts.
- **U2 scope and size:** L frontend increment completing translation UI, remaining recovery/replay/result/copy states, diagnostics, accessibility and performance coverage against U1's backend contracts. It owns no hidden new backend capability; any demonstrated additional backend need requires explicit allocation/kind reassessment.
- **U3 scope and size:** M asset integration increment delivering authorized same-origin viewing, asset-specific BFF handling, document composition and accessible viewer controls. It consumes shared authentication/proxy conventions and does not own job-result storage or generation.
- **Deployment boundaries:** Frontend/BFF remain in Next.js. U1 also changes existing backend API and worker runtimes; no new service/deployment architecture is introduced and rollout is not assumed atomic. Contract Design pins compatibility/persistence transitions; Delivery Planning and deployment stages define rollout/exposure, verification and rollback under the existing production-on-merge practice.
- **Coverage and quality:** Map all 28 active stories plus excluded US4.3, distinguish unit contributions from whole-story completion, and assign combined release evidence explicitly. Preserve the full walking-skeleton checkpoint, human-authorized verification command, security review, test-after ordering, ≥80% new-code coverage, current-suite checks, and approved performance/accessibility obligations.
- **Outputs:** Modify unit-of-work.md, unit-of-work-dependency.md, unit-of-work-story-map.md and traceability.json using the approved fifteen-component catalogue and ADR-014–ADR-016, then independently validate and review the revision.

Does this all look correct before I generate the revised unit artifacts?

- Looks correct
- Request changes

[Answer]: Looks correct

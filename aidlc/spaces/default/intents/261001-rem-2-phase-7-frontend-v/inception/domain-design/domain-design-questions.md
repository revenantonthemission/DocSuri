# Domain Design Questions — Phase 7 Frontend Wiring

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
- [requirements] `../requirements-analysis/requirements.md`: approved recovered baseline, including FR3.4 and FR5.5.
- [stories] `../user-stories/stories.md`: approved same-key recovery, result-read separation, BFF streaming prerequisites, observability, performance, and accessible asset interactions.
- [design] `../refined-mockups/mockups.md` and `interaction-spec.md`: approved UI states; the summary-level selection disposition remains an accepted review risk to make explicit in this design.

---

## Questions for Domain Design

### 1. Component Boundaries — Core Components
**Question:** How should the frontend wiring logic be decomposed into components?

- A. **Single Component: ContentJobWiring** — One component owning all wiring logic (BFF routing, SSE, idempotency, AssetViewer migration, Error Boundary)
- B. **Two Components: ContentJobApi + JobStatus** — Split API layer (BFF routing, idempotency) from UI layer (JobStatus SSE, Error Boundary, retry)
- C. **Four Components: ContentJobApi, JobStatus, AssetViewer, ErrorBoundary** — Separate each major capability
- D. **Five Components: ContentJobApi, JobStatus, AssetViewer, IdempotencyService, ErrorBoundary** — Extract idempotency as separate service
- X. Other (please specify)

### 2. Component Boundaries — Idempotency Key Management
**Question:** Where should idempotency key generation and storage logic live?

- A. **In ContentJobApi** — Part of the API layer, close to where keys are used
- B. **In IdempotencyService** — Separate reusable service, testable in isolation
- C. **In JobStatus** — Close to retry UI where key is retrieved
- D. **In a shared hook (useIdempotency)** — React hook usable by any component
- X. Other (please specify)

### 3. Component Boundaries — AssetViewer Migration
**Question:** Should AssetViewer migration be a separate component or part of an existing component?

- A. **Separate AssetViewer Component** — Owns same-origin delivery logic, zoom/pan, loading/error states
- B. **Part of DocModelViewer** — AssetViewer is only used within DocModelViewer
- C. **Part of a new AssetDelivery Component** — Handles all asset-related concerns (delivery, auth, caching)
- X. Other (please specify)

### 4. Component Boundaries — Error Boundary
**Question:** Should the Error Boundary be a standalone component or part of JobStatus?

- A. **Standalone ErrorBoundary Component** — Reusable, wraps JobStatus and potentially other SSE components
- B. **Part of JobStatus** — Tightly coupled, simpler
- C. **Higher-order Component (HOC)** — Wraps any SSE-consuming component
- X. Other (please specify)

### 5. Entity Ownership — Idempotency Key
**Question:** Which component owns the IdempotencyKey entity?

- A. **ContentJobApi** — Generates and stores keys, provides to callers
- B. **IdempotencyService** — Single source of truth for all idempotency logic
- C. **JobStatus** — Retrieves stored key for retry
- X. Other (please specify)

### 6. Entity Ownership — JobStatus State
**Question:** Which component owns the JobState entity (real-time job progress)?

- A. **JobStatus Component** — Consumes SSE, maintains local state, owns UI representation
- B. **ContentJobApi** — Manages SSE connection, exposes state via hook
- C. **JobStateStore (new)** — Centralized state management (e.g., Zustand, React Context)
- X. Other (please specify)

### 7. Component Interaction — JobStatus SSE Connection
**Question:** How should JobStatus establish and manage the SSE connection?

- A. **Direct EventSource in JobStatus** — Component manages its own EventSource lifecycle
- B. **Via useJobEvents Hook** — Custom hook encapsulates SSE logic, returns state/connection status
- C. **Via ContentJobApi** — API layer provides subscribeJobEvents function
- X. Other (please specify)

### 8. Component Interaction — AssetViewer Delivery
**Question:** How should AssetViewer fetch assets via same-origin delivery?

- A. **Direct img src** — `<img src="/bff/api/papers/{paperId}/assets/{assetId}" />` (simplest)
- B. **Via AssetDelivery Component** — Wrapper component handles auth, loading, error states
- C. **Via Hook (useAssetDelivery)** — Hook returns src, loading, error state
- X. Other (please specify)

### 9. External Dependencies
**Question:** Which external dependencies do the new components have?

- A. **BFF Proxy** — All API calls through `/bff/api/content-jobs/*` and `/bff/api/papers/*/assets/*`
- B. **Sentry** — Error tracking integration (per project.md Mandated)
- C. **SWR** — Polling fallback and server state management
- D. **crypto.subtle** — SHA-256 hashing for idempotency keys
- E. **All of the above**
- X. Other (please specify)

### 10. Integration with Existing Components
**Question:** How do new components integrate with existing frontend components?

- A. **PaperDetailIsland** — Mounts JobStatus, uses SummaryModal for job submission
- B. **DocModelViewer** — Uses AssetViewer for figures/tables
- C. **SummaryModal** — Triggers job submission, passes jobId to JobStatus
- D. **All of the above**
- X. Other (please specify)

---

## Confirmation

**Please respond with your choices (A/B/C/D/X) for questions 1-10.**

[Answer]:
1. D
2. A
3. A
4. A
5. A
6. A
7. A
8. A
9. E
10. D

---

## Previous Attempt Summary

**Summary of your choices:**

1. **Core Components**: D — Five Components (ContentJobApi, JobStatus, AssetViewer, IdempotencyService, ErrorBoundary) — Extract idempotency as separate service
2. **Idempotency Key Management**: A — In ContentJobApi (part of API layer, close to where keys are used)
3. **AssetViewer Migration**: A — Separate AssetViewer Component (owns same-origin delivery, zoom/pan, loading/error states)
5. **Idempotency Key Entity**: A — ContentJobApi (generates and stores keys, provides to callers)
6. **JobStatus State Entity**: A — JobStatus Component (consumes SSE, maintains local state, owns UI representation)
7. **JobStatus SSE Connection**: A — Direct EventSource in JobStatus (component manages its own EventSource lifecycle)
8. **AssetViewer Delivery**: A — Direct img src (`<img src="/bff/api/papers/{paperId}/assets/{assetId}" />` — simplest)
9. **External Dependencies**: E — All of the above (BFF Proxy, Sentry, SWR, crypto.subtle)
10. **Integration with Existing**: D — All of the above (PaperDetailIsland, DocModelViewer, SummaryModal)

**Confirm** — Does this all look correct before I generate the domain design artifacts?

- A. **Looks correct** — Generate the artifacts from these answers
- B. **Request changes** — Revise one or more answers before generation
- X. Other (please specify)

**Previous confirmation:** Looks correct

## Recovery Design Plan

- Modify the catalogue, ADRs, and traceability while preserving useful existing component and decision identifiers.
- Preserve Q2/Q5: ContentJobApi is the sole owner of idempotency/recovery identity and its storage lifecycle. Retain IdempotencyService as a stateless hashing helper with no duplicate IdempotencyKey ownership; its asynchronous Web Crypto operation is not a synchronous call or a separately deployed service.
- Preserve JobStatus ownership of its client-side job projection and connection lifecycle, including native EventSource and fixed two-second SWR fallback. Keep it distinct from the backend's authoritative job state and the stable parent context needed after a rendering failure.
- Preserve separate AssetViewer and ErrorBoundary responsibilities, direct same-origin image delivery, accessible zoom/pan, and existing PaperDetailIsland/DocModelViewer integration. Boundaries and callbacks must form an acyclic graph with symmetric caller/callee listings.
- Model the local BFF proxy as code that requires integration work, with the backend gateway as an external dependency. Keep Sentry and browser/library facilities as external dependencies rather than undeclared components. Do not claim BFF streaming or resultRef consumption already works.
- Resolve every entity reference to exactly one declared owner, or describe external paper/job identifiers as external context rather than invent an undeclared Paper entity.
- Cover all current story IDs, including US8.1/US8.2, and mark US4.3 N/A with its explicit exclusion rather than assign an implementation component.
- Preserve ADR history by explaining superseded or clarified decisions; catalogue ownership and human-readable diagrams must agree. Deployment grouping belongs to Units Generation; detailed types/validation and wire contracts belong to later stages.

### Q11. Separate initial submission from completed-result viewing

The approved UI must preserve the existing initial summary-level choice without submitting work when a completed result is opened. SummaryModal currently requests work on mount and when its persona toggle changes. Refined Mockups R-01 accepted this as a risk; Domain Design needs a clear ownership boundary for that split.

- A. **Separate submission and result components** — A submission component owns initial parameter selection and explicit submission; SummaryModal becomes the completed-result reading surface, showing the submitted level as non-editable metadata. PaperDetailIsland coordinates both. This adds a small boundary but makes read-only behavior independently enforceable and testable. The shared visual dialog shell can still be reused; no new backend endpoint is implied.
- B. **One component with explicit modes** — Keep SummaryModal for both initial submission and result reading, with mutually exclusive modes and mode-specific callbacks. The initial mode permits parameter selection/submission; result mode exposes only read actions and submitted-level metadata. This reduces component count but needs stronger tests to prevent cross-mode submission effects.
- X. Other (please specify)

Both alternatives are reversible frontend decompositions. Neither adds Retry with changes or lets completed-result controls initiate work. Recommendation: A for the clearer command/read boundary, especially given the current mount-triggered requests.

[Answer]: A. Separate submission and result components

## Requested Changes Feedback

[Answer]: Resolve R-01

Proposed correction: JobSubmissionForm owns inline recovery of an uncertain submission before a backend job ID is known. ContentJobApi retains the immutable original owner-bound request identity before sending and exposes its recovery availability to the form. Explicit recovery resends that captured request with the same key, never the current editable draft. The form passes the returned backend job and actual state to PaperDetailIsland through its existing completion callback; the parent establishes TrackingContext and mounts JobStatus only after that identity is known. Missing original parameters, unavailable identity, or changed owner disable recovery with an explanation. Network failures remain inline; stale replies cannot attach a job to a different owner/paper context. A recovered terminal job retains its actual terminal state.

The alternative is a pre-job mode in JobStatus; it could consolidate recovery UI but would widen a component currently organized around a known job ID. Keeping pre-job recovery with the originating submission surface preserves existing boundaries and needs no additional component. Update catalogue responsibilities/interactions, the ADR rationale, and US4.2 coverage, then independently re-review the correction.

## Previous Approved Summary

- **Reuse:** Modify the existing catalogue, architecture decisions, and traceability, preserving useful identifiers and recording superseded decisions.
- **Submission and results (Q11):** Separate components. A submission component owns initial parameter selection, including summary level, and explicit submission. SummaryModal reads completed results and shows submitted-level metadata without editable submission controls. PaperDetailIsland coordinates them; they may share a visual dialog shell. Opening, reading, copying, or retrying a result read must never submit work.
- **Pre-job recovery correction:** JobSubmissionForm owns the no-job-ID uncertain-outcome surface. It uses ContentJobApi's captured immutable original request identity and explicit same-key recovery operation, then returns the actual recovered backend job to PaperDetailIsland before JobStatus mounts. Recovery never uses a changed draft, fabricates a job ID, or resets a terminal state. Explain unavailable recovery and reject obsolete owner/paper-context responses. JobStatus retains recovery for already identified jobs.
- **Idempotency (Q1/Q2/Q5):** Keep ContentJobApi as the sole owner of idempotency/recovery identity and storage lifecycle. IdempotencyService is a stateless asynchronous SHA-256 helper. Preserve owner isolation and unchanged-request recovery; unavailable original parameters disable recovery with an explanation. No terminal-job restart or Retry with changes.
- **Tracking (Q6/Q7):** JobStatus owns the client job projection and native EventSource lifecycle, with fixed two-second SWR polling fallback. Connection status is separate from backend job status. The stable parent retains the context required for tracking-only recovery after rendering failure; replay/cursor details require verified contracts.
- **Assets (Q3/Q8):** Separate AssetViewer with same-origin image delivery, loading/error states, authorized ID copy, accessible zoom/pan/reset, and a noninteractive minimap. The server rechecks authorization/license at delivery; cached images do not imply a fresh check. Preserve DocModelViewer integration.
- **Rendering failures (Q4):** Standalone ErrorBoundary around JobStatus, with a full-page fallback coordinated outside the failed subtree. Network failures stay inline, and recovery does not create a new job.
- **Dependencies and trust (Q9/Q10):** Catalogue the local BFF proxy as project code requiring streaming/cursor/cookie integration. The gateway derives trusted identity. Sentry, SWR, and browser APIs are explicit external dependencies. Assign each client entity one owner; external paper/job IDs do not create phantom local entities.
- **Result-read prerequisites:** ContentJobApi owns transport operations through the BFF; SummaryModal owns result presentation. Contract Design must verify how resultRef resolves to authorized content. Include denied, missing/expired, transient-read-failure, and unsupported-reference states, with read-only retry where appropriate. Record the summary-level boundary decision as downstream treatment of Refined Mockups R-01, not retroactive correction of its reviewed files. Carry its remaining detailed input/default/composition follow-ups into Functional Design.
- **Quality and traceability:** Retain accessibility, scrubbed Sentry/lifecycle/connection-latency telemetry, approved performance targets, and the submit-to-SSE-to-COMPLETED-to-result walking skeleton. Map all active stories, including US8.1/US8.2; explicitly mark excluded US4.3 N/A. Detailed component interfaces and runtime verification remain later-stage deliverables.

Does this all look correct before I generate the revised domain-design artifacts?

- Looks correct
- Request changes

**Previous confirmation:** Looks correct

## Backend Amendment Design Plan

Source authority: approved Requirements Analysis Q15/Q16, FR2.5/FR3.5; revised 28 active stories including US2.6/US3.4; revised Refined Mockups. The previous twelve-component catalogue is the baseline to modify. Existing frontend boundary decisions and ADR-013 pre-job recovery remain applicable, with the preserved dispatch-failure replacement exception and revised recovery focus rules.

The bounded backend work must be explicit authored-code responsibilities rather than an external dependency assumed ready. Proposed logical boundaries map to existing router/service/worker seams, not new deployments:

- **ContentJobController:** HTTP validation/serialization and real SSE framing; translates gateway-authenticated context into job operations. Owns the public result error distinction, based on service decisions: 401 unauthenticated, indistinguishable 404 absent/not-owned, owner-only 410 expiry. It cannot invoke generation to satisfy a result read.
- **ContentJobService:** Authoritative durable job lifecycle, owner-scoped lookup, dispatch/idempotency bindings and effect reconciliation. Owns each DurableJob, backend SubmissionBinding and GenerationEffect entity; browser IdempotencyKey remains a distinct client recovery identity owned by ContentJobApi. Preserve key release on failed dispatch and actual replacement identity; never claim an old terminal job restarted.
- **ContentJobWorker:** Invokes the existing generation pipeline, inspects its real outcome, and requests durable result binding before completion publication. Owns execution coordination rather than a second job/result store. Abstention/failure and crash/redelivery windows remain explicit responsibilities and contract prerequisites. No replacement generation pipeline is proposed.
- **Prepared-result responsibility:** An immutable job-bound prepared result must preserve final personalized content as well as base artifact identity. It cannot be recomputed from current settings during reads. Select its logical read boundary below; storage technology, transaction/effect-reconciliation details and wire schemas remain later design work. Do not assert that the current effect ledger already meets every crash-window guarantee.
- **Catalogue/ADR reconciliation:** Retain stable frontend names and old ADR identifiers, clarify superseded frontend-only assumptions, and add backend entities once each with ownership/attribute names only. Update dependency symmetry/acyclicity, human views and all 28 active story mappings; keep US4.3 excluded. BffProxy reaches the controller through the trusted gateway boundary, not a direct browser/backend bypass. Storage and queues are dependencies, never fictitious authored components.

### Q12. Backend Result-Read Boundary

How should the authorized prepared-result read fit within the existing backend seams?

- A. **Keep result responsibility in ContentJobService** — Add the three logical components above to the twelve-component catalogue (15 total). ContentJobService is the sole owner of the immutable PreparedJobResult and its job binding, and exposes a read-only operation enforcing owner/expiry checks. Controller result handling calls only that read operation; the worker calls explicit write/lifecycle operations. This minimizes indirection and keeps binding/completion ownership cohesive, but command/read separation must be enforced in interfaces and tests because the service also owns submission.
- B. **Add a dedicated JobResultReader** — Add four backend boundaries (16 total). ContentJobService still owns durable jobs, result binding and writes; JobResultReader is a read-only component using a restricted query interface for authorized exact-result delivery, with no enqueue/generation capability. Controller result handling delegates to the reader. This makes the read restriction more visible but adds a component and query interface to maintain; it does not create a second entity owner or deployment.
- X. Other (please specify)

Recommendation: A for this bounded remediation, with a restricted result-read interface and explicit zero-generation/enqueue tests. Both approaches preserve the same approved behavior and are reversible internal decompositions. This choice does not settle datastore layout, transaction guarantees, delivery-unit grouping or deployment topology.

[Answer]: A. Keep result responsibility in ContentJobService

## Consolidated Summary Confirmation

- **Catalogue:** Modify the existing twelve-component design, adding ContentJobController, ContentJobService and ContentJobWorker for 15 logical code boundaries. These map to existing backend seams, not new deployments. Preserve established frontend names and the separate submission/result surfaces.
- **Backend ownership:** ContentJobService alone owns DurableJob, backend SubmissionBinding, GenerationEffect and immutable PreparedJobResult, including its job binding. ContentJobWorker coordinates execution and outcome handling without a duplicate store. The browser IdempotencyKey remains a distinct client recovery entity owned by ContentJobApi; IdempotencyService remains a stateless digest helper.
- **Restricted result reads (Q12):** ContentJobController calls a restricted ContentJobService read interface. Enforce owner checks before availability/expiry disclosure, exact prepared content including personalization, TTL on reference/content paths, and controlled legacy/unresolvable results. Reads never generate, enqueue or recalculate content from current settings. Required 401/404/owner-only 410 behavior follows the approved amendment.
- **Truthful completion:** ContentJobWorker inspects real generation outcomes and requests durable exact-result binding before publishing COMPLETED through the service. Abstention and unsuccessful outcomes follow the established legal lifecycle. Explicitly assign crash/redelivery and effect-reconciliation responsibilities; detailed mechanisms remain Contract/Functional Design prerequisites, not claimed existing guarantees.
- **Recovery:** Preserve failed-dispatch key release: retained bindings return the original job, while an explicit unchanged-request recovery after released dispatch failure may return a replacement. JobSubmissionForm owns pre-job recovery; PaperDetailIsland receives the actual identity/state before JobStatus mounts. Never infer dispatch failure from a lost response, use edited parameters, rotate keys to force execution, restart an old terminal job, or accept stale responses from an obsolete job/context. Missing original request data disables resend with an explanation.
- **Trust and transport:** BffProxy reaches the controller through gateway-derived authentication. Keep explicit BFF streaming/cursor/cookie work and actual backend SSE delimiter correctness. Storage, queues, and the existing generation pipeline remain dependencies of the authored boundaries. The command path enqueues through a dependency; queue delivery starts worker execution rather than introducing a synchronous service-to-worker call cycle.
- **Frontend continuity:** Keep native EventSource and two-second SWR fallback, stable-parent containment, read-only SummaryModal with submitted-level metadata, truthful result states, conditional recovery focus, secure same-origin assets, accessible viewer controls and scrubbed telemetry. Authorized supplied-result ID copy belongs to SummaryModal; asset view transforms belong to AssetViewer.
- **Deliverables and verification:** Update components.md, decisions.md and traceability.json for all 28 active stories plus excluded US4.3. Preserve ADR history while explicitly superseding outdated frontend-only/recovery claims. Check unique entity ownership, references, symmetric acyclic dependencies and diagram/table parity. Record ownership and attribute names here; concrete types, storage/transaction mechanisms, wire schemas, unit grouping and runtime proof belong to their later stages. Retain the full integrated skeleton, approved performance profile and testing/security obligations.

Does this all look correct before I generate the revised domain-design artifacts?

- Looks correct
- Request changes

[Answer]: Looks correct

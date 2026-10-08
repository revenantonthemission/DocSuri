# User Stories — Phase 7 Frontend Wiring

## Sources and Scope

The approved `../requirements-analysis/requirements.md` and confirmed `user-stories-questions.md` govern this document. Supporting context: `aidlc/spaces/default/codekb/DocSuri/business-overview.md`, `aidlc/spaces/default/codekb/DocSuri/component-inventory.md`, and `../practices-discovery/team-practices.md`. Those historical code analyses are not fresh runtime verification.

All active stories are Must Have for the confirmed release. US4.3 is retained as Won't Have, not renumbered or repurposed. Existing IDs remain stable; criteria with invalid prior behavior are corrected under the same IDs. These are acceptance specifications, not statements that implementation or testing is complete.

Requirements Analysis Q15/Q16 authorizes bounded backend job/result remediation and preserves the dispatch-failure key-release exception. FR2.5 and FR3.5 are elaborated by new US2.6 and US3.4. Historical frontend-only assumptions no longer bound this remediation; exact wire/storage details still belong to Contract and Functional Design.

## Story Index

| ID | User outcome | Priority | Requirement anchors |
|---|---|---|---|
| US1.1 | Submit a summarize job | Must Have | FR1.1–FR1.3 |
| US1.2 | Submit a translate job | Must Have | FR1.1–FR1.3 |
| US1.3 | Stable, owner-bound idempotency keys | Must Have | FR1.3, NFR4 |
| US1.4 | Recover submission identity across reload | Must Have | FR1.4, NFR4 |
| US1.5 | Authenticated BFF routing | Must Have | FR1.2, NFR1, NFR12 |
| US2.1 | Receive live job updates | Must Have | FR2.1, FR2.3 |
| US2.2 | Understand actual job state and progress | Must Have | FR2.1–FR2.2 |
| US2.3 | Resume updates without duplicate history | Must Have | FR2.3, NFR5 |
| US2.4 | Continue tracking through polling | Must Have | FR2.4, NFR5 |
| US2.5 | Stop obsolete tracking work | Must Have | FR2.4, NFR5 |
| US2.6 | Receive truthful worker outcomes | Must Have | FR2.5 |
| US3.1 | Retrieve a completed result | Must Have | FR3.1–FR3.3 |
| US3.2 | Display and copy an authorized asset ID | Must Have | FR3.4 |
| US3.3 | Open and leave the full result view | Must Have | FR3.1–FR3.3 |
| US3.4 | Read the exact completed result | Must Have | FR3.5, FR3.2–FR3.3 |
| US4.1 | Understand a failed job safely | Must Have | FR2.2, FR4.2, FR7.3 |
| US4.2 | Recover the same submission inline | Must Have | FR4.1–FR4.3 |
| US4.3 | Retry with modified parameters | Won't Have | FR4.3 exclusion |
| US5.1 | View same-origin figures and tables | Must Have | FR5.1, FR5.3–FR5.4, NFR3, NFR12 |
| US5.2 | Preserve asset authorization at delivery | Must Have | FR5.2, NFR2 |
| US5.3 | Zoom, pan, and reset an asset view | Must Have | FR5.5 |
| US6.1 | Receive accessible status announcements | Must Have | FR6.2, NFR10 |
| US6.2 | Operate controls and inspect progress without a mouse | Must Have | FR6.1–FR6.2, NFR10 |
| US6.3 | Read accessible status and control visuals | Must Have | FR6.3, NFR10 |
| US7.1 | Contain status rendering failures | Must Have | FR7.1, NFR6 |
| US7.2 | Understand the fallback state | Must Have | FR7.1–FR7.3, NFR6–NFR7 |
| US7.3 | Recover tracking without submitting another job | Must Have | FR7.2–FR7.3, NFR6 |
| US8.1 | Have failures and connectivity problems diagnosed safely | Must Have | NFR7 |
| US8.2 | Receive responsive job and asset feedback | Must Have | NFR9 |

## Acceptance Conventions and Dependencies

- Each acceptance criterion is independently executable using its Given fixture; it need not run another story first. Dependencies below describe implementation integration, not an ordering of test cases.
- Use existing submit/state/events behavior and the explicitly authorized job/result remediation. Do not infer a 409 response for replay, a cancellation API, or arbitrary native EventSource headers. Required owner-checked 410 expiry is an amendment, not a claim about the current backend. Retained-binding replay and failed-dispatch replacement are distinct outcomes; a lost response alone does not establish which occurred.
- Native EventSource automatically supplies Last-Event-ID during its own reconnects when event IDs are available. Recreated connections must use a backend/BFF-supported resume mechanism verified in Contract Design; the stories require the outcome, not an invented API.
- UI text quoted in older drafts is not a new localization requirement. Preserve established application language and use clear, accessible labels. Never display raw internal stacks or secrets.
- The primary personas are Researcher, Student, and Casual Reader in `personas.md`; keyboard, screen-reader, and low-vision needs are cross-cutting contexts of those personas.
- No story asserts passing tests, measured latency, or a verified walking skeleton. Those need execution evidence later.

## Submission Workflow

### US1.1 — Submit Summarize Job

As a Researcher or Student, I want to summarize an accessible paper from its detail view so that I can assess its content without leaving my reading workflow.

**Priority:** Must Have. **Dependencies:** US1.3, US1.4, US1.5.

- **AC1.1.1:** Given an authenticated user and accessible paper, when Summarize is activated, then the existing submit contract is called through `/bff/api/content-jobs/*` with task type summarize.
- **AC1.1.2:** Given a successful submission response, when its backend-assigned job ID and state arrive, then tracking mounts for that job.
- **AC1.1.3:** Given submission parameters, when preparing the request, then the owner-bound deterministic key is generated and persistence is attempted before it is needed for recovery.
- **AC1.1.4:** Given an identical submission with a retained owner/key binding, when explicitly resent, then the existing job and actual state are reconciled without duplicate execution or an invented replay HTTP status. Given failed queue dispatch released the binding, the same unchanged request/key may return a replacement identity; the UI uses that returned job/state without claiming the original terminal job restarted.
- **AC1.1.5:** Given a denied or failed submission, when the response is handled, then an understandable failure is shown without displaying submission success or another user's data.
- **AC1.1.6:** Given this release's paper-detail content-job controls, when available actions are inspected and exercised, then only summarize and translate are executable through this integration; novelty, evidence, and ingest_userdoc actions are not introduced. This does not remove unrelated existing workflows or change the backend task union.

### US1.2 — Submit Translate Job

As a Researcher or Student, I want to translate a paper's supported content so that I can read it in my selected language.

**Priority:** Must Have. **Dependencies:** US1.3, US1.4, US1.5.

- **AC1.2.1:** Given an accessible paper and supported translation input, when Translate is activated, then the existing submit contract is used through BFF with task type translate.
- **AC1.2.2:** Given a successful response, when its job identity is received, then tracking uses that identity and state.
- **AC1.2.3:** Given the selected translation parameters, when submitting, then the deterministic key includes those parameters and the authenticated owner.
- **AC1.2.4:** Given invalid input or denied access, when submission fails, then no successful job is fabricated and an actionable error is shown.

### US1.3 — Idempotency Key Generation

As a Researcher, I want repeated unchanged submissions to identify the same work so that a network retry does not request duplicate processing.

**Priority:** Must Have. **Dependencies:** None; test with authenticated-owner fixtures.

- **AC1.3.1:** Given userId, paperId, taskType, and parameters, when generating a key, then native crypto.subtle SHA-256 hashes `userId:paperId:taskType:JSON.stringify(params)`.
- **AC1.3.2:** Given identical serialized inputs, when generating again, then the same key is produced.
- **AC1.3.3:** Given representative distinct owner, paper, task, or parameter inputs, when generating keys, then they differ and another owner's cached key is not substituted.
- **AC1.3.4:** Given a generated key, when submitting, then it is sent using the established backend contract rather than an invented transport field.
- **AC1.3.5:** Given unavailable hashing or unresolved user identity, when preparing submission, then a controlled error is surfaced; no random-key fallback silently defeats deterministic recovery.

### US1.4 — Idempotency Key Persistence

As a Student, I want submission identity to survive a page reload so that I can recover the same request afterward.

**Priority:** Must Have. **Dependencies:** US1.3.

- **AC1.4.1:** Given a generated key and available storage, when persisting it, then the namespace is `idempotency:{paperId}:{taskType}`.
- **AC1.4.2:** Given a reload and the same owner/request, when recovering, then the stored identity is reconciled with the currently derived key before reuse.
- **AC1.4.3:** Given unavailable, corrupt, or quota-limited storage, when reading or writing recovery state, then a controlled outcome is shown without crashing the page or claiming persistence succeeded.
- **AC1.4.4:** Given the same paper/task namespace under a different owner or request, when recovering, then the old entry cannot override the current derived identity.
- **AC1.4.5:** Given a completed result is viewed, when displaying it, then no undocumented key rotation, expiry, or forced re-execution policy is introduced as a side effect.

### US1.5 — BFF Routing for All Job Calls

As a paper reader, I want all job operations to retain my authenticated access context so that my jobs and results remain private.

**Priority:** Must Have. **Dependencies:** None; use BFF/gateway fixtures.

- **AC1.5.1:** Given any submit, state, events, or result request, when the browser sends it, then its destination uses `/bff/api/content-jobs/*`.
- **AC1.5.2:** Given a session cookie, when BFF forwards the request, then the gateway receives the required cookie context and owns trusted-principal derivation.
- **AC1.5.3:** Given gateway Set-Cookie headers, when the response is relayed, then the browser receives them without corrupting separate cookie values.
- **AC1.5.4:** Given normal or error handling, when requests are observed, then no direct gateway/content-job bypass is used and existing CSP protection is preserved.
- **AC1.5.5:** Given a forged client principal or inaccessible job, when the operation is denied, then no other owner's state or result is displayed.
- **AC1.5.6:** Given an authorized content-job event stream traverses BFF, when receiving and resuming it, then SSE framing, event IDs, incremental delivery, and the supported reconnect cursor reach their consumers unchanged rather than being converted to an ordinary JSON response.

## Progress Workflow

### US2.1 — SSE Connection and Real-Time Progress

As a Researcher or Student, I want live updates for my active job so that I can see progress without refreshing the page.

**Priority:** Must Have. **Dependencies:** US1.5. Display acceptance can use a supplied event fixture.

- **AC2.1.1:** Given an active accessible job, when tracking mounts, then native EventSource connects through the BFF events endpoint for that job.
- **AC2.1.2:** Given the connection opens, when the UI updates, then it communicates live connectivity with text accessible independently of color.
- **AC2.1.3:** Given valid events for the selected job, when they arrive, then the display reflects their actual state without creating a new submission.
- **AC2.1.4:** Given initial connection or a resume, when connecting, then the supported cursor contract is respected; an initial connection without an event ID does not invent a Last-Event-ID value.
- **AC2.1.5:** Given a malformed event or connection error, when processing fails, then explicit error/fallback handling contains the problem without an uncaught asynchronous crash.

### US2.2 — Job State Transitions Display

As a Student, I want understandable status and history so that I know whether my job is pending, running, complete, failed, or abstained.

**Priority:** Must Have. **Dependencies:** US2.1 for integration; event fixtures suffice for isolated display tests.

- **AC2.2.1:** Given a supported backend state, when displayed, then the UI distinguishes SUBMITTED, ACCEPTED, QUEUED, RUNNING, COMPLETED, FAILED, and ABSTAINED using established labels.
- **AC2.2.2:** Given progress is supplied by the established contract, when displayed, then it matches that value; when unavailable, then the UI is indeterminate instead of inventing a percentage.
- **AC2.2.3:** Given COMPLETED, when rendered, then result access is offered without assuming every job produces an asset ID.
- **AC2.2.4:** Given FAILED, when rendered, then user-safe error information is shown without promising a backend restart.
- **AC2.2.5:** Given ABSTAINED, when rendered, then its available user-safe reason is shown without a cancellation control or invented transition.
- **AC2.2.6:** Given received events, when inspecting history, then their timestamps and ordering are retained; duplicate or older replay cannot regress the displayed state.

### US2.3 — SSE Resume Without Duplicate History

As a Researcher, I want tracking to resume after an interruption so that temporary connectivity problems do not hide progress.

**Priority:** Must Have. **Dependencies:** US2.1.

- **AC2.3.1:** Given a temporary SSE interruption, when reconnecting, then the implementation follows native EventSource and the verified backend/BFF resume contract rather than assuming configurable browser request headers.
- **AC2.3.2:** Given a last received event identity, when replay is requested, then the supported resume mechanism uses that identity; Contract Design must resolve recreated-connection behavior before implementation.
- **AC2.3.3:** Given missed and duplicate replayed events, when delivered, then missing history is recovered while duplicate IDs are suppressed and newer state is not overwritten by older events.
- **AC2.3.4:** Given SSE cannot supply updates, when failure is handled, then polling fallback activates without asserting an unconfirmed three-attempt/backoff policy.

### US2.4 — Polling Fallback Activation

As a Student, I want continued job tracking when live streaming fails so that I can still learn the outcome.

**Priority:** Must Have. **Dependencies:** US1.5, US2.1.

- **AC2.4.1:** Given SSE fails, when fallback activates, then SWR polls `/bff/api/content-jobs/{jobId}/state` with a fixed two-second configured interval.
- **AC2.4.2:** Given fallback is active, when shown, then the UI explains degraded connectivity using accessible text.
- **AC2.4.3:** Given an active job and successful poll, when state arrives, then the UI updates from the current job response; duplicate/stale responses do not regress it.
- **AC2.4.4:** Given both channels fail through a temporary connectivity problem within the unchanged authorized context, when the error is shown, then the last known state remains clearly stale and no terminal success or durable offline queue is fabricated. Known access loss is handled by AC2.5.5, not presented as a network-only outage.

### US2.5 — Polling and Subscription Cleanup

As a paper reader, I want obsolete tracking work to stop so that old jobs do not interfere with my current view.

**Priority:** Must Have. **Dependencies:** US2.4.

- **AC2.5.1:** Given polling is active and live SSE service is restored, when tracking switches to live mode, then unnecessary polling stops.
- **AC2.5.2:** Given the job reaches COMPLETED, FAILED, or ABSTAINED, when the terminal state is handled, then active-job polling/subscriptions stop when no longer needed.
- **AC2.5.3:** Given polling stops, when the UI updates, then the fallback indicator reflects the actual terminal/live/offline state rather than implying live connectivity unconditionally.
- **AC2.5.4:** Given navigation, unmount, or a selected-job change, when cleanup runs, then the previous subscriptions/timers are released and late responses cannot overwrite the new job.
- **AC2.5.5:** Given the authenticated owner changes or the established state/result/session contract indicates lost access, when tracking reconciles, then previous-owner subscriptions and late responses cannot update the new view, and protected prior state/result content is removed from that view. Do not assume EventSource exposes HTTP status or change the accepted private asset-cache policy.

### US2.6 — Receive Truthful Worker Outcomes

As a Researcher or Student, I want completion to mean my result was actually prepared and retained so that I can trust the reported job outcome.

**Priority:** Must Have. **Dependencies:** US1.5 for authenticated integration; supplied worker/store fixtures allow independent tests. **Anchor:** FR2.5.

- **AC2.6.1:** Given successful prepared summary or translation content, when completion is published, then an exact durable job/result binding already exists and the authorized owner can retrieve that content while it remains available and unexpired.
- **AC2.6.2:** Given the worker receives an explicit abstention or unsuccessful/unavailable outcome, when handling it, then it records the appropriate actual outcome through the established legal state transitions and does not mark missing content COMPLETED. Contract Design pins the exact mapping of existing DTOs without new lifecycle states.
- **AC2.6.3:** Given result-binding persistence fails or is interrupted, when the worker handles or resumes the attempt, then it does not advertise a readable completed result without a durable binding; it surfaces a controlled outcome without exposing internals.
- **AC2.6.4:** Given redelivery or concurrent processing around interrupted completion, when the job is reconciled, then legal transitions and duplicate-work protections hold: no duplicate generation and no regression of a terminal state. Verify interruption before generation, generation completed before binding, binding committed before terminal publication, and terminal publication before acknowledgement. Contract Design must specify effect reconciliation for each window; the current effect ledger is not assumed to satisfy this requirement already.
- **AC2.6.5:** Given state, events and result reads for the same job, when inspected after outcome handling, then they consistently reflect that job's persisted outcome and result availability, without a fabricated result reference or cross-owner content.

## Results Workflow

### US3.1 — Job Completion and Result Display

As a paper reader, I want to read the completed summary or translation so that I can use the generated content.

**Priority:** Must Have. **Dependencies:** US1.5, US2.2.

- **AC3.1.1:** Given COMPLETED, when rendering status, then completion is communicated accessibly.
- **AC3.1.2:** Given an accessible completed job, when viewing its status, then a result-view action is available.
- **AC3.1.3:** Given result access is activated, when fetching, then the existing `/bff/api/content-jobs/{jobId}/result` contract is used.
- **AC3.1.4:** Given an available authorized result, when received, then the corresponding summary/translation is displayed.
- **AC3.1.5:** Given any result-read outcome, when handled, then it neither submits another job nor silently rotates/deletes its recovery identity.
- **AC3.1.6:** Given an unauthenticated read, an unknown/not-owned job, or the authenticated owner's known expired result, when handled, then the amended contract returns 401, indistinguishable 404, or owner-checked 410 respectively; the UI provides safe unavailable/expired/authentication feedback and exposes no protected content or other-owner existence. A 404 is not proof that a job never existed.

**Contract prerequisite:** The approved bounded backend remediation must deliver renderable summary/translation content through an owner-checked, TTL-bounded job result contract. Contract Design pins compatible response fields and exact prepared-result identity; the inspected short resultRef is neither a full identity nor an arbitrary URL/asset ID. US2.6 and US3.4 own truthful binding and exact reads. Implementation/sizing remain conditional on the detailed design; the scope decision has been made, but compatibility and runtime readiness have not been verified. Do not reuse a generation endpoint as a read or substitute a raw reference for result content.

### US3.2 — Asset Identifier Display and Copy

As a Researcher, I want to copy an authorized result's asset ID so that I can reference the correct asset.

**Priority:** Must Have. **Dependencies:** US3.1. **Anchor:** FR3.4.

- **AC3.2.1:** Given an authorized completed result supplies an asset ID, when shown, then that exact identifier is displayed rather than fabricated from the job ID.
- **AC3.2.2:** Given the identifier is displayed, when Copy is activated by keyboard or pointer, then the exact identifier is copied and success is reported only after copying succeeds.
- **AC3.2.3:** Given a copied identifier is later used for delivery, when the asset is requested, then existing authorization still applies; possession of an ID grants no access.
- **AC3.2.4:** Given clipboard access fails, when Copy is activated, then a clear failure appears instead of a false success.
- **AC3.2.5:** Given no supplied ID or denied result access, when rendering, then no fabricated or unauthorized identifier is offered for copying.

### US3.3 — Navigate to Full Result

As a Student, I want to open and close the full result view so that I can read the content and return to the paper.

**Priority:** Must Have. **Dependencies:** US3.1.

- **AC3.3.1:** Given an authorized available result, when View Result is activated, then the existing appropriate result view opens.
- **AC3.3.2:** Given valid content, when rendered, then its formatting is retained without unsafe execution of returned content.
- **AC3.3.3:** Given the result view is open, when it is closed, then the user returns to the paper-detail workflow with appropriate focus.
- **AC3.3.4:** Given the result expires or becomes unavailable before opening, when fetched, then the controlled failure is shown and no new job is started.

### US3.4 — Read the Exact Completed Result

As a paper reader, I want to receive the result actually produced by my completed job so that later settings changes do not silently substitute different content.

**Priority:** Must Have. **Dependencies:** US3.1 and US2.6 for integration; immutable-result and owner fixtures permit independent tests. **Anchor:** FR3.5.

- **AC3.4.1:** Given a job completed under particular persona, glossary, model, prompt and source settings, when those settings later change and the owner reads the unexpired result, then it is the same prepared result bound to that job rather than a newly resolved current-settings artifact. Verify any personalized overlay applied to delivered content as well as base artifact identity; reapplying the current glossary to an old base must not silently alter the completed result.
- **AC3.4.2:** Given successful, missing, expired, denied or unsupported-reference result reads, when generation/enqueue calls are observed, then both counts remain zero. Repeated reads and explicit transient read retries do not submit or rotate recovery identity.
- **AC3.4.3:** Given a legacy, incomplete or unresolvable reference, when read, then a controlled unavailable outcome is returned without guessing an object URL, treating the reference as an asset ID, or automatically regenerating content.
- **AC3.4.4:** Given an unknown job or a job owned by another user, including an expired one, when requested, then both are indistinguishable 404 responses with no content or expiry disclosure. Unauthenticated requests return 401; the authenticated owner of a known expired result receives 410 and no content.
- **AC3.4.5:** Given a state/result reference obtained earlier, when result content is requested after expiry or under another owner, then no alternate reference/content path bypasses TTL or ownership checks. Possession of a reference grants no authority.
- **AC3.4.6:** Given two jobs whose prepared content differs because of applicable personalization or generation/source dimensions, when each owner reads its result, then each resolves its own exact binding; coincident paper/version or coarse reference strings cannot collapse the two results.

## Failure and Submission Recovery Workflow

### US4.1 — Inline Error Display

As a Researcher or Student, I want clear failure information so that I understand the job outcome and the limits of recovery.

**Priority:** Must Have. **Dependencies:** US2.2.

- **AC4.1.1:** Given FAILED, when rendered, then an inline failure state is visible and accessible.
- **AC4.1.2:** Given an error payload, when displayed, then only user-safe details from the established contract are shown.
- **AC4.1.3:** Given retryability metadata exists, when explained, then its presence does not imply that same-key resubmission restarts a terminal job.
- **AC4.1.4:** Given details are expanded, when rendered, then internal stacks, credentials, and infrastructure details remain hidden.

### US4.2 — Inline Same-Key Submission Recovery

As a Researcher or Student, I want to resend an unchanged request inline so that I can recover its outcome without changing parameters or mistakenly restarting completed work.

**Priority:** Must Have. **Dependencies:** US1.3, US1.4, US1.5.

- **AC4.2.1:** Given the original request and owner context are recoverable, when inspecting an uncertain submission or existing job outcome, then a clearly described inline same-parameter resend/recovery action is available.
- **AC4.2.2:** Given that action is activated, when resending, then the original request and same owner-bound idempotency key are used.
- **AC4.2.3:** Given a retained binding returns an existing job, when reconciling, then its actual identity/state are retained without resetting to SUBMITTED merely because recovery was clicked. Given failed dispatch released the binding and recovery returns a replacement, use its actual identity/state while preserving the old job's terminal outcome; never claim the old job restarted.
- **AC4.2.4:** Given the existing job is terminal FAILED or ABSTAINED, when it is returned, then that outcome stays visible with no claim that another execution started.
- **AC4.2.5:** Given network or authorization failure during recovery, when handled, then a controlled error appears without an automatic submission loop, parameter changes, or key rotation.
- **AC4.2.6:** Given successful or failed inline recovery, when its controls and outgoing requests are inspected, then no Retry with changes action is offered, original parameters remain unchanged, and keys are not rotated to force new execution.
- **AC4.2.7:** Given a saved key but unavailable/corrupt original parameters, or an owner mismatch, when recovery eligibility is evaluated after reload or in-session, then resend is unavailable with an accessible explanation; no guessed parameters, current edited draft or another owner's identity are substituted.
- **AC4.2.8:** Given the initial submit response is lost before a job ID is known, when explicit recovery succeeds, then the submission surface passes the actual returned backend job/state to the stable parent before tracking begins; no ID or dispatch-failure cause is inferred from the lost response alone. Late responses for obsolete owner/paper contexts cannot populate the current view. After a replacement job is selected, late state/events/results from the old job cannot overwrite it even within the same owner/paper context.
- **AC4.2.9:** Given ordinary retained-binding replay, failed-dispatch key release, and an executed terminal failure as separate fixtures, when the same-key action runs, then each follows its actual contract: original job, permitted replacement, or retained terminal job respectively. Feedback distinguishes recovery from a replacement only with authoritative evidence; unknown cause uses neutral outcome wording rather than claiming a proven dispatch failure. No automatic resubmission loop is introduced.

### US4.3 — Retry with Modified Parameters (Excluded)

**Priority:** Won't Have. **Anchor:** FR4.3. This identifier is retained solely for historical traceability. It has no active implementation or acceptance-test obligation to provide a parameter-editing retry UI. The prohibition is verified under US4.2; do not reassign US4.3 to another feature.

## Asset Viewing Workflow

### US5.1 — Same-Origin Asset Delivery

As a paper reader, I want figures and tables to load securely in the viewer so that I can inspect them while reading.

**Priority:** Must Have. **Dependencies:** None; use authorized asset/BFF fixtures.

- **AC5.1.1:** Given paperId and assetId, when AssetViewer requests content, then it uses `/bff/api/papers/{paperId}/assets/{assetId}`.
- **AC5.1.2:** Given normal or failure handling, when observing requests, then no presigned URL or legacy presigned redirect is used.
- **AC5.1.3:** Given the same-origin request, when forwarded, then the session context reaches the gateway without client exposure of credentials.
- **AC5.1.4:** Given a successful asset response, when inspecting its cache policy, then it retains `private, max-age=60`, not public/shared caching.
- **AC5.1.5:** Given loading, missing content, or a failed load, when rendering, then an understandable state is shown rather than a silent broken asset or an unauthenticated fallback URL.

### US5.2 — Asset Authorization Re-check

As a paper reader, I want each server delivery to enforce access rights so that protected assets remain private.

**Priority:** Must Have. **Dependencies:** US5.1.

- **AC5.2.1:** Given an asset delivery request reaches the server, when serving it, then authentication, authorization, and license checks run before protected bytes are returned.
- **AC5.2.2:** Given access is denied, when the server responds, then no protected bytes are delivered and the UI handles the established denial response without assuming every denial must be 403.
- **AC5.2.3:** Given an asset is missing, when requested, then the established missing-asset outcome is handled without leaking another owner's content.
- **AC5.2.4:** Given authorized delivery, when relaying, then content handling and session Cookie/Set-Cookie behavior preserve the existing contract.
- **AC5.2.5:** Given an allowed private browser-cache hit, when displaying it, then verification distinguishes that hit from a new server request; the story does not claim a new server authorization check occurred on the cache hit.

### US5.3 — Asset Zoom, Pan, and Reset

As a Researcher or Casual Reader, I want to enlarge and navigate a figure or table so that I can inspect its details.

**Priority:** Must Have. **Dependencies:** US5.1. **Anchor:** FR5.5.

- **AC5.3.1:** Given a displayed asset, when zoom-in or zoom-out is activated, then its displayed scale changes.
- **AC5.3.2:** Given an enlarged asset, when panning through supported pointer or keyboard controls, then the viewed portion changes.
- **AC5.3.3:** Given a transformed view, when Reset to fit is activated, then the entire asset fits the viewer again.
- **AC5.3.4:** Given keyboard-only use, when navigating the viewer controls, then zoom, pan, and reset are operable with accessible names and visible focus.
- **AC5.3.5:** Given an unavailable or unauthorized asset, when controls are used, then they neither reveal protected content nor switch to an alternative delivery URL.

## Accessibility Workflow

### US6.1 — ARIA Live Status Announcements

As a Student using a screen reader, I want meaningful status announcements so that I can follow progress without visual monitoring.

**Priority:** Must Have. **Dependencies:** US2.2.

- **AC6.1.1:** Given tracking mounts, when inspecting semantics, then an appropriate live status region is available.
- **AC6.1.2:** Given a meaningful state/progress change, when announced, then the announcement reflects actual known data and does not invent progress.
- **AC6.1.3:** Given COMPLETED, when announced, then the completion and available result action are understandable.
- **AC6.1.4:** Given FAILED, when announced, then failure is described without an unconditional promise that the job can restart.
- **AC6.1.5:** Given duplicate events, when processed, then they do not produce duplicate history-driven announcements.
- **AC6.1.6:** Given meaningful submission, connection-loss, polling, result-read, asset-load, recovery, or copy success/failure feedback appears without moving focus, when it changes, then its user-safe status/error is programmatically announced without fabricating a job-state change.
- **AC6.1.7:** Given repeated polling responses or replay leave meaningful status unchanged, when the UI refreshes, then the announcement is not repeated; later meaningful changes still announce.

### US6.2 — Progress Semantics and Keyboard Navigation

As a Researcher using a keyboard or screen reader, I want operable controls and accurate progress semantics so that I can use the workflow without a mouse.

**Priority:** Must Have. **Dependencies:** US2.2; other controls can be tested with their own fixtures.

- **AC6.2.1:** Given determinate progress is known, when rendering its progressbar, then its accessible range and current value accurately represent the available progress.
- **AC6.2.2:** Given progress is unknown, when rendering, then indeterminate semantics are used without a fabricated current value.
- **AC6.2.3:** Given submission, recovery, details, asset-ID copy, or viewer controls are present, when traversing with the keyboard, then names, focus visibility, and order support the workflow.
- **AC6.2.4:** Given a focused action, when activated with its standard keyboard interaction, then it performs the same operation as pointer activation.
- **AC6.2.5:** Given a result view opens, closes, a fallback replaces the focused control, or successful submission/tracking recovery removes its action, when the transition completes, then focus remains in a usable visible element of the active view, not a removed/hidden element or the document body. On dismissal it returns to the invoking control if available, otherwise a logical surviving paper-detail control. If the user moved focus elsewhere while recovery was pending, completion does not steal it back; relocate focus only when its current target is removed/hidden. Ordinary background updates do not steal focus, and keyboard navigation can leave the asset viewer without a trap. Verify pre-job recovery and boundary-reset success. Refined Mockups must pin exact destinations to the existing modal/page/inline pattern rather than introduce a new surface or shortcut.

### US6.3 — WCAG 2.1 AA Visual Accessibility

As a Casual Reader with low vision, I want readable status and controls so that I can distinguish outcomes without relying only on color.

**Priority:** Must Have. **Dependencies:** US2.2, US6.2.

- **AC6.3.1:** Given normal-size text in any status, when measured, then its contrast meets WCAG 2.1 AA's applicable 4.5:1 minimum.
- **AC6.3.2:** Given error presentation, when inspected, then meaningful text/semantics accompany the color indication.
- **AC6.3.3:** Given success presentation, when inspected, then meaningful text/semantics accompany the color indication.
- **AC6.3.4:** Given progress or other non-text controls, when assessed, then applicable WCAG 2.1 AA non-text contrast/focus criteria are met rather than applying the text ratio to every graphic indiscriminately.
- **AC6.3.5:** Given all changed UI in loading, success, failure, and recovery states, when applicable WCAG 2.1 AA checks run, then automated and targeted keyboard/focus/screen-reader checks demonstrate conformance, with tested states and criteria recorded. Live-region DOM assertions alone do not certify screen-reader behavior.
- **AC6.3.6:** Given 200% text resize, when operating the changed submission/recovery/result/asset controls, then content and functionality remain available, including long asset IDs and error messages.
- **AC6.3.7:** Given a 320 CSS-pixel viewport or equivalent browser zoom, when inspecting the changed UI, then surrounding controls/messages reflow without information loss or two-dimensional page scrolling. Figures/tables needing two-dimensional layout may retain localized navigation.

**Accessibility handoff:** Refined Mockups and Contract Design must verify existing authorized captions/text alternatives/table semantics and preserve them in the migration. Missing equivalents are accessibility gaps to resolve, not permission to invent OCR or another content service.

## Failure Containment Workflow

### US7.1 — JobStatus Error Boundary

As a paper reader, I want status-rendering failures contained so that the reading workflow remains recoverable.

**Priority:** Must Have. **Dependencies:** None; use a throwing descendant fixture.

- **AC7.1.1:** Given JobStatus is mounted, when inspecting its integration, then a React Error Boundary wraps its rendering subtree.
- **AC7.1.2:** Given a descendant render failure, when React handles it, then the boundary contains that failure.
- **AC7.1.3:** Given containment, when rendering fallback, then the status area has a recoverable failure UI rather than an unusable blank area.
- **AC7.1.4:** Given a network/EventSource callback error, when it occurs, then explicit asynchronous error handling is exercised; the test does not assume the Error Boundary catches it.

### US7.2 — Error Boundary Fallback UI

As a Student, I want a clear fallback message so that I understand a tracking failure and can recover safely.

**Priority:** Must Have. **Dependencies:** US7.1.

- **AC7.2.1:** Given a caught render failure, when fallback is shown, then it uses an understandable, user-safe message.
- **AC7.2.2:** Given recoverable tracking context, when fallback is shown, then a keyboard-accessible recovery action is provided.
- **AC7.2.3:** Given a captured client error, when reported, then Sentry receives scrubbed diagnostic context; console logging alone is not sufficient.
- **AC7.2.4:** Given fallback is displayed, when navigating or reading it, then layout and focus remain usable without promising an unmeasured zero-layout-shift budget.

### US7.3 — Recover the Tracking Connection

As a Researcher, I want to recover job tracking from its fallback so that I can inspect the existing job without submitting it again.

**Priority:** Must Have. **Dependencies:** US7.1, US7.2, US2.3.

- **AC7.3.1:** Given recovery is activated, when the boundary resets and tracking remounts, then the original job identity is retained.
- **AC7.3.2:** Given resume information is available, when reconnecting, then the verified backend/BFF resume contract is used without inventing a custom-header EventSource constructor.
- **AC7.3.3:** Given recovery succeeds, when state arrives, then actual current state is displayed and duplicate history is suppressed.
- **AC7.3.4:** Given recovery fails, when handled, then a controlled failure/fallback remains and no new submit request is made.

## Operational Visibility and Responsiveness

### US8.1 — Safe Diagnostics for Job Interactions

As a Researcher, I want job and connectivity failures to be diagnosable without exposing my content so that service problems can be investigated safely.

**Priority:** Must Have. **Dependencies:** US1.5, US2.1, US4.2, US7.1. **Anchor:** NFR7.

- **AC8.1.1:** Given a client-side error, when captured, then Sentry records scrubbed diagnostic information without cookies, credentials, or document/result contents.
- **AC8.1.2:** Given SSE opens, drops, or recovers, when instrumented, then connection lifecycle telemetry is observable; connection latency is measured in milliseconds from EventSource construction to open.
- **AC8.1.3:** Given observed submission, completion, failure or resend, when recorded, then telemetry distinguishes explicit same-key recovery from initial submission and records actual returned job identity without claiming a new execution solely from the recovery click. A failed-dispatch replacement is distinguished only when supported by authoritative evidence; unknown cause is not guessed.
- **AC8.1.4:** Given telemetry delivery itself fails, when handling the error, then the application remains usable and failure reporting does not recursively crash the page.

The latency detail makes the selected metric testable downstream; it does not claim the upstream accepted-risk finding R-02 was repaired in the requirements artifact.

### US8.2 — Responsive Status and Asset Feedback

As a paper reader, I want prompt connection, asset, and status feedback so that the interface remains responsive while background work runs.

**Priority:** Must Have. **Dependencies:** US2.1, US5.1. **Anchor:** NFR9.

- **AC8.2.1:** Given NFR9's staging profile and 100 sequential measurements, when computing SSE p95 from EventSource construction to open, then it is under 300 ms including network/gateway overhead.
- **AC8.2.2:** Given the same profile and uncached 100 KiB figure, when computing asset-request-to-decoded-readiness p95, then it is under 500 ms.
- **AC8.2.3:** Given the same profile, when computing mount-request-to-first-committed-status-UI p95, then it is under 200 ms.
- **AC8.2.4:** Given the benchmark executes, when recording evidence, then it identifies production build, real staging BFF/gateway, same-region runner, authenticated unthrottled desktop Chromium, one active job, raw samples, and percentile calculation.
- **AC8.2.5:** Given failed operations or exceeded limits, when reporting results, then failures are visible and cannot be counted as fast successful samples or hidden by weakening thresholds. Job execution time is not substituted for the UI metrics.

## Walking Skeleton and Verification Handoff

The first integrated slice demonstrates **submit -> SSE progress -> COMPLETED -> result**, using US1.1, US1.3–US1.5, US2.1–US2.2, US3.1, and the required failure-containment integration. Polling, replay, and failure cases remain required release coverage. Units Generation and Delivery Planning determine the smallest implementation unit containing that slice; this document does not equate a single component to a deployable unit.

The skeleton's technical prerequisites include BFF content-job streaming/cursor propagation and the now-authorized bounded backend result binding/delivery remediation (US2.6/US3.4). Contract Design must pin these seams before implementation, including compatible outcome/expiry semantics. Historical readiness and prior contribution files are not current runtime evidence. Include applicable accessibility/containment in the slice's completion criteria.

Verify actual browser-parseable SSE framing at the backend as well as the BFF: the developer source check found escaped newline text in the frame construction. Wire-level tests must distinguish literal backslash-n characters from the required line/event delimiters. This is part of AC1.5.6 transport correctness, not a new event format. Worker effect reconciliation and exact personalized prepared-result identity are additional technical prerequisites from US2.6/US3.4. Story dependencies denote integration, not an instruction to implement result UI before backend prerequisites; Units Generation must include those backend parts in the runnable slice.

This explicit path carries confirmed Q10 downstream; it does not alter upstream finding R-01's accepted-risk status. Construction still needs an actual human-approved verification command and successful execution evidence before its skeleton checkpoint.

Security-review scheduling (NFR8) is assigned to Delivery Planning, with verification before release. Coverage/current-suite evidence (NFR11) is assigned to Build and Test, with tests authored during Code Generation under the affirmed test-after posture. Include backend regressions for exact binding, owner isolation, expiry, truthful outcomes, interrupted persistence/redelivery, failed-dispatch replacement, and zero generation/enqueue during reads. These process obligations are mandatory, not optional features.

## Traceability and Sizing Notes

`traceability.json` is the element-level map for every approved FR group, FR sub-requirement, and NFR. Existing requirement IDs are never repurposed. Named downstream stages own Deferred process evidence; this does not defer required frontend behavior.

The active set has 28 stories plus one excluded historical identifier. Dependencies denote integration prerequisites; each story's acceptance can be tested with supplied fixtures. Story sizing and INVEST qualifications are recorded in `user-stories-assessment.md`; do not infer implementation completeness from these specifications.

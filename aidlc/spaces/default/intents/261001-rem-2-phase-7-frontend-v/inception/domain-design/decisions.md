# Architecture Decision Records — Phase 7 Frontend Wiring

## Sources

Confirmed `domain-design-questions.md`, approved requirements/stories/refined mockups, and the canonical `components.md` catalogue. This record preserves ADR-001 through ADR-011 identifiers, clarifies their contradictory historical wording, and adds ADR-012 for the newly confirmed split. Historical claims of completed security fixes were design intentions, not runtime evidence.

ADR-013 preserves pre-job recovery ownership. The approved bounded backend amendment now extends this record with ADR-014–ADR-016, based on Requirements Q15/Q16, FR2.5/FR3.5, US2.6/US3.4, and Domain Design Q12. Earlier decisions remain identifiable; the explicit qualifications below govern where scope evolved.

## ADR-001: Bounded Components and Explicit Integration

**Context:** The earlier heading said five components while listing six and omitting integration boundaries. UI, transport, and recovery have different lifetimes.

**Decision:** Retain the five core concerns ContentJobApi, IdempotencyService, JobStatus, AssetViewer, and ErrorBoundary, plus ErrorBoundaryFallback and ZoomPanControls. Include existing PaperDetailIsland, SummaryModal, DocModelViewer, local BffProxy, and the selected JobSubmissionForm: twelve logical components. The catalogue owns the exact dependency and entity lists. Deployment grouping is deferred to Units Generation.

**Amendment:** ADR-014 adds three backend boundaries for fifteen total, superseding the twelve-component scope limit without removing those twelve components. No deployment topology is selected here.

**Consequences:** More explicit boundaries make cleanup, command authority, and testing independently understandable, at the cost of composition interfaces. Call dependencies remain acyclic; supplied callbacks return through existing edges.

**Alternatives Rejected:** A single ContentJobWiring block couples all lifetimes; a two-block API/UI decomposition still conflates submission, reads, and rendering recovery. A single modal with two modes is viable but rejected by the human in Q11 in favor of independently testable read-only behavior.

**Security and compliance:** Component separation restricts where submissions originate and where protected content is retained. Every boundary still needs its own validation and context checks; decomposition alone proves no compliance.

## ADR-002: ContentJobApi Owns Recovery Identity

**Context:** Q2 and Q5 select ContentJobApi ownership; old drafts also assigned storage and IdempotencyKey to IdempotencyService.

**Decision:** ContentJobApi alone owns IdempotencyKey and its storage lifecycle. IdempotencyService is a stateless asynchronous helper computing SHA-256 of `userId:paperId:taskType:JSON.stringify(params)` with native crypto.subtle. No second key entity or storage owner exists.

**Consequences:** Digest testing is isolated while recovery remains close to submission. ContentJobApi bears storage and transport error handling; unavailable crypto fails explicitly rather than silently substituting randomness.

**Alternatives Rejected:** Entire ownership in the helper is viable but contradicts the confirmed owner; UI-owned keys mix rendering lifetime with durable identity. Duplicate ownership permits inconsistent retries.

**Security and compliance:** Owner identity participates in the digest but is not an authorization credential. Gateway authentication remains authoritative; secrets and document contents cannot enter telemetry or secret-bearing localStorage records.

## ADR-003: Separate AssetViewer and Same-Origin Image Delivery

**Context:** The migration removes presigned delivery while retaining the existing document viewer and browser image rendering.

**Decision:** AssetViewer owns load/transform state and renders `/bff/api/papers/{paperId}/assets/{assetId}` directly. DocModelViewer supplies authorized identifiers and existing semantic equivalents; ZoomPanControls emits actions without owning transforms. A noninteractive minimap uses the same authorized image.

**Consequences:** Straightforward browser delivery with accessible navigation. Image error events do not expose HTTP status; absent verified denial/session signals the UI must use honest generic failure wording. Missing captions/table equivalents remain integration gaps.

**Alternatives Rejected:** Folding everything into DocModelViewer reduces reuse; a new AssetDelivery wrapper adds another owner without an established need. Fetching arbitrary result references or falling back to a presigned URL violates the selected delivery boundary.

**Security and compliance:** The gateway/backend performs authentication, authorization, and license rechecks before server delivery. BffProxy relays protected bytes and cookies correctly. Preserve `Cache-Control: private, max-age=60`; a browser cache hit is not a fresh server authorization check.

## ADR-004: Standalone Render Containment with Stable Parent Recovery

**Context:** JobStatus can fail during rendering; EventSource/network callbacks fail outside React render containment. Approved mockups select full-page fallback.

**Decision:** ErrorBoundary contains the status subtree and reports failure to PaperDetailIsland. The stable parent presents ErrorBoundaryFallback outside the failed subtree, preserving job/context/cursor for tracking-only remount or safe return. Each async owner handles its own callback/transport failures inline.

**Consequences:** Recovery survives status teardown and cannot implicitly create a job. Full-page replacement requires deliberate focus placement and restoration; it does not promise zero layout shift.

**Alternatives Rejected:** A boundary inside the failing component cannot catch that component's own render failure. An HOC adds indirection without a distinct lifecycle. Keeping the only recovery context inside JobStatus loses it on unmount.

**Security and compliance:** Safe fallback messages omit stacks and contents; Sentry captures scrubbed diagnostics. Parent context is invalidated on owner/access loss, preventing recovery of another owner's view.

## ADR-005: JobStatus Owns Native Tracking Lifecycle

**Context:** The user selected direct EventSource management, with SWR fallback and replay continuity required by the approved stories.

**Decision:** JobStatus directly manages native EventSource to the BFF events route, with fixed two-second SWR state polling on failure. Polls go through ContentJobApi. Contract Design verifies native automatic reconnect and recreated-connection cursor propagation; no arbitrary-header EventSource constructor is assumed.

**Consequences:** Connection and UI lifetime remain aligned; cleanup, duplicate suppression, and stale-response rejection require focused tests. Stop obsolete tracking on terminal state, context change, unmount, and known access loss. Connection status never substitutes for backend job state.

**Alternatives Rejected:** A subscription API in ContentJobApi creates competing tracking ownership; a shared hook/store may later serve actual reuse but was not selected now. Replacing native EventSource with another client violates the affirmed stack.

**Security and compliance:** Streams retain authenticated BFF routing. EventSource errors do not expose HTTP status; access-loss handling relies on verified session/state/result signals. No stale protected content crosses owner contexts.

## ADR-006: Consolidate Duplicate Asset Delivery Decision

**Context:** Historical ADR-006 duplicated ADR-003 and incorrectly described BFF proxy code as the sole authorization authority.

**Decision:** Superseded by ADR-003 for delivery and ADR-010 for proxy/gateway responsibilities. Keep this identifier for historical references.

**Consequences:** There is one canonical asset-delivery decision; callers pass paper and asset identifiers rather than treating identifiers as authorization tokens.

**Alternatives Rejected:** Maintaining a parallel direct-image decision would let cache/auth semantics drift; a token-based alternate delivery path is outside the confirmed design.

**Security and compliance:** Gateway/backend rechecks, not a client identifier or BFF claim, govern server delivery.

## ADR-007: Recovery Persistence and Unchanged Requests

**Context:** The namespace `idempotency:{paperId}:{taskType}` omits the owner and parameters. A digest cannot reconstruct the original request after reload.

**Decision:** ContentJobApi validates current owner and exact original serialized request against the stored identity before reuse. Keep the mandated namespace; Functional Design defines safe metadata, storage-error outcomes, and reconstruction. If the original request is unavailable, disable inline recovery with an explanation. A result read never rotates or removes recovery identity.

**Consequences:** Reload recovery is honest about unavailable inputs. Retained-binding resend returns the actual existing job, including terminal FAILED/ABSTAINED, without claiming a restart. ADR-016 qualifies this for failed-dispatch key release and permitted replacement identity. Storage availability must not be reported falsely.

**Alternatives Rejected:** Reusing a namespace entry blindly allows cross-owner/request confusion; reconstructing parameters from a hash is impossible; rotating keys or editing parameters to force execution contradicts the selected recovery scope.

**Security and compliance:** Do not persist secrets. The logical entity shape does not authorize persisting full document/request content. Owner comparison is client isolation, not a substitute for server authorization.

## ADR-008: Client Projection Versus Backend Job Authority

**Context:** Earlier wording assigned SSE provision to ContentJobApi despite direct EventSource selection and could be mistaken for backend entity ownership.

**Decision:** JobStatus owns JobState as a client projection, including observed history, connection state, and available progress. Backend services remain authoritative for job transitions. PaperDetailIsland owns TrackingContext, a stable selected-job/replay checkpoint, not a duplicate job-state store.

**Amendment:** ContentJobService now explicitly owns the backend DurableJob and result/effect entities in the catalogue. This adds authored backend responsibility without transferring client projection ownership.

**Consequences:** Parent recovery and live state have distinct lifetimes. Duplicate or older observations cannot regress the display; absent progress remains indeterminate and unsupported ETA stays unavailable.

**Alternatives Rejected:** A centralized store duplicates existing ownership without an approved need; API-owned live state makes transport responsible for React lifetime. Mirroring authoritative job transitions client-side invents backend behavior.

**Security and compliance:** Keep stale observations only within the unchanged authorized context. Clear prior-owner protected content and prevent late responses from repopulating it.

## ADR-009: Consolidate Repeated Image Pattern

**Context:** Historical ADR-009 repeats ADR-003/006 and claims security compliance before implementation evidence.

**Decision:** Superseded by ADR-003. Secure direct-image delivery remains the single selected pattern; this identifier remains addressable.

**Consequences:** One source defines image behavior and cache semantics. Actual compliance still requires delivery-denial and browser tests.

**Alternatives Rejected:** Maintaining three parallel decisions invites contradictory updates; treating a planned path migration as a verified security fix is unsupported.

**Security and compliance:** No presigned fallback or invented fresh authorization check on browser-cache hits.

## ADR-010: Local Proxy Code Versus External Services

**Context:** The old dependency list mislabeled BFF Proxy as external third-party infrastructure and attributed trusted principal injection to it. Source spot-checks also found content-job streaming/cursor gaps.

**Decision:** BffProxy is a local component. It relays Cookie, separate Set-Cookie headers, SSE framing/IDs/cursors, cancellation, safe errors, and asset bytes to configured gateway services. The gateway derives trusted identity and backend services enforce access/license checks. Sentry, SWR, crypto.subtle, EventSource, and other browser facilities are dependencies, not authored components.

**Amendment:** The job controller/service/worker are now authored components, reached through the existing gateway. Asset services and gateway remain dependencies. HTTP/SSE transport cancellation here means stopping obsolete requests, not a new job-cancellation API. Backend SSE delimiter correctness also requires verification, not just proxy forwarding.

**Consequences:** Streaming work is explicitly planned rather than presumed ready. Existing CSP and private cache policy remain. Telemetry call sites use scrubbed context and nonrecursive failure handling; no additional telemetry service is required.

**Alternatives Rejected:** Treating BFF as a black box hides required code changes; direct browser gateway calls violate the selected boundary. Trusting client-supplied principal fields undermines server authority.

**Security and compliance:** Do not expose credentials, permit arbitrary proxy destinations, combine distinct cookie values incorrectly, or return protected bytes on denied delivery. Result-reference resolution must be an explicitly verified authorized read path.

## ADR-011: Existing UI Integration and Verification Handoff

**Context:** Existing PaperDetailIsland, SummaryModal, and DocModelViewer remain integration points, but SummaryModal's prior mount/persona-change commands conflict with read-only results.

**Decision:** PaperDetailIsland coordinates separate submission/results per ADR-012, wraps JobStatus, and preserves document viewing via DocModelViewer. Keep all active stories and mark US4.3 excluded. The first walking skeleton includes submit, SSE progress, COMPLETED, and an actually rendered result, with required containment.

**Consequences:** ResultRef resolution and streaming prerequisites must be settled before implementation. Units Generation groups logical components; Delivery Planning schedules the Week 2 security review; later verification supplies accessibility/performance/coverage evidence.

**Alternatives Rejected:** Reusing SummaryModal unchanged would initiate work while reading. A status-only skeleton fails the selected end-to-end path. Equating every component to a deployment unit prematurely chooses topology.

**Security and compliance:** Preserve initial selection, authorized reads, keyboard/focus behavior, captions/table equivalents, and scrubbed telemetry. NFR9 thresholds and ≥80% new-code coverage are obligations, not measured outcomes here.

## ADR-012: Separate Submission and Result Components

**Context:** Refined Mockups R-01 identified unresolved initial summary-level selection versus completed-result toggle behavior. Q11 explicitly chose separate components; the confirmed summary carries that decision.

**Decision:** JobSubmissionForm owns initial summary-level/translation parameter selection and explicit submission. SummaryModal owns read-only completed summary/translation display with submitted-level metadata; no submit or same-key recovery callbacks enter the result surface. PaperDetailIsland connects the accepted job to tracking and opens the result. Both may reuse a visual dialog shell without sharing command effects.

**Consequences:** Read-only behavior can be independently tested; splitting introduces another composition boundary and requires extracting existing mount/persona-change effects. Result-read transient failures permit read-only retry; missing, expired, denied, and unsupported references have explicit non-submitting outcomes. Refined Mockups now provides conceptual input/default/composition examples; Functional Design pins concrete interfaces and validation.

**Alternatives Rejected:** One component with mutually exclusive submission/result modes is viable and reduces component count, but requires stronger cross-mode effect tests. The human preferred the clearer boundary. Automatically submitting when level changes in the completed view violates read-only semantics.

**Security and compliance:** Result rendering uses safe content formatting, clears denied content, and preserves accessible modal focus. Copy exposes only an authorized supplied asset ID and reports actual success/failure. This resolves the selected ownership question downstream without rewriting the upstream reviewed artifact or claiming runtime verification.

## ADR-013: Submission Surface Owns Recovery Before Job Identity Is Known

**Context:** The server may accept a submission while its response is lost. JobStatus requires an identified job, so assigning all recovery UI to it leaves the uncertain outcome without an owner. The human requested this correction and confirmed its summary. US4.2 requires explicit unchanged-request recovery.

**Decision:** JobSubmissionForm owns inline pre-job recovery. ContentJobApi captures the immutable original request and owner-bound identity before sending. The form obtains recovery availability and a reference to that identity from ContentJobApi; explicit recovery resends the captured request with the same key, never an edited draft. The actual recovered backend job and state pass through the existing completion callback to PaperDetailIsland, which establishes TrackingContext and mounts JobStatus. JobStatus retains recovery for already identified jobs. Both form and parent reject obsolete owner/paper-context responses, and terminal recovered jobs retain their actual state.

**Consequences:** No new component, dependency edge, or key owner is needed. The form owns accessible uncertain, recovering, failed, and unavailable-recovery feedback, including on reopen/reload when safe reconstruction is possible. A stored hash without original parameters cannot enable recovery. Exact reference types, immutable snapshot representation, and safe storage remain Functional Design work. US4.2 includes the form and parent in its trace targets. Verification must exercise lost response, same-key handoff, unavailable originals, owner changes, and a terminal recovered job.

**Alternatives Rejected:** A pre-job mode in JobStatus consolidates recovery controls but broadens its known-job lifetime. A new recovery component adds a boundary for behavior already belonging to the originating submission surface. Reusing the current editable draft breaks unchanged-request recovery.

**Security and compliance:** Current ownership and captured identity are revalidated; the BFF/gateway retains authorization authority. Missing identity or access loss disables recovery, stale callbacks cannot populate a different context, and capturing the request does not authorize persisting secrets or protected document content. No automatic resend loop, key rotation, invented ID, or promise of terminal re-execution is introduced.

## ADR-014: Keep Exact Result Responsibility in ContentJobService

**Context:** The approved frontend journey requires actual prepared content, while inspected backend result references are coarse and no compatible read-only resolver was verified. Requirements Q15 authorizes bounded remediation and Domain Design Q12 selects service-owned results.

**Decision:** Add ContentJobController, ContentJobService and ContentJobWorker at the existing backend seams. ContentJobService alone owns DurableJob, SubmissionBinding, GenerationEffect and PreparedJobResult. Controller result handling receives a restricted query interface with no submission, enqueue or generation capability. Worker completion uses separate explicit write/lifecycle operations. The service's implementation may have command dependencies, but result queries must never invoke them. Keep the final prepared personalization, not just a mutable base cache reference.

**Consequences:** One authority coordinates durable result binding with completion and authorization. Interface separation and negative side-effect tests are essential because the service also handles commands. The logical shape does not choose physical storage or a transaction algorithm. Units Generation must now include backend responsibility in its runnable slice rather than assuming an external ready service.

**Alternatives Rejected:** A separate JobResultReader is viable and makes read-only boundaries more visible, but adds an interface/component without a separate entity lifecycle; the human chose cohesive service ownership. Reusing generation-on-cache-miss for reads or resolving coarse references using current settings violates exact read-only results. A separate result microservice adds unapproved deployment scope.

**Security and compliance:** Check ownership before existence/expiry disclosure. Preserve 401 unauthenticated, indistinguishable 404 unknown/not-owned, and owner-only 410 expired semantics. All reference/content paths obey TTL; legacy references stay controlled failures rather than guessed storage paths. No generation/enqueue on any read outcome, and no raw prepared content in telemetry.

## ADR-015: Bind Prepared Content Before Truthful Completion

**Context:** Current worker code invokes the orchestrator but does not inspect its returned outcome before constructing a coarse result reference and marking completion. A claimed effect alone cannot prove recoverability at every interruption point.

**Decision:** ContentJobWorker coordinates execution and inspects actual outcomes. ContentJobService owns authorization, effect reconciliation, exact durable binding and legal terminal publication. Successful prepared content is bound before COMPLETED; abstention and unsuccessful outcomes cannot fabricate completion. Queue dispatch is an external dependency; the service does not synchronously invoke the worker. The worker calls the service, keeping authored call dependencies acyclic.

**Consequences:** Contract/Functional Design must pin feasibility across interruption before generation, generation finished before binding, binding before terminal publication, and terminal publication before acknowledgement. Do not automatically regenerate after an ambiguous effect. Unprovable reconciliation surfaces a controlled outcome and design escalation rather than silently weakening the duplicate-work requirement. New contracts must preserve prepared personalization when settings later change.

**Alternatives Rejected:** Publish COMPLETED first and bind later advertises nonexistent results. Recompute a reference from mutable generation defaults breaks exact identity. Blindly release/reclaim effects on any exception can duplicate generation. These are not substitutes for a tested reconciliation mechanism.

**Security and compliance:** Worker context cannot override job ownership. Keep legal compare-and-set protections and scrub failure messages. No backend transaction, exactly-once external effect, or passing redelivery test is claimed at this stage; those need explicit design and evidence before implementation approval.

## ADR-016: Preserve Failed-Dispatch Replacement Without Terminal Restart

**Context:** Requirements Q16 preserves the existing key-release exception after enqueue failure, qualifying the older blanket statement that every same-key resend returns the same job.

**Decision:** ContentJobService owns authoritative owner/key-to-job binding and release. Retained bindings return the original job; explicit unchanged-request recovery following released failed dispatch may receive a replacement. Browser ContentJobApi retains the original request/key and adopts the actual backend identity/state. JobSubmissionForm owns the pre-job recovery surface, and PaperDetailIsland replaces tracking context only with the authoritative returned identity. The old terminal job never restarts.

**Consequences:** Late old-job events/results must be rejected even for the same owner/paper. Explain replacements only with authoritative evidence; a lost response or different ID alone does not prove dispatch failure. Preserve focus on surviving controls, or use the resulting status heading when the focused action disappears. Tracking/result-read recovery remains command-free.

**Alternatives Rejected:** Retain failed-dispatch keys forever would change the selected backend recovery policy. Rotate keys or change parameters forces new work outside scope. Treat every recovery as a restart lies about terminal state and can mislead telemetry.

**Security and compliance:** Revalidate owner and original identity, keep unavailable-original recovery disabled, prevent automatic POST loops, and never allow a key/reference to act as authorization. Tests distinguish retained replay, failed-dispatch replacement and executed terminal failure.

## Assumptions & Open Questions

No new product assumptions. Before implementation, pin remediated exact result delivery, effect reconciliation and outcome mappings, actual SSE framing/cursors, asset equivalents and safe client recovery reconstruction as assigned in `components.md`. The backend amendment is authorized, but its mechanism and verification are not assumed complete. Escalate infeasible guarantees or additional scope rather than silently weakening approved behavior.

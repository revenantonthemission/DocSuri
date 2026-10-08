# Requirements — Phase 7 Frontend Wiring for Durable Content Jobs

## Intent Analysis

Enable a signed-in paper reader to submit a supported content job, follow its progress, retrieve its result, and view authorized figures or tables through the existing web application. Connect the existing durable-job backend to the frontend while preserving authentication, authorization, and duplicate-submission protection.

Authoritative initial request [desc]:

> Phase 7 frontend wiring for durable content jobs: wire JobStatus component with SSE, replace AssetViewer presigned redirect with same-origin delivery, route contentJobApi through BFF, mount components in detail page

This is brownfield frontend integration with the bounded backend remediation authorized in Q15: exact job-bound results, authorized read-only delivery, accurate worker outcomes, expiry handling, and regression evidence. Existing contracts remain constraints except where this amendment explicitly authorizes a compatibility-reviewed correction. Historical backend-readiness claims are not current verification. The initial request above remains verbatim; Q15 records the later scope extension.

## Sources

Paths below are relative to this intent record unless they begin with `aidlc/`.

- [desc] Initial description: `project-description.json`, read through `aidlc engine workspace project-description`.
- [scope] Workflow-selected scope: `feature`; Standard depth and Standard test strategy.
- [intent] `ideation/intent-capture/intent-statement.md`: goals, state vocabulary, direct result retrieval, security boundaries, and non-goals.
- [scope-doc] `ideation/scope-definition/scope-document.md`: feature boundaries and integration dependencies. Later confirmed answers below supersede conflicting scope prose, specifically the exclusion of SSE metrics.
- [Q1–Q10] `inception/requirements-analysis/requirements-analysis-questions.md`, original numbered selections. Q3 is superseded by Q11; Q4 is clarified by Q12; Q6 is made measurable by Q13.
- [Q11] Inline same-parameter retry only; same-key submission recovers the existing job and does not promise re-execution of a terminal failure.
- [Q12] Preserve existing CSP without new nonce-validation scope.
- [Q13] Staging end-to-end performance benchmark, including network and gateway overhead.
- [Q14] Retain zoom/pan and copyable asset identifiers, as explicitly selected in `inception/user-stories/user-stories-questions.md` recovery Q8 and confirmed in the amended Requirements Analysis summary.
- [Q15] Include bounded backend remediation in this intent, selected in Contract Design Q10 and carried into Requirements Analysis Q15 and its confirmed summary.
- [Q16] Preserve the dispatch-failure exception, selected in Contract Design Q11 and carried into Requirements Analysis Q16: failed enqueue can release the key, allowing explicit same-key recovery to return a replacement job without restarting the old terminal job.
- [contract-evidence] `inception/contract-design/contract-design-questions.md#Current Contract Evidence`: source observations in backend router, worker, cache-key construction, and job service plus the frontend BFF. These establish the amendment's motivation, not runtime success.
- [confirmed] The current Consolidated Summary Confirmation in that questions file: `Looks correct`.
- [practices] `inception/practices-discovery/team-practices.md` and affirmed `aidlc/spaces/default/memory/team.md` and `project.md`: test-after ordering, coverage, BFF routing, idempotency, SSE fallback, Error Boundary, Sentry, and security review.
- [business] `aidlc/spaces/default/codekb/DocSuri/business-overview.md`: user flows and historical readiness evidence.
- [architecture] `aidlc/spaces/default/codekb/DocSuri/architecture.md`: browser/BFF/gateway separation, existing routes, event and state shapes.
- [structure] `aidlc/spaces/default/codekb/DocSuri/code-structure.md`: existing components, catch-all BFF route, API client, and test tooling.

## Decision Reconciliation

- The original Q3 selection and its prior summary disagreed. Q11 governs: same-parameter resend/recovery only. Parameter-editing retry is excluded.
- The previous security summary added CSP nonce validation. Q12 governs: preserve existing CSP; no new nonce-validation workstream.
- Q5 includes Sentry, SSE metrics, and job lifecycle events despite the older scope document's exclusion of advanced observability. A separate dashboard product is not added.
- The accepted latency targets are 300/500/200 ms, with Q13's staging measurement profile. Later draft design documents with different budgets are not authoritative inputs to this requirements baseline.
- Existing downstream stories and designs must be reconciled with this baseline during their reopened stages. Component folders alone do not establish implementation units or dependencies.
- Q14 explicitly retains zoom/pan and copyable asset identifiers. FR3.4 and FR5.5 provide their requirement anchors while preserving the existing US3.2 and US5.3 story identifiers.
- Q15 supersedes the frontend-only/no-worker-change restriction only for the authorized job/result remediation. Add FR2.5 and FR3.5 without renumbering existing requirements.
- Q16 qualifies Q11's overbroad existing-job wording: retained bindings recover the same job; a binding released after failed dispatch can yield a replacement identity. A lost response alone does not prove failed dispatch. Old terminal jobs remain terminal, and parameter changes/key rotation are still excluded.
- FR3.3's 410 response is now an explicitly required amendment for owner-verified expiry; inspected code currently folds expiry into 404. Unknown and not-owned jobs remain indistinguishable.

## Functional Requirements

The FR1–FR7 grouping preserves identifiers already referenced by the existing story drafts. Every requirement in this section is required for the confirmed release; implementation ordering belongs to Units Generation and Delivery Planning.

### FR1 — Submit Supported Jobs

- **FR1.1:** Expose summarize and translate actions in the paper-detail workflow for authenticated users with access to the paper. Do not expose executable novelty, evidence, or ingest_userdoc actions in this release. [Q1, intent]
- **FR1.2:** Submit using the existing contentJobApi contract through `/bff/api/content-jobs/*`, retaining the backend-assigned job identity and state. Browser calls must not supply a trusted principal in place of gateway authentication. [Q8, practices, architecture]
- **FR1.3:** Generate the deterministic idempotency key from the authenticated user, paper, task type, and parameters, and retain it for an unchanged-request resend. Different owners must remain isolated. [intent, practices]
- **FR1.4:** Preserve the key across page reload using the affirmed localStorage namespace. Storage unavailability or corrupted entries must produce a controlled recovery outcome rather than an uncaught page failure or use of another user's cached key. [practices, confirmed]

**Acceptance:** Given an authorized user and paper, when summarize or translate is submitted, then the BFF request uses the established contract and the returned job is tracked. Given a retained owner/key binding, when the identical request is resent, then the existing job is recovered without duplicate work. Given failed queue dispatch released that binding, when explicit unchanged-request recovery occurs, then a replacement job may be returned using the same key; the UI uses its actual identity/state and does not claim the old terminal job restarted. An uncertain/lost response alone is not proof of dispatch failure. An unauthenticated or unauthorized response must be surfaced without displaying a successful submission or another owner's data. [Q16]

### FR2 — Track Job Progress

- **FR2.1:** Mount JobStatus in the paper-detail workflow for the returned job and show the backend state vocabulary: SUBMITTED, ACCEPTED, QUEUED, RUNNING, COMPLETED, FAILED, and ABSTAINED. [intent, Q2, architecture]
- **FR2.2:** Show available progress, user-safe error information, event history, and timestamps. Where progress is unavailable, show an indeterminate state rather than inventing a percentage. [Q2]
- **FR2.3:** Receive updates using native EventSource through the BFF and support replay/resume using the backend event identity contract. Replayed events must not duplicate displayed history or regress the displayed state. [intent, practices]
- **FR2.4:** Fall back to SWR state polling at a fixed two-second interval when SSE fails. Communicate degraded connectivity, retain the last known state, and stop active-job subscriptions/polling when no longer needed. [practices, confirmed]
- **FR2.5:** Report COMPLETED for a summarize/translate job only after successful prepared content is durably bound to that job's exact result identity. Inspect the actual worker outcome: explicit abstention and unsuccessful/unavailable outcomes must not be labeled as completed content. Preserve the established state vocabulary, legal transitions, and duplicate-work protections; detailed outcome mapping belongs to Contract Design. [Q15, contract-evidence]

**Acceptance:** Given a submitted job, when ordered events arrive, then the displayed state and history update. When a connection drops and events are replayed, then the same event is not displayed twice. When SSE fails, then polling supplies updates on the configured interval; if neither channel is available, the UI shows connection loss without representing stale data as live. Switching jobs or leaving the view cleans up the previous subscription.

**Worker-outcome acceptance:** Given successfully prepared content and a durable exact binding, when completion is published, then the job's authorized result read returns that content while available and unexpired. Given an abstention or unsuccessful/unavailable outcome, when handled, then state and user-safe feedback reflect the actual outcome rather than COMPLETED with invented content. Given interrupted or failed result-binding persistence, then completion must not advertise a readable result that was never durably bound. Verify crash/redelivery cases preserve legal transitions and do not duplicate generation. [Q15]

### FR3 — Retrieve Completed Results

- **FR3.1:** On COMPLETED, retrieve and display the authorized prepared summary/translation through the job result path at `/bff/api/content-jobs/{jobId}/result`. Include the bounded backend remediation needed for renderable content delivery, with backward compatibility and exact response shape resolved in Contract Design. A short resultRef alone does not satisfy result display. [intent, Q15]
- **FR3.2:** Treat result retrieval as a read. It must not create or resubmit a job. [intent]
- **FR3.3:** Enforce owner checks before disclosing result existence or expiry: return 401 for unauthenticated requests, indistinguishable 404 for unknown/not-owned jobs, and 410 for the authenticated owner's known expired result. Render understandable unavailable/expired feedback. Unknown, unresolved, or legacy result content must have a controlled unavailable outcome, with exact error mapping pinned in Contract Design. The owner-specific 410 distinction is required remediation, not an assertion about existing code. [intent, Q15]
- **FR3.4:** When an authorized completed result supplies an asset identifier, display it and provide a keyboard-accessible copy action. Copy the identifier exactly; indicate success only after successful copying and provide a clear failure state if clipboard access fails. Do not fabricate an identifier or treat possession of it as authorization to access an asset. [Q14]
- **FR3.5:** Bind delivery to the completed job's actual prepared result, including its applicable personalization and generation/source identity. Later changes to persona, glossary, model, prompt, or source settings must not substitute a different result during a read. Never reconstruct content identity from a short reference or guess a storage URL. Owner and expiry protections apply to both references and content; missing/legacy/unresolvable results must not trigger generation, enqueue, or resubmission. [Q15, contract-evidence]

**Acceptance:** Given a completed accessible job with an available result, when the result is requested, then the user receives that result. Given an expired or unavailable result, then the UI reports that condition and does not automatically start work. Unauthorized result requests must not reveal result content.

**Exact-result and read-only acceptance:** Given a job completed under particular generation/source/personalization settings, when those settings later change and its result is read, then the delivered prepared result remains the one bound to that job. Given successful, missing, expired, denied, or unsupported-reference reads, generation and enqueue call counts remain zero. Given another owner requests a known expired job, the response remains the same 404 as an unknown job rather than exposing expiry. Given the authenticated owner requests a known expired result, return 410 without protected content. State/result references must not permit an alternative content read around the TTL. Legacy references that cannot resolve safely remain unavailable without automatic repair by generation. [Q15]

**Asset identifier acceptance:** Given an authorized completed result containing an asset identifier, when the user activates Copy by keyboard or pointer, then that exact identifier is copied and success is reported only after the copy succeeds. When clipboard access fails, then a clear failure is shown instead of a false success. When the result does not supply an identifier or access is denied, then no fabricated or unauthorized identifier is offered for copying. Using a copied identifier to request an asset still requires the existing authorization checks.

### FR4 — Recover an Unchanged Submission

- **FR4.1:** Provide an inline same-parameter resend/recovery action using the original request and idempotency key. [Q11]
- **FR4.2:** Reconcile to the actual backend job identity and state. With a retained binding, a returned terminal FAILED or ABSTAINED job stays terminal and must not be presented as restarted. Preserve the failed-dispatch exception: after enqueue failure releases the binding, explicit unchanged-request recovery may return a replacement job; describe that returned submission accurately without claiming the old terminal job changed state. [Q11, Q16, intent]
- **FR4.3:** Do not provide a Retry with changes action, automatically alter parameters, or rotate keys to force a new execution as part of this recovery action. [Q11]

**Acceptance:** Given a lost submission response and a retained key binding, when the user explicitly resends the original unchanged request, then the existing job is recovered. Given failed dispatch released the binding, the same action may return a replacement job; use its actual state and identity while the old failed job remains terminal. Given a retained terminal failure, when the same-key action returns it, then failure stays visible and is not described as restarted. An uncertain outcome must not be described as a proven dispatch failure without authoritative evidence. Missing original parameters disable recovery with a clear explanation. Network and authorization failures remain visible and do not create a retry loop. Tests distinguish retained-binding replay, failed-dispatch replacement, and executed terminal failure. [Q16]

### FR5 — Deliver Authorized Assets on the Same Origin

- **FR5.1:** AssetViewer accepts paperId and assetId and requests figures/tables through `/bff/api/papers/{paperId}/assets/{assetId}`. Eliminate the legacy presigned-URL/redirect delivery flow. [Q9, intent]
- **FR5.2:** Preserve server-side authentication, authorization, and license checks at delivery. The BFF forwards session cookies and relays gateway Set-Cookie headers. [practices, intent]
- **FR5.3:** Preserve the accepted `Cache-Control: private, max-age=60` policy. Shared/public caches must not receive authorization to cache protected asset bytes. [intent-capture Q7, confirmed]
- **FR5.4:** Provide understandable asset-loading and failure states without exposing credentials or internal error details. [Q9, confirmed]
- **FR5.5:** Provide zoom-in, zoom-out, reset-to-fit, and panning for large figures/tables in AssetViewer. Support keyboard-accessible controls as well as pointer interaction, with the same same-origin delivery and authorization protections as the underlying displayed asset. [Q14]

**Acceptance:** Given authorized access, when an asset is viewed, then the request stays on the BFF origin and returns the authorized content without a presigned redirect. When a request is denied or the asset is absent, then the UI shows a controlled failure and does not fetch an alternative unauthenticated URL. Verify authorization on server delivery and private caching separately; an allowed browser-cache hit is not a new server authorization check.

**Zoom/pan acceptance:** Given a displayed figure/table, when the user activates zoom-in or zoom-out, then the displayed scale changes; when the user pans a zoomed asset, then the viewed portion changes; and when Reset to fit is activated, then the whole asset fits the viewer again. These actions are usable by keyboard and pointer. When an asset is unavailable or unauthorized, then the controls do not reveal protected content or switch to an alternative delivery URL. The controls meet FR6's accessibility requirements.

### FR6 — Accessible Interaction

- **FR6.1:** Make submission, recovery, status/error details, and asset-related controls keyboard-operable with accessible names and visible focus. [Q7]
- **FR6.2:** Announce meaningful status/error changes with ARIA live semantics. Use progressbar semantics when applicable and accurately distinguish determinate from indeterminate progress. [Q7, practices]
- **FR6.3:** Meet WCAG 2.1 AA for the changed UI, including applicable contrast, focus, and screen-reader behavior. [Q7]

**Acceptance:** Given keyboard-only use, when a user submits and inspects a job or invokes recovery, then all applicable controls remain reachable and operable. Given a screen reader, then meaningful state changes are announced and missing progress is not announced as a fabricated percentage. Check automated accessibility findings and perform targeted keyboard/screen-reader checks.

### FR7 — Contain UI Failures

- **FR7.1:** Wrap JobStatus in a React Error Boundary and provide a recoverable fallback for descendant rendering failures. [practices]
- **FR7.2:** Handle network, EventSource, and other asynchronous errors explicitly in the relevant integration flow; do not rely on an Error Boundary to catch asynchronous callbacks. [confirmed, architecture]
- **FR7.3:** Capture client-side failures in Sentry while showing user-safe messages. Tracking/result-view recovery never submits work. Explicit submission recovery follows FR4, including truthful handling of a failed-dispatch replacement; it must not silently claim that a replacement is the old job or that an old terminal job restarted. [Q5, Q11, Q16, practices]

**Acceptance:** Given a descendant render failure, then the boundary displays its fallback rather than leaving an unusable blank status area. Given SSE or fetch failure, then the connection/error UI handles it explicitly. Recovering the status view reconnects to the existing job, and telemetry must not contain session cookies, credentials, or result/document contents.

## Non-Functional Requirements

NFR1–NFR8 retain the meanings used by existing story references. NFR9 onward capture the additional confirmed quality requirements without reassigning those original IDs.

| ID | Requirement and pass/fail condition | Source |
|---|---|---|
| NFR1 | **SEC-8:** Every content-job browser request, including SSE, state polling, submission, and results, uses `/bff/api/content-jobs/*`. Verify request destinations and gateway-derived identity; no direct-gateway bypass. | intent, Q8, practices |
| NFR2 | **SEC-9:** Asset delivery performs server-side authentication, authorization, and license checks. Verify allowed and denied delivery requests; preserve cookie forwarding and Set-Cookie relay. | intent, practices |
| NFR3 | **SECURITY-08:** No presigned URL or legacy presigned redirect is used by the asset-delivery flow. Verify browser network traffic and migrated call sites. | intent, Q9 |
| NFR4 | **Idempotency:** Use native `crypto.subtle` SHA-256 over `userId:paperId:taskType:JSON.stringify(params)` and localStorage key `idempotency:{paperId}:{taskType}`. Verify unchanged-request stability, reload persistence, changed-input key derivation, and owner isolation. Changed-input derivation does not add a Retry with changes UI. | practices, Q11 |
| NFR5 | **Connection resilience:** Native EventSource resume/replay and SWR polling fallback at a configured two-second interval. Verify disconnect, replay, duplicate events, polling failure, job switch, terminal states, and cleanup; no invented availability SLO is imposed. | intent, practices |
| NFR6 | **Failure containment:** A render failure in JobStatus descendants reaches the Error Boundary fallback; asynchronous integration errors reach explicit error/fallback handling. Verify both classes of failure and recovery without duplicate submission. | practices, FR7 |
| NFR7 | **Observability:** Integrate Sentry for client-side errors, SSE connection metrics, and job lifecycle events. Verify telemetry for connection opening/failure/recovery and observed submission/completion/failure/resend, distinguishing a resend from a new execution. Verify sensitive-data scrubbing. | Q5, Q11 |
| NFR8 | **Security review:** Conduct the recorded mid-implementation Week 2 review for AssetViewer and address SEC-8/SEC-9 findings before release. Delivery Planning must identify the accountable reviewer and schedule; a drafted design is not evidence this review passed. | practices, confirmed |
| NFR9 | **Performance:** All three p95 measurements satisfy the strict limits in the profile below. Record raw samples and environment. A failure is surfaced for resolution rather than silently relaxing a limit. | Q6, Q13 |
| NFR10 | **Accessibility:** Changed UI meets WCAG 2.1 AA. Verify applicable automated rules plus keyboard, focus, progress semantics, and live-announcement behavior. | Q7 |
| NFR11 | **Verification:** Maintain at least 80% line coverage for new code. Existing backend/frontend suites, lint, typecheck, and relevant end-to-end integration checks pass before merge. Include backend regression evidence for exact result binding, owner isolation, expiry, truthful worker outcomes, interrupted persistence/redelivery, dispatch-failure replacement, and zero generation/enqueue during reads. Historical counts are not current pass evidence. | practices, confirmed, Q15, Q16 |
| NFR12 | **Existing protections and caching:** Preserve current CSP without new nonce-validation scope and retain private 60-second asset caching. Verify integration does not remove existing controls or enable public caching. | Q12, intent-capture Q7 |

### NFR9 Performance Acceptance Profile

Use a production frontend build, the real BFF/gateway in staging, and a browser runner in the same deployment region. Use an authenticated desktop Chromium session, one active job, and no CPU/network throttling. Collect 100 sequential measurements for each metric; include network and gateway overhead.

| Metric | Start | End | Required p95 |
|---|---|---|---|
| SSE connection | EventSource construction | Connection open event | Under 300 ms |
| Asset loading | Asset request start | Image decoded and ready to display | Under 500 ms |
| JobStatus mounting | Mount request | First committed status UI | Under 200 ms |

The asset fixture is an uncached 100 KiB figure image. This is a benchmark fixture, not a maximum supported asset size or a promise about every figure. Actual job execution duration is outside these UI latency budgets. The performance-validation implementation must record browser/build versions, runner environment, cache controls, sample collection, and percentile calculation so results are reproducible. Timing alone does not establish correctness: error responses cannot count as successful connection/image/UI samples.

## Constraints

- Integrate existing frontend components and the existing BFF/API contracts in place. Do not create duplicate clients as a substitute for migration. [Q8, structure]
- Use native fetch with the custom Transport abstraction, native EventSource, SWR, strict TypeScript, CSS Modules plus Tailwind, and clsx plus tailwind-merge where applicable. Follow the affirmed forbidden-dependency rules. [practices]
- Preserve backend state vocabulary, owner-scoped access, TTL and compare-and-set protections. Q15 permits only the compatibility-reviewed result binding/delivery, worker outcome and expiry corrections required by FR2.5/FR3.1–FR3.3/FR3.5; Q16 preserves existing dispatch-failure key release. Do not add cancellation, synthetic states, extra task types or a replacement generation pipeline. [intent, architecture, Q15, Q16]
- The idempotency storage namespace omits userId, so stored data must never override the key derived from the current authenticated user and request. The detailed storage representation and account-change handling must satisfy NFR4. [practices, intent]
- Build and verify the thin integrated walking skeleton before expanding into later units, using the human-approved verification command and checkpoint. [Q10, practices]
- Follow test-after/test-last per component, trunk-based short-lived branches, and the recorded deployment practice of production deployment after passing CI on merge. These are recorded practices, not a claim that the current pipeline has been verified. [practices]

## Assumptions & Open Questions

- **Backend compatibility:** Source inspection found missing verified read-only result resolution and coarse result references, plus worker outcome and expiry gaps. Q15 explicitly authorizes bounded remediation; readiness remains unverified until the amended contracts are implemented and tested. Contract Design must pin exact outcome/error mapping, compatible response fields, and immutable result binding without guessing from current settings.
- **Progress and telemetry:** The UI shows progress only when supplied or justified by the established contract. Technical design must identify available payload fields and instrumentation for the confirmed SSE/lifecycle telemetry without adding content capture.
- **Browser resume mechanism:** Native EventSource automatically handles Last-Event-ID on its own reconnects, but does not expose arbitrary request-header configuration. Contract Design must verify the supported cursor behavior for a recreated connection; no custom-header API is assumed.
- **Performance reproducibility:** The confirmed limits and staging profile are binding. The technical verification plan must pin runner/build/browser details and a percentile calculation before collecting acceptance evidence.
- **Review scheduling:** Delivery Planning must replace the relative Week 2 milestone with a concrete schedule and accountable security reviewer.
- **Historical test counts:** References to 473 backend and 356 frontend tests are prior observations. Build and Test records the current baseline, results, and actual new-code coverage.

These items describe technical verification and scheduling work; they do not introduce additional user-facing features or claim completed validation.

## Out of Scope

- Novelty, evidence, and ingest_userdoc worker execution; separate novelty SSE.
- Job cancellation UI or a new cancellation endpoint; job-list/history pages; batch submission UI.
- Native/mobile applications; responsive web accessibility remains in scope.
- Retry with changed parameters and forced re-execution of a terminal failed job through key rotation.
- A new CSP nonce-validation workstream; existing CSP remains required.
- Browser notifications, durable offline retry queues, and a separate observability dashboard product, none of which was confirmed for this release.
- New PDF/video rendering infrastructure, cloud-platform selection, or replacement of the existing deployment architecture without a separately grounded requirement.

## Traceability and Handoff

| Requirement group | Confirmed origin | Downstream evidence required |
|---|---|---|
| FR1, NFR1, NFR4 | Q1/Q8, intent, affirmed idempotency rules | Submission/owner-isolation/reload tests and existing API contract mapping |
| FR2, NFR5 | Q2, intent, affirmed SSE/fallback rules | Event/polling/replay/cleanup scenarios |
| FR3 | Intent success criteria 5 | Authorized result and 404/410 read-only retrieval scenarios |
| FR2.5, FR3.5 | Q15 and Contract Design source evidence | Accurate worker outcomes; durable exact job/result binding; interrupted persistence/redelivery; read-only retrieval across settings changes; controlled legacy-reference handling |
| FR3.4 | Q14, User Stories recovery Q8 | US3.2; exact-identifier display/copy, keyboard access, clipboard failure, missing-ID and denied-access scenarios |
| FR4 | Q11, Q16 | Retained-binding recovery, failed-dispatch replacement, immutable original requests, terminal-failure and truthful identity behavior tests |
| FR5, NFR2/NFR3/NFR12 | Q9/Q12, intent, accepted cache policy | Same-origin delivery, denied access, cookie/cache verification |
| FR5.5 | Q14, User Stories recovery Q8 | US5.3; keyboard/pointer zoom, pan, reset-to-fit, and unavailable/unauthorized asset scenarios |
| FR6, NFR10 | Q7 | Keyboard, screen-reader, progress, contrast checks |
| FR7, NFR6/NFR7 | Q5, affirmed Error Boundary/Sentry rules | Render and asynchronous failure handling plus scrubbed telemetry checks |
| NFR8 | Affirmed security-review practice | Named review owner, schedule, findings and disposition evidence |
| NFR9 | Q6/Q13 | Staging measurements against the confirmed profile |
| NFR11 | Affirmed testing practice | Current suite results and new-code coverage evidence |

User Stories must preserve these IDs, and Units Generation must define the actual units and dependency graph. Existing downstream draft references are not proof that this requirements baseline has been implemented or tested.

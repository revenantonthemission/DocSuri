# Contract Design Questions — Phase 7 Frontend Wiring

**Gate:** Architecture Reviewer (advisory)

## Sources

- [desc] Initial description: "Phase 7 frontend wiring for durable content jobs: wire JobStatus component with SSE, replace AssetViewer presigned redirect with same-origin delivery, route contentJobApi through BFF, mount components in detail page"
- [scope] Workflow-selected scope: `feature`.
- [memory:M1] `aidlc/spaces/default/memory/team.md#Walking Skeleton`: "Stance: ON — Build a thin end-to-end slice first"
- [memory:M2] `aidlc/spaces/default/memory/team.md#Deployment`: "Continuous deployment to production on merge"
- [memory:M3] `aidlc/spaces/default/memory/project.md#Mandated`: "ALWAYS route all content-job API calls through `/bff/api/content-jobs/*` (SEC-8)"
- [memory:M4] `aidlc/spaces/default/memory/project.md#Mandated`: "ALWAYS generate idempotency keys as SHA-256 hash"
- [memory:M5] `aidlc/spaces/default/memory/project.md#Mandated`: "ALWAYS wrap JobStatus in React Error Boundary"
- [memory:M6] `aidlc/spaces/default/memory/project.md#Mandated`: "ALWAYS use same-origin asset delivery via `/bff/api/papers/{paperId}/assets/{assetId}`"
- [memory:M7] `aidlc/spaces/default/memory/project.md#Mandated`: "ALWAYS integrate Sentry for client-side error tracking"
- [memory:M8] `aidlc/spaces/default/memory/project.md#Mandated`: "ALWAYS conduct security review mid-implementation (Week 2)"

---

## Questions for Contract Design

### 1. Inter-Unit Contracts — ContentJobApi → JobStatus
**Question:** What is the contract for the SSE connection between ContentJobApi and JobStatus?

- A. **SSE via EventSource** — JobStatus uses `EventSource` to connect to `/bff/api/content-jobs/{jobId}/events` with `Last-Event-ID` header for resume; ContentJobApi provides `subscribeJobEvents(jobId, onEvent, lastEventId?)` returning unsubscribe function
- B. **Polling only** — JobStatus polls `/bff/api/content-jobs/{jobId}/state` every 2s via SWR; no SSE
- C. **WebSocket** — Use WebSocket for real-time updates
- X. Other (please specify)

### 2. Inter-Unit Contracts — ContentJobApi → IdempotencyService
**Question:** What is the contract for idempotency key generation between ContentJobApi and IdempotencyService?

- A. **Synchronous function** — `generateIdempotencyKey(userId, paperId, taskType, params)` returns `Promise<string>` (SHA-256 hash of `userId:paperId:taskType:JSON.stringify(params)`)
- B. **Async service call** — HTTP call to a separate idempotency service
- C. **Event-based** — ContentJobApi emits event, IdempotencyService responds with key
- X. Other (please specify)

### 3. Inter-Unit Contracts — AssetViewer → BFF
**Question:** What is the contract for asset delivery between AssetViewer and BFF proxy?

- A. **Direct img src** — AssetViewer renders `<img src="/bff/api/papers/{paperId}/assets/{assetId}" />`; BFF proxy handles auth re-check, streams bytes, validates content-type, returns `cache-control: private, max-age=60`
- B. **Token-based** — AssetViewer calls `/bff/api/content-jobs/assets/{assetId}/token` to get presigned URL, then uses that URL
- C. **AssetDelivery component** — Wrapper component handles fetch, auth, caching
- X. Other (please specify)

### 4. Inter-Unit Contracts — JobStatus → ContentJobApi
**Question:** What is the contract for job submission and state polling between JobStatus and ContentJobApi?

- A. **submitJob + polling** — `submitJob(request)` returns `{ jobId, state }`; JobStatus polls `/bff/api/content-jobs/{jobId}/state` via SWR (2s interval) as fallback
- B. **WebSocket** — JobStatus uses WebSocket for all communication
- C. **Server-Sent Events only** — No polling fallback, SSE only
- X. Other (please specify)

### 5. External API Contracts — BFF Proxy
**Question:** What is the public/external API surface exposed by the BFF proxy for Phase 7?

- A. **Content Jobs API** — `/bff/api/content-jobs/*` (submit, state, events, translate) — proxied to gateway
- B. **Asset Delivery** — `/bff/api/papers/{paperId}/assets/{assetId}` — same-origin asset delivery with auth re-check
- C. **Both A and B**
- X. Other (please specify)

### 6. Error Handling Contracts
**Question:** What is the error handling contract at each boundary?

- A. **Standard HTTP errors** — 4xx/5xx with JSON body `{ message, code, retryable?, retryAfterSeconds? }`; SSE errors via `onerror` event; polling fallback on SSE failure
- B. **Custom error codes** — Each boundary defines its own error code schema
- C. **GraphQL-style** — Errors in response body with `errors` array
- X. Other (please specify)

### 3. Contract Ownership & Versioning
**Question:** Who owns each contract spec and what is the versioning/breaking-change policy?

- A. **Provider owns contract** — Provider unit owns spec; breaking changes require consumer agreement; additive changes are backward-compatible (consumers ignore unknown fields)
- B. **Consumer owns contract** — Consumer defines what they need; provider implements
- C. **Shared ownership** — Both parties co-own; changes require mutual agreement
- X. Other (please specify)

### 4. Contract Versioning & Breaking Changes
**Question:** What is the versioning and breaking-change policy for contracts?

- A. **Additive only** — Only additive changes allowed (new optional fields, new endpoints); breaking changes require new version/endpoint
- B. **Semantic versioning** — MAJOR.MINOR.PATCH; breaking = MAJOR bump
- C. **No versioning** — Contracts are immutable once deployed
- X. Other (please specify)

### 5. Error, Timeout, Retry Behaviour
**Question:** What are the timeout, retry, and error behaviour standards at each boundary?

- A. **Standard timeouts** — SSE: 15s proxy timeout, Asset: 10s, Evidence: 90s, Search: 30s; GET retries once after 1.5s on 502/503/504 (SQ3 mitigation)
- B. **Per-contract timeouts** — Each contract defines its own timeouts
- C. **No timeouts** — Infinite wait
- X. Other (please specify)

---

## Confirmation

**Please respond with your choices (A/B/C/X) for questions 1-8.**

[Answer]:
1. A
2. C
3. A
4. A
5. C
6. A
7. B
8. B

---

## Historical Summary Confirmation

**Summary of your choices:**

1. **ContentJobApi → JobStatus (SSE)**: A — SSE via EventSource with Last-Event-ID resume; ContentJobApi provides subscribeJobEvents()
3. **AssetViewer → BFF**: A — Direct img src; BFF proxy handles auth re-check, streams bytes, validates content-type
4. **JobStatus → ContentJobApi**: A — submitJob + polling fallback; submitJob returns jobId, polling via SWR 2s interval
5. **BFF External API**: C — Both Content Jobs API and Asset Delivery endpoints exposed
6. **Error Handling**: A — Standard HTTP errors with JSON body; SSE errors via onerror; polling fallback on SSE failure
7. **Contract Ownership**: B — Consumer owns contract (Consumer defines what they need; provider implements)
8. **Versioning Policy**: B — Semantic versioning (MAJOR.MINOR.PATCH; breaking = MAJOR bump)

**Confirm** — Does this all look correct before I generate the contract summary artifact?

- A. **Looks correct** — Generate the contract summary artifact from these answers
- B. **Request changes** — Revise one or more answers before generation
- X. Other (please specify)

[Answer]: Looks correct

## Current Contract Evidence

The historical questions predate the approved units and component ownership. Their repeated question numbers, event-based idempotency choice, subscription-helper assumption, and unspecified timeout answer are not a current contract baseline. Use the approved three-unit definitions and Domain Design ADR-013, and distinguish observed code from proposed contract changes. Source inspection below is not a running-system test.

| Boundary | Observed source evidence | Contract implication |
|---|---|---|
| Submit/state/result | `backend/modules/summarization/src/summarization/api/router.py:48–193`: POST submit returns 202 with actual job state; state returns jobId/state/error?/resultRef?; result returns only resultRef | Existing frontend types are not canonical; do not invent assetId, progress, 409 replay, or renderable result text in these responses |
| Result identity | `worker.py:84–96` builds `summary/{paperId}/v{version}` or `translate/{paperId}/v{version}/{lang}` after calling orchestrator.run, without capturing its return | These are references, not verified read URLs or full stored-artifact identities; worker completion must be checked against actual outcome |
| Stored result identity | `domain/cache_key.py:74–113` and `service/orchestrator.py:175–242` key content by additional persona, glossary/owner, model/prompt, source and parser dimensions | A client cannot safely reconstruct the exact stored artifact from the current short reference; a job-bound result identity is needed for reliable read-only delivery |
| Existing generation route | `api/router.py:195–220` calls run_summarization; orchestrator.run can generate/enqueue on cache miss | Reusing POST /api/summarize as a result reader would violate the no-new-work requirement; it is not a safe resolver substitute |
| Result expiry | `service/job_service.py:269–282` returns None for expired results; router converts None to 404 | Despite the route docstring mentioning 410, current code does not distinguish expiry from missing results. Do not claim otherwise |
| SSE resume | `api/router.py:134–143` prefers Last-Event-ID header, then lastEventId query, using the final colon-separated integer as sequence | Native reconnect header and recreated-connection query mechanisms exist in backend source; forwarding/framing and runtime behavior still need verification |
| BFF SSE | `frontend/app/bff/[...path]/route.ts:86–113,121–190,265–285` only selects novelty and agent-turn stream branches; stream helper forwards Cookie but not Last-Event-ID | Content-job event requests require a streaming branch and header relay; query forwarding already exists. The 15-second timeout is header acquisition, not total stream lifetime |
| Same-key dispatch failure | `service/job_service.py:119–157` returns retained jobs for normal replay but releases the key when enqueue fails | Same-key recovery can return a new job ID after failed dispatch; this does not restart the old terminal job. Reconcile any absolute existing-job promise before pinning the contract |
| Asset proxy | `frontend/app/bff/[...path]/route.ts:212–262` accepts image responses, collapses failures to 404, relays Set-Cookie on success, and uses fetch without redirect: manual/error | Planned no-redirect and cookie fidelity need explicit implementation changes; comments alone do not guarantee redirect refusal or error-response cookie relay |

The inspected job result route and summarization routes do not expose a verified read-only resolver for the short resultRef. A bounded backend search for summary read routes and these reference shapes also found no compatible resolver. This is a demonstrated integration gap requiring an explicit scope/prerequisite decision, not permission to invent a new backend API silently. An existing authoritative resolver supplied by the human would be checked before proposing additional implementation.

### Q10. Handle the Backend Result-Delivery Gap

How should we address the missing verified read-only result delivery required by the approved skeleton?

- A. **Include bounded backend remediation in this intent** — Prepare a scope/design amendment for job-bound exact result identity and authorized read-only delivery, including accurate worker outcome/expiry semantics. Reconcile affected upstream requirements and unit boundaries through their normal approvals before treating the new contract as implementation authority. Review same-key dispatch-failure behavior explicitly; preserve no forced terminal restart. This keeps the skeleton deliverable together, but expands the frontend-only work.
- B. **Keep backend remediation as a separate prerequisite** — Continue specifying frontend contracts against an explicitly blocked result-delivery prerequisite. U1 implementation and the full skeleton cannot be declared ready until that backend contract is delivered and verified; do not weaken result viewing into a reference-only display.
- C. **Use an existing resolver** — Supply its route or source location so it can be verified for authorization, exact result identity, expiry, and read-only behavior.
- X. Other (please specify)

Recommendation: A, bounded to the verified job/result integration gaps and followed by explicit upstream reconciliation. This choice authorizes design/scoping work, not immediate application-code generation.

[Answer]: A. Include bounded backend remediation in this intent

## Bounded Scope Amendment Proposal

Human authorization: "Include bounded backend remediation in this intent". The following is the proposed amendment for upstream requirements/design reconciliation, not an approved replacement contract or implementation claim.

- **Exact completed-result identity:** Bind each completed summarize/translate job to the actual prepared artifact or persisted result snapshot produced for that job, with owner and expiry enforced. Do not reconstruct identity from the short paper/version reference or mutable current persona/glossary/model settings. Persist the successful result binding before publishing COMPLETED with a readable result; a crash or missing binding cannot fabricate successful delivery.
- **Authorized read-only delivery:** Provide renderable result content through an owner-checked, TTL-bounded job result contract using the existing BFF/gateway path. Prefer an additive extension of the existing job result response if compatibility permits, retaining resultRef for existing consumers. Contract Design pins exact response/schema details after upstream approval. Reads never invoke generation/enqueue, re-run the orchestrator, or guess a storage URL. Legacy/unresolvable references yield a controlled unavailable result, not automatic regeneration.
- **Accurate worker outcomes:** Inspect the actual orchestrator outcome before mapping it to terminal job state. COMPLETED must correspond to successful prepared content; explicit abstention and unsuccessful/unavailable outcomes must not be misreported as completed content. Preserve legal state transitions and idempotent processing; constrain worker changes to correctness of this job/result path. Final DTO/state mapping and crash/redelivery behavior require contract-level verification.
- **Expiry and denial:** Keep owner verification before result availability/expiry disclosure. Propose 401 for unauthenticated requests, indistinguishable 404 for absent/not-owned jobs, and 410 only for an authenticated owner's known expired result. Do not claim the current backend already emits 410; its current expiry is folded into 404. Confirm this proposed distinction with the amended requirements summary. Both reference and content reads must honor expiry; a state response must not provide an alternate unbounded content capability.
- **Same-key recovery:** Pin the dispatch-failure exception explicitly through Q11 below. Continue to prohibit changed-parameter retry, key rotation to force execution, and restarting an old terminal job. ContentJobApi, the pre-job submission surface, and parent handoff must preserve the actual identity/state returned by the backend.
- **Verification:** Add backend regression evidence for exact result binding, owner isolation, TTL, unsupported/legacy references, successful versus non-success worker outcomes, and zero generation/enqueue during reads; include applicable existing-suite/coverage checks. Retain the full integrated submit → SSE → readable result skeleton and frontend security/accessibility obligations. SSE framing, BFF streaming/cursor/cookie fidelity and asset redirect handling remain verified integration work, not reasons to declare the backend ready.

### Affected Approved Artifacts

| Stage | Amendment required |
|---|---|
| Requirements Analysis | Revise frontend-only intent framing/constraint at requirements.md lines 11 and 145; strengthen FR3.1–FR3.3 with exact result, read-only and expiry behavior; add explicit job-outcome/result-binding acceptance under FR2/FR3; reconcile FR1/FR4 recovery wording for selected dispatch-failure semantics. Preserve stable existing IDs and label any additional IDs with this human-authorized origin. |
| User Stories | Reconcile US3.1/US3.3 result behavior, US2.2 outcome accuracy, US1.1/US4.2 identity recovery, and backend acceptance/traceability. Keep US4.3 excluded. |
| Refined Mockups | Reconcile unavailable/expired result and dispatch-recovery feedback against the selected semantics; preserve the separate submission/read-only-result split and ADR-013 handoff. |
| Domain Design | Add bounded backend result-binding/delivery/worker ownership and trust boundaries rather than hiding those changes in the frontend API client. Preserve historical ADRs and document supersession/extension. |
| Units Generation | Reconcile U1's executable/backend scope, component change responsibility, tests, relative size and shared-source constraints. Keep the approved three-increment intent unless evidence requires a separately approved boundary change; do not introduce an unapproved fourth unit. |
| Contract Design | Replace historical guesses with verified existing wire behavior and explicitly approved new result contract. Preserve distinctions between current implementation and required remediation. |

No cancellation API, additional task types, terminal restart feature, new deployment architecture, or replacement generation pipeline is proposed. Application code remains a later Construction deliverable after the amended design is approved.

### Q11. Same-Key Recovery After Queue Dispatch Failure

The current service releases an idempotency binding when enqueue fails (`service/job_service.py:128–157`). The failed job remains terminal, but a later explicit unchanged-request submission can create a replacement job under the same key. Normal replay with a retained binding returns the original job. This is different from restarting an executed terminal failure.

- A. **Preserve the dispatch-failure exception** — Keep this backend behavior and document it precisely: unchanged recovery may return a replacement identity after the failed dispatch released its key. The UI adopts the actual returned job/state and accurately describes a new submission after dispatch failure, without claiming the old job restarted. Tests distinguish ordinary replay, failed dispatch, and executed terminal failure. This avoids adding an unrelated idempotency-policy change to result remediation.
- B. **Retain failed-dispatch key bindings** — Change backend policy so same-key recovery always returns the retained failed job, including dispatch failures. This matches strict lookup-only recovery but removes same-key recovery from queue-dispatch failure; any later restart mechanism would need separate authorization. Include the policy change and concurrency regression tests in the bounded amendment.
- X. Other (please specify)

Recommendation: A. Preserve established dispatch recovery and correct the overbroad existing-job wording while retaining the prohibition on terminal-job restart and changed-parameter retry.

[Answer]: A. Preserve the dispatch-failure exception

## Resumption After Approved Backend Amendment

Requirements, 28 active stories, refined mockups, fifteen-component Domain Design and the amended three-unit plan are now approved. U1 owns controller/service/worker plus required adapter remediation; ContentJobService owns exact prepared-result identity and restricted reads. The questions below pin contract choices within that approved scope, not a new frontend-only readiness assumption.

Additional source observations:

- `domain/models.py:309–404` exposes successful payloads and abstain/pending/cost_degraded/source_unavailable outcomes. `service/orchestrator.py:376–386` caches a shared translation base but returns personalized rendered content. The job snapshot must capture the final returned safe payload, not merely serialize a base TranslationDraft or rerender using today's glossary.
- `adapters/rds_jobs.py:377–403` stores an effect claim then can delete it on release. A claim does not encode whether remote generation completed or whether the exact final output was durably captured. Therefore it cannot by itself support safe automatic regeneration after an ambiguous crash.
- `backend/wiring.py:477–482` constructs the job service with a no-op enqueue callback. The inspected `real_wiring.py:165–178` supplies a ContentJobQueue to the generation pipeline but does not replace that callback; `adapters/content_job_queue.py:55–83` separately submits then sends SQS for the older generation entry path. Pin a single real durable-job dispatch path and avoid recursive submission or duplicate dispatch. This is U1's already allocated queue-integration work; runtime dispatch has not been verified.
- The queue bridge and worker use `task` values while the public job API uses `taskType`; Contract Design must explicitly map existing supported values and retain owner/job identity across the versioned payload. No additional task types are introduced.

### Q12. Renderable Result Response

How should the job result path deliver the exact prepared content while supporting existing reference consumers?

- A. **Extend the existing result response** — Keep GET `/bff/api/content-jobs/{jobId}/result` and retain `resultRef`; add a versioned prepared-result envelope containing job identity, task and the final safe summary/translation payload. New clients require the envelope for rendering; reference-only legacy responses are unavailable/unsupported, never a generation trigger. Existing consumers must be tested for tolerance of added fields, with coordinated backend/worker/frontend rollout.
- B. **Add a separate content-read endpoint** — Preserve the reference response and introduce an owner/TTL-checked job-scoped content route under the same BFF API. This isolates legacy response shape but adds a second read contract and round trip; both routes must enforce ownership/expiry and zero generation.
- X. Other (please specify)

Recommendation: A, with explicit version compatibility and legacy-response behavior rather than assuming additive fields are harmless to every existing consumer. A compatibility failure discovered in tests requires adjustment before release.

[Answer]: A. Extend the existing result response

### Q13. Ambiguous Generation After Worker Interruption

How should a job resolve when durable evidence cannot establish whether generation completed and no exact prepared result can be recovered?

- A. **Fail safely without regenerating** — Persist effect-start intent before calling generation. On interruption, resume from an already durable exact result when possible; if completion is uncertain and no exact result exists, do not invoke generation again. Once the previous worker's publication authority is fenced and reconciliation settles the ambiguity, record a user-safe FAILED outcome with no automatic retry and keep the job/key binding. A merely delayed active worker is not immediately failed. Exact lease/fencing and reconciliation timing are specified in the contract/design. This favors no duplicate generation over guaranteeing a result after every crash.
- B. **Require recoverable generation output** — Keep contract completion blocked until a verified provider or pipeline mechanism can recover the exact original output without issuing another generation attempt. This retains the no-duplicate requirement but may require further explicitly approved backend work; no provider capability is assumed.
- X. Other (please specify)

Recommendation: A as the bounded policy consistent with the approved controlled-failure outcome. This is separate from the preserved enqueue-failure key-release exception: an ambiguous generation attempt has already crossed the effect boundary, so its binding must not be released to force another job.

[Answer]: A. Fail safely without regenerating

## Consolidated Contract Plan

The two selections above were supplied together as "Result 1, interruption 1". Approved requirements, stories, mockups, domain ownership and unit allocations now replace the contradictory historical contract questionnaire. The following concrete plan is proposed for consolidated confirmation before generating contract-summary.md.

| Contract | Provider/owner | Consumer | Mechanism and boundary |
|---|---|---|---|
| C1 Job submission/state | U1 | Browser and U2 frontend extension | HTTP/OpenAPI over BFF/gateway; actual identity/state and safe errors |
| C2 Exact prepared-result read | U1 | Browser and U2 result UI | Existing HTTP result endpoint with additive versioned envelope |
| C3 Job events/resume | U1 | Native EventSource in U1/U2 | SSE frame/event schema, replay cursor and polling reconciliation |
| C4 Recovery and read-only UI capabilities | U1 | U2 | Shared typed model for immutable original request, actual job handoff and restricted query callbacks |
| C5 Asset delivery and paper context | U3 for asset behavior; U1 for shared context/proxy conventions | Browser and U3 document/viewer integration | HTTP image contract plus shared owner/paper context model |
| C6 Queue dispatch payload | U1 API/service | Existing U1 worker runtime | Versioned message schema and owner/job/task verification |
| C7 Worker outcome and durable reconciliation | U1 ContentJobService | U1 ContentJobWorker/controller | Command/query port contract for effect fencing, prepared results and terminal publication |
| C8 Cross-runtime compatibility | U1, with consumer agreement from U2/U3 | Existing API/worker/frontend releases | Version/capability schema and compatibility matrix, not a new service |

### Proposed Formal Semantics

- Keep submit/state paths, task types and established terminal vocabulary. The browser sends a deterministic key in the existing request body and never a trusted principal. Map public `summarize` to the pipeline's existing summary task value explicitly. Wire real enqueue exactly once per authoritative dispatch operation rather than using the assembled no-op callback or recursively calling the old submit-then-send adapter. Preserve the approved failed-dispatch key-release exception, with actual returned identity/state and no forced terminal restart.
- Extend `/result` with `resultRef` retained plus a versioned prepared-result envelope identifying the job/task and final safe summary/translation payload. Persist the final owner-specific rendered output, not a shared translation base or current-settings recomputation. New clients treat reference-only legacy success as unsupported/unavailable, never as authority to generate. Raw storage keys and server-only generation metadata do not become public fields. Exact spec fields and payload branches will be written in the contract document.
- Result authorization precedes disclosure: 401 unauthenticated, indistinguishable 404 unknown/not-owned, 410 owner-known expired. Known-owner not-ready/unresolvable results use controlled unavailable outcomes with safe reason codes distinguished from transient 503 failures. Read retries never submit/enqueue/generate; read-side transient errors remain recoverable without restarting terminal jobs.
- Pin actual SSE delimiters, stable per-job event ordering and replay. The inspected RDS adapter serializes database event_id but filters by seq (`adapters/rds_jobs.py:99–115,239–260`), so parsing an arbitrary event ID as sequence is unsafe. Treat cursor IDs as opaque in the browser; the server resolves a supplied ID against the authorized job's event history, with explicit adapter-compatible handling of existing cursors. Header precedence over lastEventId query is retained. Pin invalid/unknown cursor behavior and expose a compatible ordering watermark for state/event reconciliation; do not guess event ordering from state names or timestamps alone.
- Preserve per-hop defaults: ordinary gateway requests 10 seconds; asset relay 10 seconds; SSE response-header acquisition 15 seconds, not total stream lifetime. Ordinary idempotent GET relay has at most one retry after 1.5 seconds for network/502/503/504; POST is not automatically retried. Streaming reconnect is separate from JSON retry; SWR fallback remains a fixed two-second configured interval, with obsolete reads cancelled/ignored and no overlapping stale updates. Existing unrelated evidence/search budgets are not changed.
- Preserve asset same-origin paths and version query handling, server authorization/license checks, private 60-second cache, content-type validation and explicit refusal to follow/relay redirects. Forward Cookie and relay separate Set-Cookie values on success and errors. The browser's image error remains generic unless a verified session/response supplies more information; no new authorization-probe endpoint is added.
- Preserve existing queue runtime and configure one versioned job-bound payload. Worker loads authoritative job input/owner/task rather than trusting duplicated message fields, rejects mismatches and does not execute unsupported tasks. A worker receiving a job before durable acceptance is settled defers execution instead of racing legal state transitions. Compatibility explicitly covers old queued messages and prevents old workers from consuming new semantics before rollout readiness.
- Worker outcome mapping: validated successful final payload can become COMPLETED only after durable binding; explicit abstain becomes ABSTAINED; cost-degraded, source-unavailable, unexpected pending-with-enqueue-disabled, malformed result and execution failures become safe non-completed outcomes using the existing legal lifecycle. Exact codes and retry metadata are specified without promising restart of an executed terminal job.
- Persist effect-start intent before invoking generation. Active execution has renewable, server-authoritative publication ownership; expired ownership alone is not permission to generate again. A fencing/compare-and-set decision prevents an old worker from publishing after takeover. Reconciliation resumes terminal publication from an existing exact durable result, or records a controlled FAILED outcome when generation is ambiguous and no exact result exists. Keep that job/key binding and forbid blind effect release or re-execution. Cover all four interruption windows and acknowledgement/redelivery idempotency. Physical persistence implementation and lease tuning remain Functional/NFR Design work, but the durable operations, fencing requirements and outcomes are contract obligations.
- Contract governance: U1/U3 maintain the provider specifications while consumers define acceptance needs and agree to breaking changes. Preserve the previously selected semantic versioning for specifications; additive optional fields require compatibility tests, and incompatible major changes require an explicit version boundary/migration rather than silent shape changes on a live route. Deployment Planning pins staged capability/exposure, migration and rollback steps; existing runtimes are not assumed atomic. No extra deployment architecture is proposed.

## Historical Contract Plan Confirmation

Confirm the selected additive result envelope and fail-safe interruption policy, together with the eight-contract plan and proposed formal semantics above. The generated document will distinguish current source behavior from required U1/U3 changes and list any unresolved implementation parameters with accountable downstream ownership. It must not claim runtime validation, exactly-once remote generation, or a working skeleton merely because the contracts are written.

Does this all look correct before I generate the contract summary artifact?

- Looks correct
- Request changes

[Answer]: Looks correct

## Recorded Recovery Decisions — Narrow C2 Correction

The current attempt follows the human's exact response **"Q3: 1, Q4: 2."**, recorded on 2026-10-05 in `../../construction/u1-job-skeleton/code-generation/code-generation-questions.md` Q3/Q4 and the canonical audit shard. Those selections are:

- **Q3:** `A. Reopen Contract Design for the narrow correction`.
- **Q4:** `B. Prepare an isolated-bootstrap plan`.

The existing `contract-summary.md` is the starting point, with the recorded reuse decision `modify`. Prior Q10–Q13 decisions and approved Unit/component/requirement boundaries remain inputs. No answered product, hosting or staging choice is reopened here. The old confirmation above is retained as history; it does not confirm this amended content or the current attempt.

### Verified C2 Mismatch

| Source | Observed shape | Consequence |
|---|---|---|
| `contract-summary.md`, OpenAPI `SummaryContent.summary.reproducibility` | `type: string` | Rejects the actual successful DTO's reproducibility object |
| `shared/dtos/summarization.schema.json#/$defs/Reproducibility` | Object; required string `code` and `data`; `additionalProperties: false` | Existing shared shape retains both availability statements |
| `backend/modules/summarization/src/summarization/domain/models.py`, `SummaryDraft` and `SummaryResultDTO.to_dict()` | `dict[str, str]` preserved as `summary.reproducibility` | Flattening to text would change the prepared content rather than correct the specification |

An isolated read-only check instantiated the actual `SummaryResultDTO` with synthetic content and reproduced the defect against the complete current result envelope: the object was rejected and flattened text was accepted. Changing only that schema property **in memory** to the shared reference accepted the actual DTO envelope and rejected seven malformed complete envelopes: string, missing code, missing data, non-string code, null data, extra object field and array. The previously corrected translation envelope still passed, while its five malformed/wrapper cases remained rejected. All six existing YAML blocks parsed. No contract or shared schema was written by that check; no database, queue, provider or browser execution was tested.

### Proposed Contract Amendment

- Replace only the C2 reproducibility property with the resolving reference `../../../../../../../shared/dtos/summarization.schema.json#/$defs/Reproducibility`, retaining the Markdown document's base URI when extracting the OpenAPI block.
- Preserve the actual `code` and `data` strings exactly in the immutable prepared content. Missing, malformed or legacy string-only values do not acquire success through guessed defaults, concatenation or current-settings regeneration.
- Add a synthetic complete prepared-summary v1 envelope and the seven negative reproducibility substitutions above. Check those fixtures and the existing complete translation fixtures against `ResultResponse`, with resolved local/shared references and date-time format checks.
- Retain `preparedResult.schemaVersion: 1`, `resultRef`, task mapping, owner-first 401/404/409/410/422/503/504 behavior, fixed expiry, exact personalization and zero generation/enqueue during reads. This corrects an undeployed specification defect to the existing DTO shape; deployed-consumer compatibility still requires actual tests.
- Preserve the eight contracts and current Unit/task/requirement/deployment boundaries. Obtain the new contract review/approval, then revalidate affected delivery and U1 designs through their normal route. Preserve partial application source and the immutable dirty-source baseline while reconciling migration admission and implementation-plan authority.

## Proposed Isolated PostgreSQL Bootstrap Plan

**Purpose:** Prepare an owned, disposable real PostgreSQL realm for U1's required schema/owner-lifecycle checks and the separately guarded later purge lane. This is Q4's planning deliverable. Resource/rule application and fixture mutation require their own operational authorization and actual qualification evidence.

**Accountable operator:** `revenantonthemission`.

### Current Availability and Qualification

Read-only observations on 2026-10-05 found Docker context `colima`, Docker server 29.5.2 on Linux arm64, and the locally present image `docsuri/postgres-alpine-16.15-nosu@sha256:ccbe2a110992a5b602afdd4a28a45f184de67308d4e80284c0b2329a10cb0e2e`, configured to run as `postgres`. These observations establish availability only, not isolation or operational admission.

`ops/platform-integrity/sbom-targets.json` labels that image `CANDIDATE_PENDING_OPERATOR_MAINTENANCE_WINDOW`, with unresolved High `CVE-2026-85091` in zlib. Its prior test evidence is not a U1 realm receipt. The PostgreSQL pin in `backend/docker-compose.yml` is separately listed as superseded/rejected. Do not bootstrap the U1 realm from the production compose file or infer approval from the presence of either image. Qualification must resolve the actual image/runtime closure under the existing policy before application. The operator's authorization must name the admitted digest and the exact local context.

The database-only phase needs no MinIO, broker, inference, browser or external HTTPS path. Their separate unresolved artifact/control requirements continue to block the later real skeleton; a PostgreSQL-only success cannot close them.

### Proposed Ordered Procedure

| Step | Preparation/application action | Required evidence or stop condition |
|---|---|---|
| P1 | Review and authorize the concrete launcher, admitted image/dependency digests, `colima` guest/context identity, resource limits, test source snapshot, named network/volumes, credentials channel and teardown scope | All actual values must be supplied before application; no placeholder command, unresolved blocking artifact finding or production-source operation |
| P2 | Inventory existing guest workloads and effective IPv4/IPv6 filtering read-only; select a non-overlapping private CIDR and fresh run-specific realm token | Record exact collision-free identities and available resources; a context name alone is not workload isolation |
| P3 | Create one fresh internal-only database network, dedicated PostgreSQL cluster/volume and nonprivileged test workload; publish no database or test ports | No host networking, production volume/home/credentials, container socket or workload NET_ADMIN; source is an isolated read-only copy, with a separate temporary test-output area |
| P4 | Apply reviewed guest forwarding/host-input rules scoped to those exact U1 identities before admitting test workloads | Preserve existing workloads/rules; deny direct external, host, LAN, production and link-local routes; deny unsupported address families rather than claiming parity |
| P5 | Generate independent bootstrap credentials through the protected operator channel; create `docsuri_u1_authority_<realm_token>` and a distinct `docsuri_u1_purge_<realm_token>` database with separate bounded roles | Fresh cluster only; test roles have no SUPERUSER/CREATEDB/CREATEROLE/BYPASSRLS or cross-database connect/administration authority; private credential values are never written to source, public evidence or chat |
| P6 | Install an operator-owned `public.u1_test_realm` singleton marker in each database; grant the test role read access but not marker mutation | The authority database starts with no other public tables, matching the existing fixture's empty-realm check. The purge database remains a separate minimal-schema target, not a reuse of the full authority/race schema |
| P7 | Independently measure allowed test-workload → exact authority database access and denied external/host/LAN/production/direct-egress/unsupported-family paths; inspect mounts, effective rules and privilege/credential boundaries | Save raw observations, workload/network/image/rule identities and hashes. Produce no `verified` flag without its corresponding real probe; failure leaves the realm unadmitted |
| P8 | The protected launcher emits bounded read-only public manifest/receipt files from those observations, supplies their trusted hashes through a channel the test workload cannot replace, and binds the exact workload hostname, realm and database endpoint | Run-specific validity ends by the authorized run's end; configuration, image, address, rule or workload changes invalidate proof and require new qualification. The fixture cannot issue its own evidence |
| P9 | Run the existing manifest/receipt validation and a separate read-only database identity probe before opening a mutation-capable connection; recheck identity on that later connection | Match `current_database()`, `current_user`, `inet_server_addr()`, port, marker and role flags. Missing/expired/mismatched documents, wrong endpoint/role/marker or mutable trust files fail before DDL/delete |
| P10 | After the C2 and narrow migration-admission repair have current approval, execute only the implemented U1 schema and owner-lifecycle tests in the isolated frozen development closure | Preserve registered script identity/digest/current-authority protections. No raw 003 execution to bypass rejected admission; required missing-prerequisite cases fail rather than skip |
| P11 | Record source/artifact/realm identity, exact command, exit code, counts, zero-skips status and safe diagnostics; keep actual acceptance distinct from local guard-unit checks | Do not run the retained destructive root purge fixture yet: its preflight/bridge adaptation belongs to Steps 15–16. Do not advertise a schema pass as a completed job journey |
| P12 | Stop the test workload, revoke run credentials, remove only the recorded run-specific containers/network/volumes and U1-owned rule entries, and check original workload/rule inventory | Verify exact resource identity before deletion; no global prune, production compose shutdown, shared-broker restart or removal of unrelated rules. Preserve scrubbed evidence and supersede the public receipt |

### Manifest and Launcher Handoff

The current consumer is `backend/modules/summarization/tests/u1_integration/realm.py`, not a new public application API. Its public manifest must include `version: 1`, `unit: u1-job-skeleton`, `environment: u1-staging`, `realm_id`, `workload_hostname`, `internal_network_cidr`, `isolation_receipt_sha256`, `authority_database` and `purge_database`. Authority identity includes `host`, fixed internal `address`, integer `port`, `database` and `role`; the host cannot be localhost or a host-gateway alias. The receipt identifies the same realm/unit/environment, timezone-aware `valid_until` and measured `verified` values `direct_egress_denied`, `host_lan_production_denied` and `unqualified_address_families_denied`.

The launcher additionally binds the exact protected measurement output, workload/network/rule/image identities and source revision; the fixture's three boolean checks alone are not that provenance. The authority test role cannot edit the marker, trust documents, launcher, guest filtering or supplied hashes. Public documents are absolute regular nonsymlink paths, at most 65,536 bytes, not group/other writable, with exact-byte SHA-256 digests. Existing fixture checks are necessary, not a substitute for independent operator/network proof.

| Launcher variable | Bound input |
|---|---|
| `DOCSURI_U1_TEST_REALM_MANIFEST` | Absolute protected public manifest path |
| `DOCSURI_U1_TEST_REALM_SHA256` | Trusted manifest SHA-256, lowercase hex without a prefix |
| `DOCSURI_U1_ISOLATION_RECEIPT` | Absolute protected public isolation-receipt path |
| `DOCSURI_U1_ISOLATION_RECEIPT_SHA256` | Trusted receipt SHA-256, also bound by the manifest |
| `DOCSURI_U1_AUTHORITY_DSN` | Operator-channel secret matching exact manifest host/database/role/port; no inherited production/default DSN or libpq service/options/hostaddr/passfile indirection |
| `DOCSURI_U1_EVIDENCE_DIR` | Owned isolated output destination for source-bound reports; credentials and unsanitized connection errors excluded |

The separate purge connection's exact binding and no-skip runner must be implemented/reviewed with the retained fixture adaptation before that lane is enabled; no guessed purge-DSN variable or current safe-purge claim is introduced here.

**Proposed schema-only command**, from `backend/modules/summarization` in the admitted test workload and already prepared isolated frozen development environment:

```bash
uv run --project ../.. --frozen --no-sync python -m pytest tests/u1_integration/test_migrations.py tests/u1_integration/test_owner_lifecycle.py tests/u1_integration/test_realm_preflight.py -q -rs
```

This command names existing files and is not run by this planning pass. Missing realm prerequisites remain errors. The contract correction, admitted registered migration and measured isolation must be ready first. The later integrated skeleton invocation remains a separately authorized command.

### Alternatives and Operational Risks

- **Selected:** Fresh dedicated real PostgreSQL cluster within the qualified private Linux test boundary, with two independently scoped databases. This permits actual PostgreSQL constraint/deletion proof while keeping the retained minimal-schema purge fixture separate; it requires image/runtime qualification, guest enforcement and protected launcher ownership.
- **Rejected:** Reusing production's loopback database or cloning its credentials/schema into test setup. Endpoint names and a DSN are not disposal authority, and the existing purge fixture's setup is destructive.
- **Rejected:** Fakes, SQLite or self-authored isolation flags as real-schema acceptance. They cannot prove PostgreSQL triggers, commit constraints, role/server identity or the selected network boundary.
- **Shared-host risk:** New guest network/filter/resource changes can affect existing workloads. Apply only after exact reviewed scope/authorization, keep an original read-only inventory, bound resources and have the P12 identity-scoped reversal ready; any unexpected impact stops testing and removes the new U1 paths.
- **Privilege/credential risk:** Bootstrap authority must not be inherited by tests. Separate provisioner/test roles, protected credentials/trust documents, marker-write denial and measured connection/role negatives are admission conditions.

## Consolidated Summary Confirmation

- Correct the single C2 reproducibility field to the existing required `{code: string, data: string}` shared object, preserving exact successful DTO content and preparedResult v1 semantics.
- Add complete summary-envelope fixtures and malformed-object negatives; preserve and rerun the translation-envelope checks. The read-only proposal check has passed two positive envelopes and twelve negative envelopes, with the original defect reproduced; this is not runtime/database proof.
- Preserve previous contract/product/Unit/hosting choices and partial implementation. Obtain the current contract review/approval and revalidate the affected downstream records before resuming U1 application writes.
- Prepare the owned PostgreSQL bootstrap handoff from P1–P12 above, including qualified-artifact prerequisites, separate authority/purge identities, protected proof/hash/credential bindings, the existing schema-only command and scoped rollback. Local image availability and written receipts are not operational admission; resource/rule application waits for the separate concrete authorization and actual evidence.

Does this all look correct before I generate the artifact?

- Looks correct
- Request changes

[Answer]: Looks correct

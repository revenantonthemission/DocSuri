# Requirements Analysis Questions — Phase 7 Frontend Wiring

**Gate:** Product Lead Review (advisory)

## Sources

- [desc] Initial description: "Phase 7 frontend wiring for durable content jobs: wire JobStatus component with SSE, replace AssetViewer presigned redirect with same-origin delivery, route contentJobApi through BFF, mount components in detail page"
- [scope] Workflow-selected scope: `feature`.
- [memory:M1] `aidlc/spaces/default/memory/team.md#Testing Posture`: "Methodology: test-after, Ordering: Test-last per component"
- [memory:M2] `aidlc/spaces/default/memory/team.md#Walking Skeleton`: "Stance: ON — Build a thin end-to-end slice first"
- [memory:M3] `aidlc/spaces/default/memory/team.md#Deployment`: "Continuous deployment to production on merge"
- [memory:M4] `aidlc/spaces/default/memory/project.md#Mandated`: "ALWAYS route all content-job API calls through `/bff/api/content-jobs/*` (SEC-8)"
- [memory:M5] `aidlc/spaces/default/memory/project.md#Mandated`: "ALWAYS generate idempotency keys as SHA-256 hash"
- [memory:M6] `aidlc/spaces/default/memory/project.md#Mandated`: "ALWAYS wrap JobStatus in React Error Boundary"
- [memory:M7] `aidlc/spaces/default/memory/project.md#Mandated`: "ALWAYS use same-origin asset delivery via `/bff/api/papers/{paperId}/assets/{assetId}`"
- [memory:M8] `aidlc/spaces/default/memory/project.md#Mandated`: "ALWAYS integrate Sentry for client-side error tracking"
- [memory:M9] `aidlc/spaces/default/memory/project.md#Mandated`: "ALWAYS conduct security review mid-implementation (Week 2)"

---

## Questions for Requirements Completeness

### 1. Functional Requirements — Job Submission
**Question:** What job types should be supported in the initial Phase 7 release?

- A. **Summarize + Translate only** — Backend workers only implemented for these (per Intent Capture Non-Goals)
- B. **All 5 types (summarize, translate, novelty, evidence, ingest_userdoc)** — Frontend supports all, backend handles unsupported gracefully
- C. **Summarize, Translate + Novelty** — Novelty backend stub exists
- X. Other (please specify)

### 2. Functional Requirements — Job Status Display
**Question:** What job state information should be displayed in JobStatus component?

- A. **Minimal: State + Progress %** — SUBMITTED→COMPLETED with percentage
- B. **Standard: State + Progress + Error details + Asset ID** — Includes error type/message, retryable flag, assetId on completion
- C. **Full: State + Progress + Error + Event history + Timestamps** — Includes event history with timestamps (as current JobStatus implements)
- X. Other (please specify)

### 3. Functional Requirements — Retry Behavior
**Question:** When a job fails, what retry options should be available?

- A. **Inline Retry button only** — Re-submits with same idempotency key (per Intent Capture Q6: A)
- B. **Retry with modified parameters** — Allow user to change params before retry (new idempotency key)
- C. **Both inline + "Retry with changes"** — Default retry uses same key, option to modify
- X. Other (please specify)

### 4. Non-Functional — Security Requirements
**Question:** What security requirements are mandatory for Phase 7?

- A. **SEC-8 + SEC-9 + SECURITY-08 only** — BFF routing, auth re-check, no presigned URLs (per project.md Mandated)
- B. **Above + CSP nonce validation** — Verify CSP nonce on all responses
- C. **Above + Sentry error tracking** — Client-side error tracking integration (per project.md Mandated)
- X. Other (please specify)

### 5. Non-Functional — Observability Requirements
**Question:** What observability features are required for Phase 7?

- A. **Sentry integration only** — Error tracking + performance monitoring (per project.md Mandated)
- B. **Sentry + SSE connection metrics** — Track connection drops, reconnects, latency
- C. **Sentry + SSE metrics + Job lifecycle events** — Full job lifecycle tracking (submitted, completed, failed, retried)
- X. Other (please specify)

### 6. Non-Functional — Performance Requirements
**Question:** What are the performance targets for Phase 7 components?

- A. **SSE connect < 500ms, Asset load < 1s** — Basic targets
- B. **SSE connect < 300ms, Asset load < 500ms, JobStatus mount < 200ms** — Aggressive targets
- C. **No specific targets** — Meet existing budgets (FCP < 1.8s, LCP < 2.5s)
- X. Other (please specify)

### 7. Accessibility Requirements
**Question:** What accessibility standards must Phase 7 meet?

- A. **WCAG 2.1 AA** — ARIA live region, progressbar role, keyboard navigation (per project.md Mandated)
- B. **WCAG 2.1 AA + reduced motion** — Respect `prefers-reduced-motion` for animations
- C. **WCAG 2.1 AA + high contrast** — Specific tokens for forced colors mode
- X. Other (please specify)

### 8. Integration — BFF Routing
**Question:** How should contentJobApi.ts be updated for BFF routing?

- A. **Change API_BASE to `/bff/api/content-jobs`** — Minimal change, all functions use new base
- B. **Create new contentJobApiBff.ts** — Separate file for BFF routing, deprecate old
- C. **Feature flag** — Toggle between old/new routing via env var
- X. Other (please specify)

### 9. Integration — AssetViewer Migration
**Question:** How should AssetViewer component be migrated?

- A. **Props: paperId + assetId** — Direct `<img src="/bff/api/papers/{paperId}/assets/{assetId}" />`
- B. **Props: assetId + token (new token endpoint)** — Keep token pattern but new same-origin token
- C. **Higher-order component** — Wrap AssetViewer with same-origin provider
- X. Other (please specify)

### 10. Walking Skeleton — First Unit
**Question:** What is the smallest working end-to-end slice for the walking skeleton?

- A. **BFF Routing only** — Submit job → get state via polling (no SSE)
- B. **JobStatus SSE + Mount** — Submit → SSE connected → state transitions visible
- C. **Full submit → SSE → COMPLETED → Result** — End-to-end happy path
- X. Other (please specify)

---

## Assumptions Being Carried Forward

| # | Assumption | Source |
|---|------------|--------|
| 1 | Backend `/api/content-jobs/*` endpoints stable (473 tests) | Intent Capture / Feasibility |
| 2 | SSE `Last-Event-ID` implemented in gateway_seam | Feasibility Assumption 2 |
| 3 | BFF proxy operational with principal injection | Feasibility Assumption 3 |
| 4 | AssetViewer presigned logic isolated | Feasibility Assumption 4 |
| 5 | JobStatus component exists, unmounted | Feasibility Assumption 5 |
| 6 | Next.js App Router + BFF configured | Feasibility Assumption 6 |
| 7 | Owner-scoped auth enforced (RJ-AC05) | Feasibility Assumption 7 |
| 8 | Idempotency key: SHA-256 hash(userId:paperId:task:params) | project.md Mandated |
| 9 | Idempotency storage: localStorage | project.md Mandated |
| 10 | Error Boundary on JobStatus | project.md Mandated |
| 11 | Same-origin asset delivery | project.md Mandated |
| 12 | Sentry integration | project.md Mandated |
| 13 | Security review Week 2 | project.md Mandated |

---

## Open Questions for Stakeholder Input

1. **Job cancellation UI:** Should FAILED/ABSTAINED jobs show a "Cancel" button (backend has ABSTAINED state)?
2. **Job history:** Should users see a list of their past jobs (needs GET /content-jobs endpoint)?
3. **Real-time notifications:** Should completed/failed jobs trigger browser notifications?
4. **Offline support:** Should JobStatus queue retries when offline and replay on reconnect?

---

## Confirmation

**Please respond with your choices (A/B/C/X) for questions 1-10.**

[Answer]:
1. A
2. C
3. B
4. C
5. C
6. B
7. A
8. A
9. A
10. C

---

## Previous Attempt Summary

The following summary is retained verbatim as historical context. Its retry and security descriptions conflict with the recorded selections. The user selected **Modify** during recovery on 2026-10-03; the follow-up answers below will resolve these discrepancies before a new consolidated summary is presented.

**Summary of your choices:**

1. **Job Types**: A — Summarize + Translate only (backend workers only for these)
2. **Job Status Display**: C — Full (State + Progress + Error + Event history + Timestamps)
3. **Retry Behavior**: B — Both inline + "Retry with changes" (default same key, option to modify)
4. **Security Requirements**: C — SEC-8 + SEC-9 + SECURITY-08 + CSP nonce validation + Sentry
5. **Observability**: C — Sentry + SSE metrics + Job lifecycle events
6. **Performance Targets**: B — Aggressive (SSE < 300ms, Asset < 500ms, Mount < 200ms)
7. **Accessibility**: A — WCAG 2.1 AA (ARIA live, progressbar, keyboard)
8. **BFF Routing**: A — Change API_BASE to `/bff/api/content-jobs` (minimal change)
9. **AssetViewer Migration**: A — Props: paperId + assetId, direct `<img src="/bff/api/papers/{paperId}/assets/{assetId}" />`
10. **Walking Skeleton**: C — Full end-to-end happy path (submit → SSE → COMPLETED → Result)

**Assumptions Confirmed:** All 13 assumptions from reverse-engineering and project.md mandates carry forward.

**Open Questions Noted:** Job cancellation UI, Job history, Real-time notifications, Offline support — to be addressed in later stages.

**Confirm** — Does this all look correct before I generate the requirements artifact?

- A. **Looks correct** — Generate the requirements artifact from these answers
- B. **Request changes** — Revise one or more answers before generation
- X. Other (please specify)

**Previous confirmation:** Looks correct

## Recovery Follow-Up Questions

### Q11. Retry behavior reconciliation

The original Requirements Analysis Q3 answer is **B**, meaning retry with modified parameters. Its previous summary instead describes **both** unchanged and modified-parameter submission (original option C). Intent Capture Q6 and Refined Mockups Q3 also record an inline same-key Retry action. Which behavior should the recovered Phase 7 requirements specify?

- A. **Inline same-parameter retry only** — Resend the same request with the same idempotency key and recover the existing job. This does not promise that a terminal failed job executes again.
- B. **Retry with changes only** — Let the user modify parameters and submit with the newly derived idempotency key.
- C. **Both actions** — Offer same-parameter resend/recovery and a separate Retry with changes action.
- X. Other (please specify)

[Answer]: A — Inline same-parameter retry only

### Q12. CSP requirement reconciliation

The original Requirements Analysis Q4 answer is **C**, describing the baseline security requirements plus Sentry. Its previous summary also adds CSP nonce validation, which was separately listed in option B. Existing CSP protection must remain in place in either case. Should Phase 7 add an explicit nonce-validation requirement?

- A. **Preserve existing CSP without new nonce-validation scope** — Require BFF routing, asset authorization re-checks, no presigned URLs, and Sentry; retain the current CSP controls.
- B. **Include explicit CSP nonce validation** — Require the same baseline and Sentry, plus verification that the Phase 7 integration preserves nonce-based CSP behavior.
- X. Other (please specify)

[Answer]: A — Preserve existing CSP without new nonce-validation scope

### Q13. Performance acceptance measurement

Original Q6 selects SSE connection under 300 ms, asset loading under 500 ms, and JobStatus mounting under 200 ms. These targets remain unchanged. The saved answer does not specify a test environment, percentile, or asset size, so a reproducible pass/fail check still needs a measurement profile.

For options A and B, the proposed common profile is: p95 across 100 sequential measurements per metric; one active job; an authenticated desktop Chromium session with no CPU/network throttling; an uncached 100 KiB figure image. Measure SSE from EventSource construction to open, asset loading from request start to decoded image readiness, and JobStatus mounting from mount request to first committed status UI. Job execution duration is a separate concern and is not included in these UI latency budgets. These details are proposals pending this answer, not prior decisions.

- A. **Controlled integration benchmark** — Apply the profile to a production frontend build with the real BFF and deterministic local gateway responses. This measures frontend/BFF overhead; deployed network and backend latency are reported separately.
- B. **Staging end-to-end benchmark** — Apply the profile to the production frontend build and real gateway in staging, with the browser runner in the same deployment region. Include the measured network and gateway overhead in the targets.
- X. Other (please specify the environment, workload, percentile, and measurement boundaries)

[Answer]: B — Staging end-to-end benchmark

### Q14. Retained enhancements from User Stories

Source: `inception/user-stories/user-stories-questions.md`, recovery Q8. The user selected **Retain both enhancements**, explicitly requesting requirements for asset zoom/pan and copyable asset IDs before those stories are included. This is the recorded scope decision, not a new question.

[Answer]: Retain both enhancements

Proposed requirement amendment:

- Add **FR3.4**: When an authorized completed result supplies an asset identifier, display it and provide a keyboard-accessible copy action. Copy the identifier exactly; show success only after a successful copy, and give a clear failure state if clipboard access fails. Do not invent an identifier or treat possession of it as authorization.
- Add **FR5.5**: Provide zoom-in, zoom-out, reset-to-fit, and panning for large figures/tables in AssetViewer, with keyboard-accessible controls as well as pointer interaction. Apply the same-origin delivery and authorization requirements to the displayed asset.
- Preserve the existing **US3.2** and **US5.3** story identifiers for these capabilities. Carry the additions into story acceptance criteria, design, and verification without renumbering existing requirements.
- Retain all previously confirmed requirements, including same-key recovery only, existing CSP protection, mandatory Sentry, the staging latency profile, and the full SSE walking skeleton. This amendment does not resolve or reclassify the previously accepted minor review findings.

### Q15. Bounded backend remediation authorized during Contract Design

Source: `../contract-design/contract-design-questions.md`, Q10 and Current Contract Evidence. The human selected the following scope amendment after source inspection found no verified read-only result resolver. This records an existing human decision, not a new selection.

[Answer]: Include bounded backend remediation in this intent

Carry into the amended requirements: exact job-bound result identity, authorized read-only content delivery, accurate worker outcomes, expiry handling, and associated backend regression tests. Replace the frontend-only/no-worker-change constraint only for this bounded remediation. Preserve the original project description verbatim as historical initial intent.

### Q16. Failed-dispatch idempotency exception

Source: Contract Design Q11 and `service/job_service.py:119–157`. The human explicitly chose to retain the current dispatch-failure exception.

[Answer]: Preserve the dispatch-failure exception

Ordinary replay with a retained binding recovers the existing job. If queue dispatch failed and the backend released that binding, explicit unchanged-request recovery may produce a replacement job ID using the same key. The original failed job remains terminal. The UI must adopt and describe the actual returned identity/state without calling it a restart of the old job. A lost response alone is not evidence that dispatch failed; tests and wording must distinguish an uncertain outcome from an established dispatch-failure replacement.

### Proposed Amendment for Summary Confirmation

- Preserve existing identifiers and add **FR2.5** for truthful worker outcomes: successful prepared content and a durable exact job/result binding precede reporting COMPLETED; abstention or unsuccessful/unavailable outcomes cannot be mislabeled as completed content. Verify successful, abstained, failed/unavailable and interrupted-persistence cases, retaining legal state transitions and duplicate-work protections. Contract Design defines the exact mapping of existing DTOs without inventing new lifecycle states.
- Add **FR3.5** for immutable result identity: an authorized read returns the completed job's exact prepared summary/translation, not content recomputed from current persona/glossary/model/source settings or guessed from the short reference. Legacy/unresolvable references produce a controlled unavailable result. Neither missing content nor an expired binding triggers generation/enqueue.
- Clarify **FR3.1–FR3.3**: bounded backend remediation enables the job result read path to deliver renderable content. Proposed response semantics are 401 when unauthenticated, indistinguishable 404 for unknown/not-owned jobs, 410 for the authenticated owner's known expired result, and controlled unavailable handling for unresolved content. Exact additional error mappings and backward-compatible response fields belong to Contract Design. The current implementation's expiry is folded into 404; the proposed 410 distinction is a change, not a verified existing capability.
- Amend **FR1/FR4** wording to preserve Q16's failed-dispatch replacement exception alongside ordinary retained-binding replay. Require truthful identity/state handling and user-safe feedback; no changed-parameter retry, forced key rotation, automatic resubmission loop, or restart of an old terminal job.
- Extend **NFR11** verification to backend result identity, owner isolation, expiry, worker outcomes, dispatch-failure replacement, and proof that reads cause zero generation/enqueue. Keep the existing test-after posture and new-code coverage floor.
- Carry the amendment into stories, mockups, domain ownership, unit scope and contracts through their approval checkpoints. Preserve the selected three-increment direction pending updated backend responsibility/size checks; existing downstream documents remain reference material until reconciled.

## Consolidated Summary Confirmation

This summary carries forward the existing requirements with the human-authorized bounded backend remediation and failed-dispatch exception. The confirmation below applies to this amendment; previously approved documents are not evidence that the new behavior is implemented.

- **Job types (Q1: A):** Phase 7 exposes summarize and translate. Novelty, evidence, and ingest_userdoc execution remain outside this release.
- **Status display (Q2: C):** Show job state, available progress, error details, event history, and timestamps. Integrate JobStatus into the paper-detail workflow; retain the backend state vocabulary.
- **Retry (Q11 and Q16):** Offer explicit unchanged-request recovery with the same key. Retained bindings return the existing job; a key released after failed queue dispatch may yield a replacement identity. Use actual returned identity/state and do not claim the old terminal job restarted. Missing original parameters disable recovery with an explanation; never substitute an edited draft, rotate keys to force execution, or add Retry with changes.
- **Security (Q4: C, clarified by Q12: A):** Route content-job calls through BFF, retain owner-scoped access and asset authorization/license re-checks, eliminate presigned asset delivery, and integrate Sentry. Preserve existing CSP protections without adding a separate nonce-validation requirement.
- **Observability (Q5: C):** Include Sentry, SSE connection metrics, and job lifecycle events. This selected observability scope supersedes the older scope document's exclusion of SSE metrics; it does not introduce a separate dashboard product.
- **Performance thresholds (Q6: B):** SSE connection under 300 ms, asset loading under 500 ms, and JobStatus mounting under 200 ms.
- **Performance verification (Q13: B):** Use the production frontend build and real gateway in staging, with the browser runner in the same deployment region. Network and gateway overhead count toward the targets. Evaluate p95 across 100 sequential measurements per metric, one active job, authenticated desktop Chromium without CPU/network throttling, and an uncached 100 KiB figure image. Measure EventSource construction to open, asset request start to decoded-image readiness, and mount request to first committed status UI. Job execution duration is not part of these UI latency budgets.
- **Accessibility (Q7: A):** Meet WCAG 2.1 AA, including ARIA live status announcements, appropriate progress semantics, and keyboard access.
- **API integration (Q8 and Q15):** Migrate the existing client through `/bff/api/content-jobs`, retaining trusted gateway identity and established submit/state/events behavior. Permit bounded, compatibility-reviewed backend result-delivery/worker corrections needed for the completed-result journey; do not create a bypass client or silently assume existing result references contain text.
- **Backend result correctness (Q15):** Add FR2.5 and FR3.5 as specified above. Bind actual successful prepared content to its job before COMPLETED; preserve exact result identity across later settings changes, owner/TTL checks, truthful non-success outcomes and controlled legacy-reference failure. Reads must never generate or enqueue work. Detailed wire/storage design belongs to subsequent design stages.
- **Result expiry/denial amendment:** Propose owner-checked expiry disclosure: 401 unauthenticated, indistinguishable 404 unknown/not-owned, and 410 for the owner's known expired result. Verify both reference and content paths cannot bypass TTL. This adds the explicit expiry distinction absent from the inspected code.
- **Asset integration (Q9: A):** Use paperId and assetId with same-origin `/bff/api/papers/{paperId}/assets/{assetId}` delivery. Retain the previously accepted private 60-second browser-cache policy and session-cookie forwarding/Set-Cookie relay.
- **Retained enhancements (Q14):** Add FR3.4 for displaying/copying an authorized result's asset identifier with explicit copy success/failure handling, and FR5.5 for accessible zoom-in/out, reset-to-fit, and panning of figures/tables. Preserve US3.2 and US5.3 as their corresponding story identifiers.
- **Walking skeleton (Q10: C):** Prove the integrated submit -> SSE progress -> COMPLETED -> result path first. Unit boundaries and the actual verification command will be defined and approved in their owning stages.
- **Affirmed practices:** Native EventSource with replay/resume support; SWR polling fallback at a fixed 2-second interval; SHA-256 idempotency keys persisted in localStorage; a React Error Boundary around JobStatus; test-after, test-last per component; at least 80% line coverage for new code; existing suites, lint, and typecheck must pass. Retain the recorded mid-implementation AssetViewer security review.
- **Scope boundaries:** Include only the job/result backend remediation described above and its regression evidence alongside the frontend work. Cancellation UI, job-history pages, batch submission, novelty SSE, native/mobile apps, terminal restart, new deployment architecture, browser notifications and durable offline retry queues remain excluded.
- **Evidence limits:** Historical backend/frontend test counts and backend-readiness statements are prior evidence, not fresh test results. Contract compatibility and current test baselines must be checked during subsequent technical work; this summary does not certify that those checks have passed.

Does this all look correct before I generate the requirements artifact?

- Looks correct
- Request changes

[Answer]: Looks correct

# User Stories Questions — Phase 7 Frontend Wiring

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
- [memory:M10] `aidlc/spaces/default/memory/team.md#Testing Posture`: "Ordering: Test-last per component"
- [requirements] `inception/requirements-analysis/requirements.md`: approved recovered baseline, including the confirmed FR3.4/FR5.5 amendment for User Stories Q8. This baseline supersedes conflicting descriptions in the historical story drafts.

---

## PART 1: Planning Questions

### 1. Persona Development Approach
**Question:** How should we define personas for Phase 7? The system serves researchers, students, and casual paper readers.

- A. **Three core personas** — Researcher (power user), Student (occasional), Casual Reader (light) — with distinct goals
- B. **Single unified persona** — "Paper Consumer" with configurable preferences
- C. **Four personas** — Add Librarian/Administrator for content management
- X. Other (please specify)

### 2. Story Format
**Question:** What story format should we use for acceptance criteria?

- A. **Standard Gherkin** — Given/When/Then format for all criteria
- B. **Simple format** — "As a [persona], I want [goal], so that [benefit]" with bullet ACs
- C. **Hybrid** — Standard format with Gherkin for complex scenarios
- X. Other (please specify)

### 3. Story Breakdown Approach
**Question:** How should we break down the 7 feature areas into stories?

- A. **By feature area** — One epic per area (Job Submit, Progress, Completion, Retry, Assets, A11y, Error Boundary)
- B. **By persona** — Stories grouped by who benefits (Researcher, Student, Casual)
- C. **By workflow** — End-to-end flows (Submit→Track→Complete, Submit→Fail→Retry, View Assets)
- D. **By component** — Stories per component (JobStatus, AssetViewer, SummaryModal, ErrorBoundary)
- X. Other (please specify)

### 4. MoSCoW Priority Baseline
**Question:** What should be "Must Have" vs "Should Have" for Phase 7?

- A. **Must: Submit, Progress, Completion, Retry, Assets** — Should: A11y, Error Boundary
- B. **Must: Submit, Progress, Completion, Assets** — Should: Retry, A11y, Error Boundary
- C. **Must: All 7 areas** — All are security/UX critical per project.md Mandated
- X. Other (please specify)

### 5. Story Granularity
**Question:** What level of story granularity is appropriate?

- A. **Coarse** — ~5-7 stories (one per feature area)
- B. **Medium** — ~10-12 stories (split complex areas like Progress into SSE + Polling)
- C. **Fine** — ~15+ stories (split by state transition, error case, edge case)
- X. Other (please specify)

### 6. Walking Skeleton Story
**Question:** Which story should be the walking skeleton (first implemented)?

- A. **Submit → Progress (SSE) → Completion** — End-to-end happy path
- B. **Submit → Progress (Polling) → Completion** — Resilient path first
- C. **Submit → Failure → Retry → Completion** — Error path validation
- X. Other (please specify)

---

## PART 2: Mob Generation Parameters

### 7. Mob Collaboration Style
**Question:** How should the mob (Designer, Developer, QA) collaborate during generation?

- A. **Sequential rounds** — Designer drafts UX stories → Developer sizes → QA writes ACs
- B. **Parallel review** — All three review each story independently, then lead integrates
- C. **Focused expertise** — Designer on UX/A11y, Developer on sizing, QA on testability
- X. Other (please specify)

---

## Confirmation

**Please respond with your choices (A/B/C/D/X) for questions 1-7.**

[Answer]:
1. A
2. A
3. C
4. C
5. C
6. B
7. A

---

## Previous Attempt Summary

Historical summary preserved for provenance. The recovered Requirements Analysis approval supersedes conflicting retry, security, performance, and walking-skeleton descriptions. The user selected Modify for these story artifacts; a fresh consolidated summary is required before rewriting them.

**Summary of your choices:**

1. **Persona Development**: A — Three core personas (Researcher, Student, Casual Reader)
2. **Story Format**: A — Standard Gherkin (Given/When/Then for all criteria)
3. **Story Breakdown**: C — By workflow (Submit→Track→Complete, Submit→Fail→Retry, View Assets)
4. **MoSCoW Priority**: C — Must: All 7 areas (all security/UX critical per project.md Mandated)
5. **Story Granularity**: C — Fine (~15+ stories, split by state transition, edge case)
6. **Walking Skeleton Story**: B — Submit → Progress (Polling) → Completion (resilient path first)
7. **Mob Collaboration**: A — Sequential rounds (Designer → Developer → QA)

**Confirm** — Does this all look correct before I generate the story plan?

- A. **Looks correct** — Generate the story plan from these answers
- B. **Request changes** — Revise one or more answers before generation
- X. Other (please specify)

**Previous confirmation:** Looks correct

## Recovery Planning

- Preserve the three persona archetypes, workflow grouping, Gherkin acceptance criteria, fine-grained stories, and existing identifiers where their meaning remains valid.
- Reconcile US4.2 with same-key resend/recovery: retained bindings recover the existing job; the now-approved failed-dispatch exception may return a replacement identity. Old terminal jobs remain terminal, and the actual returned identity/state governs the UI.
- Retain US4.3's identifier as excluded historical scope, not an active Retry with changes feature.
- Follow the newly confirmed submit -> SSE progress -> COMPLETED -> result walking-skeleton path, superseding the historical polling-only Q6 selection. Polling remains required fallback coverage.
- Extend traceability to all approved FR/sub-requirement and NFR identifiers, including NFR9–NFR12. Keep Sentry mandatory and remove unsupported claims of completed implementation or verification.
- Obtain independent design, development, and quality contributions to the revised draft, with product-led integration and a subsequent product-lead review.

### Q8. Asset-viewing enhancements and result identifier copying

The previous mockup answers requested zoom/pan, and old story US5.3 marks it Must Have. Old story US3.2 also requires a copyable asset ID. The newly approved FR5 specifies secure same-origin figure/table delivery with loading/error states, and FR3 specifies result retrieval; neither explicitly requires these enhancements. How should these older story features be reconciled with the approved baseline?

- A. **Defer both enhancements** — Keep zoom/pan and copyable asset IDs outside this release's required stories; retain their identifiers as deferred historical scope. Keep secure viewing and result retrieval in scope.
- B. **Retain zoom/pan only** — Add an explicit zoom/pan requirement through Requirements Analysis before including US5.3; defer the copyable asset-ID feature.
- C. **Retain both enhancements** — Add explicit requirements for zoom/pan and copyable asset IDs through Requirements Analysis before including both stories.
- X. Other (please specify)

[Answer]: C — Retain both enhancements

## Backend Amendment Story Plan

Source: the newly approved `../requirements-analysis/requirements.md`, including FR2.5, FR3.5 and Requirements Analysis Q15/Q16. This is downstream elaboration of the approved amendment, not a new scope choice. The prior backend-readiness assumption is invalid; bounded backend result remediation is now required work.

- Preserve every existing US/AC identifier and the three persona archetypes. Revise existing submission, recovery and result criteria where the approved semantics changed.
- Add **US2.6 — Receive truthful job outcomes**, anchored to FR2.5: successful prepared content is durably bound before COMPLETED; abstention, unsuccessful/unavailable outcomes and interrupted persistence cannot fabricate completion. Include legal transitions and crash/redelivery duplicate-work protection, with implementation details delegated to Contract/Functional Design.
- Add **US3.4 — Read the exact completed result**, anchored to FR3.5: results retain the job's exact prepared identity despite later settings changes; owner and TTL checks apply to references and content; unsupported/legacy references remain controlled failures; all read outcomes cause zero generation/enqueue.
- Clarify US1.1/US4.2: ordinary retained-binding replay returns the original job; failed dispatch may release the key and allow a replacement. Do not infer dispatch failure solely from a lost response. Preserve immutable original request, owner isolation, explicit action, actual identity/state handoff and no old-terminal-job restart.
- Clarify US3.1/US3.3: renderable authorized content is required; 401 unauthenticated, indistinguishable 404 unknown/not-owned, and 410 only for the owner's known expired result. The latter is required backend remediation, not current-code evidence. Read-only retry never calls generation.
- Carry the prior User Stories recovery-availability concern into explicit acceptance: a retained key without reconstructible original parameters cannot enable resend. Continue to separate initial submission from read-only results and preserve the ADR-013 pre-job recovery behavior as design provenance subject to downstream reconciliation.
- Update sizing/INVEST, dependencies and all **47 requirement IDs** (7 FR groups, 28 FR children, 12 NFRs). Preserve process-evidence assignments for NFR8/NFR11, adding backend regression obligations rather than treating Deferred as optional.
- Refresh designer, developer and quality contributions against the new draft, then obtain independent product-lead review. Prior contribution/review files are history, not current validation.

## Consolidated Summary Confirmation

- **Reuse:** Modify the existing stories, personas, assessment, and traceability map, as requested. Preserve useful stable US/AC identifiers; never reuse an excluded story's identifier for a different feature.
- **Personas (Q1: A):** Retain Researcher, Student, and Casual Reader. Treat invented names, occupations, and usage counts as illustrative persona assumptions, not validated user research or new workload requirements. Accessibility needs can apply to every persona.
- **Format (Q2: A):** Use user/value statements and Given/When/Then acceptance criteria with stable AC identifiers, including happy paths and relevant error/edge cases. Check INVEST explicitly rather than claiming every criterion passes without analysis.
- **Organization (Q3: C):** Group stories by user workflow: submission, progress/recovery, results, asset viewing, accessibility, and failure containment. Include the confirmed operational visibility and responsiveness requirements.
- **Priorities (Q4: C):** All seven approved functional areas remain required. Apply Must Have to confirmed release behavior; preserve US4.3 as Won't Have because Retry with changes is explicitly excluded. Process requirements remain mandatory even when assigned to a named downstream stage.
- **Granularity (Q5: C and approved backend amendment):** Retain the 26 existing active stories and add US2.6 for truthful worker outcomes and US3.4 for exact completed-result reads: 28 active Must Have stories plus excluded US4.3. Keep existing IDs and independently testable Given/When/Then criteria; backend mechanisms remain technical design work.
- **Walking skeleton:** Follow the newly approved submit -> SSE progress -> COMPLETED -> result path, superseding historical Q6's polling-only choice. Polling remains a mandatory resilience path. Do not claim the skeleton is implemented or verified; its executable check still requires later approval.
- **Retry:** Update US1.1/US4.2 for retained-binding replay versus the approved failed-dispatch replacement exception. Use the immutable original request and actual returned job/state; never restart the old terminal job, guess that a lost response means failed dispatch, use edited parameters, or rotate keys. Explicitly handle missing original parameters and preserve pre-job recovery handoff. Keep US4.3 excluded.
- **Retained enhancements (Q8: C):** Keep US3.2 for authorized asset-ID display/copy, now traced to FR3.4, including missing-ID and clipboard-failure cases. Keep US5.3 for accessible zoom-in/out, pan, and reset-to-fit, now traced to FR5.5, preserving same-origin authorization boundaries.
- **Contract fidelity:** Distinguish existing behavior from newly required remediation. Preserve native EventSource and verify recreated-connection cursors. Require exact job-bound renderable results and accurate worker outcomes; no read may generate/enqueue. Preserve owner isolation, storage failures, honest progress, replay/cleanup and controlled legacy-reference failure. Pin approved owner-checked 401/404/410 semantics without claiming the current code already implements them.
- **Observability and performance:** Keep Sentry mandatory; cover SSE drops/recovery/connection latency and job lifecycle events with sensitive-data scrubbing. Retain NFR9's p95 staging profile and strict 300/500/200 ms limits. Carry forward accepted upstream review findings as provenance without claiming they were resolved in the requirements document.
- **Traceability:** Enumerate all approved FR groups, FR sub-requirements, and NFR1–NFR12. Map user-facing obligations to actual story IDs; any Deferred process obligation must name its accountable downstream stage rather than disappear from coverage.
- **Collaboration:** The product lead drafts and integrates. Designer, developer, and quality engineer independently contribute UX, implementability, and testability feedback, followed by the separate product-lead review. Historical contribution files do not establish that this revised draft has been checked.

Does this all look correct before I generate the revised user-story artifacts?

- Looks correct
- Request changes

[Answer]: Looks correct

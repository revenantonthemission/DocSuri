# Scope Definition Questions — Phase 7 Frontend Wiring

**Gate:** Product Lead Review (advisory)

## Sources

- [desc] Initial description: "Phase 7 frontend wiring for durable content jobs: wire JobStatus component with SSE, replace AssetViewer presigned redirect with same-origin delivery, route contentJobApi through BFF, mount components in detail page"
- [scope] Workflow-selected scope: `feature`.
- [memory:M1] `aidlc/spaces/default/memory/org.md#Way of Working`: "We use **trunk-based development**. All work merges to `main` via short-lived feature branches (typically resolved within 1-2 days)."
- [memory:M2] `aidlc/spaces/default/memory/org.md#Testing Posture`: "`feature` scope adds an 80% line-coverage floor and CI execution before merge."
- [memory:M3] `aidlc/spaces/default/memory/phases/ideation.md#Scope Discipline`: "Do not carry forward scope decisions that have not been explicitly approved"

---

## Questions for Scope Definition

### 1. Minimum Viable Scope (Must-Have)
**Question:** What is the absolute minimum scope that delivers user value for Phase 7?

- A. **Core wiring only**: BFF routing + JobStatus SSE + AssetViewer same-origin (no polling fallback, no retry UX)
- B. **Core + resilience**: Core wiring + SSE polling fallback + inline Retry button
- C. **Full scope per Intent Capture**: All 6 success criteria including idempotency keys, error UX, cache headers
- D. **Full scope + observability**: Full scope + SSE connection metrics, error tracking
- X. Other (please specify)

### 2. Capability Prioritization (MoSCoW)
**Question:** Classify each capability as Must/Should/Could/Won't for this feature scope:

| Capability | Must | Should | Could | Won't |
|------------|------|--------|-------|-------|
| BFF routing for contentJobApi | ☐ | ☐ | ☐ | ☐ |
| JobStatus SSE consumption | ☐ | ☐ | ☐ | ☐ |
| JobStatus polling fallback | ☐ | ☐ | ☐ | ☐ |
| JobStatus Last-Event-ID resume | ☐ | ☐ | ☐ | ☐ |
| AssetViewer same-origin delivery | ☐ | ☐ | ☐ | ☐ |
| Idempotency key generation (hash) | ☐ | ☐ | ☐ | ☐ |
| Inline Retry on FAILED | ☐ | ☐ | ☐ | ☐ |
| Asset cache-control headers | ☐ | ☐ | ☐ | ☐ |

### 3. Sequencing Strategy
**Question:** What sequencing preference for implementation?

- A. **Risk-first**: SSE integration (highest risk) → AssetViewer → BFF routing → Polish
- B. **Value-first**: JobStatus mount (visible value) → BFF routing → AssetViewer → Polish
- C. **Dependency-first**: BFF routing (foundation) → JobStatus → AssetViewer → Polish
- D. **Parallel tracks**: All capabilities in parallel via trunk-based short-lived branches
- X. Other (please specify)

### 4. Non-Functional Requirements in Scope
**Question:** Which NFRs are explicitly in scope for this feature?

- A. **Security (SEC-8, SEC-9, SECURITY-08)**: Mandatory — BFF routing, no presigned URLs, auth re-check
- B. **Reliability (SSE resume, polling fallback)**: In scope per Intent Capture Q2
- C. **Performance (80% coverage, lint/typecheck)**: Org standard for feature scope
- D. **Accessibility (WCAG for JobStatus)**: Not explicitly required but Should
- E. **Observability (SSE metrics, error rates)**: Could for future iteration
- X. Other (please specify)

### 5. Out-of-Scope Confirmation
**Question:** Confirm these remain out of scope for Phase 7:

- Novelty/evidence/ingest_userdoc job execution workers
- Novelty SSE stream (`/api/novelty`)
- Job cancellation UI (`/cancel` endpoint)
- Job list/history page (`GET /content-jobs`)
- Mobile app / native integration
- Batch job submission UI

- A. **Confirmed — all out of scope**
- B. **Move Job cancellation to Should** (backend has ABSTAINED state)
- C. **Move Job history to Could** (needs GET /content-jobs endpoint)
- X. Other (please specify)

---

## Assumptions Being Carried Forward

| # | Assumption | Source |
|---|------------|--------|
| 1 | Backend contracts stable (473 tests) | Feasibility Assessment |
| 2 | SSE Last-Event-ID implemented in gateway_seam | Feasibility Assumption 2 |
| 3 | BFF proxy operational with principal injection | Feasibility Assumption 3 |
| 4 | AssetViewer presigned logic isolated | Feasibility Assumption 4 |
| 5 | JobStatus component exists, unmounted | Feasibility Assumption 5 |
| 6 | Next.js App Router + BFF configured | Feasibility Assumption 6 |
| 7 | Owner-scoped auth enforced (RJ-AC05) | Feasibility Assumption 7 |
| 8 | Idempotency key: hash(userId, paperId, task, params) | Intent Capture Q5: B |
| 9 | Error UX: Inline Retry with same key | Intent Capture Q6: A |
| 10 | Asset cache: 60s private cache | Intent Capture Q7: A |
| 11 | SSE fallback: Fixed 2s polling | Feasibility Open Q1: C |
| 12 | Idempotency storage: localStorage | Feasibility Open Q2: C |
| 13 | Asset cache sufficient: 60s private | Feasibility Open Q3: B |
| 14 | Error boundary: Wrap JobStatus | Feasibility Open Q4: B |

---

## Open Questions Requiring Input

1. **Sequencing preference**: Risk-first vs Value-first vs Dependency-first?
2. **Polish items**: Accessibility audit, observability hooks — in scope or next iteration?

---

## Confirmation

**Please respond with your choices for questions 1-5.** For Q2, list MoSCoW classification (e.g., "All Must except polling fallback=Should, cache headers=Could").

[Answer]:
1. D
2. BFF routing=Should, JobStatus SSE=Must, Polling fallback=Could, Last-Event-ID=Should, AssetViewer=Should, Idempotency=Should, Inline Retry=Must, Cache headers=Could
3. A
4. C
5. A

---

## Consolidated Summary Confirmation

**Summary of your choices:**

1. **Minimum Viable Scope**: D — Full scope + observability (SSE metrics, error tracking)
2. **MoSCoW Prioritization**:
   - Must: JobStatus SSE consumption, Inline Retry on FAILED
   - Should: BFF routing, Last-Event-ID resume, AssetViewer same-origin, Idempotency key generation
   - Could: JobStatus polling fallback, Asset cache-control headers
   - Won't: (none specified)
3. **Sequencing Strategy**: A — Risk-first (SSE integration → AssetViewer → BFF routing → Polish)
4. **NFRs in Scope**: C — Performance (80% coverage, lint/typecheck) as org standard
5. **Out-of-Scope**: A — All confirmed out of scope (novelty workers, novelty SSE, cancellation, history, mobile, batch)

**Open Questions Addressed:**
- Sequencing: Risk-first (SSE highest risk first)
- Polish: Accessibility/observability not in scope for this iteration

**Confirm** — Does this all look correct before I generate the artifact?

- A. **Looks correct** — Generate the artifact from these answers
- B. **Request changes** — Revise one or more answers before generation
- X. Other (please specify)

[Answer]: Looks correct
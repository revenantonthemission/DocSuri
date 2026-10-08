# Approval & Handoff Questions — Phase 7 Frontend Wiring

**Gate:** Product Lead Review (advisory) + Delivery Lead Approval

## Sources

- [desc] Initial description: "Phase 7 frontend wiring for durable content jobs: wire JobStatus component with SSE, replace AssetViewer presigned redirect with same-origin delivery, route contentJobApi through BFF, mount components in detail page"
- [scope] Workflow-selected scope: `feature`.

---

## Questions for Initiative Approval

### 1. Initiative Brief Approval
**Question:** Does the initiative brief accurately capture the Phase 7 frontend wiring scope, approach, and success criteria?

- A. **Yes, approve as written** — Brief is complete and accurate
- B. **Minor edits needed** — Update specific sections (specify)
- C. **Major revision needed** — Scope or approach needs rework
- X. Other (please specify)

### 2. Scope Boundary Confirmation
**Question:** Is the in-scope / out-of-scope boundary correct for this feature?

- A. **Yes, boundary is correct** — Must/Should/Could items properly classified
- B. **Move polling fallback to Must** — Resilience is critical
- C. **Move Error Boundary/Accessibility to Must** — Production quality bar
- D. **Add Job Cancellation to Should** — Backend has ABSTAINED state
- X. Other (please specify)

### 3. Sequencing Strategy
**Question:** Is risk-first sequencing (SSE → AssetViewer → BFF → Polish) the right approach?

- A. **Yes, risk-first** — Mitigate SSE integration risk first
- B. **Switch to dependency-first** — BFF routing first as foundation
- C. **Switch to value-first** — JobStatus mount first for visible progress
- D. **Parallel tracks** — All capabilities simultaneously
- X. Other (please specify)

### 4. Team & Timeline
**Question:** Is the proposed team composition and 6.5-day timeline realistic?

- A. **Yes, confident** — Team velocity supports this
- B. **Add 1-2 day buffer** — SSE integration uncertainty
- C. **Reduce scope** — Drop Should/Could items
- D. **Add 1 more Frontend engineer** — Workload distribution
- X. Other (please specify)

### 5. Security Review Plan
**Question:** Is the mid-implementation security review (Week 2) sufficient for SEC-8/SEC-9 sign-off?

- A. **Yes, mid-review + final sign-off** — Review U4 implementation, final approval pre-merge
- B. **Early review only** — Design review Week 1, no mid-review needed
- C. **Continuous review** — Security reviewer in daily standups
- D. **External audit required** — Third-party security assessment
- X. Other (please specify)

### 6. Handoff to Inception
**Question:** Are the artifacts and context sufficient for the Inception phase to begin?

- A. **Yes, ready for Inception** — All ideation artifacts complete
- B. **Add technical spike results** — SSE reconnection POC needed first
- C. **Add backend contract docs** — Formal API spec for reverse engineering
- D. **Wait for security pre-review** — SEC-8/SEC-9 pre-approval before Inception
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
| 8 | Idempotency key: hash(userId+paperId+task+params) | Intent Capture Q5: B |
| 9 | Error UX: Inline Retry + error details expandable | Rough Mockups Q3: C |
| 10 | Asset cache: 60s private cache | Intent Capture Q7: A |
| 11 | SSE fallback: 2s fixed polling | Feasibility Open Q1: C |
| 12 | Idempotency storage: localStorage | Feasibility Open Q2: C |
| 13 | Asset cache sufficient: 60s private | Feasibility Open Q3: B |
| 14 | Error boundary: Preserve last SSE state | Rough Mockups Q5: B |
| 15 | JobStatus visual: Progress bar + live indicator | Rough Mockups Q1: A |
| 16 | JobStatus mount: Below action buttons | Rough Mockups Q2: A |
| 17 | AssetViewer: Zoom/pan controls | Rough Mockups Q4: C |
| 18 | Accessibility: ARIA live + progressbar | Rough Mockups Q6: A |

---

## Confirmation

**Please respond with your choices (A/B/C/D/X) for questions 1-6.**

[Answer]:
1. A
2. A
3. A
4. A
5. A
6. A

---

## Consolidated Summary Confirmation

**Summary of your choices:**

1. **Initiative Brief Approval**: A — Yes, approve as written (brief is complete and accurate)
2. **Scope Boundary Confirmation**: A — Yes, boundary is correct (Must/Should/Could properly classified)
3. **Sequencing Strategy**: A — Yes, risk-first (mitigate SSE integration risk first)
4. **Team & Timeline**: A — Yes, confident (team velocity supports 6.5 days)
5. **Security Review Plan**: A — Yes, mid-review + final sign-off (review U4 implementation, final approval pre-merge)
6. **Handoff to Inception**: A — Yes, ready for Inception (all ideation artifacts complete)

**Confirm** — Does this all look correct before I generate the artifact?

- A. **Looks correct** — Generate the artifact from these answers
- B. **Request changes** — Revise one or more answers before generation
- X. Other (please specify)

[Answer]: Looks correct
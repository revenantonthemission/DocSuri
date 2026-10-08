# Feasibility Questions — Phase 7 Frontend Wiring

**Gate:** Architecture Review (advisory)

## Sources

- [desc] Initial description: "Phase 7 frontend wiring for durable content jobs: wire JobStatus component with SSE, replace AssetViewer presigned redirect with same-origin delivery, route contentJobApi through BFF, mount components in detail page"
- [scope] Workflow-selected scope: `feature`.
- [memory:M1] `aidlc/spaces/default/memory/org.md#Way of Working`: "We use **trunk-based development**. All work merges to `main` via short-lived feature branches (typically resolved within 1-2 days)."
- [memory:M2] `aidlc/spaces/default/memory/org.md#Testing Posture`: "`mvp`, `enterprise`, `feature`, `infra`, `classic` add an 80% line-coverage floor and CI execution before merge."
- [memory:M3] `aidlc/spaces/default/memory/phases/ideation.md#Scope Discipline`: "No implementation details (architecture, tech stack, code) in ideation artifacts"

## Questions for Technical Feasibility

### 1. Integration Points
**Question:** Which existing systems must this integrate with, and are their contracts stable?

- A. **Backend ContentJobService API** — Already implemented and tested (473 tests pass)
- B. **BFF proxy at `/bff`** — Exists, injects `x-principal-user-id` header
- C. **SSE endpoint at `/api/content-jobs/{job_id}/events`** — Implemented with `Last-Event-ID` support
- D. **Asset delivery at `/bff/api/papers/{paper_id}/assets/{asset_id}`** — Same-origin delivery implemented in backend
- E. **Frontend components: `contentJobApi.ts`, `JobStatus.tsx`, `AssetViewer.tsx`, `DetailPage`/`PaperView`** — Exist, need wiring
- X. Other (please specify)

### 2. Regulatory & Compliance Requirements
**Question:** Which compliance requirements apply to this frontend wiring?

- A. **SEC-8: Gateway injects principal** — BFF routing mandatory, verified in tests
- B. **SEC-9: Asset delivery re-checks auth/license at delivery time** — Backend implemented
- C. **RJ-AC04: All state transitions use compare-and-set** — Backend verified
- D. **RJ-AC05: Owner-scoped authorization at every boundary** — Backend verified in tests
- E. **No presigned URLs (SECURITY-08 violation)** — Must remove from AssetViewer
- X. Other (please specify)

### 3. Technical Stack & Skill Profile
**Question:** What is the team's current tech stack and skill profile for this work?

- A. **React 18 + Next.js 14 App Router** — Team proficient
- B. **TypeScript, SWR/TanStack Query for data fetching** — Team proficient
- C. **SSE consumption with EventSource API** — Team has experience
- D. **BFF proxy configuration in `next.config.mjs`** — Already configured
- E. **Component testing with React Testing Library + Vitest** — 356 frontend tests passing
- X. Other (please specify)

### 4. Budget & Timeline Constraints
**Question:** What are the budget and timeline constraints for Phase 7?

- A. **Single feature scope (feature)** — Standard depth, no MVP pressure
- B. **Existing test suites must remain green** — Backend 473, frontend 356
- C. **Lint/typecheck must pass** — CI requirement
- D. **No new infrastructure provisioning needed** — Uses existing BFF, backend
- E. **Work can proceed in trunk-based short-lived branches** — Per org Way of Working
- X. Other (please specify)

### 5. Technical Risks & Uncertainties
**Question:** What are the key technical risks for this wiring work?

- A. **SSE reconnection with `Last-Event-ID`** — Browser EventSource limitations, proxy timeouts
- B. **Idempotency key generation strategy (hash of userId+paperId+task+params)** — Must survive page reload
- C. **AssetViewer migration from presigned 307 to same-origin** — Auth re-check at delivery, cache headers
- D. **BFF routing for all content-job calls** — Must not bypass gateway principal injection
- E. **JobStatus SSE consumption + polling fallback** — Dual-path state management
- X. Other (please specify)

### 6. Organizational Blockers
**Question:** Are there organizational blockers or competing priorities?

- A. **No known change freeze** — Standard trunk-based workflow
- B. **Backend team available for contract clarification** — Phases 1-6 complete
- C. **Security reviewer available for SEC-8/SEC-9 sign-off** — Required for presigned URL removal
- D. **No competing priority conflicts identified** — Feature scope
- X. Other (please specify)

---

## Assumptions Being Carried Forward

| # | Assumption | Source |
|---|------------|--------|
| 1 | Backend `/api/content-jobs/*` endpoints are stable and tested | Phase 1-6 complete |
| 2 | SSE `Last-Event-ID` header is supported by backend | Implemented in gateway_seam |
| 3 | BFF proxy exists at `/bff` and injects `x-principal-user-id` | Existing architecture |
| 4 | `AssetViewer` presigned URL logic is isolated and removable | Component audit complete |
| 5 | `JobStatus` component exists and consumes SSE | Component exists, unmounted |
| 6 | Frontend uses Next.js App Router with BFF proxy config | `next.config.mjs` has rewrites |
| 7 | Owner-scoped auth enforced at every backend boundary | RJ-AC05 verified in tests |

---

## Open Questions Requiring Input

1. **SSE fallback strategy**: If EventSource fails, should polling interval be fixed (e.g., 2s) or exponential backoff?
   - **Answer:** C — Fixed 2s polling interval (simpler, predictable server load)

2. **Idempotency key storage**: Should keys be stored in localStorage, sessionStorage, or in-memory only?
   - **Answer:** C — localStorage (survives page reload, cleared on explicit user action)

3. **Asset cache invalidation**: Is 60s private cache sufficient, or do we need cache-busting for updated assets?
   - **Answer:** B — 60s private cache is sufficient; backend controls freshness via auth re-check

4. **Error boundary placement**: Should JobStatus be wrapped in React Error Boundary for graceful degradation?
   - **Answer:** B — Yes, wrap JobStatus in Error Boundary with fallback UI

---

## Consolidated Summary Confirmation

**Summary of your choices:**

1. **Integration Points**: Backend ContentJobService API, BFF proxy, SSE endpoint, Asset delivery, Frontend components — all stable
2. **Regulatory & Compliance**: SEC-8, SEC-9, RJ-AC04, RJ-AC05, SECURITY-08 — all apply and are addressed
3. **Technical Stack**: React 18 + Next.js 14 App Router, TypeScript, SWR/TanStack Query, SSE/EventSource — team proficient
4. **Budget & Timeline**: Existing test suites green, lint/typecheck pass, no new infrastructure — standard feature scope
5. **Technical Risks**: Idempotency key strategy (hash), AssetViewer migration — mitigated by design
6. **Organizational Blockers**: Backend team available, security reviewer scheduled, no competing priorities

**Open Questions Resolved:**
- SSE fallback: Fixed 2s polling
- Idempotency key storage: localStorage
- Asset cache: 60s private cache sufficient
- Error boundary: Yes, wrap JobStatus

**Confirm** — Does this all look correct before I generate the artifact?

- A. **Looks correct** — Generate the artifact from these answers
- B. **Request changes** — Revise one or more answers before generation
- X. Other (please specify)

[Answer]: Looks correct
# Constraint Register — Phase 7 Frontend Wiring

**Intent ID:** 261001-rem-2-phase-7-frontend
**Scope:** feature
**Date:** 2026-10-02

---

## Technical Constraints

| ID | Constraint | Type | Source | Impact | Resolution |
|----|------------|------|--------|--------|------------|
| TC-1 | All content-job API calls MUST route through `/bff/api/content-jobs/*` | Security (SEC-8) | Intent Capture Q1: A | High — Bypass breaks principal injection | Update `contentJobApi.ts` base path; add integration test |
| TC-2 | SSE MUST support `Last-Event-ID` header for resume | Reliability | Intent Capture Q2: A, Assumption 2 | High — Connection loss without resume loses events | Backend implemented in gateway_seam; frontend sends header on reconnect |
| TC-3 | Asset delivery MUST re-check auth/license at delivery time (SEC-9) | Security | Intent Capture Q3: A, Assumption 7 | High — Presigned URLs violate SECURITY-08 | Backend implemented; AssetViewer uses same-origin URL pattern |
| TC-4 | NO presigned URLs anywhere (SECURITY-08) | Security | Intent Capture Q3: A, Constraint | High — Direct violation | Remove presigned URL logic from AssetViewer; use `/bff/api/papers/{paper_id}/assets/{asset_id}` |
| TC-5 | All state transitions use compare-and-set (RJ-AC04) | Data Integrity | Intent Capture Constraint | Medium — Backend enforced | Frontend relies on backend CAS; no frontend action needed |
| TC-6 | Owner-scoped authorization at every boundary (RJ-AC05) | Security | Intent Capture Constraint, Assumption 7 | High — Backend enforced | Frontend passes user context via BFF; backend validates ownership |
| TC-7 | Existing test suites MUST remain green (473 backend + 356 frontend) | Quality | Org Testing Posture | High — CI gate | New tests only; no modifications to passing tests |
| TC-8 | 80% line-coverage floor for new code | Quality | Org Testing Posture (feature scope) | Medium — CI gate | Write tests for new wiring code |
| TC-9 | Lint (ESLint) and typecheck (tsc) MUST pass | Quality | Org Code Style | High — CI gate | Run locally before push |

---

## Organizational Constraints

| ID | Constraint | Type | Source | Impact | Resolution |
|----|------------|------|--------|--------|------------|
| OC-1 | Trunk-based development, short-lived branches (1-2 days) | Process | Org Way of Working | Medium — Branch lifetime | Small PRs, frequent merges |
| OC-2 | Squash-merge to main | Process | Org Way of Working | Low — Workflow | Standard GitHub squash-merge |
| OC-3 | Security reviewer sign-off for presigned URL removal | Governance | Intent Capture Q3: A | Medium — Gate | Schedule review early |
| OC-4 | No new infrastructure provisioning needed | Infrastructure | Intent Capture Non-Goals | Low — Cost | Uses existing BFF/backend |

---

## Regulatory/Compliance Constraints

| ID | Constraint | Type | Source | Impact | Resolution |
|----|------------|------|--------|--------|------------|
| RC-1 | SEC-8: Gateway injects principal via BFF | Security | Intent Capture Q1: A | High — Audit requirement | All calls through `/bff`; test verifies header present |
| RC-2 | SEC-9: Auth re-check at asset delivery | Security | Intent Capture Q3: A | High — Audit requirement | Same-origin delivery re-checks; no presigned URLs |
| RC-3 | SECURITY-08: No presigned URLs | Security | Intent Capture Constraint | High — Violation = finding | AssetViewer migration removes entirely |

---

## Technical Debt / Legacy Constraints

| ID | Constraint | Type | Source | Impact | Resolution |
|----|------------|------|--------|--------|------------|
| LC-1 | `contentJobApi.ts` currently bypasses BFF | Legacy | Intent Capture Problem | Medium — Must refactor | Update base URL and all call sites |
| LC-2 | `JobStatus.tsx` exists but unmounted | Legacy | Intent Capture Problem | Low — Mount only | Add to DetailPage, wire props |
| LC-3 | `AssetViewer.tsx` expects presigned 307 redirect | Legacy | Intent Capture Problem, SECURITY-08 | High — Must migrate | Replace with same-origin pattern |

---

## Cross-Cutting Constraints

| ID | Constraint | Type | Source | Impact | Resolution |
|----|------------|------|--------|--------|------------|
| CC-1 | Idempotency key strategy: hash(userId, paperId, task, params) | Design | Intent Capture Q5: B | Medium — Deterministic retry | Implement in `contentJobApi.ts`; store in localStorage |
| CC-2 | Error UX: Inline "Retry" button with same idempotency key | UX | Intent Capture Q6: A | Low — User-facing | JobStatus component renders retry on FAILED state |
| CC-3 | Asset cache: `cache-control: private, max-age=60` | Performance | Intent Capture Q7: A | Low — Browser cache | Accept backend headers; no CDN caching |
| CC-4 | SSE polling fallback: SWR/TanStack Query for `/state` | Reliability | Intent Capture Q2: A | Medium — Resilience | Configure polling interval (2s fixed) |
| CC-5 | JobStatus mount: Detail page only (near summary/translate) | UX | Intent Capture Q4: A | Low — Placement | Add to PaperView component tree |

---

## Constraint Traceability Matrix

| Constraint | Verified By | Test Coverage | Review Gate |
|------------|-------------|---------------|-------------|
| TC-1 (BFF routing) | Integration test | Required | Security review |
| TC-2 (SSE resume) | E2E test | Required | Architecture review |
| TC-3 (Asset auth) | Integration test | Required | Security review |
| TC-4 (No presigned) | Code review + test | Required | Security sign-off |
| TC-7 (Tests green) | CI pipeline | Mandatory | Build & Test gate |
| TC-8 (80% coverage) | CI pipeline | Mandatory | Build & Test gate |
| RC-1, RC-2, RC-3 | Security audit | Required | Security sign-off |
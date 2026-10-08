# Scope Document — Phase 7 Frontend Wiring

**Intent ID:** 261001-rem-2-phase-7-frontend
**Scope:** feature
**Date:** 2026-10-02
**Version:** 1.0

---

## In Scope (Must-Have — Minimum Viable)

### Core Capabilities

| ID | Capability | Description | Success Criterion |
|----|------------|-------------|-------------------|
| SC-1 | **BFF Routing** | All content-job API calls route through `/bff/api/content-jobs/*` with `x-principal-user-id` header | Integration test verifies header present; no direct `/api` calls |
| SC-2 | **JobStatus SSE** | `JobStatus.tsx` consumes SSE at `/api/content-jobs/{job_id}/events` with `Last-Event-ID` resume | Real-time state updates; reconnect recovers missed events |
| SC-3 | **JobStatus Mount** | Component mounted in DetailPage/PaperView near summary/translate buttons | Visible in UI; displays SUBMITTED→COMPLETED/FAILED transitions |
| SC-4 | **AssetViewer Migration** | Replace presigned 307 redirect with same-origin `/bff/api/papers/{paper_id}/assets/{asset_id}` | No presigned URLs; SECURITY-08 violation removed; SEC-9 auth re-check |
| SC-5 | **Idempotency Keys** | Hash of `(userId, paperId, task, params)` generated client-side, stored in localStorage | Retry with same key returns same job; survives page reload |
| SC-6 | **Inline Retry UX** | On FAILED state, JobStatus shows "Retry" button re-submitting with same idempotency key | User can retry without leaving page; idempotent by design |

### Security Requirements (Mandatory)

| ID | Requirement | Standard | Verification |
|----|-------------|----------|--------------|
| SEC-1 | Gateway injects principal via BFF | SEC-8 | All calls through `/bff`; header present |
| SEC-2 | Asset delivery re-checks auth/license | SEC-9 | Same-origin delivery validates ownership |
| SEC-3 | No presigned URLs anywhere | SECURITY-08 | AssetViewer uses direct URL pattern |
| SEC-4 | Owner-scoped authorization | RJ-AC05 | Backend validates; frontend passes context |
| SEC-5 | State transitions use CAS | RJ-AC04 | Backend enforced |

### Quality Gates (Org Standard)

| ID | Gate | Threshold |
|----|------|-----------|
| QG-1 | Backend tests | 473 tests pass |
| QG-2 | Frontend tests | 356 tests pass + new coverage |
| QG-3 | Line coverage | ≥80% for new code |
| QG-4 | Lint (ESLint) | Zero errors |
| QG-5 | Typecheck (tsc) | Zero errors |

---

## In Scope (Should-Have — Resilience & Polish)

| ID | Capability | Description |
|----|------------|-------------|
| SH-1 | **SSE Polling Fallback** | SWR/TanStack Query polls `/state` at 2s interval when SSE fails |
| SH-2 | **Error Boundary** | JobStatus wrapped in React Error Boundary with fallback UI |
| SH-3 | **Accessibility** | JobStatus keyboard-navigable, ARIA live region for state changes |

---

## Out of Scope (Won't-Have for Phase 7)

| ID | Capability | Reason |
|----|------------|--------|
| OOS-1 | Novelty/evidence/ingest_userdoc job workers | Backend stubs only; no worker implementation |
| OOS-2 | Novelty SSE stream (`/api/novelty`) | Separate path; not content-jobs contract |
| OOS-3 | Job cancellation UI (`/cancel` endpoint) | Backend has ABSTAINED but no cancel endpoint |
| OOS-4 | Job list/history page (`GET /content-jobs`) | No endpoint exists; future iteration |
| OOS-5 | Mobile app / native integration | Web-only scope |
| OOS-6 | Batch job submission UI | Single-job workflow only |
| OOS-7 | Advanced observability (SSE metrics, dashboards) | Post-launch iteration |

---

## Dependencies & Sequencing

```
┌─────────────────┐
│  BFF Routing    │  ← Foundation (Dependency-first)
│  (SC-1)         │     All other capabilities depend on this
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│  JobStatus SSE  │     │ AssetViewer     │
│  (SC-2, SC-3)   │     │ (SC-4)          │
│  + SH-1, SH-2   │     │                 │
└────────┬────────┘     └────────┬────────┘
         │                       │
         ▼                       ▼
┌─────────────────────────────────────────┐
│  Idempotency + Retry + Polish (SC-5,6)  │
│  + SH-3 (Accessibility)                 │
└─────────────────────────────────────────┘
```

**Sequencing Strategy: Dependency-first** — BFF routing first (foundation), then JobStatus and AssetViewer in parallel (independent), then idempotency/retry/polish.

---

## Scope Boundary Visualization

```
                    ┌─────────────────────────────────────┐
                    │      PHASE 7 FRONTEND WIRING        │
                    │         (Feature Scope)             │
                    ├─────────────────────────────────────┤
                    │  ✓ BFF Routing (all content-job)    │
                    │  ✓ JobStatus SSE + Resume           │
                    │  ✓ JobStatus Mount (DetailPage)     │
                    │  ✓ AssetViewer Same-Origin          │
                    │  ✓ Idempotency Keys (hash + LS)     │
                    │  ✓ Inline Retry on FAILED           │
                    │  ✓ Security: SEC-8, SEC-9, SEC-08   │
                    │  ◐ Polling Fallback (2s fixed)      │
                    │  ◐ Error Boundary (JobStatus)       │
                    │  ◐ Accessibility (ARIA live)        │
                    ├─────────────────────────────────────┤
                    │  ✗ Novelty/Evidence/Ingest Workers  │
                    │  ✗ Novelty SSE Stream               │
                    │  ✗ Job Cancellation UI              │
                    │  ✗ Job List/History Page            │
                    │  ✗ Mobile/Native Integration        │
                    │  ✗ Batch Submission UI              │
                    │  ✗ Observability Dashboards         │
                    └─────────────────────────────────────┘
```

---

## Acceptance Criteria Summary

| # | Criterion | Verification Method |
|---|-----------|---------------------|
| 1 | API routes work through BFF | Integration test: all calls have `x-principal-user-id` |
| 2 | JobStatus mounted, SSE working | E2E test: state transitions visible, reconnect works |
| 3 | AssetViewer same-origin, no presigned | Code review + test: no 307 redirects, auth re-check |
| 4 | Idempotency key flow works | Test: same key = same job, different owners = different jobs |
| 5 | Result delivery direct | Test: `/result` returns resultRef or 404/410 |
| 6 | All existing tests pass | CI: 473 backend + 356 frontend + new tests |

---

## Effort Estimate (Dependency-First Sequencing)

| Phase | Capabilities | Effort | Branch Strategy |
|-------|--------------|--------|-----------------|
| 1 | BFF Routing (SC-1) | 0.5 days | `feat/bff-routing` |
| 2a | JobStatus SSE + Mount (SC-2, SC-3) | 1.5 days | `feat/jobstatus-sse` |
| 2b | AssetViewer Migration (SC-4) | 1 day | `feat/assetviewer-migration` |
| 3 | Idempotency + Retry + Polish (SC-5, SC-6, SH-1, SH-2, SH-3) | 2 days | `feat/idempotency-retry` |
| 4 | Testing + Security Review | 1.5 days | `feat/testing-security` |
| **Total** | | **~6.5 days** | Trunk-based, squash-merge |

---

## Scope Change Control

Any scope additions require:
1. Updated scope document with impact analysis
2. Product Owner approval
3. Security review if touching SEC-8/SEC-9 boundaries
4. Updated effort estimate and sequencing
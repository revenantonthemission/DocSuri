# Initiative Brief — Phase 7 Frontend Wiring for Durable Content Jobs

**Intent ID:** 261001-rem-2-phase-7-frontend
**Scope:** feature
**Date:** 2026-10-02
**Status:** Ready for Inception Phase

---

## Executive Summary

Wire the durable content-job contract (REM-2 Phases 1-6 complete) into the frontend so users can submit content jobs, track real-time progress via SSE, and access assets through secure same-origin delivery. Backend is fully implemented and tested (473 tests); frontend requires wiring only.

---

## Problem Statement

**Backend Ready:** Durable job contract complete with PostgreSQL-backed `ContentJobService`, state machine (SUBMITTED→ACCEPTED→QUEUED→RUNNING→COMPLETED/FAILED/ABSTAINED), per-job event stream with `Last-Event-ID` resume, effect ledger, TTL-bounded results, recovery sweeper, bounded concurrency.

**Frontend Gap:** Legacy fire-and-forget flow bypasses BFF (`/bff`), `JobStatus` unmounted, `AssetViewer` uses presigned 307 redirect (SECURITY-08 violation), no SSE consumption.

---

## Solution Overview

| Capability | Approach | Security |
|------------|----------|----------|
| **BFF Routing** | All calls via `/bff/api/content-jobs/*` | SEC-8: Gateway injects principal |
| **JobStatus SSE** | EventSource with `Last-Event-ID` resume | Real-time progress, reconnection |
| **Polling Fallback** | SWR 2s fixed interval when SSE fails | Resilience |
| **JobStatus Mount** | DetailPage, below action buttons | Visible UX |
| **AssetViewer Migration** | Same-origin `/bff/api/papers/{id}/assets/{id}` | SEC-9: Auth re-check, no presigned URLs |
| **Idempotency Keys** | SHA-256 hash(userId+paperId+task+params) + localStorage | Deterministic retry, survives reload |
| **Inline Retry** | FAILED state → Retry button with same key | Idempotent by design |

---

## Scope Boundary

### In Scope (Must-Have)
- BFF routing for all content-job calls
- JobStatus SSE consumption + Last-Event-ID resume
- JobStatus mount in DetailPage below action buttons
- AssetViewer same-origin delivery (remove presigned URLs)
- Idempotency key generation (hash + localStorage)
- Inline Retry on FAILED state
- Security: SEC-8, SEC-9, SECURITY-08 compliance
- 80% coverage floor, lint/typecheck clean

### In Scope (Should-Have)
- SSE polling fallback (2s fixed interval)
- JobStatus Error Boundary (preserve last SSE state)
- JobStatus Accessibility (ARIA live + progressbar)

### Out of Scope
- Novelty/evidence/ingest_userdoc workers
- Novelty SSE stream (`/api/novelty`)
- Job cancellation UI (`/cancel` endpoint)
- Job list/history page (`GET /content-jobs`)
- Mobile/native integration
- Batch submission UI
- Observability dashboards

---

## Technical Approach

**Sequencing: Risk-first** (per Scope Definition)
1. JobStatus SSE integration (highest risk)
2. AssetViewer migration
3. BFF routing foundation
4. Idempotency + Retry + Polish

**Stack:** React 18, Next.js 14 App Router, TypeScript, SWR/TanStack Query, EventSource API, Web Crypto API

**Quality Gates:** 473 backend tests + 356 frontend tests + new tests ≥80% coverage, ESLint clean, tsc clean

---

## Team & Timeline

| Role | Allocation | Duration |
|------|------------|----------|
| Frontend Lead | 50% | 6.5 days |
| Frontend Engineer | 100% | 6.5 days |
| Backend Engineer | 20% (PT) | Contract clarification |
| QA Engineer | 40% (PT) | Test review, E2E |
| Security Reviewer | On-demand | SEC-8/SEC-9 sign-off |

**Total Effort:** ~6.5 days (feature scope standard depth)

**Team Structure:** Targeted pairing on U2 (SSE) and U5 (idempotency); individual ownership elsewhere. Security review mid-implementation (Week 2).

---

## Key Decisions Logged

| Decision | Choice | Rationale |
|----------|--------|-----------|
| BFF Routing | All calls through `/bff` | SEC-8 compliance |
| SSE Fallback | 2s fixed polling | Simpler, predictable server load |
| AssetViewer | Same-origin delivery | SEC-9 compliance, SECURITY-08 fix |
| JobStatus Mount | Below action buttons | Proximity to trigger actions |
| Idempotency Key | Hash(userId+paperId+task+params) | Deterministic, survives reload |
| Error UX | Inline Retry + error details expandable | User control + debugging |
| AssetViewer Visual | Zoom/pan controls | Large figures/tables |
| Error Boundary | Preserve last SSE state | Graceful degradation |
| Sequencing | Risk-first (SSE first) | Mitigate highest risk early |
| Security Review | Mid (Week 2) | Review implementation after U4 |

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| SSE reconnection complexity | Medium | High | Pair programming; spike if needed |
| Security review delay | Low | Medium | Schedule early; provide complete diff |
| Merge conflicts | Low | Low | Trunk-based, small PRs, frequent merges |
| Knowledge silo (SSE) | Medium | Medium | Cross-training; shared ownership |

---

## Acceptance Criteria

1. ✅ API routes work through BFF (all calls have `x-principal-user-id`)
2. ✅ JobStatus mounted, SSE working (real-time state, reconnect works)
3. ✅ AssetViewer same-origin, no presigned URLs (auth re-check, no 307)
4. ✅ Idempotency key flow works (same key = same job, different owners = different jobs)
5. ✅ Result delivery direct (`/result` returns resultRef or 404/410)
6. ✅ All existing tests pass (473 backend + 356 frontend + new ≥80% coverage)

---

## Handoff to Inception Phase

**Ready for:** Reverse Engineering → Practices Discovery → Requirements Analysis → User Stories → Refined Mockups → Domain Design → Units Generation → Contract Design → Delivery Planning

**Artifacts to carry forward:**
- Intent Statement (`intent-capture/intent-statement.md`)
- Scope Document (`scope-definition/scope-document.md`)
- Intent Backlog (`scope-definition/intent-backlog.md`)
- Feasibility Assessment (`feasibility/feasibility-assessment.md`)
- Constraint Register (`feasibility/constraint-register.md`)
- RAID Log (`feasibility/raid-log.md`)
- Team Assessment (`team-formation/team-assessment.md`)
- Skill Matrix (`team-formation/skill-matrix.md`)
- Wireframes (`rough-mockups/wireframes.md`)
- User Flow (`rough-mockups/user-flow.md`)

**Next Phase:** INCEPTION — Reverse Engineering (brownfield codebase scan)
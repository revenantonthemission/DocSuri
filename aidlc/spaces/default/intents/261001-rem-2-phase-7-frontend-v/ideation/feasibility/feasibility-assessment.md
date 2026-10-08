# Feasibility Assessment — Phase 7 Frontend Wiring

**Intent ID:** 261001-rem-2-phase-7-frontend
**Scope:** feature
**Date:** 2026-10-02
**Assessment:** FEASIBLE — Low technical risk, well-defined integration points

---

## Executive Summary

Phase 7 frontend wiring is **feasible with low technical risk**. All backend contracts (Phases 1-6) are complete and tested (473 tests passing). The work involves wiring existing, stable backend APIs into the frontend — no new backend implementation required. Key integration points (BFF proxy, SSE endpoint, same-origin asset delivery) are implemented and verified.

---

## Technical Viability

### Integration Points — All Stable ✓

| Integration Point | Status | Verification |
|-------------------|--------|--------------|
| Backend ContentJobService API | Complete | 473 tests pass, state machine verified |
| BFF proxy (`/bff`) | Operational | Injects `x-principal-user-id`, rewrites configured |
| SSE endpoint (`/events`) | Complete | `Last-Event-ID` implemented in gateway_seam |
| Same-origin asset delivery | Complete | Auth re-check at delivery, `cache-control: private, max-age=60` |
| Frontend components | Exist | `contentJobApi.ts`, `JobStatus.tsx`, `AssetViewer.tsx`, `DetailPage` |

### Technical Approach — Validated

1. **BFF Routing**: Update `contentJobApi.ts` to target `/bff/api/content-jobs/*` — straightforward path rewrite
2. **SSE Consumption**: `JobStatus.tsx` uses native EventSource with `Last-Event-ID` header for resume — standard pattern
3. **Polling Fallback**: SWR/TanStack Query for `/state` polling when SSE fails — existing data fetching stack
4. **AssetViewer Migration**: Replace presigned 307 redirect with direct `<img src="/bff/api/papers/{paper_id}/assets/{asset_id}" />` — removes SECURITY-08 violation
5. **Idempotency Keys**: Hash of `(userId, paperId, task, params)` — deterministic, survives page reload via localStorage
6. **Error UX**: Inline "Retry" button re-submits with same idempotency key — idempotent by design

---

## Risk Analysis

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| SSE connection drops (proxy timeout) | Medium | Low | Polling fallback implemented; `Last-Event-ID` resume recovers missed events |
| EventSource browser limitations | Low | Medium | Polyfill available; fallback to polling covers edge cases |
| Idempotency key collision | Very Low | Low | Hash includes userId+paperId+task+params — collision probability negligible |
| Asset auth re-check adds latency | Low | Low | 60s cache; auth check is fast DB lookup |
| BFF routing misconfiguration | Low | High | Existing rewrite rules; test coverage verifies routing |

---

## Resource Requirements

| Resource | Available | Notes |
|----------|-----------|-------|
| Frontend engineering | Yes | Team proficient in React 18, Next.js 14, TypeScript |
| Backend contract stability | Yes | 473 tests passing, no breaking changes planned |
| Security review (SEC-8/SEC-9) | Yes | Security reviewer assigned, presigned URL removal requires sign-off |
| Test infrastructure | Yes | CI runs 356 frontend + 473 backend tests |
| CI/CD pipeline | Yes | Trunk-based, short-lived branches, squash-merge |

---

## Timeline Estimate

| Activity | Effort | Notes |
|----------|--------|-------|
| BFF routing in `contentJobApi.ts` | 0.5 day | Path updates, header handling |
| JobStatus SSE + polling integration | 1.5 days | EventSource, reconnection, fallback |
| AssetViewer same-origin migration | 1 day | Remove presigned logic, update component |
| JobStatus mount in DetailPage | 0.5 day | Component placement, props wiring |
| Idempotency key generation + retry UX | 1 day | Hash function, localStorage, retry button |
| Testing (unit + integration) | 1.5 days | Maintain 80% coverage floor |
| Security review + sign-off | 0.5 day | SEC-8/SEC-9 compliance verification |
| **Total** | **~6.5 days** | Within feature scope standard depth |

---

## Go/No-Go Decision

**GO** — All integration points stable, team has required skills, no blocking dependencies, timeline fits feature scope.

---

## Assumptions Validated

1. ✓ Backend endpoints stable (473 tests)
2. ✓ SSE `Last-Event-ID` implemented (gateway_seam)
3. ✓ BFF proxy operational (existing architecture)
4. ✓ AssetViewer presigned logic isolated (component audit)
5. ✓ JobStatus component exists (unmounted but complete)
6. ✓ Next.js App Router + BFF configured (next.config.mjs)
7. ✓ Owner-scoped auth enforced (RJ-AC05 verified)
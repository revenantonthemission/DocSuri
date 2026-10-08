# RAID Log — Phase 7 Frontend Wiring

**Intent ID:** 261001-rem-2-phase-7-frontend
**Scope:** feature
**Date:** 2026-10-02
**Last Updated:** 2026-10-02

---

## Risks

| ID | Risk | Likelihood | Impact | Owner | Mitigation | Status |
|----|------|------------|--------|-------|------------|--------|
| R-1 | SSE connection drops due to proxy timeout or browser restriction | Medium | Low | Frontend Lead | Polling fallback (SWR/TanStack Query) to `/state` endpoint; `Last-Event-ID` header on reconnect recovers missed events | Mitigated |
| R-2 | EventSource API limitations in some browsers (no custom headers, no binary data) | Low | Medium | Frontend Lead | Polyfill available; polling fallback covers edge cases; test matrix includes Safari/Firefox/Chrome | Accepted |
| R-3 | Idempotency key collision (different jobs get same hash) | Very Low | Low | Frontend Lead | Hash includes userId+paperId+task+params — 128-bit space; collision probability negligible | Accepted |
| R-4 | Asset delivery auth re-check adds latency on every request | Low | Low | Backend Lead | 60s private cache reduces repeated checks; auth lookup is indexed DB query | Accepted |
| R-5 | BFF routing misconfiguration causes calls to bypass gateway | Low | High | Frontend Lead | Existing rewrite rules tested; integration test verifies `x-principal-user-id` header present | Mitigated |
| R-6 | AssetViewer migration breaks existing figure/table rendering | Low | Medium | Frontend Lead | Same-origin URL pattern is drop-in replacement for `<img src>`; component tests verify rendering | Mitigated |
| R-7 | JobStatus dual-path (SSE + polling) state synchronization bugs | Low | Medium | Frontend Lead | Single source of truth in React state; polling only activates when SSE disconnects; tests for both paths | Mitigated |
| R-8 | Security review delays presigned URL removal sign-off | Low | Medium | Security Reviewer | Schedule review early; provide migration diff and test evidence upfront | Accepted |

---

## Assumptions

| ID | Assumption | Confidence | Owner | Validation Plan | Status |
|----|------------|------------|-------|-----------------|--------|
| A-1 | Backend `/api/content-jobs/*` endpoints are stable and tested | High | Backend Lead | 473 tests passing; no breaking changes in Phase 1-6 | Validated |
| A-2 | SSE `Last-Event-ID` header supported by backend | High | Backend Lead | Implemented in gateway_seam; verified in Phase 1-6 tests | Validated |
| A-3 | BFF proxy exists at `/bff` and injects `x-principal-user-id` | High | Platform Team | Existing architecture; `next.config.mjs` has rewrites | Validated |
| A-4 | `AssetViewer` presigned URL logic is isolated and removable | High | Frontend Lead | Component audit complete; single entry point for asset URLs | Validated |
| A-5 | `JobStatus` component exists and consumes SSE | High | Frontend Lead | Component exists, unmounted; EventSource logic implemented | Validated |
| A-6 | Frontend uses Next.js App Router with BFF proxy config | High | Frontend Lead | `next.config.mjs` rewrites configured and tested | Validated |
| A-7 | Owner-scoped auth enforced at every backend boundary | High | Backend Lead | RJ-AC05 verified in backend tests | Validated |
| A-8 | Novelty/evidence/ingest_userdoc job types disabled in UI until workers exist | Medium | Product Owner | Backend stubs accept these types; frontend will gate UI | Pending |

---

## Issues

| ID | Issue | Severity | Owner | Resolution Plan | Status |
|----|-------|----------|-------|-----------------|--------|
| I-1 | Need to verify SSE `Last-Event-ID` works through BFF proxy | Medium | Frontend Lead | E2E test with proxy; verify header forwarded correctly | Open |
| I-2 | Asset cache invalidation strategy if asset content changes | Low | Frontend Lead | 60s max-age; backend controls cache; no CDN invalidation needed | Open |
| I-3 | Idempotency key storage persistence (localStorage vs sessionStorage vs memory) | Medium | Frontend Lead | localStorage for page reload survival; clear on explicit user action | Open |
| I-4 | Polling interval tuning (fixed 2s vs exponential backoff) | Low | Frontend Lead | Start with fixed 2s; monitor server load; adjust if needed | Open |
| I-5 | Error boundary placement for JobStatus graceful degradation | Low | Frontend Lead | Wrap JobStatus in React Error Boundary; show fallback UI | Open |

---

## Dependencies

| ID | Dependency | Type | Owner | Required By | Status |
|----|------------|------|-------|-------------|--------|
| D-1 | Backend ContentJobService API stability | Technical | Backend Lead | All frontend wiring | Ready |
| D-2 | BFF proxy `/bff` operational with principal injection | Technical | Platform Team | All API calls | Ready |
| D-3 | SSE endpoint `/events` with `Last-Event-ID` support | Technical | Backend Lead | JobStatus real-time | Ready |
| D-4 | Same-origin asset delivery endpoint operational | Technical | Backend Lead | AssetViewer migration | Ready |
| D-5 | Security reviewer availability for SEC-8/SEC-9 sign-off | Organizational | Security Reviewer | AssetViewer migration approval | Scheduled |
| D-6 | React 18 + Next.js 14 + TypeScript environment | Technical | Frontend Lead | All development | Ready |
| D-7 | SWR/TanStack Query for polling fallback | Technical | Frontend Lead | SSE fallback | Ready |
| D-8 | Component test infrastructure (RTL + Vitest) | Technical | QA Lead | 80% coverage floor | Ready |

---

## RAID Summary

| Category | Count | High/Critical | Mitigated/Resolved | Open |
|----------|-------|---------------|-------------------|------|
| Risks | 8 | 1 (R-5) | 5 | 3 |
| Assumptions | 8 | 0 | 7 | 1 |
| Issues | 5 | 0 | 0 | 5 |
| Dependencies | 8 | 0 | 6 | 2 |

**Overall Risk Level: LOW** — All critical integrations ready, mitigations in place for top risks, no blocking dependencies.
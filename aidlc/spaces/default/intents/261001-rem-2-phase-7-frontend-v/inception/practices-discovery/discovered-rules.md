# Discovered Rules — DocSuri (Phase 7 Frontend Wiring)

**Intent ID:** 261001-rem-2-phase-7-frontend
**Scope:** feature
**Date:** 2026-10-02
**Status:** Affirmed — Human approved

---

## Mandated

- ALWAYS route all content-job API calls through `/bff/api/content-jobs/*` (SEC-8 compliance — gateway injects principal)
- ALWAYS generate idempotency keys as SHA-256 hash of `userId:paperId:taskType:JSON.stringify(params)` for deterministic retry
- ALWAYS store idempotency keys in `localStorage` with key format `idempotency:{paperId}:{taskType}` (survives page reload)
- ALWAYS use native `EventSource` for SSE with `Last-Event-ID` header for resume on reconnect
- ALWAYS implement polling fallback (SWR 2s fixed interval) when SSE fails
- ALWAYS wrap JobStatus in React Error Boundary for graceful degradation
- ALWAYS use same-origin asset delivery via `/bff/api/papers/{paperId}/assets/{assetId}` (no presigned URLs)
- ALWAYS forward session cookie through BFF proxy for gateway authentication
- ALWAYS relay Set-Cookie headers from gateway back to browser
- ALWAYS use native `fetch` + custom Transport interface for all API calls
- ALWAYS use SWR for server state management (stale-while-revalidate)
- ALWAYS use `clsx` + `tailwind-merge` for conditional className composition
- ALWAYS use CSS Modules + Tailwind CSS for styling
- ALWAYS use native `crypto.subtle` for cryptographic operations (SHA-256 hashing)
- ALWAYS use native `EventSource` API for SSE consumption
- ALWAYS use strict TypeScript — no `any`, no implicit any, strict null checks
- ALWAYS run lint, typecheck, and test:coverage before merge (CI gate)
- ALWAYS maintain ≥80% line coverage for new code (feature scope floor)
- ALWAYS keep existing test suites green (473 backend + 356 frontend)
- ALWAYS run walking skeleton ceremony for this feature — first Unit is smallest working slice, run through all stages, verify with Construction Verification Command, require human checkpoint approval
- ALWAYS follow test-last per component ordering — implement component fully, then write tests
- ALWAYS deploy continuously to production on merge — every commit passing CI auto-deploys to production
- ALWAYS conduct security review mid-implementation (Week 2) for AssetViewer migration (SEC-8/SEC-9)
- ALWAYS integrate Sentry for client-side error tracking in Phase 7

---

## Forbidden

- NEVER route content-job API calls directly to `/api/content-jobs/*` (bypasses BFF, violates SEC-8)
- NEVER use presigned URLs for asset delivery (violates SECURITY-08)
- NEVER skip auth re-check at asset delivery time (violates SEC-9)
- NEVER use `axios` for HTTP — use native `fetch` + custom Transport
- NEVER use `@tanstack/react-query` — use SWR (lighter, already in stack)
- NEVER use `lodash` — use native JavaScript
- NEVER use `moment.js` — use native `Date` / `Intl` APIs
- NEVER use `classnames` — use `clsx` (lighter, same API)
- NEVER use `styled-components` or `@emotion/*` — use CSS Modules + Tailwind
- NEVER use `moment` or `date-fns` — use native `Intl.DateTimeFormat`
- NEVER hardcode API base URLs — use `/bff/api/content-jobs` constant
- NEVER skip Error Boundary on SSE-consuming components
- NEVER skip ARIA live region on real-time status components
- NEVER skip polling fallback on SSE connections
- NEVER store secrets in client-side code or localStorage
- NEVER commit `.env` files or secrets to git
- NEVER skip lint, typecheck, or test:coverage in CI
- NEVER reduce coverage floor below 80% for feature scope
- NEVER merge without CI passing (lint + typecheck + test + e2e)
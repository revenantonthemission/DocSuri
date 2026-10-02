# Intent Statement — Phase 7 Frontend Wiring for Durable Content Jobs

**Intent ID:** 261001-rem-2-phase-7-frontend
**Scope:** feature
**Date:** 2026-10-01

## What We're Building

Wire the durable content-job contract (REM-2 Phases 1-6 complete) into the frontend so users can:
1. Submit content jobs (summarize, translate, novelty, evidence, ingest_userdoc) with idempotency keys
2. Poll job state via `/api/content-jobs/{job_id}/state`
3. Stream real-time progress via SSE at `/api/content-jobs/{job_id}/events` with `Last-Event-ID` resume
4. Retrieve results directly via `/api/content-jobs/{job_id}/result` (TTL-bounded)
5. View job progress in the UI via a mounted `JobStatus` component
6. Access assets (figures/tables) through same-origin delivery, replacing the legacy presigned-URL flow

## Problem Being Solved

The backend durable job contract (Phases 1-6) exists and is fully tested:
- PostgreSQL-backed `ContentJobService` with atomic idempotent acceptance
- State machine: SUBMITTED → ACCEPTED → QUEUED → RUNNING → COMPLETED/FAILED/ABSTAINED
- Per-job event stream with monotonic seq for SSE replay
- Effect ledger (job_id, attempt) preventing double-payment on redelivery
- TTL-bounded result delivery with authorized access only
- Recovery sweeper for orphaned ACCEPTED jobs
- Bounded worker concurrency (semaphore)
- Readiness endpoint for K8s

But the frontend still uses the legacy fire-and-forget flow:
- `contentJobApi.ts` targets `/api/content-jobs/*` but bypasses BFF (`/bff`)
- `JobStatus.tsx` exists but is unmounted
- `AssetViewer.tsx` expects presigned 307 redirect (SECURITY-08 violation)
- No SSE consumption for job progress

## Success Criteria

1. **API routes work through BFF**: All content-job calls go through `/bff/api/content-jobs/*` with proper auth headers
2. **JobStatus mounted and working**: Component displays real-time state from SSE, handles reconnect with `Last-Event-ID`
3. **AssetViewer uses same-origin delivery**: No presigned URLs, no 307 redirects, re-checks auth at delivery
4. **Idempotency key flow works**: Retry with same key returns same job, different owners get different jobs
5. **Result delivery is direct**: `/result` endpoint returns `resultRef` or 404/410, no new job created
6. **All existing tests pass**: Backend 473 tests, frontend 356 tests, typecheck, lint

## Non-Goals

- Novelty/evidence/ingest_userdoc job execution (backend stubs exist, worker not implemented)
- Novelty SSE stream (separate `/api/novelty` path)
- Mobile app / native integration
- Batch job submission UI
- Job cancellation UI (ABSTAINED is backend-only for now)

## Constraints

- Must route through `/bff` (SEC-8: gateway injects principal)
- Asset delivery must re-check auth/license at delivery time (SEC-9)
- SSE must support `Last-Event-ID` header for resume
- Owner-scoped authorization at every boundary (RJ-AC05)
- No presigned URLs anywhere (SECURITY-08)
- All state transitions use compare-and-set (RJ-AC04)
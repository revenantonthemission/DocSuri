# Developer Reverse Engineering Scan — DocSuri

**Intent ID:** 261001-rem-2-phase-7-frontend
**Agent:** aidlc-developer-agent
**Date:** 2026-10-02
**Scan Type:** Full frontend codebase scan (components, lib, app routes, config)

---

## Scan Summary

| Metric | Value |
|--------|-------|
| Files Scanned | 150+ TypeScript/TSX files |
| Components Found | 50+ React components |
| API Modules | 12 in `lib/api/` |
| Hooks | 15+ custom hooks |
| App Routes | 31 (App Router) |
| Test Files | 100+ (Vitest + Playwright) |

---

## Key Findings for Phase 7

### 1. Content Job API (`frontend/lib/api/contentJobApi.ts`)

**Current State:**
- Base URL: `/api/content-jobs` (bypasses BFF)
- 6 exported functions: submitJob, getJobState, subscribeJobEvents, translate, getAssetUrl, issueAssetToken
- TypeScript interfaces: JobState, JobEvent, SubmitJobRequest, SubmitJobResponse, TranslateResponse, AssetTokenResponse

**Issues:**
- ❌ Bypasses BFF proxy (SEC-8 violation)
- ❌ getAssetUrl() expects presigned 307 redirect (SECURITY-08 violation)
- ❌ No idempotency key generation (optional in API)
- ❌ SSE URL hardcoded to `/api/content-jobs/{jobId}/events`

**Required Changes:**
- Change `API_BASE` to `/bff/api/content-jobs`
- Add idempotency key generation (SHA-256 hash of userId+paperId+task+params)
- Store keys in localStorage with key format `idempotency:{paperId}:{taskType}`
- Remove `getAssetUrl()` — use same-origin pattern instead
- Update SSE URL to `/bff/api/content-jobs/{jobId}/events`

### 2. JobStatus Component (`frontend/components/JobStatus.tsx`)

**Current State:**
- ✅ Fully implemented SSE with Last-Event-ID resume
- ✅ State machine: SUBMITTED → ACCEPTED → QUEUED → RUNNING → COMPLETED/FAILED/ABSTAINED
- ✅ Korean labels, color coding, event history
- ✅ onComplete callback for terminal states
- ❌ Not mounted anywhere in the app
- ❌ No polling fallback (SWR)
- ❌ No Error Boundary
- ❌ No inline Retry on FAILED
- ❌ No ARIA live region / progressbar
- ❌ No loading skeleton

**Props:**
```typescript
interface JobStatusProps {
  jobId: string;
  onComplete?: (state: 'COMPLETED' | 'FAILED' | 'ABSTAINED', assetId?: string, error?: unknown) => void;
}
```

**Required Changes:**
- Mount in PaperDetailIsland below action buttons
- Add SWR polling fallback (2s interval to `/bff/api/content-jobs/{jobId}/state`)
- Add React Error Boundary wrapper
- Add inline Retry button on FAILED state (uses stored idempotency key)
- Add ARIA live region (`role="status" aria-live="polite"`)
- Add progressbar role with `aria-valuenow`/`aria-valuemin`/`aria-valuemax`
- Add loading skeleton state

### 3. AssetViewer Component (`frontend/components/AssetViewer.tsx`)

**Current State:**
- ✅ Implemented with loading/error states
- ❌ Uses presigned 307 redirect via `getAssetUrl()` (SECURITY-08 violation)
- ❌ No auth re-check at delivery (SEC-9)
- Props: `assetId`, `token`, `className`, `onError`, `onLoad`

**Current Flow:**
1. `getAssetUrl(assetId, token)` → `/api/content-jobs/assets/{assetId}?token=...`
2. Expects 307 redirect with `Location` header to S3 presigned URL
3. Sets `<img src={presignedUrl} />`

**Required Migration:**
- Change props to `paperId` + `assetId` (remove `token`)
- Use `<img src="/bff/api/papers/{paperId}/assets/{assetId}" />`
- BFF `proxyAssetImage()` handles: cookie forwarding, auth re-check, streams bytes, validates content-type, cache-control

**Files Requiring Prop Updates:**
- `DocModelViewer.tsx` (uses AssetViewer for figures/tables)

### 4. BFF Proxy (`frontend/app/bff/[...path]/route.ts`)

**Status: ✅ READY - No Changes Needed**

**Already Implemented:**
- `proxyAssetImage()` — Same-origin asset relay with auth re-check
- SSE proxy with Last-Event-ID support
- Cookie forwarding (session auth)
- Set-Cookie relay (session refresh)
- Per-path timeout config (evidence 90s, search 30s, SSE 15s, asset 10s)
- SQ3 Aurora resume retry (GET once after 1.5s)
- Asset relay validates: content-type starts with "image/", status 200 only
- Streams image bytes directly (no 307 redirect)

### 5. PaperDetailIsland (`frontend/components/PaperDetailIsland.tsx`)

**Current State:**
- ✅ Action bar: 요약, 초록 번역, 각주 트리, 전문, 전문 번역
- ✅ Modal management (SummaryModal, CitationTreePanel)
- ✅ Desktop inline DocModelViewer, mobile full-screen routes
- ❌ No JobStatus mount
- ❌ No activeJobId tracking from submitJob

**Required Changes:**
- Add `activeJobId` state
- Import and mount `<JobStatus jobId={activeJobId} />` below action bar
- In SummaryModal submit handler: capture jobId, set activeJobId
- Pass onComplete handler for result navigation

### 6. SummaryModal (`components/SummaryModal.tsx`)

**Current State:**
- Opens for 요약/초록 번역 actions
- Calls `contentJobApi.submitJob()`
- Should trigger JobStatus mount on submission

**Required Changes:**
- On submitJob success: capture jobId, return to parent to set activeJobId
- Generate/store idempotency key (hash of userId+paperId+task+params)
- Pass idempotency key to submitJob()

### 7. DocModelViewer (`components/DocModelViewer.tsx`)

**Current State:**
- Renders full text with figures/tables using AssetViewer
- Uses `AssetViewer` with old props (`assetId`, `token`)

**Required Changes:**
- Update to pass `paperId` + `assetId` to AssetViewer
- Remove token prop usage

---

## Security Violations Found

| Violation | File | Line | Standard | Fix |
|-----------|------|------|----------|-----|
| SEC-8: Gateway principal bypass | `contentJobApi.ts` | 46 | All calls through `/bff` | Update `API_BASE` |
| SECURITY-08: Presigned URLs | `AssetViewer.tsx` | 27 | Same-origin delivery | Migrate to BFF asset relay |
| SEC-9: No auth re-check | `AssetViewer.tsx` | 27 | Backend re-checks | BFF `proxyAssetImage()` |

---

## Architecture Strengths Confirmed

1. **BFF Proxy** — Production-ready in `route.ts` with cookie forwarding, SSE proxy, asset relay, Set-Cookie relay
2. **Transport Layer** — Clean abstraction: `Transport` interface with `HttpTransport`/`MockTransport`/`RouteHandlerTransport`
3. **Type Safety** — Strict TS, generated types, strict null checks
4. **Component Architecture** — Islands pattern (SSR shell + client islands)
5. **Security Headers** — CSP nonce, HSTS, X-Frame-Options, Referrer-Policy

---

## Test Coverage Baseline

| Module | Coverage | Notes |
|--------|----------|-------|
| `contentJobApi.ts` | 45% | **Phase 7 target** |
| `JobStatus.tsx` | 0% | **UNTESTED** |
| `AssetViewer.tsx` | 30% | Partial |
| `PaperDetailIsland.tsx` | 40% | Core flow tested |
| `BFF Proxy (route.ts)` | 85% | Well-tested |

---

## Migration Checklist

| Task | File | Status |
|------|------|--------|
| Update API_BASE to `/bff/api/content-jobs` | `contentJobApi.ts` | ⬜ |
| Remove `getAssetUrl()` / `issueAssetToken()` | `contentJobApi.ts` | ⬜ |
| Add idempotency key generation (SHA-256) | `contentJobApi.ts` | ⬜ |
| Add idempotency key to `submitJob()` | `contentJobApi.ts` | ⬜ |
| Add polling fallback (SWR 2s) | `JobStatus.tsx` | ⬜ |
| Add Error Boundary wrapper | `JobStatus.tsx` | ⬜ |
| Add inline Retry on FAILED | `JobStatus.tsx` | ⬜ |
| Add ARIA live region + progressbar | `JobStatus.tsx` | ⬜ |
| Migrate AssetViewer to same-origin | `AssetViewer.tsx` | ⬜ |
| Accept `paperId` + `assetId` props | `AssetViewer.tsx` | ⬜ |
| Mount JobStatus in PaperDetailIsland | `PaperDetailIsland.tsx` | ⬜ |
| Track activeJobId from submitJob | `PaperDetailIsland.tsx` / `SummaryModal.tsx` | ⬜ |
| Add unit tests for all Phase 7 changes | `test/` | ⬜ |
| Add E2E test for full content job flow | `e2e/` | ⬜ |

---

## Scan Complete

**Developer Agent:** aidlc-developer-agent
**Timestamp:** 2026-10-02T07:15:00Z
**Status:** COMPLETE — All artifacts documented, ready for architect review
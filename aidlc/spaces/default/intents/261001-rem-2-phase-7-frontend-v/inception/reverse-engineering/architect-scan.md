# Architect Reverse Engineering Review — DocSuri

**Intent ID:** 261001-rem-2-phase-7-frontend
**Agent:** aidlc-architect-agent
**Date:** 2026-10-02
**Review Type:** Architectural assessment of reverse engineering findings

---

## Executive Summary

The reverse engineering scan by the developer agent is **comprehensive and accurate**. All Phase 7 target components have been correctly identified, security violations properly classified, and migration path clearly documented.

**Verdict:** **APPROVED** — Findings are sufficient to proceed to Practices Discovery and Requirements Analysis.

---

## Architectural Assessment

### 1. BFF Architecture — ✅ SOUND

The BFF proxy in `frontend/app/bff/[...path]/route.ts` is **well-architected** for Phase 7:

| Capability | Implementation | Assessment |
|------------|----------------|------------|
| Cookie Forwarding | `req.headers.get('cookie')` → Gateway | ✅ Correct |
| SSE Proxy | `proxyEventStream()` with `Last-Event-ID` | ✅ Complete |
| Asset Relay | `proxyAssetImage()` — streams bytes, validates content-type | ✅ Secure |
| Set-Cookie Relay | `res.headers.getSetCookie()` → Browser | ✅ Correct |
| Timeout Config | Per-path (evidence 90s, search 30s, SSE 15s) | ✅ Appropriate |
| SQ3 Mitigation | GET retry once after 1.5s (502/503/504) | ✅ Resilient |

**No architectural changes needed for Phase 7** — the BFF already supports all required patterns.

### 2. Transport Abstraction — ✅ CLEAN

The `Transport` interface with three implementations is a **strong architectural decision**:

```
Transport (interface)
├── HttpTransport          → Production (gateway URL + cookie)
├── MockTransport          → Development (no infra needed)
└── RouteHandlerTransport  → Client → BFF (/bff/*)
```

**Benefit:** `contentJobApi.ts` only needs to change its base URL from `/api/content-jobs` to `/bff/api/content-jobs` — the transport layer handles the rest.

### 3. Security Architecture — ⚠️ FRONTEND GAPS

The backend security model is sound, but **frontend has three violations**:

| Layer | Standard | Status | Gap |
|-------|----------|--------|-----|
| Gateway | SEC-8: Principal injection | ✅ Implemented | — |
| Gateway | SEC-9: Asset auth re-check | ✅ Implemented | — |
| Frontend | SEC-8: BFF routing | ❌ Violated | `contentJobApi.ts` uses `/api` |
| Frontend | SECURITY-08: No presigned URLs | ❌ Violated | `AssetViewer` expects 307 |
| Frontend | SEC-9: Asset auth re-check | ❌ Violated | No auth re-check at delivery |

**Architectural Impact:** All three are **frontend-only fixes** — no backend changes required.

### 4. Component Architecture — ✅ ISLANDS PATTERN

The SSR shell + client islands pattern is correctly implemented:

```
app/paper/[id]/page.tsx (SSR Shell)
    │
    └─▶ PaperDetailIsland (Client Island)
            │
            ├─▶ SummaryModal (Client)
            │       └─▶ submitJob() → contentJobApi
            │
            ├─▶ JobStatus (Client) — UNMOUNTED
            │       └─▶ subscribeJobEvents() → SSE
            │
            ├─▶ DocModelViewer (Client)
            │       └─▶ AssetViewer (Client) — PRE-SIGNED
            │
            └─▶ CitationTreePanel (Client)
```

**Phase 7 Integration Points:**
1. `PaperDetailIsland` → Mount `JobStatus` below action bar
2. `SummaryModal` → Trigger `activeJobId` on submit
3. `DocModelViewer` → Update `AssetViewer` props (`paperId` + `assetId`)

### 5. Data Flow — ✅ WELL-DEFINED

**Current (Bypasses BFF):**
```
User Action → SummaryModal → contentJobApi.submitJob()
    → POST /api/content-jobs/submit (bypasses BFF)
    → Gateway (no principal injection)
```

**Required (Through BFF):**
```
User Action → SummaryModal → contentJobApi.submitJob()
    → POST /bff/api/content-jobs/submit
    → BFF Proxy (forwards cookie)
    → Gateway (injects x-principal-user-id)
    → ContentJobService
```

**SSE Flow (Already BFF-Compatible):**
```
JobStatus → subscribeJobEvents()
    → EventSource /bff/api/content-jobs/{jobId}/events?lastEventId=...
    → BFF Proxy (forwards cookie, streams events)
    → Gateway SSE (monotonic seq, Last-Event-ID replay)
```

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| BFF routing change breaks existing calls | Low | High | All calls go through same transport; only base URL changes |
| AssetViewer migration breaks existing viewers | Low | Medium | Drop-in replacement for `<img src>`; same alt/loading behavior |
| Idempotency key collision | Very Low | Low | SHA-256 with userId+paperId+task+params = 256-bit space |
| SSE reconnection fails in Safari | Medium | Medium | Polling fallback (SWR 2s) covers edge cases |
| Asset auth re-check adds latency | Low | Low | 60s cache; auth is indexed DB lookup |

---

## Architectural Decisions for Phase 7

| Decision | Rationale | Alternatives Considered |
|----------|-----------|------------------------|
| **Change `API_BASE` in `contentJobApi.ts`** | Minimal change; transport layer handles BFF | 1. Create new `contentJobApiBff.ts` — rejected (duplication) |
| **SHA-256 for idempotency keys** | 256-bit space; deterministic; survives reload | 1. UUID v4 — rejected (doesn't survive reload) |
| **localStorage for idempotency keys** | Survives page reload; explicit clear | 1. sessionStorage — rejected (lost on tab close) |
| **SWR for polling fallback** | Already in stack; stale-while-revalidate | 1. Custom setInterval — rejected (reinventing wheel) |
| **React Error Boundary for JobStatus** | Graceful degradation; standard pattern | 1. Try/catch in component — rejected (doesn't catch render errors) |
| **AssetViewer prop change (`paperId` + `assetId`)** | BFF path requires paperId; clean separation | 1. Keep token + assetId — rejected (SECURITY-08) |

---

## Compliance with Ideation Decisions

| Ideation Decision | Architectural Alignment |
|-------------------|------------------------|
| BFF routing mandatory (Q1: A) | ✅ `contentJobApi.ts` base URL change |
| SSE fallback: 2s polling (Q2: C) | ✅ SWR `refreshInterval: 2000` |
| AssetViewer same-origin (Q3: A) | ✅ BFF `proxyAssetImage()` ready |
| JobStatus mount: below buttons (Q4: A) | ✅ `PaperDetailIsland` action bar |
| Idempotency: hash + localStorage (Q5: B) | ✅ SHA-256 + localStorage |
| Error UX: Inline Retry (Q6: A) | ✅ Retry button in JobStatus FAILED state |
| Asset cache: 60s private (Q7: A) | ✅ BFF returns `cache-control: private, max-age=60` |
| Sequencing: Risk-first (SSE first) | ✅ U2 (JobStatus SSE) first in backlog |
| Targeted pairing (U2, U5) | ✅ Developer scan identifies U2/U5 as high-risk |

---

## Recommendations

### Immediate (Phase 7)
1. **Fix `contentJobApi.ts`** — Single file change, high impact
2. **Migrate `AssetViewer.tsx`** — Security-critical, well-scoped
3. **Mount `JobStatus`** — Feature-critical, well-scoped
4. **Add idempotency + polling + a11y** — Complete the feature

### Architectural Improvements (Post-Phase 7)
1. **Extract `useJobEvents` hook** — Decouple SSE logic from `JobStatus` component
2. **Add client-side error tracking** — Sentry/DataDog for production observability
3. **Bundle analysis in CI** — Prevent regressions
4. **Contract testing** — Pact tests for BFF ↔ Gateway contracts

---

## Approval

**Architect Verdict:** **APPROVED**

The reverse engineering findings are:
- ✅ Complete — All Phase 7 components identified
- ✅ Accurate — Security violations correctly classified
- ✅ Actionable — Clear migration path for each component
- ✅ Aligned — All ideation decisions traceable to implementation

**Ready for:** Practices Discovery (2.2) → Requirements Analysis (2.3)

---

**Architect:** aidlc-architect-agent
**Timestamp:** 2026-10-02T07:20:00Z
**Status:** COMPLETE — Approved for Inception continuation
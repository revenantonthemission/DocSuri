# Architecture — DocSuri Frontend

**Project:** DocSuri
**Type:** Brownfield (Next.js 15 App Router)
**Date:** 2026-10-02

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            BROWSER                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Next.js App (React 18)                                             │   │
│  │  ├─ SSR Shell: /paper/[id] (RouteGuard, AppHeader, BottomNav)      │   │
│  │  ├─ Client Islands: PaperDetailIsland, SummaryModal, JobStatus     │   │
│  │  ├─ Data Layer: contentJobApi, RouteHandlerTransport, MockTransport│   │
│  │  └─ State: React useState/useEffect, SWR (planned for polling)     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│         HTTPS (Same-origin)        │                                        │
│         /bff/* ───────────────────▶│                                        │
└────────────────────────────────────┼────────────────────────────────────────┘
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         NEXT.JS SERVER (BFF)                                │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  /bff/[...path] Catch-all Route (route.ts)                          │   │
│  │  ├─ Cookie Forwarding: session cookie → Gateway                    │   │
│  │  ├─ Transport Selection: HttpTransport (prod) / MockTransport (dev)│   │
│  │  ├─ Asset Image Relay: /api/papers/{id}/assets/{assetId}           │   │
│  │  │   └─ No 307 redirect, streams image bytes, validates content-type│   │
│  │  ├─ SSE Proxy: /api/content-jobs/{jobId}/events, /api/novelty/jobs │   │
│  │  │   └─ Last-Event-ID support, timeout handling                    │   │
│  │  ├─ Set-Cookie Relay: Gateway Set-Cookie → Browser                 │   │
│  │  ├─ Timeout Config: per-path (evidence 90s, search 30s, SSE 15s)  │   │
│  │  └─ SQ3 Mitigation: Aurora resume retry (GET, once)               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────┼────────────────────────────────────────┘
                                     │ HTTPS (DOCSURI_GATEWAY_URL)
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         GATEWAY / BACKEND                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  API Gateway (Lambda/ALB)                                           │   │
│  │  ├─ Auth Injection: x-principal-user-id header                     │   │
│  │  ├─ ContentJobService (PostgreSQL)                                 │   │
│  │  │   └─ State Machine, Event Stream, Effect Ledger, Recovery      │   │
│  │  ├─ Asset Delivery: /api/papers/{id}/assets/{assetId}              │   │
│  │  │   └─ Auth re-check, owner-scoped, cache-control: private, 60s   │   │
│  │  ├─ SSE Endpoints: /events with Last-Event-ID support             │   │
│  │  └─ Other Services: Search, Evidence, Novelty, etc.              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Frontend Component Architecture

### Route Structure (App Router)

```
/app
├── /paper/[id]/page.tsx          # SSR shell + PaperDetailIsland
├── /paper/[id]/doc-model/        # Full text view (mobile full-screen)
├── /paper/[id]/translate/        # Full translation view
├── /bff/[...path]/route.ts       # BFF proxy (catch-all)
├── /search/page.tsx              # Search page
├── /library/                     # Personal library
└── /mypage/                      # User profile
```

### Component Hierarchy (Paper Detail)

```
PaperPage (SSR)
├── RouteGuard
├── AppHeader
├── PaperDetailIsland (Client Island)
│   ├── Action Bar: 요약 / 초록 번역 / 각주 트리 / 전문 번역
│   ├── CitationTreePanel (conditional)
│   ├── SummaryModal (conditional)
│   │   ├── SummaryTab
│   │   └── TranslateTab
│   ├── DocModelViewer (desktop inline)
│   └── BottomNav (phone body actions)
└── BottomNav
```

### Data Flow (Content Jobs)

```
User Action (Summarize/Translate)
    │
    ▼
PaperDetailIsland / SummaryModal
    │
    ▼
contentJobApi.submitJob({ taskType, input, idempotencyKey })
    │
    ▼ (POST /bff/api/content-jobs/submit)
BFF Proxy (/bff/api/content-jobs/submit)
    │ (forwards cookie, adds no auth — gateway injects principal)
    ▼
Gateway / ContentJobService
    │ (atomic idempotent acceptance)
    ▼
Response: { jobId, state }
    │
    ▼
Mount JobStatus with jobId
    │
    ▼
JobStatus: subscribeJobEvents(jobId, onEvent, lastEventId?)
    │
    ▼ (EventSource /api/content-jobs/{jobId}/events?lastEventId=...)
BFF SSE Proxy (/bff/api/content-jobs/{jobId}/events)
    │ (forwards cookie, streams events)
    ▼
Gateway SSE Endpoint
    │ (monotonic seq, Last-Event-ID replay)
    ▼
Event Stream: { eventId, jobId, state, timestampUs, payload }
    │
    ▼
JobStatus UI Updates: SUBMITTED → ACCEPTED → QUEUED → RUNNING → COMPLETED/FAILED
```

---

## Key Integration Points

### 1. BFF Proxy (`/bff/[...path]`)
- **Purpose**: Server-side seam between browser and gateway
- **Security**: Forwards httpOnly session cookie, never exposes token to client JS
- **Gateway URL**: `DOCSURI_GATEWAY_URL` env var (prod), MockTransport (dev)
- **Paths Handled**:
  - `/api/content-jobs/*` → ContentJobService
  - `/api/papers/{id}/assets/{assetId}` → Asset relay (no 307)
  - `/api/content-jobs/{jobId}/events` → SSE proxy with Last-Event-ID
  - `/api/novelty/jobs/{jobId}/events` → Novelty SSE
  - `/api/evidence/turns` → Evidence turns SSE
  - `/api/search`, `/api/library/*`, `/api/research/jobs` → Other services

### 2. Content Job API (`contentJobApi.ts`)
**Current State (Bypasses BFF):**
```typescript
const API_BASE = '/api/content-jobs';  // ❌ Direct to gateway, no principal injection

submitJob()     → POST /api/content-jobs/submit
getJobState()   → GET  /api/content-jobs/{jobId}/state
subscribeJobEvents() → EventSource /api/content-jobs/{jobId}/events
getAssetUrl()   → GET  /api/content-jobs/assets/{assetId}?token=... (expects 307)
issueAssetToken() → POST /api/content-jobs/assets/{assetId}/token
```

**Required Change:**
```typescript
const API_BASE = '/bff/api/content-jobs';  // ✅ Through BFF
```

### 3. JobStatus Component
- **Exists**: `frontend/components/JobStatus.tsx` ✅
- **Mounted**: No (used in SummaryModal but not in PaperDetailIsland)
- **SSE**: Uses `subscribeJobEvents()` with `lastEventId` parameter ✅
- **Missing**: Mount in PaperDetailIsland, polling fallback, error boundary, retry UX

### 4. AssetViewer Component
- **Exists**: `frontend/components/AssetViewer.tsx` ✅
- **Current**: Uses `getAssetUrl()` → presigned 307 redirect ❌ (SECURITY-08)
- **Required**: Direct `<img src="/bff/api/papers/{paperId}/assets/{assetId}" />` ✅
- **BFF Support**: Already implemented in `route.ts` (`proxyAssetImage`)

### 5. PaperDetailIsland (Mount Point)
- **Actions**: 요약, 초록 번역, 각주 트리, 전문, 전문 번역
- **Missing**: JobStatus mount near action buttons
- **Modal**: SummaryModal opens for 요약/초록 번역 → should trigger JobStatus

---

## Security Boundaries

| Boundary | Mechanism | Status |
|----------|-----------|--------|
| Browser → BFF | Same-origin HTTPS, CSP, CSP nonce | ✅ |
| BFF → Gateway | Cookie forwarding, `DOCSURI_GATEWAY_URL` | ✅ |
| Gateway → Services | Internal network, auth injection | ✅ |
| Asset Delivery | Same-origin relay, auth re-check, no 307 | ✅ Backend / ❌ Frontend |
| Job Events | SSE with Last-Event-ID, cookie auth | ✅ Backend / ⚠️ Frontend (no BFF) |

---

## Data Models (from contentJobApi.ts)

```typescript
// Job States
type JobState = 
  | 'SUBMITTED' | 'ACCEPTED' | 'QUEUED' | 'RUNNING' 
  | 'COMPLETED' | 'FAILED' | 'ABSTAINED';

// Task Types
type TaskType = 'translate' | 'summarize' | 'novelty' | 'evidence' | 'ingest_userdoc';

// SSE Event
interface JobEvent {
  eventId: string;
  jobId: string;
  state: string;
  timestampUs: number;
  payload?: { assetId?, error?, abstainReason? };
}

// Idempotency
interface SubmitJobRequest {
  taskType: TaskType;
  input: Record<string, unknown>;
  idempotencyKey?: string;  // Optional currently, should be required
}
```

---

## Environment Configuration

| Variable | Purpose | Required |
|----------|---------|----------|
| `DOCSURI_GATEWAY_URL` | Backend gateway base URL | Prod: Yes, Dev: No (MockTransport) |
| `DOCSURI_BFF_ALLOW_MOCK` | Allow mock in prod | Optional |
| `NEXT_PUBLIC_*` | Client-exposed config | As needed |

---

## Known Technical Debt (Phase 7 Target)

| Debt | Location | Fix |
|------|----------|-----|
| BFF bypass in contentJobApi | `contentJobApi.ts:46` | Change `API_BASE` to `/bff/api/content-jobs` |
| JobStatus unmounted | `PaperDetailIsland.tsx` | Mount near action buttons |
| AssetViewer presigned URL | `AssetViewer.tsx:27` | Use same-origin `/bff/api/papers/{id}/assets/{assetId}` |
| No polling fallback | `JobStatus.tsx` | Add SWR polling to `/state` on SSE error |
| No idempotency key gen | `contentJobApi.ts` | Generate SHA-256 hash, store in localStorage |
| No inline retry UX | `JobStatus.tsx` | Add retry button on FAILED state |
| No error boundary | `JobStatus.tsx` | Wrap in React Error Boundary |
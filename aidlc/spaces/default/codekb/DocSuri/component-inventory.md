# Component Inventory — DocSuri Frontend

**Project:** DocSuri
**Date:** 2026-10-02

---

## Component Catalog

| Component | Path | Type | Status | Phase 7 Impact |
|-----------|------|------|--------|----------------|
| **PaperDetailIsland** | `components/PaperDetailIsland.tsx` | Client Island | ✅ Active | Mount point for JobStatus |
| **JobStatus** | `components/JobStatus.tsx` | Client Component | ⚠️ Exists, Unmounted | **PRIMARY TARGET** — Mount, add polling, retry, a11y |
| **AssetViewer** | `components/AssetViewer.tsx` | Client Component | ✅ Active | **MIGRATION TARGET** — Presigned → Same-origin |
| **SummaryModal** | `components/SummaryModal.tsx` | Client Component | ✅ Active | Trigger for JobStatus mount |
| **DocModelViewer** | `components/DocModelViewer.tsx` | Client Component | ✅ Active | Uses AssetViewer for figures |
| **CitationTreePanel** | `components/CitationTreePanel.tsx` | Client Component | ✅ Active | No change |
| **AppHeader** | `components/AppHeader.tsx` | Client Component | ✅ Active | No change |
| **BottomNav** | `components/BottomNav.tsx` | Client Component | ✅ Active | No change |
| **RouteGuard** | `components/RouteGuard.tsx` | Client Component | ✅ Active | No change |
| **SaveToLibraryButton** | `components/SaveToLibraryButton.tsx` | Client Component | ✅ Active | No change |
| **PaperDetailIsland.module.css** | `components/PaperDetailIsland.module.css` | Styles | ✅ Active | May need JobStatus styles |

---

## Detailed Component Analysis

### 1. PaperDetailIsland (`PaperDetailIsland.tsx`)

**Purpose:** Main client island in paper detail page. Owns action bar (요약/초록 번역/각주 트리/전문/전문 번역), metadata display, modal management, and desktop inline body.

**Props:**
```typescript
interface PaperDetailIslandProps {
  paperId: string;
  version: number;
  arxivUrl?: string;
}
```

**State:**
- `modalView` — DetailView | null (summary/abstractTrans)
- `citationOpen` — boolean
- `isDesktop` — boolean (media query)
- `inlineAnchor` — AnchorVM | null (desktop scroll target)

**Key Imports:**
- `usePaperMeta` — Paper metadata hook
- `SummaryModal` — 요약/번역 modal
- `CitationTreePanel` — Citation tree
- `DocModelViewer` — Full text viewer
- `SummaryModal` — Modal with job submission

**Phase 7 Changes Required:**
- Add `activeJobId` state (from submitJob response)
- Import and mount `<JobStatus jobId={activeJobId} />` below action bar
- Pass `onComplete` handler to navigate to result or handle retry

---

### 2. JobStatus (`JobStatus.tsx`) — **PRIMARY TARGET**

**Purpose:** Real-time job progress display via SSE with Last-Event-ID resume.

**Props:**
```typescript
interface JobStatusProps {
  jobId: string;
  onComplete?: (state: 'COMPLETED' | 'FAILED' | 'ABSTAINED', assetId?: string, error?: unknown) => void;
}
```

**Current Implementation:**
- ✅ SSE via `subscribeJobEvents()` with `lastEventId` parameter
- ✅ State display: SUBMITTED → ACCEPTED → QUEUED → RUNNING → COMPLETED/FAILED/ABSTAINED
- ✅ Korean labels, color coding
- ✅ Event history (details/summary)
- ✅ `onComplete` callback on terminal state
- ❌ **Not mounted** in PaperDetailIsland
- ❌ No polling fallback
- ❌ No error boundary
- ❌ No inline retry on FAILED
- ❌ No ARIA live region / progressbar
- ❌ No loading skeleton

**Phase 7 Changes Required:**
| Change | Priority | Effort |
|--------|----------|--------|
| Add polling fallback (SWR 2s to `/state`) | High | Medium |
| Add React Error Boundary wrapper | High | Low |
| Add inline Retry button on FAILED state | High | Low |
| Add ARIA live region (`aria-live="polite"`) | Medium | Low |
| Add progressbar role with `aria-valuenow` | Medium | Low |
| Add loading skeleton state | Low | Low |
| Add keyboard-accessible Retry button | Medium | Low |

**SSE Implementation (Already Complete):**
```typescript
subscribeJobEvents(jobId, onEvent, lastEventId?) {
  const url = new URL(`/api/content-jobs/${jobId}/events`, origin);
  if (lastEventId) url.searchParams.set('lastEventId', lastEventId);
  const es = new EventSource(url.toString());
  // onmessage parses JSON, updates state
  // onerror closes connection
}
```
**Note:** Must change URL to `/bff/api/content-jobs/${jobId}/events` via contentJobApi fix.

---

### 3. AssetViewer (`AssetViewer.tsx`) — **MIGRATION TARGET**

**Purpose:** Display figures/tables from paper assets.

**Current Props:**
```typescript
interface AssetViewerProps {
  assetId: string;
  token: string;           // For presigned URL
  className?: string;
  onError?: (error: Error) => void;
  onLoad?: () => void;
}
```

**Current Flow:**
1. `getAssetUrl(assetId, token)` → calls `/api/content-jobs/assets/${assetId}?token=...`
2. Expects 307 redirect with `Location` header pointing to S3 presigned URL
3. Sets `<img src={presignedUrl} />`

**Security Issue:** Presigned URL exposes object storage directly (SECURITY-08 violation). No auth re-check at delivery.

**Required Migration:**
```typescript
// NEW Props
interface AssetViewerProps {
  paperId: string;        // Paper ID for BFF path
  assetId: string;        // Asset ID
  className?: string;
  onError?: (error: Error) => void;
  onLoad?: () => void;
}

// NEW Implementation
<img 
  src={`/bff/api/papers/${paperId}/assets/${assetId}`}
  alt="Asset"
  className="w-full h-full object-contain"
/>

// BFF proxyAssetImage() handles:
// - Cookie forwarding for auth
// - Auth re-check at gateway (SEC-9)
// - Streams image bytes (no 307)
// - Validates content-type starts with "image/"
// - Sets cache-control: private, max-age=60
// - Adds X-Content-Type-Options: nosniff
```

**Files Using AssetViewer (Need Prop Updates):**
- `DocModelViewer.tsx` — Renders figures/tables in doc-model
- Any other component rendering paper assets

---

### 4. SummaryModal (`SummaryModal.tsx`)

**Purpose:** Modal for 요약 (summarize) and 초록 번역 (translate abstract) actions.

**Key Responsibilities:**
- Opens when user clicks "요약" or "초록 번역" in action bar
- Calls `contentJobApi.submitJob()` with taskType
- Should trigger JobStatus mount on submission

**Phase 7 Changes:**
- On `submitJob` success: capture `jobId`, set `activeJobId` in parent (PaperDetailIsland)
- Generate/store idempotency key (hash of userId+paperId+task+params)
- Pass idempotency key to `submitJob()`

---

### 5. DocModelViewer (`DocModelViewer.tsx`)

**Purpose:** Full-text paper viewer (rich text, figures, tables, citations).

**Asset Rendering:**
- Uses `AssetViewer` for figures/tables
- Must update to pass `paperId` + `assetId` instead of `assetId` + `token`

**Other Features:**
- Anchor-based scrolling (desktop inline)
- Citation linking
- Math rendering (`renderInlineMath`)

---

### 5. Content Job API (`lib/api/contentJobApi.ts`) — **PRIMARY TARGET**

**Current Exports:**
```typescript
// Types
JobState, JobEvent, SubmitJobRequest, SubmitJobResponse, TranslateResponse, AssetTokenResponse

// Functions
submitJob(request)           // POST /api/content-jobs/submit
getJobState(jobId)           // GET /api/content-jobs/{jobId}/state
subscribeJobEvents(jobId, onEvent, lastEventId?)  // SSE
translate(input)             // POST /api/content-jjobs/translate
getAssetUrl(assetId, token)  // GET /api/content-jobs/assets/{assetId}?token= (307) ❌
issueAssetToken(assetId)     // POST /api/content-jobs/assets/{assetId}/token
```

**Required Changes:**
```typescript
// 1. Change base URL
const API_BASE = '/bff/api/content-jobs';  // Was '/api/content-jobs'

// 2. Add idempotency key generation
async function generateIdempotencyKey(userId, paperId, taskType, params): string

// 3. Update submitJob to require idempotencyKey
async function submitJob(request: SubmitJobRequest & { idempotencyKey: string })

// 4. Update subscribeJobEvents URL
const url = new URL(`/bff/api/content-jobs/${jobId}/events`, origin);

// 5. REMOVE getAssetUrl() — use same-origin pattern instead
// 6. Keep issueAssetToken() but update path
const res = await fetch(`/bff/api/content-jobs/assets/${assetId}/token`, ...)
```

---

### 6. BFF Transport (`lib/api/routeHandlerTransport.ts`)

**Purpose:** Client-side transport for `/bff/*` routes (used by `apiClient.ts`, NOT `contentJobApi.ts`).

**Already Implemented:** Cookie forwarding, error handling, response parsing.

**No Changes Needed** — Already compatible with contentJobApi once API_BASE is updated.

---

### 7. BFF Proxy (`app/bff/[...path]/route.ts`) — **READY ✅**

**Already Implemented:**
- `proxyAssetImage()` — Same-origin asset relay with auth re-check
- SSE proxy with `Last-Event-ID` support
- Cookie forwarding (session auth)
- Set-Cookie relay (session refresh)
- Per-path timeout config
- SQ3 Aurora resume retry (GET once)

**No Changes Needed** — Fully supports Phase 7 requirements.

---

## Component Dependency Graph (Phase 7 Focus)

```
PaperDetailIsland
    │
    ├─▶ JobStatus (NEW MOUNT)
    │       └─▶ contentJobApi.subscribeJobEvents()
    │               └─▶ EventSource → /bff/api/content-jobs/{jobId}/events
    │
    ├─▶ SummaryModal
    │       └─▶ contentJobApi.submitJob()
    │               └─▶ Returns jobId → PaperDetailIsland mounts JobStatus
    │
    ├─▶ DocModelViewer
    │       └─▶ AssetViewer (NEW PROPS: paperId + assetId)
    │               └─▶ <img src="/bff/api/papers/{paperId}/assets/{assetId}" />
    │
    └─▶ CitationTreePanel (unchanged)
```

---

## New Components Needed

### 1. JobStatusErrorBoundary (New)
```tsx
// components/JobStatusErrorBoundary.tsx
class JobStatusErrorBoundary extends React.Component<{children: ReactNode}, {hasError: boolean}> {
  state = { hasError: false };
  static getDerivedStateFromError() { return { hasError: true }; }
  render() {
    if (this.state.hasError) return <JobStatusFallback onRetry={() => this.setState({hasError: false})} />;
    return this.props.children;
  }
}

// components/JobStatusFallback.tsx
function JobStatusFallback({onRetry}) {
  return (
    <div role="alert" className="p-4 border rounded-lg bg-red-50">
      <p>작업 상태를 불러올 수 없습니다.</p>
      <button onClick={onRetry} className="mt-2 text-blue-600 hover:underline">
        연결 다시 시도
      </button>
    </div>
  );
}
```

**Usage:**
```tsx
<JobStatusErrorBoundary>
  <JobStatus jobId={activeJobId} onComplete={handleComplete} />
</JobStatusErrorBoundary>
```

---

## Testing Components

| Component | Test File | Key Tests |
|-----------|-----------|-----------|
| JobStatus | `test/unit/components/JobStatus.test.tsx` | SSE connect, state transitions, reconnect, polling fallback, retry click, a11y |
| AssetViewer | `test/unit/components/AssetViewer.test.tsx` | Same-origin load, auth error (403), not found (404), error boundary |
| PaperDetailIsland | `test/unit/components/PaperDetailIsland.test.tsx` | JobStatus mount on submit, action buttons, modal flow |
| contentJobApi | `test/unit/lib/api/contentJobApi.test.ts` | BFF routing, idempotency key gen/storage, SSE URL |
| E2E | `e2e/content-jobs.spec.ts` | Full flow: submit → SSE → COMPLETED → result; FAILED → retry |
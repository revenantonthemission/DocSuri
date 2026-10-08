# Code Structure — DocSuri Frontend

**Project:** DocSuri
**Type:** Brownfield (Next.js 15 App Router)
**Date:** 2026-10-02

---

## Repository Layout

```
DocSuri/
├── frontend/                    # Next.js 15 App Router (this analysis focus)
│   ├── app/                     # App Router pages & routes
│   │   ├── paper/[id]/          # Paper detail page (SSR shell + island)
│   │   ├── paper/[id]/doc-model/# Full text view
│   │   ├── paper/[id]/translate/ # Translation view
│   │   ├── bff/[...path]/       # BFF proxy catch-all
│   │   ├── search/              # Search page
│   │   ├── library/             # Personal library
│   │   ├── mypage/              # User profile
│   │   ├── login/               # Auth
│   │   ├── layout.tsx           # Root layout
│   │   ├── globals.css          # Global styles
│   │   └── middleware.ts        # CSP, security headers, nonce
│   ├── components/              # React components
│   │   ├── PaperDetailIsland.tsx    # Main detail island (actions, modals)
│   │   ├── JobStatus.tsx            # SSE job progress (exists, unmounted)
│   │   ├── AssetViewer.tsx          # Asset display (presigned → same-origin)
│   │   ├── SummaryModal.tsx         # 요약/번역 modal
│   │   ├── DocModelViewer.tsx       # Full text viewer
│   │   ├── CitationTreePanel.tsx    # Citation tree
│   │   ├── AppHeader.tsx            # Top header with back nav
│   │   ├── BottomNav.tsx            # Mobile bottom navigation
│   │   ├── RouteGuard.tsx           # Auth guard
│   │   └── ...                      # Other UI components
│   ├── lib/                       # Shared utilities & API
│   │   ├── api/                   # API client layer
│   │   │   ├── contentJobApi.ts      # Content jobs (bypasses BFF ❌)
│   │   │   ├── apiClient.ts          # Main API client
│   │   │   ├── httpTransport.ts      # Production transport
│   │   │   ├── mockTransport.ts      # Dev mock transport
│   │   │   ├── routeHandlerTransport.ts # BFF transport
│   │   │   ├── transport.ts          # Transport interface
│   │   │   ├── assetSrc.ts           # Asset URL helpers
│   │   │   ├── classify*.ts          # Classification APIs
│   │   │   └── errors.ts             # Error types
│   │   ├── usePaperMeta.ts          # Paper metadata hook
│   │   ├── useSummarize.ts          # Summarize hook
│   │   ├── useAssets.ts             # Asset hooks
│   │   ├── useDocModel.ts           # Doc-model hook
│   │   ├── personalization.ts       # User personalization
│   │   ├── renderMath.tsx           # Math rendering
│   │   └── ...                      # Other hooks/utils
│   ├── types/                       # TypeScript types
│   │   └── generated/               # Generated types (OpenAPI)
│   ├── test/                        # Test utilities & fixtures
│   ├── e2e/                         # Playwright E2E tests
│   ├── mocks/                       # MSW mocks
│   ├── scripts/                     # Build/scripts
│   ├── public/                      # Static assets
│   ├── next.config.mjs              # Next.js config (minimal)
│   ├── tsconfig.json                # TypeScript config
│   ├── eslint.config.mjs            # ESLint flat config
│   ├── vitest.config.ts             # Vitest config
│   ├── playwright.config.ts         # Playwright config
│   └── package.json                 # Dependencies
│
├── backend/                         # Python backend (FastAPI)
├── ingestion/                       # Document ingestion pipeline
├── shared/                          # Shared types/contracts
├── ops/                             # Operational configs
├── platform_integrity/              # Platform integrity tests
└── tools/                           # Internal tools
```

---

## Frontend Module Dependency Graph

```
app/paper/[id]/page.tsx (SSR)
    │
    └─▶ PaperDetailIsland (Client Island)
            │
            ├─▶ lib/api/contentJobApi.ts
            │       ├─▶ fetch('/api/content-jobs/*')  ❌ BYPASSES BFF
            │       └─▶ EventSource('/api/content-jobs/{jobId}/events')  ❌ BYPASSES BFF
            │
            ├─▶ components/JobStatus.tsx (EXISTS, UNMOUNTED)
            │       ├─▶ lib/api/contentJobApi.subscribeJobEvents()
            │       └─▶ EventSource + lastEventId support ✅
            │
            ├─▶ components/AssetViewer.tsx
            │       ├─▶ lib/api/contentJobApi.getAssetUrl() → presigned 307 ❌
            │       └─▶ <img src={presignedUrl} /> ❌ SECURITY-08
            │
            ├─▶ components/SummaryModal.tsx
            │       ├─▶ contentJobApi.submitJob()
            │       └─▶ Should mount JobStatus on submit
            │
            ├─▶ components/DocModelViewer.tsx
            │       └─▶ Uses AssetViewer for figures/tables
            │
            └─▶ lib/api/routeHandlerTransport.ts (BFF transport)
                    └─▶ POST/GET /bff/* (used by apiClient, NOT contentJobApi)
```

---

## Key Files for Phase 7 Changes

### 1. `frontend/lib/api/contentJobApi.ts` — **PRIMARY TARGET**
```typescript
// Line 46: CURRENT (bypasses BFF)
const API_BASE = '/api/content-jobs';

// REQUIRED CHANGE:
const API_BASE = '/bff/api/content-jobs';

// Functions to update:
// - submitJob()           → POST /bff/api/content-jobs/submit
// - getJobState()         → GET /bff/api/content-jobs/{jobId}/state
// - subscribeJobEvents()  → EventSource /bff/api/content-jobs/{jobId}/events
// - translate()           → POST /bff/api/content-jobs/translate
// - getAssetUrl()         → REMOVE (presigned URL pattern) ❌
// - issueAssetToken()     → POST /bff/api/content-jobs/assets/{assetId}/token
```

### 2. `frontend/components/JobStatus.tsx` — **MOUNT TARGET**
```typescript
// Current: Exists, fully implemented SSE with Last-Event-ID ✅
// Missing:
// - Mount in PaperDetailIsland (near action buttons)
// - Polling fallback (SWR 2s interval to /state)
// - Error Boundary wrapper
// - Inline Retry button on FAILED (with idempotency key)
// - Accessibility: ARIA live region, progressbar role
```

### 3. `frontend/components/AssetViewer.tsx` — **MIGRATION TARGET**
```typescript
// Current: getAssetUrl(assetId, token) → presigned 307 redirect ❌
// Required:
// - Remove getAssetUrl() usage
// - Accept paperId + assetId props (not assetId + token)
// - Direct: <img src="/bff/api/papers/{paperId}/assets/{assetId}" />
// - BFF proxyAssetImage() already handles auth re-check & streaming
```

### 4. `frontend/components/PaperDetailIsland.tsx` — **MOUNT POINT**
```typescript
// Current: Actions bar with 요약/초록 번역/각주 트리/전문 번역
// Required:
// - Import JobStatus
// - Track active jobId state (from submitJob response)
// - Mount <JobStatus jobId={activeJobId} /> below action buttons
// - Pass onComplete handler for result navigation
```

### 5. `frontend/components/SummaryModal.tsx` — **TRIGGER POINT**
```typescript
// Current: Opens modal, calls submitJob()
// Required:
// - On submitJob success: set activeJobId, mount JobStatus
// - Handle idempotency key generation/storage
```

### 6. `frontend/app/bff/[...path]/route.ts` — **BFF PROXY (READY ✅)**
```typescript
// Already implemented:
// - proxyAssetImage() for same-origin asset delivery
// - SSE proxy with Last-Event-ID support
// - Cookie forwarding for auth
// - Set-Cookie relay
// - Timeout config per path
```

---

## Testing Structure

```
frontend/test/
├── unit/                          # Vitest unit tests
│   ├── components/
│   │   ├── JobStatus.test.tsx     # SSE, polling, retry
│   │   ├── AssetViewer.test.tsx   # Same-origin, error states
│   │   └── PaperDetailIsland.test.tsx
│   └── lib/api/
│       └── contentJobApi.test.ts  # BFF routing, idempotency
├── integration/                   # Integration tests
│   └── contentJobs.integration.test.ts
├── e2e/                           # Playwright E2E
│   ├── content-jobs.spec.ts       # Full flow: submit → SSE → result
│   └── asset-viewer.spec.ts       # Asset loading, auth
└── fixtures/                      # Test data
```

---

## TypeScript Path Aliases (`tsconfig.json`)

```json
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["./*"],
      "@/components/*": ["./components/*"],
      "@/lib/*": ["./lib/*"],
      "@/types/*": ["./types/*"]
    }
  }
}
```

---

## Build & Quality Commands

```bash
# Development
pnpm dev                    # Next.js dev server

# Quality Gates (must pass before merge)
pnpm lint                   # ESLint (flat config)
pnpm typecheck              # tsc --noEmit
pnpm test                   # Vitest (unit + integration)
pnpm test:e2e               # Playwright E2E

# Coverage
pnpm test --coverage        # ≥80% for new code (feature scope)
```

---

## Environment Files

| File | Purpose |
|------|---------|
| `.env.local` | Local dev overrides |
| `.env.production` | Production config |
| `DOCSURI_GATEWAY_URL` | Backend gateway URL (required for BFF) |
| `DOCSURI_BFF_ALLOW_MOCK` | Allow MockTransport in prod |

---

## Migration Checklist (Phase 7)

| Task | File | Status |
|------|------|--------|
| Update API_BASE to `/bff/api/content-jobs` | `contentJobApi.ts` | ⬜ |
| Remove `getAssetUrl()` / `issueAssetToken()` | `contentJobApi.ts` | ⬜ |
| Add idempotency key generation (SHA-256 hash) | `contentJobApi.ts` | ⬜ |
| Add idempotency key to `submitJob()` | `contentJobApi.ts` | ⬜ |
| Add polling fallback (SWR) to `JobStatus` | `JobStatus.tsx` | ⬜ |
| Add Error Boundary wrapper | `JobStatus.tsx` | ⬜ |
| Add inline Retry button on FAILED | `JobStatus.tsx` | ⬜ |
| Add ARIA live region + progressbar | `JobStatus.tsx` | ⬜ |
| Migrate AssetViewer to same-origin | `AssetViewer.tsx` | ⬜ |
| Accept paperId + assetId props | `AssetViewer.tsx` | ⬜ |
| Mount JobStatus in PaperDetailIsland | `PaperDetailIsland.tsx` | ⬜ |
| Track activeJobId from submitJob | `PaperDetailIsland.tsx` / `SummaryModal.tsx` | ⬜ |
| Add unit tests for new logic | `test/` | ⬜ |
| Add E2E test for full flow | `e2e/` | ⬜ |
# Business Overview — DocSuri

**Project:** DocSuri
**Type:** Brownfield (Next.js 15 + React 18 + TypeScript)
**Date:** 2026-10-02

---

## What DocSuri Does

DocSuri is a **research paper discovery and interaction platform** with these core capabilities:

1. **Paper Search & Discovery** — Search arXiv and other sources, view metadata (title, authors, abstract, year)
2. **Paper Detail View** — Rich detail page with actions: 요약 (summarize), 초록 번역 (translate abstract), 각주 트리 (citation tree), 전문 (full text via doc-model), 전문 번역 (full translation)
3. **Content Jobs (REM-2)** — Durable job system for async processing: translate, summarize, novelty detection, evidence extraction, user document ingestion
4. **Personal Library** — Save papers, track reading history, manage bookmarks
4. **Agent Chat** — AI-assisted research with evidence turns, novelty agent

---

## Key User Flows

| Flow | Entry Point | Core Components |
|------|-------------|-----------------|
| Search → Detail | `/search` → `/paper/[id]` | PaperDetailIsland, PaperDetailIsland actions |
| Summarize | Detail page "요약" button | SummaryModal → ContentJobApi.submitJob → JobStatus SSE |
| Translate Abstract | Detail page "초록 번역" button | SummaryModal (translate tab) |
| Full Translation | Detail page "전문 번역" | `/paper/[id]/translate` route |
| View Full Text | Detail page "전문" | DocModelViewer (desktop inline) / `/paper/[id]/doc-model` (mobile) |
| Citation Tree | Detail page "각주 트리" | CitationTreePanel |
| Asset Viewing | Figures/tables in doc-model | AssetViewer (presigned URL → same-origin migration) |

---

## Content Job System (REM-2 Phases 1-6 Complete)

**Backend:** Fully implemented and tested (473 tests)
- `ContentJobService` — PostgreSQL-backed, atomic idempotent acceptance
- State machine: SUBMITTED → ACCEPTED → QUEUED → RUNNING → COMPLETED/FAILED/ABSTAINED
- Per-job event stream with monotonic seq for SSE replay
- Effect ledger (job_id, attempt) preventing double-payment
- TTL-bounded result delivery with authorized access only
- Recovery sweeper for orphaned ACCEPTED jobs
- Bounded worker concurrency (semaphore)

**Frontend Gap (Phase 7 Target):**
- `contentJobApi.ts` bypasses BFF (`/api` instead of `/bff/api`)
- `JobStatus` component exists but unmounted
- `AssetViewer` uses presigned 307 redirect (SECURITY-08 violation)
- No SSE consumption for job progress
- No idempotency key generation strategy

---

## Security Architecture

| Requirement | Implementation | Status |
|-------------|----------------|--------|
| SEC-3/12: CSP | middleware.ts nonce-based CSP | ✅ |
| SEC-4: Nonce per request | Edge runtime crypto.randomUUID() | ✅ |
| SEC-8: Gateway injects principal | BFF `/bff/*` routes, cookie forwarding | ✅ Backend, ❌ Frontend (bypasses BFF) |
| SEC-9: Asset auth re-check | Same-origin asset relay via BFF | ✅ Backend, ❌ Frontend (presigned) |
| SECURITY-08: No presigned URLs | Same-origin delivery | ✅ Backend, ❌ Frontend |
| RJ-AC04: CAS state transitions | Backend ContentJobService | ✅ |
| RJ-AC05: Owner-scoped auth | Backend validates ownership | ✅ |

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Framework | Next.js 15 (App Router, standalone output) |
| React | 18 |
| Language | TypeScript (strict) |
| Styling | CSS Modules + Tailwind (utility) |
| Data Fetching | SWR / custom transport (RouteHandlerTransport, HttpTransport) |
| Testing | Vitest (unit), Playwright (E2E), MockTransport for previews |
| Package Manager | pnpm |
| Lint | ESLint (flat config) |
| Typecheck | tsc |

---

## Deployment

- **Frontend:** Next.js standalone output → containerized
- **BFF:** Same Next.js server (catch-all `/bff/[...path]` route)
- **Gateway:** External (DOCSURI_GATEWAY_URL), cookie-based auth
- **Auth:** HttpOnly session cookie forwarded via BFF
- **Asset Delivery:** Same-origin via BFF (`/bff/api/papers/{id}/assets/{assetId}`)

---

## Relevant Code Locations

| Concern | Path |
|---------|------|
| BFF Proxy | `frontend/app/bff/[...path]/route.ts` |
| Content Job API | `frontend/lib/api/contentJobApi.ts` |
| JobStatus Component | `frontend/components/JobStatus.tsx` |
| AssetViewer Component | `frontend/components/AssetViewer.tsx` |
| Paper Detail Page | `frontend/app/paper/[id]/page.tsx` |
| Paper Detail Island | `frontend/components/PaperDetailIsland.tsx` |
| Summary Modal | `frontend/components/SummaryModal.tsx` |
| DocModelViewer | `frontend/components/DocModelViewer.tsx` |
| BFF Transport | `frontend/lib/api/routeHandlerTransport.ts` |
| Middleware (CSP, Security) | `frontend/middleware.ts` |
| Next Config | `frontend/next.config.mjs` |
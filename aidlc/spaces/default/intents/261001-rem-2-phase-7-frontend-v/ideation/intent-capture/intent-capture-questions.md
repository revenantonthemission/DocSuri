# Intent Capture Questions — Phase 7 Frontend Wiring

**Gate:** Product Lead Review (advisory)

## Questions for Stakeholder Confirmation

### 1. BFF Routing Strategy
**Question:** All content-job API calls must route through `/bff/api/content-jobs/*` (not direct `/api`). The BFF proxy adds gateway-injected principal headers. Confirm this routing is acceptable.

- A. **Yes, route through `/bff`** (Recommended — SEC-8 compliance)
- B. **No, keep direct `/api` calls** (Breaks SEC-8, not recommended)
- X. Other (please specify)

### 2. SSE vs Polling Fallback
**Question:** Primary progress channel is SSE (`/api/content-jobs/{job_id}/events`). If SSE fails (proxy timeout, browser restriction), should the UI fall back to polling `/state`?

- A. **Yes, implement polling fallback** (Recommended — resilient UX)
- B. **No, SSE only** (Simpler but fragile)
- X. Other (please specify)

### 3. AssetViewer Migration
**Question:** `AssetViewer.tsx` currently expects a presigned 307 redirect. The new same-origin delivery serves bytes directly with `cache-control: private, max-age=60`. This requires:
- Removing presigned URL logic
- Using `<img src="/bff/api/papers/{paper_id}/assets/{asset_id}" />` pattern
- Re-checking auth/license at delivery (already implemented in backend)

Confirm this migration approach.

- A. **Yes, migrate to same-origin delivery** (Recommended — SEC-9 compliance)
- B. **No, keep presigned URLs** (Breaks SECURITY-08, not recommended)
- X. Other (please specify)

### 4. JobStatus Mount Points
**Question:** Where should `JobStatus` be mounted in the UI?

- A. **Detail page only** (Paper detail view, near summary/translate buttons)
- B. **Global toast/notification** (Persistent across navigation)
- C. **Both** (Detail page primary, toast for background jobs)
- X. Other (please specify)

### 5. Idempotency Key Generation
**Question:** Frontend generates idempotency keys for retries. Should keys be:
- A. **Client-generated UUID v4** (Simple, stateless)
- B. **Hash of (userId, paperId, task, params)** (Deterministic, survives page reload)
- C. **Server-generated on first submit** (Returned in receipt, client stores)
- X. Other (please specify)

### 6. Error State UX
**Question:** When a job reaches `FAILED` state, what should the UI show?

- A. **Inline error with "Retry" button** (Re-submits with same idempotency key)
- B. **Toast notification + link to job detail**
- C. **Both inline + toast**
- X. Other (please specify)

### 7. Asset Delivery Cache Headers
**Question:** Same-origin asset delivery returns `cache-control: private, max-age=60`. Confirm this is acceptable for:
- Figures/tables in detail view
- Private userdoc assets (when implemented)
- No CDN caching (private = browser only)

- A. **Yes, 60s private cache is fine**
- B. **No, different cache policy needed** (Specify)
- X. Other (please specify)

---

## Assumptions Being Carried Forward

| # | Assumption | Source |
|---|------------|--------|
| 1 | Backend `/api/content-jobs/*` endpoints are stable and tested | Phase 1-6 complete |
| 2 | SSE `Last-Event-ID` header is supported by backend | Implemented in gateway_seam |
| 3 | BFF proxy exists at `/bff` and injects `x-principal-user-id` | Existing architecture |
| 4 | `AssetViewer` presigned URL logic is isolated and removable | Component audit complete |
| 5 | `JobStatus` component exists and consumes SSE | Component exists, unmounted |
| 5 | Frontend uses Next.js App Router with BFF proxy config | `next.config.mjs` has rewrites |
| 6 | Owner-scoped auth enforced at every backend boundary | RJ-AC05 verified in tests |

## Open Questions Requiring Backend Input

1. **Novelty/Evidence/Ingest job types**: Backend accepts these `taskType` values but worker only handles summarize/translate. Should frontend disable these in UI until workers exist?
2. **Job cancellation**: `ABSTAINED` state exists but no cancel endpoint. Add `/api/content-jobs/{job_id}/cancel`?
3. **Job list/history endpoint**: Need `GET /api/content-jobs` for "My Jobs" page?

---

## Confirmation

**Please respond with your choices (A/B/C/X) for questions 1-7 above.** Any "X" responses should include a brief explanation.

[Answer]: A / B / C / X

---

*This form will be reviewed by the Product Lead (advisory). The gate passes on explicit confirmation or if no objections are raised within 24 hours.*
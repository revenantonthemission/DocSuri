# Business Rules — AssetViewer

**Unit:** AssetViewer
**Phase:** Construction — Functional Design
**Date:** 2026-10-02

---

## Business Rules

### BR-ASV-001: Same-Origin Delivery Only
**Description:** AssetViewer MUST use same-origin delivery via BFF proxy. NO presigned URLs.
**Implementation:**
- `<img src="/bff/api/papers/{paperId}/assets/{assetId}" />`
- NO presigned URL generation or 307 redirect handling
- BFF proxy handles auth re-check at delivery time (SEC-9)

### BR-ASV-002: Auth Re-Check at Delivery
**Description:** Every asset request MUST re-check authorization at delivery time.
**Implementation:** Handled by BFF `proxyAssetImage()`:
- Validates ownership/license before serving bytes
- Returns 403 if requester is not owner
- Returns 404 if asset doesn't exist
- Returns 200 + image bytes on success

### BR-ASV-003: Cache Control
**Description:** Assets MUST respect cache-control headers from backend.
**Headers:** `cache-control: private, max-age=60`
**Behavior:**
- Browser caches for 60 seconds
- No CDN caching (private)
- Revalidation on each request after 60s

### BR-ASV-004: Content-Type Validation
**Description:** Response MUST be valid image content type.
**Validation:**
- Response `Content-Type` must start with `image/`
- Non-image responses → 404 degrade
- Prevents content-type confusion attacks

### BR-ASV-005: Loading & Error States
**Description:** AssetViewer MUST handle all loading/error states gracefully.
**States:**
1. **Loading** — Spinner overlay, aspect-ratio preserved
2. **Loaded** — Image displayed, fade-in animation
3. **Error (401/403)** — "접근 권한이 없습니다" + retry button
4. **Error (404)** — "자산을 찾을 수 없습니다" + retry button
4. **Error (5xx/Network)** — "자산 로드 실패" + retry button

### BR-ASV-006: Zoom/Pan Controls (US5.3)
**Description:** Large assets MUST support zoom and pan.
**Interactions:**
- **Desktop:** Mouse wheel zoom, click-drag pan, double-click reset
- **Touch:** Pinch zoom, two-finger pan, double-tap reset
- **Keyboard:** `+/-` zoom, arrow keys pan, `0` reset
- **Zoom Range:** 0.5x to 4x
- **Transition:** `transform 200ms ease-out` (respects `prefers-reduced-motion`)

### BR-ASV-007: No Presigned URLs (SECURITY-08)
**Description:** NEVER use presigned URLs or 307 redirects.
**Enforcement:**
- ESLint rule forbids presigned URL patterns
- AssetViewer component only accepts `paperId` + `assetId` props
- Direct `<img src="/bff/api/papers/{paperId}/assets/{assetId}" />`

### BR-ASV-008: Accessibility (WCAG 2.1 AA)
**Requirements:**
- Alt text from caption/figcaption
- Keyboard operable zoom controls (`aria-label`)
- High contrast mode support
- Reduced motion respected (zoom transitions)

---

## Data Invariants

### Invariant: Asset Belongs to Paper
**Statement:** Every Asset references exactly one Paper via `paperId`.
**Violation:** Orphaned asset or cross-paper reference.

### Invariant: Auth Re-Check on Every Request
**Statement:** Every asset request triggers fresh auth check at gateway.
**Violation:** Cached auth bypassed = SEC-9 violation.

### Invariant: No Presigned URLs in Component
**Statement:** AssetViewer component never receives or uses presigned URLs.
**Violation:** Props contain `token` or `presignedUrl` = SECURITY-08 violation.

---

## Error Scenarios

| Scenario | Detection | Recovery |
|----------|-----------|----------|
| 401/403 on asset load | `img.onError` + status check | Show "접근 권한이 없습니다" + reload page button |
| 404 not found | 404 status | Show "자산을 찾을 수 없습니다" + retry |
| 5xx / network error | `img.onError` / fetch fail | Show "자산 로드 실패" + retry button |
| Wrong content-type | `Content-Type` check | Degrade to 404, no broken image |
| Zoom/pan state lost on error | State reset on error | Reset zoom/pan on retry |
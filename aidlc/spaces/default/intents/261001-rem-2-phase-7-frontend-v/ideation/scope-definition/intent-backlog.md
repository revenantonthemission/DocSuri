# Intent Backlog — Phase 7 Frontend Wiring

**Intent ID:** 261001-rem-2-phase-7-frontend
**Scope:** feature
**Date:** 2026-10-02
**Prioritization:** Dependency-first sequencing with MoSCoW classification

---

## Proto-Units (Delivery Planning Units)

| Unit ID | Name | MoSCoW | WSJF* | Dependencies | Description |
|---------|------|--------|-------|--------------|-------------|
| U1 | BFF Routing Foundation | Must | 100 | — | Update `contentJobApi.ts` to route all calls through `/bff/api/content-jobs/*` |
| U2 | JobStatus SSE Integration | Must | 90 | U1 | Wire `JobStatus.tsx` to SSE endpoint with `Last-Event-ID` resume |
| U3 | JobStatus Mount in DetailPage | Must | 85 | U2 | Mount JobStatus component in PaperView near summary/translate |
| U4 | AssetViewer Same-Origin Migration | Must | 80 | U1 | Replace presigned 307 redirect with same-origin delivery pattern |
| U5 | Idempotency Key Generation | Must | 75 | U1 | Hash-based keys (userId+paperId+task+params) with localStorage persistence |
| U6 | Inline Retry on FAILED | Must | 70 | U2, U5 | Retry button in JobStatus re-submits with same idempotency key |
| U7 | SSE Polling Fallback | Should | 60 | U2 | SWR/TanStack Query polls `/state` at 2s when SSE disconnects |
| U8 | JobStatus Error Boundary | Should | 55 | U2 | React Error Boundary wrapper with graceful fallback UI |
| U9 | JobStatus Accessibility | Should | 50 | U2 | ARIA live region, keyboard navigation, screen reader support |

*WSJF = Weighted Shortest Job First (relative score: Value × Urgency / Effort)

---

## Detailed Backlog Items

### U1: BFF Routing Foundation [Must]
**Effort:** 0.5 days | **Branch:** `feat/bff-routing` | **Owner:** Frontend

**Acceptance Criteria:**
- [ ] `contentJobApi.ts` base URL updated to `/bff/api/content-jobs`
- [ ] All existing call sites work without modification
- [ ] Integration test verifies `x-principal-user-id` header present on requests
- [ ] No direct `/api/content-jobs/*` calls remain in codebase
- [ ] All 356 existing frontend tests pass

**Technical Notes:**
- Update `src/lib/api/contentJobApi.ts` base path
- Verify `next.config.mjs` rewrites handle `/bff` → backend correctly
- Add test: `expect(request.headers.get('x-principal-user-id')).toBeDefined()`

---

### U2: JobStatus SSE Integration [Must]
**Effort:** 1.5 days | **Branch:** `feat/jobstatus-sse` | **Owner:** Frontend | **Depends on:** U1

**Acceptance Criteria:**
- [ ] `JobStatus.tsx` uses native `EventSource` to connect to `/api/content-jobs/{job_id}/events`
- [ ] `Last-Event-ID` header sent on reconnect for event replay
- [ ] Component displays real-time state: SUBMITTED → ACCEPTED → QUEUED → RUNNING → COMPLETED/FAILED
- [ ] Connection state managed (connecting, connected, disconnected, reconnecting)
- [ ] Unit tests cover: connection, message parsing, reconnect logic, error handling

**Technical Notes:**
- Use `EventSource` API with `withCredentials: true` for auth
- Implement exponential backoff for reconnect (max 30s)
- Handle `message`, `error`, `open` events
- Parse SSE data as JSON: `{ seq: number, type: string, payload: object }`

---

### U3: JobStatus Mount in DetailPage [Must]
**Effort:** 0.5 days | **Branch:** `feat/jobstatus-mount` | **Owner:** Frontend | **Depends on:** U2

**Acceptance Criteria:**
- [ ] `JobStatus` component rendered in `PaperView`/`DetailPage` near summary/translate buttons
- [ ] Receives `jobId` prop from parent (from content job submission response)
- [ ] Loading state shown while connecting to SSE
- [ ] Error state shown if SSE fails permanently (with fallback to polling)

**Technical Notes:**
- Locate mount point in `src/app/papers/[id]/PaperView.tsx` or similar
- Pass `jobId` from job submission hook/context
- Conditional render: only show when `jobId` exists

---

### U4: AssetViewer Same-Origin Migration [Must]
**Effort:** 1 day | **Branch:** `feat/assetviewer-migration` | **Owner:** Frontend | **Depends on:** U1

**Acceptance Criteria:**
- [ ] `AssetViewer.tsx` no longer uses presigned URL logic
- [ ] Component uses `<img src="/bff/api/papers/{paper_id}/assets/{asset_id}" />` pattern
- [ ] No 307 redirects in network tab for asset loads
- [ ] SECURITY-08 violation removed — security review sign-off obtained
- [ ] Figures/tables render correctly in DetailPage
- [ ] Cache headers respected: `cache-control: private, max-age=60`

**Technical Notes:**
- Remove presigned URL generation/handling code
- Update prop interface: accept `paperId` + `assetId` instead of presigned URL
- Backend already implements auth re-check at delivery (SEC-9)
- Test with private assets (different owners cannot access)

---

### U5: Idempotency Key Generation [Must]
**Effort:** 0.5 days | **Branch:** `feat/idempotency-keys` | **Owner:** Frontend | **Depends on:** U1

**Acceptance Criteria:**
- [ ] Key generated as SHA-256 hash of `(userId + paperId + taskType + JSON.stringify(params))`
- [ ] Key stored in `localStorage` with key format: `idempotency:{paperId}:{taskType}`
- [ ] Key retrieved on retry; same key sent with repeat submission
- [ ] Key cleared on explicit user action (e.g., "Clear retry state" button)
- [ ] Unit tests: hash determinism, storage, retrieval, clearing

**Technical Notes:**
```typescript
function generateIdempotencyKey(userId: string, paperId: string, task: string, params: object): string {
  const input = `${userId}:${paperId}:${task}:${JSON.stringify(params)}`;
  return crypto.subtle.digest('SHA-256', new TextEncoder().encode(input));
}
```
- Use Web Crypto API for hashing
- localStorage key: `idempotency:${paperId}:${taskType}`

---

### U6: Inline Retry on FAILED [Must]
**Effort:** 0.5 days | **Branch:** `feat/inline-retry` | **Owner:** Frontend | **Depends on:** U2, U5

**Acceptance Criteria:**
- [ ] When job state = FAILED, JobStatus shows "Retry" button
- [ ] Clicking Retry re-submits with same idempotency key (from localStorage)
- [ ] Button disabled during submission; shows loading state
- [ ] On success, JobStatus resets to show new job progress
- [ ] Accessible: keyboard focus, ARIA label

**Technical Notes:**
- Use existing `contentJobApi.submit()` with `idempotencyKey` option
- Retrieve key from localStorage before submit
- Handle race condition: if key missing, generate new (warn user)

---

### U7: SSE Polling Fallback [Should]
**Effort:** 0.5 days | **Branch:** `feat/sse-polling-fallback` | **Owner:** Frontend | **Depends on:** U2

**Acceptance Criteria:**
- [ ] When SSE `EventSource` enters error state, polling activates automatically
- [ ] Polling uses SWR/TanStack Query at 2s fixed interval to `/api/content-jobs/{job_id}/state`
- [ ] Polling stops when SSE reconnects successfully
- [ ] No duplicate state updates (SSE is source of truth when connected)
- [ ] Unit tests: fallback activation, polling interval, graceful handoff

**Technical Notes:**
- Use `useSWR` with `refreshInterval: 2000` and conditional fetch
- Track SSE connection state: `connected` → `error` → `reconnecting` → `connected`
- Only poll when `!sseConnected && jobNotTerminal`

---

### U8: JobStatus Error Boundary [Should]
**Effort:** 0.5 days | **Branch:** `feat/jobstatus-error-boundary` | **Owner:** Frontend | **Depends on:** U2

**Acceptance Criteria:**
- [ ] `JobStatus` wrapped in class-based Error Boundary (React 18)
- [ ] On error: fallback UI shows "Unable to load job status" with "Retry connection" button
- [ ] Error logged to console/error tracking service
- [ ] Fallback preserves layout (no layout shift)
- [ ] Test: simulate component crash, verify fallback renders

**Technical Notes:**
```tsx
class JobStatusErrorBoundary extends React.Component {
  state = { hasError: false, error: null };
  static getDerivedStateFromError(error) { return { hasError: true, error }; }
  render() { if (this.state.hasError) return <JobStatusFallback />; return this.props.children; }
}
```
- Fallback component: inline, matches JobStatus dimensions

---

### U9: JobStatus Accessibility [Should]
**Effort:** 0.5 days | **Branch:** `feat/jobstatus-a11y` | **Owner:** Frontend | **Depends on:** U2

**Acceptance Criteria:**
- [ ] `role="status"` with `aria-live="polite"` on state display
- [ ] State changes announced to screen readers
- [ ] Retry button: `aria-label="Retry job"`, keyboard accessible
- [ ] Progress indicator: `role="progressbar"` with `aria-valuenow`/`aria-valuemin`/`aria-valuemax`
- [ ] Color contrast ≥ 4.5:1 for all states
- [ ] Test: axe-core + manual screen reader (NVDA/VoiceOver)

**Technical Notes:**
- Map job states to progress values: SUBMITTED=10, ACCEPTED=20, QUEUED=30, RUNNING=50, COMPLETED=100, FAILED=0
- Use `visually-hidden` for live region text

---

## Sequencing Summary

```
Phase 1 (Foundation):     U1 → 0.5d
Phase 2a (JobStatus):     U2 → 1.5d → U3 (0.5d) → U7 (0.5d) → U8 (0.5d) → U9 (0.5d)
Phase 2b (AssetViewer):   U4 → 1d
Phase 3 (Polish):         U5 (0.5d) → U6 (0.5d)
Phase 4 (Hardening):      Testing + Security Review → 1.5d

Total: ~6.5 days | All branches trunk-based, squash-merge
```

---

## Value Stream Map

```
Idea → BFF Routing → JobStatus SSE → JobStatus Mount → Idempotency + Retry
                      ↘ AssetViewer Migration ↗
                              ↓
                        Testing + Security → Done
```

**Lead Time Target:** 6.5 days (feature scope standard)
**Cycle Time per Unit:** 0.5-1.5 days (trunk-based, 1-2 day branches)
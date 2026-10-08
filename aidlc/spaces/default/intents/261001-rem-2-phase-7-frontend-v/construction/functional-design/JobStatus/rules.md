# Business Rules — JobStatus

**Unit:** JobStatus
**Phase:** Construction — Functional Design
**Date:** 2026-10-02

---

## Business Rules

### BR-JST-001: SSE Connection Lifecycle
**Description:** JobStatus manages SSE connection lifecycle automatically.
**States:** `connecting` → `connected` → `reconnecting` → `polling` → `disconnected`
**Transitions:**
- Mount → `connecting` → SSE open → `connected`
- SSE error → `reconnecting` (max 3 attempts: 1s, 2s, 4s)
- 3 failed reconnects → `polling` (SWR 2s interval)
- SSE reconnects → `connected` (polling stops)
- Terminal state → `disconnected` (polling stops)

### BR-JST-002: SSE Event Processing
**Description:** SSE events drive JobState updates.
**Event Format:**
```json
{
  "eventId": "evt_...",
  "jobId": "job_...",
  "state": "RUNNING",
  "timestampUs": 1234567890123,
  "payload": { "progress": 45, "assetId": "asset_123" }
}
```
**Processing:**
1. Parse `event.data` as JSON
2. Validate `state` is known enum
3. Update `state`, `progress`, `assetId`, `error`
4. Append to `eventHistory` with timestamp

### BR-JST-003: SSE Reconnection with Last-Event-ID
**Description:** SSE reconnection uses Last-Event-ID for event replay.
**Behavior:**
1. On reconnect, include `Last-Event-ID: <lastEventId>` header
2. Backend replays missed events
3. Events processed in order, deduplicated by `eventId`
4. Max 3 attempts with exponential backoff (1s, 2s, 4s)

### BR-JST-004: Polling Fallback
**Description:** SWR polling activates when SSE fails completely.
**Configuration:**
- Interval: 2000ms fixed
- Endpoint: `/bff/api/content-jobs/{jobId}/state`
- Fallback data: last known SSE state
- Deduplication: ignore polling updates if SSE connected

### BR-JST-005: Job Completion Flow
**Description:** Terminal states trigger completion callback.
**Terminal States:** `COMPLETED`, `FAILED`, `ABSTAINED`
**Callback:** `onComplete(state, assetId?, error?)`
**UI:** Shows "결과 보기" (View Result) button on COMPLETED

### BR-JST-006: Inline Retry on FAILED
**Description:** FAILED state shows inline Retry button.
**Behavior:**
1. FAILED state → show "🔄 재시도" (Retry) button
2. Click → retrieve idempotency key from localStorage
3. Call `ContentJobApi.submitJob()` with SAME idempotency key
4. JobStatus resets to `SUBMITTED` state
5. New SSE connection established

### BR-JST-007: Retry with Modified Parameters
**Description:** Optional "Retry with Changes" for parameter adjustment.
**Behavior:**
1. Click "수정 후 재시도" → opens modal with editable params
2. User modifies params → submits
3. NEW idempotency key generated (different params = new key)
4. New job submitted, old job abandoned

### BR-JST-008: Error Boundary Wrapper
**Description:** JobStatus wrapped in React Error Boundary.
**Fallback UI:**
- Message: "작업 상태를 불러올 수 없습니다"
- Button: "연결 다시 시도" (Retry Connection)
- Error logged to console + Sentry
- Layout preserved (no layout shift)

### BR-JST-009: Error Boundary Retry
**Description:** Error Boundary fallback has retry button.
**Behavior:**
1. Click "연결 다시 시도" → `setState({ hasError: false })`
2. JobStatus remounts
3. SSE reconnects with Last-Event-ID
3. Current state displayed

### BR-JST-010: Accessibility (WCAG 2.1 AA)
**Requirements:**
- `role="status" aria-live="polite"` on status container
- Progress bar: `role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow={progress}`
- State changes announced: "작업 상태: 처리중, 45% 완료"
- Retry button: `aria-label="작업 재시도"`, keyboard accessible
- Dismiss button: `aria-label="작업 상태 닫기"`, Escape key
- Color contrast ≥ 4.5:1 for all states
- `prefers-reduced-motion` respected (progress animation)

---

## Data Invariants

### Invariant: JobId Stability
**Statement:** `jobId` never changes for the lifetime of a JobStatus instance.
**Violation:** Component remount with different jobId = new component.

### Invariant: Event History Completeness
**Statement:** `eventHistory` contains all received events in order.
**Violation:** Missing events = SSE gap or processing bug.

### Invariant: Connection State Consistency
**Statement:** `connectionState` accurately reflects SSE/polling status.
**Violation:** UI shows "Live" but SSE disconnected.

---

## Error Scenarios

| Scenario | Detection | Recovery |
|----------|-----------|----------|
| SSE connect fails | `EventSource.onerror` | Reconnect (3x) → polling |
| SSE reconnect fails (3x) | Attempt counter | Switch to polling (SWR 2s) |
| Polling fetch fails | SWR `onError` | Retry next interval |
| JobStatus render error | Error Boundary | Fallback UI + retry button |
| Error Boundary retry fails | State still error | Fallback persists, log to Sentry |
| AssetId missing on COMPLETED | `assetId` undefined | Show "완료" without asset link |
| Retry with missing idempotency key | `getKey()` returns null | Generate new key, warn user |
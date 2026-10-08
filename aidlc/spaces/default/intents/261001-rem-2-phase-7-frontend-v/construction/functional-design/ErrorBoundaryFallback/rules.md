# Business Rules — ErrorBoundaryFallback

**Unit:** ErrorBoundaryFallback
**Phase:** Construction — Functional Design
**Date:** 2026-10-02

---

## Business Rules

### BR-EBF-001: Minimal Fallback UI
**Description:** ErrorBoundaryFallback MUST provide a minimal, clear fallback UI.
**Content:**
- Message: "작업 상태를 불러올 수 없습니다" (Unable to load job status)
- Hint: "백그라운드에서 작업이 계속 실행 중일 수 있습니다." (Job may still be running in background)
- Actions: "연결 다시 시도" (Retry Connection) button, "닫기" (Dismiss) button

### BR-EBF-002: Retry Mechanism
**Description:** Fallback MUST provide a retry mechanism.
**Behavior:**
1. Click "연결 다시 시도" (Retry Connection)
2. Calls `onRetry` callback
2. ErrorBoundary resets state (`hasError: false`)
3. JobStatus remounts
4. SSE reconnects with `Last-Event-ID`

### BR-EBF-003: Dismiss Action
**Description:** Fallback MUST provide dismiss option.
**Behavior:**
1. Click "닫기" (Dismiss)
2. Reloads page (simplest recovery)

### BR-EBF-004: Layout Preservation
**Description:** Fallback UI MUST preserve layout.
**Requirements:**
- Same dimensions as JobStatus card
- Same border, padding, shadow
- Inline fallback (not full-screen overlay)
- No layout shift

### BR-EBF-005: Error Logging
**Description:** Error MUST be logged when fallback renders.
**Implementation:**
```typescript
useEffect(() => {
  console.error('JobStatus Error:', error);
  if (window.Sentry) {
    window.Sentry.captureException(error);
  }
}, [error]);
```

---

## Data Invariants

### Invariant: Layout Preservation
**Statement:** Fallback UI dimensions match JobStatus card.
**Violation:** Layout shift when fallback shows.

### Invariant: Retry Restores Functionality
**Statement:** After retry, JobStatus remounts and functions normally.
**Violation:** Retry button does nothing = broken retry.

---

## Error Scenarios

| Scenario | Detection | Recovery |
|----------|-----------|----------|
| JobStatus render error | ErrorBoundary catches | Fallback UI + retry button |
| Retry fails again | ErrorBoundary catches again | Fallback persists |
| Retry succeeds | ErrorBoundary resets | JobStatus remounts, works normally |
| Sentry unavailable | Console log only | No crash |
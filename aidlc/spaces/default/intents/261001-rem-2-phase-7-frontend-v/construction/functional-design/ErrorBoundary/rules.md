# Business Rules — ErrorBoundary

**Unit:** ErrorBoundary
**Phase:** Construction — Functional Design
**Date:** 2026-10-02

---

## Business Rules

### BR-EBD-001: Class-Based Error Boundary
**Description:** ErrorBoundary MUST be a class component (React 18 requirement for getDerivedStateFromError).
**Implementation:**
```typescript
class ErrorBoundary extends React.Component<Props, State> {
  state = { hasError: false, error: null, errorInfo: null };
  
  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }
  
  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    this.setState({ hasError: true, error, errorInfo });
    logErrorToSentry(error, errorInfo);
  }
}
```

### BR-EBD-002: Graceful Degradation
**Description:** ErrorBoundary MUST catch render errors in JobStatus and display fallback UI.
**Behavior:**
- Catches render errors in JobStatus (and any wrapped children)
- Renders fallback UI instead of crashing parent
- Preserves layout (no layout shift)
- Logs error to console + Sentry

### BR-EBD-003: Fallback UI
**Description:** Fallback UI MUST provide meaningful error message and recovery action.
**Content:**
- Message: "작업 상태를 불러올 수 없습니다" (Unable to load job status)
- Hint: "백그라운드에서 작업이 계속 실행 중일 수 있습니다." (Job may still be running in background)
- Action: "연결 다시 시도" (Retry Connection) button
- Layout preserved (no layout shift)

### BR-EBD-004: Error Logging
**Description:** All caught errors MUST be logged to console and Sentry.
**Implementation:**
```typescript
componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
  console.error('JobStatus Error:', error, errorInfo);
  Sentry.captureException(error, { extra: { componentStack: errorInfo.componentStack } });
}
```

### BR-EBD-005: Retry Connection
**Description:** Fallback UI MUST provide retry mechanism.
**Behavior:**
1. Click "연결 다시 시도" (Retry Connection)
2. ErrorBoundary resets state (`hasError: false`)
3. JobStatus remounts
4. SSE reconnects with `Last-Event-ID`
5. Current state displayed

### BR-EBD-006: Sentry Integration
**Description:** All caught errors MUST be reported to Sentry.
**Implementation:**
```typescript
componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
  Sentry.captureException(error, {
    extra: { 
      componentStack: errorInfo.componentStack,
      componentName: 'JobStatus'
    }
  });
}
```

### BR-EBD-007: Layout Preservation
**Description:** Fallback UI MUST NOT cause layout shift.
**Requirements:**
- Same dimensions as JobStatus card
- Same border, padding, shadow
- Inline fallback (not full-screen overlay)

---

## Data Invariants

### Invariant: Single Error per Boundary
**Statement:** Each ErrorBoundary instance catches at most one error at a time.
**Violation:** Multiple simultaneous errors = nested boundaries needed.

### Invariant: Error Recovery
**Statement:** After retry, ErrorBoundary state resets cleanly.
**Violation:** Stuck in error state after retry = state management bug.

---

## Error Scenarios

| Scenario | Detection | Recovery |
|----------|-----------|----------|
| JobStatus render error | `getDerivedStateFromError` | Fallback UI + retry button |
| SSE connection error in render | `componentDidCatch` | Fallback + Sentry log |
| Async error in SSE handler | Not caught by ErrorBoundary | Handle in SSE `onerror` |
| Sentry unavailable | `Sentry.captureException` fails | Console log only, no crash |
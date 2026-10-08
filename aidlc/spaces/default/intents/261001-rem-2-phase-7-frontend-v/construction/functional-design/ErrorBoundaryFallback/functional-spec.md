# Functional Specification — ErrorBoundaryFallback

**Unit:** ErrorBoundaryFallback
**Phase:** Construction — Functional Design
**Date:** 2026-10-02
**Kind:** ui

---

## Overview

ErrorBoundaryFallback is a stateless React component that renders the fallback UI when ErrorBoundary catches an error. It provides a minimal, clear UI with retry and dismiss options.

---

## Props

```typescript
interface ErrorBoundaryFallbackProps {
  onRetry: () => void;
  error?: Error; // Optional, for logging
}
```

---

## UI Specification

```
┌─────────────────────────────────────────────────────────────┐
│  ⚠️  작업 상태를 불러올 수 없습니다                          │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  작업 상태 컴포넌트에서 오류가 발생했습니다.           │  │
│  │  백그라운드에서 작업이 계속 실행 중일 수 있습니다.      │  │
│  └───────────────────────────────────────────────────────┘  │
│  [🔄 연결 다시 시도]  [닫기]                                │
└─────────────────────────────────────────────────────────────┘
```

### UI Elements

| Element | Text | Action |
|---------|------|--------|
| Icon | ⚠️ | — |
| Title | "작업 상태를 불러올 수 없습니다" | — |
| Description | "작업 상태 컴포넌트에서 오류가 발생했습니다. 백그라운드에서 작업이 계속 실행 중일 수 있습니다." | — |
| Retry Button | "🔄 연결 다시 시도" | Calls `onRetry` |
| Dismiss Button | "닫기" | Reloads page |

### Retry Flow
```
User clicks "연결 다시 시도"
        │
        ▼
Calls onRetry()
        │
        ▼
ErrorBoundary.resetError()
        │
        ▼
JobStatus remounts
        │
        ▼
SSE reconnects with Last-Event-ID
        │
        ▼
Current job state displayed
```

### Dismiss Flow
```
User clicks "닫기"
        │
        ▼
window.location.reload()
        │
        ▼
Page reloads, fresh state
```

---

## Component API

```typescript
interface ErrorBoundaryFallbackProps {
  onRetry: () => void;
  error?: Error; // Optional, for logging
}
```

```tsx
export function ErrorBoundaryFallback({ onRetry, error }: ErrorBoundaryFallbackProps) {
  useEffect(() => {
    if (error) {
      console.error('JobStatus Error:', error);
      if (window.Sentry) {
        window.Sentry.captureException(error);
      }
    }
  }, [error]);

  return (
    <div className={styles.fallback} role="alert">
      <p className={styles.text}>작업 상태를 불러올 수 없습니다.</p>
      <p className={styles.hint}>백그라운드에서 작업이 계속 실행 중일 수 있습니다.</p>
      <button 
        className={styles.retryButton}
        onClick={onRetry}
        aria-label="연결 다시 시도"
      >
        🔄 연결 다시 시도
      </button>
      <button 
        className={styles.dismissButton}
        onClick={() => window.location.reload()}
        aria-label="닫기"
      >
        닫기
      </button>
    </div>
  );
}
```

---

## CSS Module (ErrorBoundaryFallback.module.css)

```css
.fallback {
  @apply p-4 border border-red-200 rounded-xl bg-red-50 min-h-[120px];
}

.fallback_text {
  @apply text-red-700 mb-2;
}

.fallback_hint {
  @apply text-red-600 text-sm mb-2;
}

.fallback_retryButton {
  @apply mt-2 text-sm text-blue-600 hover:underline inline-block;
}

.fallback_dismissButton {
  @apply mt-2 text-sm text-gray-500 hover:underline inline-block ml-2;
}

/* Layout preservation */
.fallback {
  @apply min-h-[120px]; /* Match JobStatus card height */
}
```

---

## Accessibility

| Requirement | Implementation |
|-------------|----------------|
| Role | `role="alert"` on container |
| Retry button | `aria-label="연결 다시 시도"` |
| Dismiss button | `aria-label="닫기"` |
| Focus | Retry button auto-focused on mount |

---

## Integration

```tsx
// In ErrorBoundary.render()
render() {
  if (this.state.hasError) {
    if (this.props.fallback) {
      return this.props.fallback;
    }
    return <ErrorBoundaryFallback onRetry={this.resetError} error={this.state.error} />;
  }
  return this.props.children;
}
```

---

## Test Points

| Scenario | Test |
|----------|------|
| Render fallback | Correct UI shown |
| Retry button | Calls onRetry, resets ErrorBoundary |
| Dismiss button | Reloads page |
| Error logging | Console + Sentry |
| Layout | No shift when fallback shows |
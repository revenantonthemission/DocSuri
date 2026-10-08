# Frontend Components — ErrorBoundary

**Unit:** ErrorBoundary
**Phase:** Construction — Functional Design
**Date:** 2026-10-02

---

## Component Overview

ErrorBoundary is a **ui** class component that provides graceful degradation for JobStatus (and other SSE-consuming components). It catches render errors, displays a fallback UI with retry capability, and logs errors to Sentry.

---

## Component API

### Props
```typescript
interface ErrorBoundaryProps {
  children: React.ReactNode;
  fallback?: React.ReactNode; // Custom fallback (optional)
  onError?: (error: Error, errorInfo: React.ErrorInfo) => void;
  className?: string;
}
```

### Internal State
```typescript
interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  errorInfo: React.ErrorInfo | null;
}
```

---

## Internal Structure

### Main Component: ErrorBoundary (Class Component)
```typescript
class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state = { hasError: false, error: null, errorInfo: null };

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo): void {
    this.setState({ hasError: true, error, errorInfo });
    
    console.error('ErrorBoundary caught:', error, errorInfo);
    
    if (typeof window !== 'undefined' && window.Sentry) {
      window.Sentry.captureException(error, {
        extra: { 
          componentStack: errorInfo.componentStack,
          componentName: 'JobStatus'
        }
      });
    }
  }

  resetError = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }
      return <ErrorBoundaryFallback onRetry={this.resetError} />;
    }
    return this.props.children;
  }

  resetError = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
  };
}
```

---

## Sub-component: ErrorBoundaryFallback

### Props
```typescript
interface ErrorBoundaryFallbackProps {
  onRetry: () => void;
}
```

### UI
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

### Props
```typescript
interface ErrorBoundaryFallbackProps {
  onRetry: () => void;
}
```

### UI Elements
| Element | Text | Action |
|---------|------|--------|
| Message | "작업 상태를 불러올 수 없습니다" | — |
| Hint | "백그라운드에서 작업이 계속 실행 중일 수 있습니다." | — |
| Retry Button | "🔄 연결 다시 시도" | Calls `onRetry` |
| Dismiss Button | "닫기" | Reloads page |

---

## Integration Points

### With JobStatus (PaperDetailIsland)
```tsx
{activeJobId && (
  <ErrorBoundary>
    <JobStatus 
      jobId={activeJobId} 
      onComplete={handleJobComplete} 
    />
  </ErrorBoundary>
)}
```

### With Sentry
```typescript
// Sentry initialization (in _app.tsx or layout.tsx)
import * as Sentry from '@sentry/nextjs';

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  tracesSampleRate: 1.0,
  environment: process.env.NODE_ENV,
});

// In ErrorBoundary.componentDidCatch
componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
  Sentry.captureException(error, {
    extra: { 
      componentStack: errorInfo.componentStack,
      componentName: 'JobStatus'
    },
    tags: {
      feature: 'phase-7-content-jobs',
      component: 'JobStatus'
    }
  });
}
```

---

## CSS Module (ErrorBoundary.module.css)

```css
.errorBoundary {
  @apply p-4 border border-red-200 rounded-xl bg-red-50;
}

.errorBoundary_text {
  @apply text-red-700 mb-2;
}

.errorBoundary_hint {
  @apply text-red-600 text-sm mb-2;
}

.errorBoundary_retryButton {
  @apply mt-2 text-sm text-blue-600 hover:underline inline-block;
}

.errorBoundary_dismissButton {
  @apply mt-2 text-sm text-gray-500 hover:underline inline-block ml-2;
}

/* Layout preservation */
.errorBoundary_fallback {
  @apply min-h-[120px]; /* Match JobStatus card height */
}
```

---

## Test Points

| Scenario | Test |
|----------|------|
| Render error in JobStatus | ErrorBoundary catches, shows fallback |
| Error in child component | ErrorBoundary catches, parent unaffected |
| Retry button click | Resets state, remounts JobStatus |
| Sentry unavailable | Console log only, no crash |
| Layout shift | No shift when fallback shows |
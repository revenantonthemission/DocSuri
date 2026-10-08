# Frontend Components — JobStatus

**Unit:** JobStatus
**Phase:** Construction — Functional Design
**Date:** 2026-10-02

---

## Component Overview

JobStatus is a **ui** component that displays real-time job progress via SSE with polling fallback, error handling, retry logic, and full accessibility support.

---

## Component API

### Props
```typescript
interface JobStatusProps {
  jobId: string;
  onComplete?: (state: 'COMPLETED' | 'FAILED' | 'ABSTAINED', assetId?: string, error?: unknown) => void;
  className?: string;
}
```

### Internal Hooks
```typescript
function useJobEvents(jobId: string): {
  state: JobState | null;
  connectionState: ConnectionState;
  eventHistory: string[];
  lastEventId: string | null;
  subscribe: () => () => void;
}
```

---

## Internal Structure

### Sub-components (Internal)

| Component | Purpose |
|-----------|---------|
| `JobStatusHeader` | Title + state badge + dismiss button |
| `JobStatusProgress` | Progress bar with percentage |
| `JobStatusState` | State label + progress % + assetId |
| `JobStatusError` | Error display + expandable details |
| `JobStatusHistory` | Collapsible event history |
| `JobStatusActions` | Retry / Retry with Changes / Dismiss buttons |
| `JobStatusErrorBoundary` | Error Boundary wrapper |
| `JobStatusFallback` | Error Boundary fallback UI |

---

## Integration Points

### Parent: PaperDetailIsland
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

### Dependencies
| Dependency | Purpose |
|------------|---------|
| `ContentJobApi.subscribeJobEvents()` | SSE subscription |
| `ContentJobApi.getJobState()` | Polling fallback |
| `ContentJobApi.submitJob()` | Retry with same idempotency key |
| `IdempotencyService.getKey()` | Retrieve stored idempotency key |
| `IdempotencyService.generateKey()` | Generate new key for "Retry with Changes" |
| `ErrorBoundary` | Graceful degradation |
| `Sentry` | Error logging (ErrorBoundary) |

---

## Sub-component Specifications

### JobStatusHeader
```tsx
<div className={styles.header}>
  <span className={styles.title}>작업 상태</span>
  <span className={`${styles.state} ${STATE_COLORS[state.state]}`}>
    {STATE_LABELS[state.state]}
  </span>
  <button 
    className={styles.dismiss}
    onClick={() => onComplete?.('ABSTAINED')}
    aria-label="작업 상태 닫기"
  >
    ✕
  </button>
</div>
```

### JobStatusProgress
```tsx
<div className={styles.progressContainer}>
  <div className={styles.progressBar}>
    <div 
      className={styles.progressFill}
      style={{ width: `${progress}%` }}
      role="progressbar"
      aria-valuemin="0"
      aria-valuemax="100"
      aria-valuenow={progress}
    />
  </div>
  <div className={styles.meta}>
    <span>시작: {formatTimeAgo(startTime)}</span>
    <span>마지막 업데이트: {formatTimeAgo(lastUpdate)}</span>
    <LiveIndicator connectionState={connectionState} />
  </div>
</div>
```

### JobStatusState
```tsx
<div className={styles.stateDisplay}>
  {assetId && (
    <div className={styles.assetId}>
      자산 ID: <code className={styles.code}>{assetId}</code>
    </div>
  )}
  {error && (
    <div className={styles.error}>
      오류: {error.message} ({error.errorType})
      {error.retryable && <span className={styles.retryable}> (재시도 가능)</span>}
      <ErrorDetailToggle error={error} />
    </div>
  )}
  {abstainReason && (
    <div className={styles.abstain}>
      기권 사유: {abstainReason}
    </div>
  )}
</div>
```

### JobStatusActions (FAILED state)
```tsx
<div className={styles.actions}>
  <button
    className={`${styles.button} ${styles.retry}`}
    onClick={handleRetry}
    aria-label="작업 재시도"
  >
    🔄 재시도
  </button>
  <button
    className={`${styles.button} ${styles.retryWithChanges}`}
    onClick={handleRetryWithChanges}
    aria-label="수정 후 재시도"
  >
    수정 후 재시도
  </button>
  <button
    className={styles.button}
    onClick={() => onComplete?.('ABSTAINED')}
    aria-label="작업 상태 닫기"
  >
    닫기
  </button>
</div>
```

### LiveIndicator Component
```tsx
function LiveIndicator({ connectionState }: { connectionState: ConnectionState }) {
  const config = {
    connected: { label: '🟢 Live', color: 'text-green-500', pulse: true },
    reconnecting: { label: '🟡 재연결 중...', color: 'text-amber-500', pulse: false },
    polling: { label: '🔴 Polling', color: 'text-red-500', pulse: false },
    disconnected: { label: '⚪ Offline', color: 'text-gray-500', pulse: false },
  };
  
  const { label, color, pulse } = config[connectionState];
  
  return (
    <span className={`${styles.liveIndicator} ${color} ${pulse ? styles.pulse : ''}`}>
      {label}
    </span>
  );
}
```

### ErrorDetailToggle
```tsx
function ErrorDetailToggle({ error }: { error: JobError }) {
  const [expanded, setExpanded] = useState(false);
  
  return (
    <details className={styles.errorDetail}>
      <summary 
        className={styles.summary}
        onClick={() => setExpanded(!expanded)}
        aria-expanded={expanded}
      >
        {expanded ? '▲ 접기' : '▼ 상세 보기'}
      </summary>
      {expanded && (
        <div className={styles.details}>
          <p>오류 타입: {error.errorType}</p>
          <p>메시지: {error.message}</p>
          <p>재시도 가능: {error.retryable ? '예' : '아니오'}</p>
          {error.retryAfterSeconds && (
            <p>재시도 후 대기 시간: {error.retryAfterSeconds}초</p>
          )}
          <pre className={styles.stackTrace}>{error.stack}</pre>
        </div>
      )}
    </details>
  );
}
```

### ErrorBoundaryFallback
```tsx
function JobStatusFallback({ onRetry }: { onRetry: () => void }) {
  return (
    <div className={styles.fallback} role="alert">
      <p>작업 상태를 불러올 수 없습니다.</p>
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

## CSS Module Structure (JobStatus.module.css)

```css
/* Base */
.jobStatus {
  @apply p-4 border border-gray-200 rounded-xl bg-white shadow-sm;
}

/* Header */
.jobStatus_header { @apply flex items-center justify-between mb-2; }
.jobStatus_title { @apply font-medium text-gray-900; }
.jobStatus_state { @apply font-medium; }

/* Progress */
.jobStatus_progressContainer { @apply mt-2; }
.jobStatus_progressBar { @apply h-2 bg-gray-200 rounded-full overflow-hidden; }
.jobStatus_progressFill { 
  @apply h-full bg-status-running transition-all duration-300 ease-out; 
}

/* State Text */
.jobStatus_stateText { @apply mt-1 text-sm font-medium; }

/* Asset ID */
.jobStatus_assetId { @apply mt-2 text-sm text-green-600; }
.jobStatus_code { @apply break-all font-mono text-xs bg-gray-100 px-1 rounded; }

/* Error */
.jobStatus_error { @apply mt-2 text-sm text-red-600; }
.jobStatus_errorExpandable { @apply mt-1 text-xs text-gray-500 cursor-pointer; }

/* Event History */
.jobStatus_eventHistory { @apply mt-2 text-xs text-gray-500 space-y-1; }

/* Actions */
.jobStatus_actions { @apply mt-4 pt-4 border-t border-gray-100 flex gap-2; }
.jobStatus_button { @apply text-sm text-blue-600 hover:underline; }
.jobStatus_retry { @apply text-blue-600; }
.jobStatus_retryWithChanges { @apply text-amber-600; }

/* Live Indicator */
.jobStatus_liveIndicator { @apply inline-flex items-center gap-1 text-sm; }
.jobStatus_liveDot { 
  @apply w-2 h-2 bg-green-500 rounded-full; 
  @apply animate-pulse;
}

/* Error Detail Toggle */
.errorDetail_summary { @apply cursor-pointer text-sm text-blue-600 hover:underline; }
.errorDetail_details { @apply mt-2 text-xs text-gray-600 space-y-1; }
.errorDetail_stackTrace { 
  @apply mt-2 p-2 bg-gray-100 rounded text-xs overflow-x-auto; 
}

/* Error Boundary Fallback */
.fallback { @apply p-4 border border-red-200 rounded-xl bg-red-50; }
.fallback_text { @apply text-red-700 mb-2; }
.fallback_hint { @apply text-red-600 text-sm mb-2; }
.fallback_retryButton { 
  @apply mt-2 text-sm text-blue-600 hover:underline inline-block; 
}
.fallback_dismissButton { 
  @apply mt-2 text-sm text-gray-500 hover:underline inline-block ml-2; 
}

/* Live Indicator Pulse */
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
.animate-pulse { animation: pulse 1.5s ease-in-out infinite; }
```

---

## Accessibility Attributes Checklist

| Element | ARIA Attributes |
|---------|-----------------|
| Status Container | `role="status" aria-live="polite" aria-atomic="true"` |
| Progress Bar | `role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow={progress}` |
| Retry Button | `aria-label="작업 재시도"` |
| Dismiss Button | `aria-label="작업 상태 닫기"` |
| Error Detail Toggle | `aria-expanded="{expanded}" aria-controls="error-detail-{id}"` |
| Error Detail Content | `id="error-detail-{id}" aria-hidden="{!expanded}"` |
| Live Indicator | `aria-live="off"` (decorative) |

---

## Test Selectors (data-testid)

| Component | Selector |
|-----------|----------|
| JobStatus Root | `data-testid="job-status"` |
| State Label | `data-testid="job-status-state"` |
| Progress Bar | `data-testid="job-status-progress"` |
| Asset ID | `data-testid="job-status-asset-id"` |
| Error Message | `data-testid="job-status-error"` |
| Retry Button | `data-testid="job-status-retry"` |
| Retry With Changes | `data-testid="job-status-retry-changes"` |
| Dismiss Button | `data-testid="job-status-dismiss"` |
| Live Indicator | `data-testid="job-status-live-indicator"` |
| Event History Toggle | `data-testid="job-status-history-toggle"` |
| Event History List | `data-testid="job-status-history-list"` |
| Error Boundary Fallback | `data-testid="job-status-fallback"` |
| Fallback Retry Button | `data-testid="job-status-fallback-retry"` |
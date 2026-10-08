# Functional Specification — JobStatus

**Unit:** JobStatus
**Phase:** Construction — Functional Design
**Date:** 2026-10-02
**Kind:** ui

---

## Overview

JobStatus is a React component that displays real-time job progress via SSE with polling fallback, error handling, retry logic, and full accessibility support. It mounts in PaperDetailIsland when a job is submitted.

---

## Props

```typescript
interface JobStatusProps {
  jobId: string;
  onComplete?: (state: 'COMPLETED' | 'FAILED' | 'ABSTAINED', assetId?: string, error?: unknown) => void;
  className?: string;
}
```

---

## State Management

### Local State
```typescript
interface JobStatusState {
  state: JobState | null;
  eventHistory: string[];
  connectionState: 'connecting' | 'connected' | 'reconnecting' | 'polling' | 'disconnected';
  lastEventId: string | null;
  isRetrying: boolean;
  showErrorDetails: boolean;
}
```

### Connection State Machine
```
connecting → connected ↔ reconnecting → polling
                    ↓
              disconnected (terminal)
```

---

## Component Lifecycle

### Mount
1. Initialize state
2. Call `ContentJobApi.subscribeJobEvents(jobId, onEvent)`
3. Set `connectionState = 'connecting'`
4. On SSE `open` → `connectionState = 'connected'`

### SSE Event Handler
```typescript
const onEvent = (event: JobEvent) => {
  if (!isValidJobState(event.state)) return;
  
  setState(prev => ({
    state: { ...prev.state, ...event.payload, state: event.state },
    eventHistory: [...prev.eventHistory, formatEvent(event)],
    lastEventId: event.eventId
  });
  
  if (isTerminalState(event.state)) {
    unsubscribe();
    onComplete?.(event.state, event.payload?.assetId, event.payload?.error);
  }
}
```

### SSE Reconnection Logic
```typescript
const reconnect = (attempt = 1) => {
  if (attempt > 3) {
    activatePolling();
    return;
  }
  
  setConnectionState('reconnecting');
  setTimeout(() => {
    const es = new EventSource(url, { 
      headers: { 'Last-Event-ID': lastEventId }
    });
    // ... setup handlers
  }, [1000, 2000, 4000][attempt - 1]);
}
```

### Polling Fallback (SWR)
```typescript
const { data } = useSWR(
  `/bff/api/content-jobs/${jobId}/state`,
  fetcher,
  {
    refreshInterval: 2000,
    revalidateOnFocus: true,
    dedupingInterval: 1000,
    fallbackData: lastSSEState,
    onSuccess: (data) => {
      if (data.state !== lastState) updateUI(data);
      if (isTerminalState(data.state)) stopPolling();
    }
  }
);
```

---

## UI Specification

### Layout Structure
```
┌─────────────────────────────────────────────┐
│  🔄  작업 상태: RUNNING              [✕]    │  ← Header
├─────────────────────────────────────────────┤
│  ████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░│  ← Progress bar
│  시작: 2분 전  |  마지막 업데이트: 3초 전  🟢  │  ← Meta info
├─────────────────────────────────────────────┤
│  ▼ 이벤트 히스토리                          │  ← Collapsible
│  RUNNING @ 14:32:15                         │
│  QUEUED @ 14:32:10                          │
│  ACCEPTED @ 14:32:05                        │
│  SUBMITTED @ 14:32:00                       │
├─────────────────────────────────────────────┤
│  [🔄 재시도]              [닫기]             │  ← Actions (on FAILED)
└─────────────────────────────────────────────┘
```

### State-Specific Rendering

| State | Label | Color | Progress | Actions |
|-------|-------|-------|----------|---------|
| SUBMITTED | 접수됨 | Blue | 10% | — |
| ACCEPTED | 대기중 | Amber | 20% | — |
| QUEUED | 대기중 | Amber | 30% | — |
| RUNNING | 처리중 | Blue | 0-99% | — |
| COMPLETED | 완료 | Green | 100% | [결과 보기] [닫기] |
| FAILED | 실패 | Red | 0-99% | [🔄 재시도] [상세] [닫기] |
| ABSTAINED | 기권 | Gray | 0% | [닫기] |

### Error Detail Toggle (FAILED)
```
❌ 실패
오류: The summarization model timed out. (MODEL_TIMEOUT) (재시도 가능)
[▼ 상세 보기]  (expandable error stack)
[🔄 재시도]  [닫기]
```

### Error Boundary Fallback
```
⚠️ 작업 상태를 불러올 수 없습니다
┌─────────────────────────────────────┐
│  작업 상태 컴포넌트에서 오류가       │
│  발생했습니다. 백그라운드에서 작업이 │
│  계속 실행 중일 수 있습니다.          │
└─────────────────────────────────────┘
[🔄 연결 다시 시도]  [닫기]
```

---

## Accessibility (WCAG 2.1 AA)

| Requirement | Implementation |
|-------------|----------------|
| Live Region | `role="status" aria-live="polite"` on status container |
| Progressbar | `role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow={progress}` |
| State Announcements | Polite live region announces: "작업 상태: 처리중, 45% 완료" |
| Retry Button | `aria-label="작업 재시도"`, keyboard Enter/Space |
| Dismiss Button | `aria-label="작업 상태 닫기"`, Escape key |
| Error Detail Toggle | `aria-expanded`, `aria-controls` |
| Reduced Motion | `@media (prefers-reduced-motion: reduce)` disables progress animation |
| Color Contrast | All state colors ≥ 4.5:1 on white |

### Live Region Messages
| State | Announcement |
|-------|--------------|
| SUBMITTED | "작업이 접수되었습니다" |
| ACCEPTED | "작업이 대기열에 추가되었습니다" |
| QUEUED | "작업이 대기 중입니다" |
| RUNNING (progress) | "작업 상태: 처리중, 45% 완료" |
| COMPLETED | "작업이 완료되었습니다" |
| FAILED | "작업이 실패했습니다. 재시도 가능합니다" |
| ABSTAINED | "작업이 기권되었습니다" |

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
// Custom hook for SSE + polling logic
function useJobEvents(jobId: string): {
  state: JobState | null;
  connectionState: ConnectionState;
  eventHistory: string[];
  lastEventId: string | null;
  subscribe: () => () => void;
}
```

---

## CSS Modules (JobStatus.module.css)

```css
.jobStatus {
  @apply p-4 border border-gray-200 rounded-xl bg-white shadow-sm;
}

.jobStatus_header {
  @apply flex items-center justify-between mb-2;
}

.jobStatus_title {
  @apply font-medium text-gray-900;
}

.jobStatus_state {
  @apply font-medium;
}

.jobStatus_progressContainer {
  @apply mt-2;
}

.jobStatus_progressBar {
  @apply h-2 bg-gray-200 rounded-full overflow-hidden;
}

.jobStatus_progressFill {
  @apply h-full bg-status-running transition-all duration-300 ease-out;
}

.jobStatus_stateText {
  @apply mt-1 text-sm font-medium;
}

.jobStatus_assetId {
  @apply mt-2 text-sm text-green-600;
}

.jobStatus_error {
  @apply mt-2 text-sm text-red-600;
}

.jobStatus_errorExpandable {
  @apply mt-1 text-xs text-gray-500 cursor-pointer;
}

.jobStatus_eventHistory {
  @apply mt-2 text-xs text-gray-500 space-y-1;
}

.jobStatus_actions {
  @apply mt-4 pt-4 border-t border-gray-100 flex gap-2;
}

.jobStatus_button {
  @apply text-sm text-blue-600 hover:underline;
}
```

---

## Accessibility Test Checklist

- [ ] Screen reader (NVDA/VoiceOver) announces state changes
- [ ] Keyboard navigation: Tab order, Enter/Space on buttons, Escape dismisses
- [ ] 200% zoom: No horizontal scrolling, all text readable
- [ ] High contrast mode: Colors adapt correctly
- [ ] Reduced motion: Progress animation disabled
- [ ] Color blindness: Status distinguishable without color
- [ ] axe-core: 0 violations in CI
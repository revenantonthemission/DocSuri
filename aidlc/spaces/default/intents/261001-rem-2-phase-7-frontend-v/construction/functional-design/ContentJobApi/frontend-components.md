# Frontend Components — ContentJobApi

**Unit:** ContentJobApi
**Phase:** Construction — Functional Design
**Date:** 2026-10-02

---

## Component Architecture

ContentJobApi is a **library** unit (no UI components). It provides:
- API functions for job submission, state polling, SSE subscription
- Idempotency key management via IdempotencyService integration
- BFF routing enforcement

---

## Related UI Components (Consumers)

### JobStatus (Consumer)
**File:** `components/JobStatus.tsx`
**Props:**
```typescript
interface JobStatusProps {
  jobId: string;
  onComplete?: (state: 'COMPLETED' | 'FAILED' | 'ABSTAINED', assetId?: string, error?: unknown) => void;
}
```

**Integration:**
```tsx
<JobStatus 
  jobId={activeJobId} 
  onComplete={handleJobComplete} 
/>
```

**Data Flow:**
1. `useEffect` on mount → calls `ContentJobApi.subscribeJobEvents(jobId, onEvent)`
3. Updates local state from SSE events
4. On terminal state → calls `onComplete()`
5. On cleanup → calls unsubscribe function

### SummaryModal (Consumer)
**File:** `components/SummaryModal.tsx`
**Props:**
```typescript
interface SummaryModalProps {
  paperId: string;
  version: number;
  initialView: 'summary' | 'abstractTrans';
  onClose: () => void;
  onSubmit: (jobId: string) => void;
}
```

**Integration:**
```tsx
const handleSubmit = async (taskType: TaskType) => {
  const idempotencyKey = await generateIdempotencyKey(userId, paperId, taskType, params);
  const response = await contentJobApi.submitJob({
    taskType,
    input: params,
    idempotencyKey
  });
  onSubmit(response.jobId);
  setModalView(null);
};
```

### PaperDetailIsland (Mount Point)
**File:** `components/PaperDetailIsland.tsx`
**State:**
```typescript
const [activeJobId, setActiveJobId] = useState<string | null>(null);
```

**Integration:**
```tsx
{activeJobId && (
  <ErrorBoundary>
    <JobStatus 
      jobId={activeJobId} 
      onComplete={handleJobComplete} 
    />
  </ErrorBoundary>
)}

<SummaryModal 
  paperId={paperId} 
  version={version}
  onSubmit={(jobId) => setActiveJobId(jobId)}
/>
```

---

## API Contract Summary

### ContentJobApi Exports

| Function | Purpose | Used By |
|----------|---------|---------|
| `submitJob(request)` | Submit job with idempotency | SummaryModal, JobStatus (retry) |
| `getJobState(jobId)` | Poll job state | JobStatus (polling fallback) |
| `subscribeJobEvents(jobId, onEvent, lastEventId?)` | SSE subscription | JobStatus (real-time) |
| `translate(input)` | Translate with cache | SummaryModal (translate tab) |
| `generateIdempotencyKey()` | Generate SHA-256 key | SummaryModal, JobStatus (retry) |
| `storeIdempotencyKey()` / `getIdempotencyKey()` / `clearIdempotencyKey()` | localStorage management | SummaryModal (submit), JobStatus (retry) |

### Type Definitions

```typescript
type TaskType = 'summarize' | 'translate' | 'novelty' | 'evidence' | 'ingest_userdoc';

interface SubmitJobRequest {
  taskType: TaskType;
  input: Record<string, unknown>;
  idempotencyKey: string; // Required for Phase 7
}

interface SubmitJobResponse {
  jobId: string;
  state: string;
}

interface JobState {
  jobId: string;
  state: 'SUBMITTED' | 'ACCEPTED' | 'QUEUED' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'ABSTAINED';
  assetId?: string;
  error?: {
    errorType: string;
    message: string;
    retryable: boolean;
    retryAfterSeconds?: number;
  };
  abstainReason?: string;
}

interface JobEvent {
  eventId: string;
  jobId: string;
  state: string;
  timestampUs: number;
  payload?: {
    assetId?: string;
    error?: { errorType: string; message: string; retryable: boolean };
    abstainReason?: string;
  };
}
```

---

## Integration Points

### BFF Proxy (`/bff/api/content-jobs/*`)
All calls route through BFF:
- `POST /bff/api/content-jobs/submit` → submitJob
- `GET /bff/api/content-jobs/{jobId}/state` → getJobState
- `GET /bff/api/content-jobs/{jobId}/events` → subscribeJobEvents (SSE)
- `POST /bff/api/content-jobs/translate` → translate

### IdempotencyService Integration
```typescript
// In ContentJobApi.submitJob()
const idempotencyKey = await IdempotencyService.generateKey(userId, paperId, taskType, params);
IdempotencyService.storeKey(paperId, taskType, idempotencyKey);

// On retry (JobStatus)
const key = IdempotencyService.getKey(paperId, taskType);
await submitJob({ taskType, input: params, idempotencyKey: key });
```

---

## Component Test Points

### Unit Test Targets
| Function | Test Cases |
|----------|------------|
| `generateIdempotencyKey` | Deterministic hash, different inputs = different hashes |
| `submitJob` | Includes idempotencyKey, correct endpoint, headers |
| `subscribeJobEvents` | EventSource URL, Last-Event-ID, reconnection logic |
| `translate` | Correct payload, cache-aware response |

### Integration Test Scenarios
1. **Submit → SSE → COMPLETED** → Result displayed
2. **Submit → 409 Conflict** → Existing job mounted
3. **SSE disconnect** → Reconnect with Last-Event-ID → Resume
4. **SSE fails** → Polling activates → Job completes
4. **FAILED** → Retry with same key → New attempt
5. **Retry with Changes** → New idempotency key → New job

---

## Accessibility Notes

ContentJobApi itself has no UI, but enables:
- JobStatus: ARIA live region, progressbar role
- SummaryModal: Focus trap, Escape to close, labeled inputs
- AssetViewer: Alt text, zoom controls, keyboard navigation

All consumer components follow WCAG 2.1 AA (per project.md Mandated).
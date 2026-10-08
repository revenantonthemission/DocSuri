# User Flow — Phase 7 Frontend Wiring

**Intent ID:** 261001-rem-2-phase-7-frontend
**Scope:** feature
**Date:** 2026-10-02

---

## Primary Flow: Submit Job → Track Progress → View Result

```mermaid
flowchart TD
    A[User on Paper Detail Page] --> B{Click Action Button}
    B -->|Summarize| C[Generate Idempotency Key]
    B -->|Translate| C
    B -->|Other| C
    C --> D[POST /bff/api/content-jobs]
    D --> E{Response}
    E -->|202 Accepted| F[Receive jobId + idempotencyKey]
    E -->|409 Conflict| G[Show "Job already exists" + Retry]
    E -->|4xx/5xx| H[Show Error + Retry]
    F --> I[Store idempotencyKey in localStorage]
    I --> J[Mount JobStatus with jobId]
    J --> K[Open SSE Connection]
    K --> L{SSE Connected?}
    L -->|Yes| M[Receive Real-time Events]
    L -->|No| N[Activate Polling Fallback]
    M --> O{Job Terminal State?}
    N --> O
    O -->|COMPLETED| P[Fetch /result]
    O -->|FAILED| Q[Show Inline Retry]
    O -->|ABSTAINED| R[Show "Job Cancelled"]
    P --> S[Display Result / Navigate to Result]
    Q --> T[User Clicks Retry]
    T --> U[Re-submit with Same Idempotency Key]
    U --> D
    R --> V[Dismiss]
```

---

## Detailed Step-by-Step Flow

### Step 1: Job Submission
```
User Action          System Response
────────────────────────────────────────────────────────────
Click "Summarize"    1. Generate idempotency key:
                     hash(userId + paperId + "summarize" + params)
                     
                     2. Check localStorage for existing key
                     (survives page reload)
                     
                     3. POST /bff/api/content-jobs
                     Body: { paperId, taskType, params, idempotencyKey }
                     
                     4. BFF injects x-principal-user-id header
                     5. Backend: atomic idempotent acceptance
```

### Step 2: Response Handling
| Response | Handling |
|----------|----------|
| `202 Accepted` | `{ jobId, idempotencyKey }` → mount JobStatus, open SSE |
| `409 Conflict` | Job exists with same key → fetch existing job, mount JobStatus |
| `401/403` | Auth error → redirect to login / show auth error |
| `5xx` | Server error → show inline error with retry |

### Step 3: SSE Connection & Real-time Updates
```
EventSource("/api/content-jobs/{jobId}/events")
  ├── open → connection established 🟢
  ├── message (event: state)
  │     ├── SUBMITTED → show "Submitted..."
  │     ├── ACCEPTED → show "Accepted, queuing..."
  │     ├── QUEUED → show "Waiting for worker..."
  │     ├── RUNNING → show progress % from payload
  │     ├── COMPLETED → fetch /result, show success
  │     ├── FAILED → show error + retry button
  │     └── ABSTAINED → show "Job cancelled"
  ├── error → disconnect → attempt reconnect with Last-Event-ID
  │     ├── reconnect success → resume events 🟢
  │     └── reconnect fail (3 attempts) → activate polling 🔴
  └── close → unexpected close → reconnect logic
```

### Step 4: Polling Fallback (When SSE Fails)
```
useSWR("/api/content-jobs/{jobId}/state", {
  refreshInterval: 2000,        // 2s fixed interval
  revalidateOnFocus: true,
  dedupingInterval: 1000,
  fallbackData: lastSSEState,   // preserve last known state
  onSuccess: (data) => {
    if (data.state !== lastState) updateUI(data);
    if (isTerminalState(data.state)) stopPolling();
  }
})
```

### Step 5: Job Completion
```
COMPLETED:
  1. Fetch GET /bff/api/content-jobs/{jobId}/result
  2. Response: { resultRef, resultType, metadata }
  3. Display result inline or navigate to result view
  4. Clear idempotencyKey from localStorage
  5. Show "View Result" button

FAILED:
  1. Show error message from SSE payload
  2. Display "Retry" button (uses stored idempotencyKey)
  3. On retry click → re-submit with same key
  4. Backend returns same jobId (idempotent)

ABSTAINED:
  1. Show "Job was cancelled" message
  2. No retry option (backend-only state)
```

---

## Edge Cases & Error Flows

### Edge Case 1: Page Reload During Job
```
User reloads page
    │
    ▼
Check localStorage for idempotencyKey
    │
    ├── Found → GET /bff/api/content-jobs/{jobId}/state
    │           Mount JobStatus with current state
    │           Reconnect SSE or start polling
    │
    └── Not Found → No JobStatus mounted
                    User can submit new job
```

### Edge Case 2: SSE Disconnect During RUNNING
```
SSE error event
    │
    ▼
Attempt reconnect (max 3, exponential backoff 1s, 2s, 4s)
    │
    ├── Success → Resume with Last-Event-ID header
    │             Backend replays missed events
    │
    └── All fail → Switch to polling fallback
                   Show 🔴 "Polling" indicator
                   Continue 2s polling until terminal
```

### Edge Case 3: Network Failure on Retry
```
User clicks Retry (FAILED state)
    │
    ▼
POST with same idempotencyKey
    │
    ├── 202 → New attempt started, mount JobStatus
    ├── 409 → Same job returned (already retried)
    ├── 401 → Auth expired → redirect login
    └── 5xx → Show error, keep retry button enabled
```

### Edge Case 4: Asset Load Failure
```
<img src="/bff/api/papers/{id}/assets/{assetId}" />
    │
    ├── 200 → Render image ✓
    ├── 401/403 → Show "Access denied" placeholder
    ├── 404 → Show "Asset not found" placeholder
    └── 5xx → Show "Failed to load" + retry button
```

---

## State Machine (JobStatus UI)

```
                    ┌─────────────┐
                    │  IDLE       │  (no jobId)
                    └──────┬──────┘
                           │ submit job
                           ▼
                    ┌─────────────┐
                    │ CONNECTING  │  (SSE opening)
                    └──────┬──────┘
                           │ open
                           ▼
                    ┌─────────────┐
              ┌──────▶│  LIVE (SSE) │◀────────┐
              │       └──────┬──────┘         │
              │              │ error          │ reconnect
              │              ▼                │
              │       ┌─────────────┐         │
              └───────│ RECONNECTING │────────┘
                      └──────┬──────┘
                             │ max retries exceeded
                             ▼
                      ┌─────────────┐
                      │  POLLING    │  (2s interval)
                      └──────┬──────┘
                             │ terminal state
                             ▼
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
       ┌───────────┐  ┌───────────┐  ┌───────────┐
       │ COMPLETED │  │  FAILED   │  │ ABSTAINED │
       └─────┬─────┘  └─────┬─────┘  └─────┬─────┘
             │              │              │
             ▼              ▼              ▼
       [View Result]   [Retry Button]  [Dismiss]
             │              │              │
             │         same key         │
             │         re-submit        │
             └──────────────┬───────────┘
                            ▼
                      (back to LIVE)
```

---

## Success Metrics (UX)

| Metric | Target | Measurement |
|--------|--------|-------------|
| Time to first SSE event | < 500ms | Client timestamp |
| SSE reconnection success rate | > 95% | EventSource error/reopen ratio |
| Polling activation rate | < 5% | Fallback trigger count |
| Retry success rate | > 90% | Retry → COMPLETED ratio |
| JobStatus mount time | < 200ms | React render + mount |
| Asset load time (same-origin) | < 1s | Resource timing API |
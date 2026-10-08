# Reliability Requirements — JobStatus

## NFR4.1: SSE Resilience
- **Target**: Automatic reconnect with `Last-Event-ID` on network interruption
- **Implementation**: Native `EventSource` handles reconnect; browser sends `Last-Event-ID` header
- **Validation**: Simulate network disconnect/reconnect; verify missed events replayed

## NFR4.2: Polling Fallback Activation (NFR5)
- **Target**: Fallback to SWR polling within 3s of SSE permanent failure
- **Trigger**: SSE `onerror` fires 3 consecutive times without `onopen`
- **Implementation**: `useEffect` tracks error count; switches to SWR `useSWR` with 2s refreshInterval
- **Validation**: Chaos test — kill SSE endpoint, verify polling takes over

## NFR4.3: Error Boundary Containment (NFR6)
- **Target**: JobStatus errors never crash parent page
- **Implementation**: `<ErrorBoundary>` wraps JobStatus; fallback shows retry button + error message
- **Recovery**: User clicks retry → remounts JobStatus with fresh SSE connection
- **Validation**: Inject render error; verify parent remains interactive

## NFR4.4: Graceful Degradation
- **Target**: If both SSE and polling fail, show last known status + "Connection lost" indicator
- **Implementation**: State machine: `connecting` → `live` → `polling` → `offline`
- **UI**: ARIA live region announces status changes; offline state shows timestamp of last update

## NFR4.5: Session Recovery
- **Target**: Page refresh preserves job monitoring via idempotency key
- **Implementation**: Job ID in URL (`/papers/{paperId}/jobs/{jobId}`); ContentJobApi resumes via idempotency key
- **Validation**: Refresh during active job; verify status continues

## Traceability
| Inception NFR | Derived ID | Status |
|---------------|------------|--------|
| NFR5 (Polling Fallback) | NFR4.1, NFR4.2 | OK |
| NFR6 (Error Boundary) | NFR4.3, NFR4.4 | OK |
| NFR4 (Idempotency) | NFR4.5 | OK |
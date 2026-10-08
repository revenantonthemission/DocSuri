# Reliability Design — JobStatus

## NFR4.1: SSE Resilience with Last-Event-ID
**Design**: Native `EventSource` automatic reconnection
- Browser handles reconnect on network interruption
- `Last-Event-ID` header sent automatically on reconnect
- Gateway replays missed events (idempotent event IDs)
- **No Custom Code**: Native behavior; no wrapper needed

## NFR4.2: Polling Fallback Activation (NFR5)
**Design**: State machine with explicit fallback trigger
```ts
const [mode, setMode] = useState<'sse' | 'polling' | 'offline'>('sse');
const errorCount = useRef(0);

useEffect(() => {
  const es = new EventSource(url);
  es.onopen = () => { errorCount.current = 0; setMode('sse'); };
  es.onerror = () => {
    errorCount.current++;
    if (errorCount.current >= 3) {
      es.close();
      setMode('polling'); // Triggers SWR hook
    }
  };
  return () => es.close();
}, [url]);
```
- **Threshold**: 3 consecutive errors without open
- **SWR**: `refreshInterval: 2000` takes over seamlessly
- **Fallback Data**: Last SSE event cached for instant UI

## NFR4.3: Error Boundary Containment (NFR6)
**Design**: `<ErrorBoundary>` wraps JobStatus
- Fallback: `ErrorBoundaryFallback` with retry button
- **Retry**: `key` prop change on parent → full remount → fresh SSE
- **Recovery**: New `EventSource` + fresh SWR cache

## NFR4.4: Graceful Degradation
**Design**: Four-state status machine
```ts
type ConnectionState = 'connecting' | 'live' | 'polling' | 'offline';
```
- **ARIA Live Region**: Announces state changes for screen readers
- **Offline UI**: Shows last status + timestamp + "Connection lost" badge
- **Recovery**: Auto-retry on `online` event + focus

## NFR4.5: Session Recovery via Idempotency
**Design**: Job ID in URL → ContentJobApi resumes
- URL: `/papers/{paperId}/jobs/{jobId}`
- On mount: ContentJobApi checks localStorage for idempotency key
- If key exists: resume polling/SSE with same job ID
- **Validation**: Refresh during active job → status continues

## Traceability
| NFR Requirement | Design Solution |
|-----------------|-----------------|
| NFR4.1 | Native EventSource Last-Event-ID |
| NFR4.2 | 3-error threshold → SWR polling |
| NFR4.3 | ErrorBoundary + key-based remount |
| NFR4.4 | 4-state machine + ARIA live |
| NFR4.5 | URL-based job ID + idempotency key resume |
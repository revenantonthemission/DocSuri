# Performance Design — JobStatus

## NFR1.1: SSE Connection Latency ≤500ms
**Design**: Native `EventSource` with no middleware overhead
- Browser handles connection establishment natively
- BFF proxy (`/bff/api/content-jobs/{jobId}/events`) adds ≤50ms (validated in ContentJobApi perf design)
- **Optimization**: Preconnect hint in HTML `<link rel="preconnect" href="/bff/api/content-jobs">`

## NFR1.2: Status Update Propagation ≤100ms
**Design**: Direct SSE stream → React state via `useReducer`
- No intermediate buffering; `EventSource.onmessage` → dispatch → render
- **Batching**: Multiple rapid events batched via `useTransition` for concurrent renders
- **Budget**: 16ms render + 84ms network/processing headroom

## NFR1.3: Polling Fallback Activation ≤2s
**Design**: SWR `useSWR` with `refreshInterval: 2000`
```ts
const { data } = useSWR(`/bff/api/content-jobs/${jobId}`, fetcher, {
  refreshInterval: 2000,
  revalidateOnFocus: false,
  dedupingInterval: 1000,
  fallbackData: lastKnownStatus,
})
```
- **Trigger**: SSE `onerror` ×3 without `onopen` → switch to SWR
- **Fallback Data**: Last SSE event cached in `useRef` for instant UI

## NFR1.4: Re-render Budget ≤2ms
**Design**: 
- `useReducer` for status state (single state object)
- `useTransition` for non-blocking updates during rapid events
- `React.memo` on status display components
- **Avoid**: New object creation in render path

## NFR1.5: Bundle Size ≤15KB gzipped
**Design**:
- Native `EventSource` (0KB)
- SWR (~5KB gzipped) — already in stack
- Custom `ErrorBoundary` (~2KB)
- No external deps (axios, tanstack-query, lodash forbidden)

## NFR1.6: Zero Memory Leaks (30-min session)
**Design**:
- `useEffect` cleanup: `eventSource.close()` on unmount
- SWR cache auto-eviction: `cache.timeToLive = 5min`
- No global event listeners

## Traceability
| NFR Requirement | Design Solution |
|-----------------|-----------------|
| NFR1.1 | Native EventSource + preconnect |
| NFR1.2 | Direct stream → useReducer |
| NFR1.3 | SWR refreshInterval: 2000 |
| NFR1.4 | useReducer + useTransition |
| NFR1.5 | Zero external deps |
| NFR1.6 | useEffect cleanup + SWR TTL |
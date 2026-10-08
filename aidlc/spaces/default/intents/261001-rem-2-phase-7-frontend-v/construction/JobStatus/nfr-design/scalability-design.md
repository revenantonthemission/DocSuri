# Scalability Design — JobStatus

## NFR3.1: Concurrent Job Monitoring (10 jobs)
**Design**: Independent `EventSource` per JobStatus instance
- Parent component manages array of job IDs
- Each JobStatus mounts own `EventSource`
- **Browser Limit**: 6 connections/hostname (HTTP/2 multiplexing handles >6)
- **Mitigation**: For >6 jobs, parent switches excess to polling-only mode

## NFR3.2: Event Throughput (1 event/s per job)
**Design**: Batched state updates via `useReducer`
```ts
const [state, dispatch] = useReducer(statusReducer, initialState);
// In onmessage:
dispatch({ type: 'STATUS_UPDATE', jobId, event });
// Reducer batches multiple events per render cycle
```
- `useTransition` wraps dispatch for concurrent renders
- Max 10 events/s total → well within React 18 concurrent capabilities

## NFR3.3: Constant Memory (24-hour session)
**Design**:
- `EventSource.close()` on job completion (terminal states: `completed`, `failed`, `cancelled`)
- SWR cache TTL: 5 minutes → auto-eviction
- `useRef` for last-known status (no re-renders on update)
- **Validation**: Heap snapshots at 0/12/24 hours in CI

## Traceability
| NFR Requirement | Design Solution |
|-----------------|-----------------|
| NFR3.1 | Independent EventSource per job; HTTP/2 multiplexing |
| NFR3.2 | useReducer batching + useTransition |
| NFR3.3 | EventSource.close() on terminal state + SWR TTL |
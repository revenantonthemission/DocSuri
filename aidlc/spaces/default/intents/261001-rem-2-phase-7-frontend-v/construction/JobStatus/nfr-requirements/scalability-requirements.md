# Scalability Requirements — JobStatus

## NFR3.1: Concurrent Job Monitoring
- **Target**: Support monitoring 10 concurrent jobs without performance degradation
- **Implementation**: Each JobStatus instance maintains independent `EventSource`; parent component manages array
- **Resource Bound**: ≤10 `EventSource` connections per browser tab (browser limit ~6 per hostname, but SSE uses HTTP/2 multiplexing)
- **Mitigation**: For >6 jobs, consider polling-only mode or shared WebSocket (out of scope)

## NFR3.2: Event Throughput
- **Target**: Handle 1 status event/second per job without UI lag
- **Measurement**: 10 jobs × 1 event/s = 10 events/s total
- **Implementation**: Batched state updates via `useReducer` or `useTransition` for concurrent renders

## NFR3.3: Memory Growth
- **Target**: Constant memory over 24-hour session with job completion/cleanup
- **Implementation**: `EventSource.close()` on job completion; SWR cache eviction after 5 min
- **Validation**: Heap snapshot comparison at 0/12/24 hours

## Traceability
| Inception NFR | Derived ID | Status |
|---------------|------------|--------|
| NFR5 (Polling Fallback) | NFR3.1, NFR3.2 | OK |
| NFR6 (Error Boundary) | NFR3.3 | OK |
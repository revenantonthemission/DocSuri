# Performance Requirements — JobStatus

## NFR1.1: SSE Connection Latency
- **Target**: SSE connection established within 500ms of component mount
- **Measurement**: Time from `EventSource` constructor to `onopen` event
- **Rationale**: User perceives immediate status updates; delays >500ms feel sluggish

## NFR1.2: Status Update Propagation
- **Target**: Status events delivered to UI within 100ms of gateway emission
- **Measurement**: Gateway timestamp → UI render timestamp
- **Rationale**: Real-time feel requires sub-second propagation

## NFR1.3: Polling Fallback Latency
- **Target**: First polling response within 2s of SSE failure detection
- **Measurement**: SSE `onerror` → first SWR fetch completion
- **Rationale**: SWR 2s fixed interval; user should not wait >2s for fallback

## NFR1.4: Re-render Budget
- **Target**: Status updates trigger ≤2ms React render time
- **Measurement**: React DevTools Profiler — component render duration
- **Rationale**: Frequent status updates (potentially every few seconds) must not block main thread

## NFR1.5: Bundle Size Impact
- **Target**: JobStatus + dependencies ≤15KB gzipped
- **Measurement**: `next-bundle-analyzer` or `webpack-bundle-analyzer`
- **Rationale**: Lightweight component; no heavy dependencies (no tanstack-query, axios, lodash)

## NFR1.6: Memory Footprint
- **Target**: No memory leaks over 30-minute session with continuous SSE
- **Measurement**: Chrome DevTools heap snapshots at 0/15/30 min
- **Rationale**: Long-running SSE connections must clean up EventSource on unmount

## Traceability
| Inception NFR | Derived ID | Status |
|---------------|------------|--------|
| NFR5 (Polling Fallback) | NFR1.1, NFR1.2, NFR1.3 | OK |
| NFR6 (Error Boundary) | NFR1.4 | OK |
| NFR7 (Sentry) | NFR1.5 | OK |
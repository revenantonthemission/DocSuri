# Scalability Requirements — ContentJobApi

## NFR3.1: Concurrent Submissions
- **Target**: Handle 50 concurrent job submissions without client-side queueing
- **Implementation**: Each `fetch` is independent; browser HTTP/2 multiplexing handles concurrency
- **Backpressure**: UI disables submit button during in-flight request (per-job)

## NFR3.2: Idempotency Key Storage Growth
- **Target**: ≤100 keys in localStorage (1 per paper/taskType combo)
- **Cleanup**: Keys older than 30 days purged on app load
- **Storage Quota**: ~50KB total (well under 5MB limit)

## Traceability
| Inception NFR | Derived ID | Status |
|---------------|------------|--------|
| NFR4 (Idempotency) | NFR3.2 | OK |
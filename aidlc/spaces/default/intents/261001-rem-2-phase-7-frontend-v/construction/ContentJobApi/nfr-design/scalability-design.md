# Scalability Design — ContentJobApi

## NFR3.1: 50 Concurrent Submissions
**Design**: Stateless per-request `fetch`
- No connection pooling needed (browser handles HTTP/2)
- Each submission independent; no queue
- **UI Backpressure**: Disable submit button per-job during in-flight

## NFR3.2: Idempotency Key Storage ≤100 Keys
**Design**: Namespaced localStorage with TTL
- Key format: `idempotency:{paperId}:{taskType}` → max 1 per paper/taskType
- **Cleanup**: On app init, purge keys older than 30 days
- **Quota**: ~50KB total (well under 5MB limit)

## Traceability
| NFR Requirement | Design Solution |
|-----------------|-----------------|
| NFR3.1 | Stateless fetch + HTTP/2 multiplexing |
| NFR3.2 | Namespaced localStorage + 30-day TTL cleanup |
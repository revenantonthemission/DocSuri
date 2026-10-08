# Performance Requirements — ContentJobApi

## NFR1.1: BFF Request Latency
- **Target**: BFF proxy adds ≤50ms overhead vs direct gateway call
- **Measurement**: `fetch` start → response headers received (proxy only)
- **Rationale**: BFF is thin proxy; must not add perceptible latency

## NFR1.2: Idempotency Key Generation
- **Target**: SHA-256 hash computed within 5ms
- **Implementation**: `crypto.subtle.digest('SHA-256', encoder.encode(keyMaterial))`
- **Rationale**: Called on every job submission; must be fast

## NFR1.3: Request Throughput
- **Target**: Support 50 concurrent job submissions without queueing
- **Implementation**: Native `fetch` + `AbortController` for cancellation
- **Resource Bound**: Browser connection pool (6 per hostname, HTTP/2 multiplexing)

## NFR1.4: Bundle Size
- **Target**: ContentJobApi + Transport ≤10KB gzipped
- **Measurement**: Bundle analyzer
- **Rationale**: Single-purpose module; no heavy dependencies

## Traceability
| Inception NFR | Derived ID | Status |
|---------------|------------|--------|
| NFR1 (SEC-8) | NFR1.1 | OK |
| NFR4 (Idempotency) | NFR1.2 | OK |
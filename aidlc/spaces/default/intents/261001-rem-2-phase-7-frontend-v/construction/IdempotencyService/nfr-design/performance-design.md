# Performance Design — IdempotencyService

## NFR1.1: SHA-256 ≤5ms
**Design**: Native `crypto.subtle.digest` — benchmarked at ~1-2ms

## NFR1.2: localStorage Read/Write ≤2ms
**Design**: Synchronous localStorage API (acceptable for <1KB values)
- `getItem`/`setItem` direct calls
- No async wrapper overhead

## Traceability
| NFR Requirement | Design Solution |
|-----------------|-----------------|
| NFR1.1 | crypto.subtle.digest |
| NFR1.2 | Direct localStorage API |
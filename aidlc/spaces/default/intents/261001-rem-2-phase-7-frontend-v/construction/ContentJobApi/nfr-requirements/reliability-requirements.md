# Reliability Requirements — ContentJobApi

## NFR4.1: Idempotent Retry (NFR4)
- **Target**: Automatic retry on network failure with same idempotency key
- **Implementation**: Transport layer catches `TypeError` (network error); retries once with exponential backoff (1s, 2s)
- **Idempotency**: Same key sent; server deduplicates
- **Non-Retry**: 4xx errors (client errors) never retried; 5xx retried once

## NFR4.2: BFF Proxy Availability
- **Target**: BFF proxy failure surfaces as network error to caller
- **Implementation**: No special handling — `fetch` fails → Transport retries → ErrorBoundary catches
- **Fallback**: None at this layer (handled by ErrorBoundary at UI layer)

## NFR4.3: Request Cancellation
- **Target**: In-flight requests cancelled on component unmount / navigation
- **Implementation**: `AbortController` signal passed to `fetch`; `useEffect` cleanup calls `abort()`

## Traceability
| Inception NFR | Derived ID | Status |
|---------------|------------|--------|
| NFR4 (Idempotency) | NFR4.1 | OK |
| NFR5 (Polling Fallback) | NFR4.3 | OK |
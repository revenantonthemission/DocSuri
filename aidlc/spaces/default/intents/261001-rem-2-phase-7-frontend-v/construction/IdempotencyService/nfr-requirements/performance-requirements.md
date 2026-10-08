# Performance Requirements — IdempotencyService

## NFR1.1: Key Generation Speed
- **Target**: SHA-256 hash computed ≤5ms
- **Implementation**: `crypto.subtle.digest('SHA-256', data)`
- **Input Size**: ~200 bytes typical (userId:paperId:taskType:params)
- **Rationale**: Called on every job submission; must not block UI

## NFR1.2: Storage Read/Write
- **Target**: localStorage get/set ≤2ms
- **Implementation**: Synchronous localStorage API (acceptable for small values)
- **Validation**: Performance.now() measurements in tests

## Traceability
| Inception NFR | Derived ID | Status |
|---------------|------------|--------|
| NFR4 (Idempotency) | NFR1.1, NFR1.2 | OK |
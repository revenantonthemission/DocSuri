# Reliability Requirements — IdempotencyService

## NFR4.1: Persistence Across Reloads
- **Target**: Idempotency keys survive page reload / browser restart
- **Mechanism**: localStorage (not sessionStorage)
- **Validation**: Generate key → reload → retrieve same key

## NFR4.2: Corruption Resilience
- **Target**: Malformed localStorage entry doesn't crash app
- **Implementation**: try/catch on JSON.parse; corrupted entries deleted
- **Fallback**: Regenerate key if storage read fails

## NFR4.3: Quota Exceeded Handling
- **Target**: localStorage quota exceeded doesn't break key generation
- **Implementation**: Catch `QuotaExceededError`; purge oldest keys; retry
- **Fallback**: In-memory Map as last resort (session-only)

## Traceability
| Inception NFR | Derived ID | Status |
|---------------|------------|--------|
| NFR4 (Idempotency) | NFR4.1, NFR4.2, NFR4.3 | OK |
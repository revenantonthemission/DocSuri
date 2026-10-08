# Observability Requirements — IdempotencyService

## NFR5.1: Key Lifecycle Events
- **Target**: Structured logs for key generation, retrieval, expiry
- **Events**: `idempotency.generate`, `idempotency.retrieve`, `idempotency.expire`, `idempotency.purge`
- **Fields**: `paperId`, `taskType`, `keyHash` (prefix), `source` (generated|cached|regenerated)

## NFR5.2: Error Tracking
- **Target**: Storage errors reported to Sentry
- **Events**: `idempotency.storage.error` (quota, parse, permission)
- **Context**: Browser, localStorage usage, available space

## Traceability
| Inception NFR | Derived ID | Status |
|---------------|------------|--------|
| NFR4 (Idempotency) | NFR5.1 | OK |
| NFR7 (Sentry) | NFR5.2 | OK |
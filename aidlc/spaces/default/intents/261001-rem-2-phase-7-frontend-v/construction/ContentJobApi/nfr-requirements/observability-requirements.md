# Observability Requirements — ContentJobApi

## NFR5.1: Request/Response Logging
- **Target**: Structured logs for all BFF requests
- **Events**: `bff.request.start`, `bff.request.complete`, `bff.request.error`
- **Fields**: `method`, `path`, `jobId`, `paperId`, `taskType`, `duration`, `statusCode`, `idempotencyKey` (hashed)
- **Destination**: Sentry breadcrumbs + console (dev)

## NFR5.2: Idempotency Key Audit
- **Target**: Key generation and reuse logged for debugging
- **Events**: `idempotency.key.generated`, `idempotency.key.reused`, `idempotency.key.expired`
- **Fields**: `paperId`, `taskType`, `keyHash` (first 8 chars), `source` (generated|localStorage)

## NFR5.3: Error Rate Metrics
- **Target**: Client-side error rate per endpoint
- **Metrics**: `bff.error.rate` (counter by statusCode), `bff.retry.count` (counter)
- **Alerting**: Sentry alerts on error rate >5% over 5min window

## Traceability
| Inception NFR | Derived ID | Status |
|---------------|------------|--------|
| NFR1 (SEC-8) | NFR5.1 | OK |
| NFR4 (Idempotency) | NFR5.2 | OK |
| NFR7 (Sentry) | NFR5.1, NFR5.3 | OK |
# Observability Design — ContentJobApi

## NFR5.1: Request/Response Logging
**Design**: Structured Sentry Breadcrumbs
```ts
const logBFF = (event: string, data: object) => {
  Sentry.addBreadcrumb({ category: 'bff', message: event, level: 'info', data });
};

// Usage:
logBFF('request.start', { method, path, jobId, paperId, taskType });
logBFF('request.complete', { statusCode, duration, jobId });
logBFF('request.error', { errorCode, duration, jobId });
```
- Fields: `method`, `path`, `jobId`, `paperId`, `taskType`, `duration`, `statusCode`, `idempotencyKeyHash` (first 8 chars)

## NFR5.2: Idempotency Key Audit
**Design**: Key Lifecycle Breadcrumbs
```ts
logBFF('idempotency.key.generated', { paperId, taskType, keyHash });
logBFF('idempotency.key.reused', { paperId, taskType, keyHash, source: 'localStorage' });
logBFF('idempotency.key.expired', { paperId, taskType, keyHash });
```

## NFR5.3: Error Rate Metrics
**Design**: Sentry Metrics + Alerting
- **Metrics**: `bff.error.rate` (counter by statusCode), `bff.retry.count` (counter)
- **Alert**: Sentry alert on error rate >5% over 5min window

## Traceability
| NFR Requirement | Design Solution |
|-----------------|-----------------|
| NFR5.1 | Sentry breadcrumbs for BFF request lifecycle |
| NFR5.2 | Sentry breadcrumbs for idempotency key lifecycle |
| NFR5.3 | Sentry metrics + alert rules |
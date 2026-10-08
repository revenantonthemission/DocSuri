# Monitoring Design — ContentJobApi

## Client-Side Monitoring (Sentry)

### Request/Response Breadcrumbs
```ts
Sentry.addBreadcrumb({ category: 'bff', message: 'request.start', data: { method, path, jobId, paperId, taskType } });
Sentry.addBreadcrumb({ category: 'bff', message: 'request.complete', data: { statusCode, duration } });
Sentry.addBreadcrumb({ category: 'bff', message: 'request.error', data: { errorCode, duration } });
```

### Idempotency Key Audit
```ts
Sentry.addBreadcrumb({ category: 'idempotency', message: 'key.generated', data: { paperId, taskType, keyHash } });
Sentry.addBreadcrumb({ category: 'idempotency', message: 'key.reused', data: { paperId, taskType, keyHash, source: 'localStorage' } });
```

### Metrics & Alerts
| Metric | Type | Alert |
|--------|------|-------|
| `bff.error.rate` | Counter by statusCode | >5% in 5min |
| `bff.retry.count` | Counter | >10/min |
| `bff.latency.p95` | Histogram | >2s |

## Server-Side (Gateway)
- Gateway owns auth, rate limiting, idempotency validation
- BFF proxy adds minimal latency (≤50ms)

## Traceability
| NFR Design | Monitoring Solution |
|------------|---------------------|
| NFR5.1 (Request Logging) | Sentry breadcrumbs for BFF lifecycle |
| NFR5.2 (Idempotency Audit) | Sentry breadcrumbs for key lifecycle |
| NFR5.3 (Error Rates) | Sentry metrics + alerts |
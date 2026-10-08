# Observability Design — IdempotencyService

## NFR5.1: Key Lifecycle Events
**Design**: Sentry Breadcrumbs
```ts
Sentry.addBreadcrumb({ category: 'idempotency', message: 'generate', data: { paperId, taskType, keyHash } });
Sentry.addBreadcrumb({ category: 'idempotency', message: 'retrieve', data: { paperId, taskType, keyHash, source } });
Sentry.addBreadcrumb({ category: 'idempotency', message: 'expire', data: { paperId, taskType } });
Sentry.addBreadcrumb({ category: 'idempotency', message: 'purge', data: { count } });
```

## NFR5.2: Storage Errors → Sentry
**Design**: `Sentry.captureException` on quota/parse/permission errors

## Traceability
| NFR Requirement | Design Solution |
|-----------------|-----------------|
| NFR5.1 | Sentry breadcrumbs for key lifecycle |
| NFR5.2 | Sentry captureException on storage errors |
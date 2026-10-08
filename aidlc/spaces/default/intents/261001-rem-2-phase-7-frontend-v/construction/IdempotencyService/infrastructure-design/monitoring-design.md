# Monitoring Design — IdempotencyService

## Client-Side Monitoring (Sentry)

### Key Lifecycle Breadcrumbs
```ts
Sentry.addBreadcrumb({ category: 'idempotency', message: 'generate', data: { paperId, taskType, keyHash } });
Sentry.addBreadcrumb({ category: 'idempotency', message: 'retrieve', data: { paperId, taskType, keyHash, source } });
Sentry.addBreadcrumb({ category: 'idempotency', message: 'expire', data: { paperId, taskType } });
Sentry.addBreadcrumb({ category: 'idempotency', message: 'purge', data: { count } });
```

### Error Tracking
```ts
Sentry.captureException(err, { extra: { operation: 'localStorage', paperId, taskType } });
```
- Errors: quota exceeded, parse error, permission denied

## Traceability
| NFR Design | Monitoring Solution |
|------------|---------------------|
| NFR5.1 (Key Lifecycle) | Sentry breadcrumbs |
| NFR5.2 (Storage Errors) | Sentry captureException |
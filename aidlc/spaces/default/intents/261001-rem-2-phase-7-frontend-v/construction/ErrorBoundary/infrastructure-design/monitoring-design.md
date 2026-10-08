# Monitoring Design — ErrorBoundary

## Sentry Monitoring

### Error Capture
- **100% Coverage**: All `componentDidCatch` → `Sentry.captureException()`
- **Context**: `component`, `componentStack`, `boundaryName`
- **Grouping**: By error type + component stack

### Metrics & Alerts
| Metric | Type | Alert |
|--------|------|-------|
| `error_boundary.catch.count` | Counter by boundaryName | >10/min |
| `error_boundary.retry.success` | Counter | N/A |
| `error_boundary.retry.failed` | Counter | >5/min |

### Recovery Tracking
```ts
// In ErrorBoundaryFallback
Sentry.addBreadcrumb({ category: 'error_boundary', message: 'retry', data: { boundaryName } });
// On successful remount
Sentry.addBreadcrumb({ category: 'error_boundary', message: 'retry.success', data: { boundaryName } });
```

## Traceability
| NFR Design | Monitoring Solution |
|------------|---------------------|
| NFR5.1 (Error Capture) | componentDidCatch → Sentry |
| NFR5.2 (Error Rates) | Sentry metrics by boundary |
| NFR5.3 (Recovery) | Breadcrumbs on retry + success |
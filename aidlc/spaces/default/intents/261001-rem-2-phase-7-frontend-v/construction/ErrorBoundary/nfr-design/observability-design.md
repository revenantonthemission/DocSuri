# Observability Design — ErrorBoundary

## NFR5.1: 100% Error Capture
**Design**: `componentDidCatch` → `Sentry.captureException()`
- All caught errors reported
- Sentry groups by error type + component stack

## NFR5.2: Boundary-Specific Error Rates
**Design**: Sentry Metrics
- `error_boundary.catch.count` (counter by boundary name)
- **Alert**: >10/min per boundary

## NFR5.3: Recovery Tracking
**Design**: Custom Events
```ts
// In ErrorBoundaryFallback onRetry
Sentry.addBreadcrumb({ category: 'error_boundary', message: 'retry', data: { boundaryName } });
// On successful remount (useEffect in wrapped component)
Sentry.addBreadcrumb({ category: 'error_boundary', message: 'retry.success', data: { boundaryName } });
```

## Traceability
| NFR Requirement | Design Solution |
|-----------------|-----------------|
| NFR5.1 | componentDidCatch → Sentry captureException |
| NFR5.2 | Sentry metrics by boundary name |
| NFR5.3 | Breadcrumb on retry + success |
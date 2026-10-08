# Observability Requirements — ErrorBoundary

## NFR5.1: Error Capture (NFR7)
- **Target**: 100% of caught errors reported to Sentry
- **Implementation**: `componentDidCatch` → `Sentry.captureException()`
- **Deduplication**: Sentry groups by error type + component stack

## NFR5.2: Error Rate Metrics
- **Target**: Boundary-specific error rates
- **Metrics**: `error_boundary.catch.count` (counter by boundary name)
- **Alerting**: Sentry alert on boundary catch rate >10/min

## NFR5.3: Recovery Tracking
- **Target**: Retry success/failure tracked
- **Events**: `error_boundary.retry`, `error_boundary.retry.success`, `error_boundary.retry.failed`

## Traceability
| Inception NFR | Derived ID | Status |
|---------------|------------|--------|
| NFR6 (Error Boundary) | NFR5.1, NFR5.2 | OK |
| NFR7 (Sentry) | NFR5.1, NFR5.2, NFR5.3 | OK |
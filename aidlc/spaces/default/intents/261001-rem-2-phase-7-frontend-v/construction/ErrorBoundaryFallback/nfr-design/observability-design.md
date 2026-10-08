# Observability Design — ErrorBoundaryFallback

## NFR5.1: Retry Analytics
**Design**: Sentry Breadcrumbs + Custom Analytics
```tsx
const handleRetry = () => {
  Sentry.addBreadcrumb({ category: 'error_boundary', message: 'fallback.retry.click', data: { boundaryName, errorCode } });
  analytics.track('error_boundary_retry', { boundaryName, errorCode });
  reset();
};
```
- Events: `fallback.retry.click`, `fallback.dismiss.click`
- Fields: `boundaryName`, `errorCode`

## Traceability
| NFR Requirement | Design Solution |
|-----------------|-----------------|
| NFR5.1 | Sentry breadcrumbs + custom analytics on retry |
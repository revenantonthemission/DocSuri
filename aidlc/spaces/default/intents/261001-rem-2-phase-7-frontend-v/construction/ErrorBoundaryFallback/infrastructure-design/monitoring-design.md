# Monitoring Design — ErrorBoundaryFallback

## Sentry Breadcrumbs
```tsx
const handleRetry = () => {
  Sentry.addBreadcrumb({ category: 'error_boundary', message: 'fallback.retry.click', data: { boundaryName, errorCode } });
  analytics.track('error_boundary_retry', { boundaryName, errorCode });
  reset();
};
```
- Events: `fallback.retry.click`, `fallback.dismiss.click`

## Traceability
| NFR Design | Monitoring Solution |
|------------|---------------------|
| NFR5.1 (Retry Analytics) | Sentry breadcrumbs + custom analytics |
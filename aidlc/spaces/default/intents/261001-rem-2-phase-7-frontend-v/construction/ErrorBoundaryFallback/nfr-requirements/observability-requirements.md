# Observability Requirements — ErrorBoundaryFallback

## NFR5.1: Retry Analytics
- **Target**: Track retry attempts and outcomes
- **Events**: `fallback.retry.click`, `fallback.dismiss.click`
- **Fields**: `boundaryName`, `errorCode`
- **Destination**: Sentry breadcrumbs + custom analytics

## Traceability
| Inception NFR | Derived ID | Status |
|---------------|------------|--------|
| NFR6 (Error Boundary) | NFR5.1 | OK |
| NFR7 (Sentry) | NFR5.1 | OK |
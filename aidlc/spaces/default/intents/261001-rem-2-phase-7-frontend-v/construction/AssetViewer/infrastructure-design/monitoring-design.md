# Monitoring Design — AssetViewer

## Client-Side Monitoring (Sentry)

### Asset Access Breadcrumbs
```ts
Sentry.addBreadcrumb({ category: 'asset', message: 'request', data: { paperId, assetId, assetType } });
Sentry.addBreadcrumb({ category: 'asset', message: 'delivered', data: { paperId, assetId, size, duration } });
Sentry.addBreadcrumb({ category: 'asset', message: 'denied', data: { paperId, assetId, statusCode } });
Sentry.addBreadcrumb({ category: 'asset', message: 'error', data: { paperId, assetId, errorCode } });
```

### Performance Metrics
| Metric | Type | Alert |
|--------|------|-------|
| `asset.load.time` | Histogram (by type) | P95 >10s |
| `asset.stream.throughput` | Gauge (bytes/sec) | <1MB/s |
| `asset.error.rate` | Counter | >5% in 5min |

### Error Tracking
```ts
Sentry.captureException(err, { extra: { paperId, assetId, assetType }, tags: { feature: 'phase7-assetviewer' } });
```

## Server-Side Audit (Gateway)
- Every request logged: `paperId`, `assetId`, `userId`, `assetType`, `size`, `duration`, `statusCode`, `ip`
- Security review Week 2 validates audit completeness

## Traceability
| NFR Design | Monitoring Solution |
|------------|---------------------|
| NFR5.1 (Asset Audit) | Client breadcrumbs + Gateway audit log |
| NFR5.2 (Performance) | Sentry measurements + alerts |
| NFR5.3 (Error Tracking) | Sentry captureException with context |
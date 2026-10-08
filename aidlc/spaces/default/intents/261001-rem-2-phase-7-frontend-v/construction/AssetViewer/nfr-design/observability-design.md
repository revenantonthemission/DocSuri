# Observability Design — AssetViewer

## NFR5.1: Asset Access Audit (Security Review NFR8)
**Design**: Gateway Audit Log + Sentry Breadcrumbs
- **Gateway**: Every request logged with `paperId`, `assetId`, `userId`, `assetType`, `size`, `duration`, `statusCode`, `ip`
- **Client**: Breadcrumbs for `asset.request`, `asset.delivered`, `asset.denied`, `asset.error`

## NFR5.2: Performance Metrics
**Design**: Sentry Measurements
- `asset.load.time` (histogram by type: pdf/image/video)
- `asset.stream.throughput` (bytes/sec)
- **Alert**: P95 >10s → investigation

## NFR5.3: Error Tracking
**Design**: Sentry Error Capture
- `asset.load.error` with `errorCode`, `assetType`, `paperId`
- Context: userAgent, viewport, network type

## Traceability
| NFR Requirement | Design Solution |
|-----------------|-----------------|
| NFR5.1 | Gateway audit log + client breadcrumbs |
| NFR5.2 | Sentry measurements + alert rules |
| NFR5.3 | Sentry captureException with context |
# Observability Requirements — AssetViewer

## NFR5.1: Asset Access Audit (Security Review NFR8)
- **Target**: Every asset request logged for security audit
- **Events**: `asset.request`, `asset.delivered`, `asset.denied`, `asset.error`
- **Fields**: `paperId`, `assetId`, `userId`, `assetType`, `size`, `duration`, `statusCode`, `ip` (via gateway)
- **Destination**: Gateway audit log + Sentry breadcrumbs

## NFR5.2: Performance Metrics
- **Target**: Asset load time distribution
- **Metrics**: `asset.load.time` (histogram by type), `asset.stream.throughput` (bytes/sec)
- **Alerting**: P95 load time >10s triggers investigation

## NFR5.3: Error Tracking (NFR7)
- **Target**: Asset load errors captured in Sentry
- **Events**: `asset.load.error` with `errorCode`, `assetType`, `paperId`
- **Context**: User agent, viewport, network type (navigator.connection)

## Traceability
| Inception NFR | Derived ID | Status |
|---------------|------------|--------|
| NFR2 (SEC-9) | NFR5.1 | OK |
| NFR3 (SECURITY-08) | NFR5.1 | OK |
| NFR7 (Sentry) | NFR5.3 | OK |
| NFR8 (Security Review) | NFR5.1 | OK |
# Monitoring Design — JobStatus

## Client-Side Monitoring (Sentry)

### Error Tracking
- **ErrorBoundary** captures all JobStatus subtree errors
- `Sentry.captureException(error, { extra: { component: 'JobStatus', jobId }, tags: { feature: 'phase7-jobstatus' } })`
- **Breadcrumbs**: SSE lifecycle (`connected`, `event_received`, `error`, `fallback_activated`)

### Performance Monitoring
- **Web Vitals**: LCP, FID, CLS via `reportWebVitals` → Sentry
- **Custom Measurements**:
  - `sse.connect.latency` (histogram, ms)
  - `sse.events.per.second` (counter)
  - `polling.fallback.activations` (counter)
  - `render.duration` (histogram, ms)

### Alerting Rules (Sentry)
| Alert | Condition | Severity |
|-------|-----------|----------|
| SSE Error Rate | >5% of connections error in 5min | Warning |
| Polling Fallback Rate | >10% of sessions use fallback in 1hr | Warning |
| ErrorBoundary Catches | >5 catches/min per boundary | Critical |

## Server-Side Monitoring (Gateway Responsibility)

### BFF Proxy Metrics (Next.js)
- Request latency (p50, p95, p99)
- Error rate by status code
- Upstream gateway latency

### Gateway Metrics (Out of Scope)
- SSE connection count
- Event throughput
- Auth failure rate

## Dashboards
- **Sentry Dashboard**: "Phase 7 - JobStatus" with error trends, performance, fallback activations
- **Custom Dashboard**: SSE connection health, event latency distribution

## Traceability
| NFR Design | Monitoring Solution |
|------------|---------------------|
| NFR5.1 (Error Tracking) | ErrorBoundary + Sentry captureException |
| NFR5.2 (Performance) | Web Vitals + custom measurements |
| NFR5.3 (SSE Health) | Structured breadcrumbs |
| NFR5.4 (A11y Audit) | axe-core in CI |
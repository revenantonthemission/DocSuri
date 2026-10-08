# Observability Requirements — JobStatus

## NFR5.1: Client-Side Error Tracking (NFR7)
- **Target**: All unhandled errors in JobStatus subtree reported to Sentry
- **Implementation**: ErrorBoundary `componentDidCatch` → `Sentry.captureException(error, { extra: { component: 'JobStatus', jobId } })`
- **Breadcrumbs**: SSE connection events (`open`, `error`, `message`), polling switches, retry clicks
- **Release Tracking**: `Sentry.setTag('release', process.env.NEXT_PUBLIC_APP_VERSION)`

## NFR5.2: Performance Monitoring
- **Target**: Web Vitals (CLS, FID, LCP) for pages containing JobStatus
- **Implementation**: `next/app` `reportWebVitals` → Sentry + custom analytics
- **Custom Metrics**: 
  - `sse.connect.latency` (histogram)
  - `sse.events.per.second` (counter)
  - `polling.fallback.activations` (counter)

## NFR5.3: SSE Health Logging
- **Target**: Structured logs for SSE lifecycle
- **Events**: `sse.connected`, `sse.reconnected`, `sse.failed`, `sse.fallback.activated`
- **Fields**: `jobId`, `paperId`, `userId`, `duration`, `eventCount`, `errorCode`
- **Destination**: Browser console (dev) → Sentry breadcrumbs (prod)

## NFR5.4: Accessibility Audit Trail
- **Target**: ARIA live region announcements logged for screen reader verification
- **Implementation**: Custom hook logs `aria-live` messages to console (dev) / analytics (prod)
- **Validation**: axe-core automated tests in CI

## Traceability
| Inception NFR | Derived ID | Status |
|---------------|------------|--------|
| NFR5 (Polling Fallback) | NFR5.2, NFR5.3 | OK |
| NFR6 (Error Boundary) | NFR5.1 | OK |
| NFR7 (Sentry) | NFR5.1, NFR5.2, NFR5.3 | OK |
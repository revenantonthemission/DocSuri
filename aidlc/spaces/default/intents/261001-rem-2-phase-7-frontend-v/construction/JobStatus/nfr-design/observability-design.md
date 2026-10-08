# Observability Design — JobStatus

## NFR5.1: Client-Side Error Tracking (NFR7)
**Design**: ErrorBoundary + Sentry integration
- `ErrorBoundary.componentDidCatch` → `Sentry.captureException()`
- **Context**: `component: 'JobStatus'`, `jobId`, `paperId`
- **Breadcrumbs**: SSE lifecycle events auto-added
```ts
Sentry.addBreadcrumb({ category: 'sse', message: 'connected', level: 'info' });
Sentry.addBreadcrumb({ category: 'sse', message: 'event_received', level: 'info', data: { eventType } });
Sentry.addBreadcrumb({ category: 'sse', message: 'fallback_activated', level: 'warning' });
```

## NFR5.2: Performance Monitoring
**Design**: Web Vitals + Custom Metrics
- **Web Vitals**: `reportWebVitals` → Sentry + custom analytics
- **Custom Metrics** (via Sentry `measurements`):
  - `sse.connect.latency` (histogram, ms)
  - `sse.events.per.second` (counter)
  - `polling.fallback.activations` (counter)
  - `render.duration` (histogram, ms)

## NFR5.3: SSE Health Logging
**Design**: Structured console (dev) → Sentry breadcrumbs (prod)
```ts
const logSSE = (event: string, data?: object) => {
  if (process.env.NODE_ENV === 'development') {
    console.log(`[SSE] ${event}`, data);
  }
  Sentry.addBreadcrumb({ category: 'sse', message: event, level: 'info', data });
};
```
- Events: `connected`, `reconnected`, `event_received`, `error`, `fallback_activated`
- Fields: `jobId`, `paperId`, `userId`, `duration`, `eventCount`, `errorCode`

## NFR5.4: Accessibility Audit Trail
**Design**: ARIA live region announcements logged
```ts
const announce = (message: string) => {
  const region = document.getElementById('jobstatus-aria-live');
  if (region) region.textContent = message;
  if (process.env.NODE_ENV === 'development') console.log('[A11y]', message);
};
```
- Validated by axe-core in CI

## Traceability
| NFR Requirement | Design Solution |
|-----------------|-----------------|
| NFR5.1 | ErrorBoundary + Sentry captureException + breadcrumbs |
| NFR5.2 | Web Vitals + custom Sentry measurements |
| NFR5.3 | Structured SSE lifecycle breadcrumbs |
| NFR5.4 | ARIA live region + dev console logging |
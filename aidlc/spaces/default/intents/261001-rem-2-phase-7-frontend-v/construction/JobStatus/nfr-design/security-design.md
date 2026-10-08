# Security Design — JobStatus

## NFR2.1: SSE Authentication
**Design**: Same-origin `EventSource` with automatic cookie inclusion
- `EventSource('/bff/api/content-jobs/${jobId}/events')` — browser sends cookies automatically
- BFF proxy forwards `Cookie` header to gateway
- Gateway validates session, injects principal
- **Failure**: 401 → `EventSource` closes → ErrorBoundary catches → redirect to login

## NFR2.2: Idempotency Key Handling
**Design**: Keys received via props from ContentJobApi
- JobStatus never generates keys; receives `idempotencyKey` prop
- Keys passed in SSE headers by gateway (not in URL)
- **No Logging**: Keys never logged, never in console, never in Sentry breadcrumbs

## NFR2.3: Error Information Disclosure
**Design**: ErrorBoundary sanitizes all error output
- Production: Generic "Connection lost" + error code `ERR_JOBSTATUS_SSE_FAILED`
- Development: Full error + component stack
- **Sentry**: Full error captured server-side; client sees only code

## NFR2.4: Content Security Policy
**Design**: Next.js CSP header in `next.config.js`
```js
headers: [
  {
    source: '/:path*',
    headers: [
      { key: 'Content-Security-Policy', value: "connect-src 'self';" }
    ]
  }
]
```
- Allows SSE to `/bff/api/content-jobs/*`
- Blocks external connections

## NFR2.5: Sentry Integration (NFR7)
**Design**: ErrorBoundary + Sentry breadcrumbs
```ts
componentDidCatch(error, info) {
  Sentry.captureException(error, {
    extra: { component: 'JobStatus', jobId: this.props.jobId },
    tags: { feature: 'phase7-jobstatus' }
  });
  Sentry.addBreadcrumb({
    category: 'sse',
    message: 'JobStatus error boundary caught',
    level: 'error',
    data: { jobId: this.props.jobId }
  });
}
```

## Traceability
| NFR Requirement | Design Solution |
|-----------------|-----------------|
| NFR2.1 | Native EventSource + BFF cookie forwarding |
| NFR2.2 | Keys via props, never logged |
| NFR2.3 | ErrorBoundary sanitization |
| NFR2.4 | CSP connect-src 'self' |
| NFR2.5 | ErrorBoundary → Sentry + breadcrumbs |
# Infrastructure Specification — JobStatus

## Frontend Infrastructure (Next.js on Vercel/AWS)

### BFF Proxy Routes
| Route | Method | Upstream | Auth | Purpose |
|-------|--------|----------|------|---------|
| `/bff/api/content-jobs/:jobId/events` | GET | Gateway SSE | Cookie | SSE stream for job status |
| `/bff/api/content-jobs/:jobId` | GET | Gateway REST | Cookie | Polling fallback endpoint |

### Next.js Configuration
```js
// next.config.js
module.exports = {
  output: 'standalone',
  async headers() {
    return [{
      source: '/:path*',
      headers: [
        { key: 'Content-Security-Policy', value: "connect-src 'self';" }
      ]
    }];
  }
};
```

### Build & Deploy
- **Build Command**: `next build` (outputs `.next/standalone`)
- **Docker**: `Dockerfile` copies standalone output
- **Deploy**: Vercel / AWS ECS Fargate (continuous deployment on merge)

### Environment Variables
| Variable | Source | Required |
|----------|--------|----------|
| `DOCSURI_GATEWAY_URL` | Platform secret | Yes |
| `NEXT_PUBLIC_APP_VERSION` | Build-time | Yes |
| `SENTRY_DSN` | Platform secret | Yes |

## Client-Side Infrastructure

### SSE Connection
- Native `EventSource` → `/bff/api/content-jobs/{jobId}/events`
- Auto-reconnect with `Last-Event-ID` (browser handled)
- No infrastructure needed beyond BFF proxy

### Polling Fallback (SWR)
- `useSWR('/bff/api/content-jobs/{jobId}', fetcher, { refreshInterval: 2000 })`
- SWR cache: 5min TTL, deduping 1s
- No additional infrastructure

### Error Boundary
- Client-side only (React class component)
- Sentry DSN via `NEXT_PUBLIC_SENTRY_DSN`

## Traceability
| Logical Component | Infrastructure Need |
|-------------------|---------------------|
| JobStatus (UI) | BFF SSE route, BFF polling route |
| useSSE hook | BFF SSE route |
| usePollingFallback hook | BFF polling route |
| ErrorBoundary | Sentry DSN |
# Infrastructure Specification — ErrorBoundary

## Client-Only Infrastructure

### ErrorBoundary Component
- **Type**: React Class Component (required for `componentDidCatch`)
- **Sentry**: `@sentry/nextjs` (auto source map upload)
- **No Server Infrastructure**

### ErrorBoundaryFallback (Separate Unit)
- **Type**: Functional Component
- **Styling**: CSS Module + Tailwind
- **Icons**: Inline SVG

### Sentry Integration
```js
// sentry.client.config.ts
import * as Sentry from '@sentry/nextjs';
Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  tracesSampleRate: 1.0,
  integrations: [new Sentry.BrowserTracing()],
});
```

## Traceability
| Logical Component | Infrastructure Need |
|-------------------|---------------------|
| ErrorBoundary | Sentry DSN (build env) |
| ErrorBoundaryFallback | CSS Module + Tailwind (build) |
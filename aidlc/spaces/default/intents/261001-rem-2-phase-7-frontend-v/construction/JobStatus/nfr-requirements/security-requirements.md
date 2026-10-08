# Security Requirements — JobStatus

## NFR2.1: SSE Authentication
- **Requirement**: SSE connection must include session cookie for gateway authentication
- **Implementation**: `EventSource` uses browser's automatic cookie inclusion (same-origin)
- **Validation**: Gateway returns 401 if session invalid; UI redirects to login
- **Threat**: Session hijacking via stolen SSE connection (mitigated by short-lived sessions)

## NFR2.2: Idempotency Key Handling
- **Requirement**: JobStatus does not generate idempotency keys; receives them from ContentJobApi
- **Validation**: Keys passed via props; never logged or exposed in URL
- **Threat**: Key leakage enabling replay attacks (mitigated by server-side validation)

## NFR2.3: Error Information Disclosure
- **Requirement**: Error messages from SSE/gateway must not leak internal stack traces or infrastructure details
- **Implementation**: ErrorBoundary sanitizes error messages; shows user-friendly fallbacks
- **Validation**: Security review of error payloads

## NFR2.4: Content Security Policy
- **Requirement**: SSE endpoint (`/bff/api/content-jobs/{jobId}/events`) must be allowed in `connect-src`
- **Implementation**: Next.js CSP header includes `connect-src 'self'`
- **Validation**: CSP report-only mode in staging

## NFR2.5: Sentry Integration (NFR7)
- **Requirement**: Client-side errors captured by Sentry with release tracking
- **Implementation**: `Sentry.init()` in `_app.tsx`; ErrorBoundary calls `Sentry.captureException()`
- **Data Classification**: Error context only; no PII in breadcrumbs
- **Validation**: Sentry dashboard shows Phase 7 errors

## Traceability
| Inception NFR | Derived ID | Status |
|---------------|------------|--------|
| NFR1 (SEC-8) | NFR2.1 | OK |
| NFR4 (Idempotency) | NFR2.2 | OK |
| NFR7 (Sentry) | NFR2.5 | OK |
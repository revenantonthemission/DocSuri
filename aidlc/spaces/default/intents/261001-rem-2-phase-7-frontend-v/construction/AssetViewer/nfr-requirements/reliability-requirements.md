# Reliability Requirements — AssetViewer

## NFR4.1: Network Interruption Handling
- **Target**: Partial asset loads resume on reconnect (Range requests)
- **Implementation**: BFF proxy supports `Range` headers; forwards to gateway
- **UI**: Show loading indicator; retry button on failure

## NFR4.2: Auth Expiry During View
- **Target**: Session expiry during asset view → graceful re-auth
- **Behavior**: 401 on asset request → ErrorBoundary catches → redirect to login with return URL
- **Recovery**: Post-login, asset request retries automatically

## NFR4.3: Error Boundary Integration (NFR6)
- **Target**: AssetViewer wrapped in ErrorBoundary
- **Fallback**: Shows "Unable to load asset" with retry button + error code
- **Recovery**: Retry re-fetches from BFF (new auth check)

## NFR4.4: PDF.js Error Containment
- **Target**: PDF.js parse errors don't crash parent
- **Implementation**: PDF.js loaded in try/catch; ErrorBoundary catches render errors

## Traceability
| Inception NFR | Derived ID | Status |
|---------------|------------|--------|
| NFR2 (SEC-9) | NFR4.2 | OK |
| NFR3 (SECURITY-08) | NFR4.1 | OK |
| NFR6 (Error Boundary) | NFR4.3, NFR4.4 | OK |
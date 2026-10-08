# Reliability Design — AssetViewer

## NFR4.1: Range Request Resume
**Design**: BFF supports `Range` header
- Browser sends `Range` for partial content (video seek, PDF byte-range)
- BFF forwards `Range` to gateway
- Gateway forwards to object storage
- **UI**: Loading indicator during resume

## NFR4.2: Auth Expiry During View
**Design**: 401 → ErrorBoundary → redirect with return URL
- Asset request returns 401
- ErrorBoundary catches → fallback with "Session expired"
- Redirect: `/login?returnTo=/papers/{paperId}/assets/{assetId}`
- Post-login: Auto-retry asset request

## NFR4.3: Error Boundary Integration
**Design**: `<ErrorBoundary>` wraps AssetViewer
- Fallback: "Unable to load asset" + retry button
- Retry → remount → fresh BFF request → fresh auth check

## NFR4.4: PDF.js Error Containment
**Design**: Try/catch + ErrorBoundary
```ts
try {
  const pdf = await pdfjsLib.getDocument({ url }).promise;
} catch (err) {
  throw new Error(`PDF_LOAD_FAILED: ${err.message}`);
}
```
- ErrorBoundary catches → fallback UI

## Traceability
| NFR Requirement | Design Solution |
|-----------------|-----------------|
| NFR4.1 | BFF Range header passthrough |
| NFR4.2 | 401 → ErrorBoundary → login redirect |
| NFR4.3 | ErrorBoundary wrap + retry remount |
| NFR4.4 | Try/catch PDF.js + ErrorBoundary |
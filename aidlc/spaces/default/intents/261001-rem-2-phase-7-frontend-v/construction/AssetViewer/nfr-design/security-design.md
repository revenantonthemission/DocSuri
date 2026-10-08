# Security Design — AssetViewer

## NFR2.1: Same-Origin Delivery (SECURITY-08)
**Design**: **Strict BFF-only asset delivery**
- **Zero Presigned URLs**: ESLint rule forbids `presigned`, `s3.amazonaws.com`, `blob.core.windows.net`
- **Asset URL**: `/bff/api/papers/{paperId}/assets/{assetId}` only
- **BFF Proxy**: Forwards to gateway `/papers/{paperId}/assets/{assetId}`
- **Gateway**: Streams from object storage (S3/GCS) with signed internal URLs (never exposed)

## NFR2.2: Auth Re-Check at Delivery (SEC-9)
**Design**: Per-request gateway validation
```
Browser → BFF (Cookie) → Gateway (Validate Session + ACL) → Object Storage
```
- **BFF**: Forwards `Cookie` header
- **Gateway**: Validates session, checks `paperId` access ACL
- **Failure**: 401/403 → BFF relays → ErrorBoundary catches → redirect to login
- **Threat Model**: Stolen asset URL useless without valid session

## NFR2.3: Session Cookie Forwarding
**Design**: Bidirectional cookie proxy (same as ContentJobApi)
- Request: `Cookie` → upstream
- Response: `Set-Cookie` → browser

## NFR2.4: CSP for Assets
**Design**: Next.js CSP
```js
headers: [
  { key: 'Content-Security-Policy', value: "img-src 'self' data:; media-src 'self'; frame-src 'self';" }
]
```
- `img-src`: Images via BFF
- `media-src`: Video/audio via BFF
- `frame-src`: PDF.js iframe via BFF

## NFR2.5: No Client-Side Secrets
**Design**: Code scan enforcement
- Forbidden patterns: `presigned`, `signature`, `X-Amz-`, `SharedAccessSignature`
- AssetViewer receives only BFF URL — no tokens, no signatures

## Traceability
| NFR Requirement | Design Solution |
|-----------------|-----------------|
| NFR2.1 | BFF-only URLs, ESLint forbids presigned |
| NFR2.2 | Per-request gateway auth + ACL check |
| NFR2.3 | BFF bidirectional cookie forwarding |
| NFR2.4 | CSP img-src/media-src/frame-src 'self' |
| NFR2.5 | Code scan for forbidden patterns |
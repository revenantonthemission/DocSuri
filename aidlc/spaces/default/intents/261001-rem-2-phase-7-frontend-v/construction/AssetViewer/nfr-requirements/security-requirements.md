# Security Requirements — AssetViewer

## NFR2.1: Same-Origin Asset Delivery (NFR3/SECURITY-08)
- **Requirement**: ALL assets delivered via `/bff/api/papers/{paperId}/assets/{assetId}` — NO presigned URLs
- **Implementation**: 
  - AssetViewer `src` prop points to BFF asset endpoint
  - BFF proxy (`/bff/[...path]`) forwards to gateway `/papers/{paperId}/assets/{assetId}`
  - Gateway validates session, checks permissions, streams asset
- **Validation**: 
  - ESLint rule forbids `presigned`, `s3.amazonaws.com`, `blob.core.windows.net` in asset URLs
  - Security review Week 2 verifies no presigned URL code paths

## NFR2.2: Auth Re-Check at Delivery Time (NFR2/SEC-9)
- **Requirement**: Gateway re-validates authentication AND authorization on EVERY asset request
- **Implementation**: 
  - BFF forwards `Cookie` header to gateway
  - Gateway verifies session, checks paper access ACL
  - Gateway returns 401/403 if invalid → BFF relays to browser
- **Threat**: Stolen asset URL used without valid session (mitigated by per-request auth check)

## NFR2.3: Session Cookie Forwarding
- **Requirement**: BFF proxy forwards cookies bidirectionally
- **Implementation**: 
  - Request: `headers.cookie` → upstream `Cookie`
  - Response: upstream `Set-Cookie` → browser `Set-Cookie`
- **Validation**: Integration test with expired session → 401 on asset request

## NFR2.4: Content Security Policy
- **Requirement**: Asset endpoints allowed in `img-src`, `media-src`, `frame-src` (for PDF embed)
- **Implementation**: Next.js CSP: `img-src 'self' data:; media-src 'self'; frame-src 'self'`
- **Note**: PDF.js worker loaded from same origin

## NFR2.5: No Client-Side Secrets
- **Requirement**: AssetViewer never receives or stores presigned URLs, signatures, or tokens
- **Validation**: Code scan for `presigned`, `signature`, `X-Amz-`, `SharedAccessSignature`

## Traceability
| Inception NFR | Derived ID | Status |
|---------------|------------|--------|
| NFR2 (SEC-9) | NFR2.2, NFR2.3 | OK |
| NFR3 (SECURITY-08) | NFR2.1, NFR2.5 | OK |
| NFR7 (Sentry) | NFR2.4 | OK |
| NFR8 (Security Review) | NFR2.1, NFR2.2, NFR2.5 | OK |
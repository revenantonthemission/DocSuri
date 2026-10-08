# Security Requirements — ContentJobApi

## NFR2.1: BFF Routing Enforcement (NFR1/SEC-8)
- **Requirement**: ALL content-job API calls route through `/bff/api/content-jobs/*`
- **Implementation**: 
  - Base URL constant: `CONTENT_JOB_API_BASE = '/bff/api/content-jobs'`
  - ESLint rule forbids direct `/api/content-jobs` or gateway URLs
  - Runtime assertion in development throws if non-BFF URL detected
- **Validation**: Gateway injects principal; bypass = auth bypass = SEC-8 violation

## NFR2.2: Idempotency Key Security (NFR4)
- **Requirement**: Idempotency keys generated as SHA-256 hash of `userId:paperId:taskType:JSON.stringify(params)`
- **Storage**: `localStorage` key `idempotency:{paperId}:{taskType}` (survives page reload)
- **Transmission**: Sent via `Idempotency-Key` header (never in URL/query)
- **Rotation**: Key regenerated on parameter change; old keys expire server-side (24h TTL)

## NFR2.3: Session Cookie Forwarding
- **Requirement**: BFF proxy forwards `Cookie` header to gateway; relays `Set-Cookie` back
- **Implementation**: Next.js `route.ts` copies `cookie` header from request to upstream; copies `set-cookie` from upstream to response
- **Validation**: Integration test verifies cookie round-trip

## NFR2.4: Input Sanitization
- **Requirement**: All request bodies validated against Zod schemas before BFF forwarding
- **Implementation**: `contentJobApi.ts` validates with `jobSubmitSchema` before `fetch`
- **Threat**: Malformed requests causing gateway errors (mitigated by client-side validation)

## NFR2.5: Error Information Disclosure
- **Requirement**: Gateway error responses sanitized before returning to UI
- **Implementation**: Transport layer strips internal fields (`stack`, `traceId`, `serviceName`)
- **Validation**: Error shape matches public `ApiError` interface only

## Traceability
| Inception NFR | Derived ID | Status |
|---------------|------------|--------|
| NFR1 (SEC-8) | NFR2.1, NFR2.3 | OK |
| NFR4 (Idempotency) | NFR2.2 | OK |
| NFR7 (Sentry) | NFR2.5 | OK |
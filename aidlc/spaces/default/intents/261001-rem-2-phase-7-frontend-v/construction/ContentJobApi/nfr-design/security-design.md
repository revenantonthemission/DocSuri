# Security Design — ContentJobApi

## NFR2.1: BFF Routing Enforcement (SEC-8)
**Design**: Compile-time + Runtime guards
- **Constant**: `CONTENT_JOB_API_BASE = '/bff/api/content-jobs'`
- **ESLint Rule**: `no-restricted-imports` blocks direct `/api/content-jobs` or gateway URLs
- **Runtime Assertion** (dev): `if (!url.startsWith(CONTENT_JOB_API_BASE)) throw new Error('SEC-8 violation')`
- **Gateway**: Injects principal from session; bypass = no principal = auth bypass

## NFR2.2: Idempotency Key Security
**Design**: Deterministic SHA-256 + Secure Transport
- **Generation**: `SHA-256(userId:paperId:taskType:JSON.stringify(params))`
- **Header**: `Idempotency-Key: <hash>` (never in URL/query)
- **Storage**: localStorage `idempotency:{paperId}:{taskType}` (namespaced, no secrets)
- **Rotation**: New params → new hash; server TTL 24h

## NFR2.3: Session Cookie Forwarding
**Design**: BFF Bidirectional Cookie Proxy
```ts
// Request: Browser → BFF → Gateway
headers: { Cookie: req.headers.get('cookie') || '' }

// Response: Gateway → BFF → Browser
response.headers.forEach((value, key) => {
  if (key === 'set-cookie') res.headers.append('Set-Cookie', value);
});
```
- **Validation**: Integration test with expired session → 401

## NFR2.4: Input Sanitization
**Design**: Zod Schema Validation Before BFF
```ts
const jobSubmitSchema = z.object({
  paperId: z.string().uuid(),
  taskType: z.enum(['summarize', 'extract', 'analyze']),
  params: z.record(z.unknown()).optional(),
});
// Validated in contentJobApi.ts before fetch
```
- **Fail Fast**: Invalid input → 400 before network call

## NFR2.5: Error Information Disclosure
**Design**: Transport Layer Sanitization
```ts
function sanitizeError(error: unknown): ApiError {
  if (error instanceof Response) {
    return { code: 'GATEWAY_ERROR', message: 'Request failed', status: error.status };
  }
  return { code: 'UNKNOWN_ERROR', message: 'An error occurred' };
}
```
- Strips: `stack`, `traceId`, `serviceName`, internal codes

## Traceability
| NFR Requirement | Design Solution |
|-----------------|-----------------|
| NFR2.1 | Constant base URL + ESLint + runtime assert |
| NFR2.2 | SHA-256 deterministic + header transport + localStorage |
| NFR2.3 | BFF bidirectional cookie forwarding |
| NFR2.4 | Zod validation pre-fetch |
| NFR2.5 | Transport sanitization layer |
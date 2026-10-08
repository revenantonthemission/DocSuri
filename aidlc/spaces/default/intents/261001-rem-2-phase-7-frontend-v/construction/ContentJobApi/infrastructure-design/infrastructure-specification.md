# Infrastructure Specification — ContentJobApi

## Frontend Infrastructure (Next.js)

### BFF Proxy Routes
| Route | Method | Upstream | Auth | Purpose |
|-------|--------|----------|------|---------|
| `/bff/api/content-jobs` | POST | Gateway POST | Cookie | Submit job with idempotency key |
| `/bff/api/content-jobs/:jobId` | GET | Gateway GET | Cookie | Get job status (polling) |
| `/bff/api/content-jobs/:jobId` | DELETE | Gateway DELETE | Cookie | Cancel job |

### Next.js BFF Implementation
```ts
// app/bff/api/content-jobs/[...path]/route.ts
export async function POST(req: Request) {
  const gatewayUrl = `${process.env.DOCSURI_GATEWAY_URL}/api/content-jobs${path}`;
  const idempotencyKey = req.headers.get('Idempotency-Key');
  const response = await fetch(gatewayUrl, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Cookie: req.headers.get('cookie') || '',
      ...(idempotencyKey && { 'Idempotency-Key': idempotencyKey })
    },
    body: await req.text(),
    duplex: 'half',
  });
  // Forward Set-Cookie
  const res = new Response(response.body, { headers: response.headers });
  response.headers.getSetCookie?.().forEach(c => res.headers.append('Set-Cookie', c));
  return res;
}
```

### Client-Side Transport
- **Interface**: `Transport` with `fetch`, `fetchWithRetry`, `abort`
- **Base URL**: `/bff/api/content-jobs` (constant)
- **Validation**: Zod schemas pre-fetch
- **Idempotency**: `IdempotencyService` generates SHA-256 keys

### Environment Variables
| Variable | Source | Required |
|----------|--------|----------|
| `DOCSURI_GATEWAY_URL` | Platform secret | Yes |

## Traceability
| Logical Component | Infrastructure Need |
|-------------------|---------------------|
| contentJobApi | BFF proxy routes (POST/GET/DELETE) |
| Transport | BFF proxy + AbortController |
| IdempotencyService | crypto.subtle + localStorage |
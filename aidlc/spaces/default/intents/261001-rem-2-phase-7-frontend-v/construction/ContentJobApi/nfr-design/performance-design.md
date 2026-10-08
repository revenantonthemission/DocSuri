# Performance Design — ContentJobApi

## NFR1.1: BFF Proxy Overhead ≤50ms
**Design**: Thin Next.js route proxy with streaming
```ts
// app/bff/api/content-jobs/[...path]/route.ts
export async function POST(req: Request) {
  const gatewayUrl = `${process.env.DOCSURI_GATEWAY_URL}/api/content-jobs${path}`;
  const response = await fetch(gatewayUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Cookie: req.headers.get('cookie') || '' },
    body: await req.text(),
    duplex: 'half', // streaming
  });
  // Stream response back without buffering
  return new Response(response.body, { headers: response.headers });
}
```
- **No Buffering**: `duplex: 'half'` + `response.body` passthrough
- **Header Forwarding**: Cookie → upstream, Set-Cookie → downstream

## NFR1.2: SHA-256 Generation ≤5ms
**Design**: Native `crypto.subtle` with TextEncoder
```ts
async function generateIdempotencyKey(material: string): Promise<string> {
  const encoder = new TextEncoder();
  const data = encoder.encode(material);
  const hash = await crypto.subtle.digest('SHA-256', data);
  return Array.from(new Uint8Array(hash)).map(b => b.toString(16).padStart(2, '0')).join('');
}
```
- **Benchmark**: ~1-2ms for 200-byte input on modern CPUs

## NFR1.3: 50 Concurrent Submissions
**Design**: Independent `fetch` per submission
- Browser HTTP/2 multiplexing (6 connections × multiplexing)
- `AbortController` per request for cancellation
- **No Client Queueing**: UI disables button per-job during in-flight

## NFR1.4: Bundle ≤10KB gzipped
**Design**: Minimal exports
- `contentJobApi.ts`: ~3KB (submit, getStatus, cancel)
- `Transport` interface: ~1KB
- `IdempotencyService` (separate unit): ~2KB
- Zod schemas: ~2KB (tree-shaken)

## Traceability
| NFR Requirement | Design Solution |
|-----------------|-----------------|
| NFR1.1 | Streaming BFF proxy, no buffering |
| NFR1.2 | crypto.subtle.digest + TextEncoder |
| NFR1.3 | Independent fetch + AbortController |
| NFR1.4 | Modular exports, tree-shaking |
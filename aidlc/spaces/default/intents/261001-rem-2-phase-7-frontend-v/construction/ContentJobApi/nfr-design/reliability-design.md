# Reliability Design — ContentJobApi

## NFR4.1: Idempotent Retry on Network Failure
**Design**: Transport Layer Retry with Same Key
```ts
async function fetchWithRetry(url: string, options: RequestInit, retries = 1): Promise<Response> {
  try {
    return await fetch(url, options);
  } catch (err) {
    if (retries === 0 || err instanceof TypeError === false) throw err; // Only retry network errors
    await new Promise(r => setTimeout(r, 1000 * (2 - retries))); // 1s, 2s
    return fetchWithRetry(url, options, retries - 1);
  }
}
```
- **Same Idempotency Key**: Retry sends identical `Idempotency-Key` header
- **Server Deduplication**: Gateway recognizes key → returns cached result
- **Non-Retry**: 4xx (client errors) never retried

## NFR4.2: BFF Proxy Failure → Network Error
**Design**: Transparent Failure Propagation
- BFF proxy errors (502, 503, 504) → surface as fetch rejection
- Transport retries once → ErrorBoundary catches
- **No Special Handling**: Standard error flow

## NFR4.3: Request Cancellation on Unmount
**Design**: AbortController in useEffect
```ts
useEffect(() => {
  const controller = new AbortController();
  submit(controller.signal);
  return () => controller.abort();
}, [jobId]);
```
- Cancels in-flight `fetch` on navigation/unmount

## Traceability
| NFR Requirement | Design Solution |
|-----------------|-----------------|
| NFR4.1 | Transport retry with same idempotency key |
| NFR4.2 | Transparent error propagation |
| NFR4.3 | AbortController in useEffect cleanup |
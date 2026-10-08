# Performance Design — AssetViewer

## NFR1.1: Asset Load ≤1s First Byte
**Design**: BFF Streaming Proxy
- `fetch('/bff/api/papers/{paperId}/assets/{assetId}')` → streams via BFF
- BFF: `duplex: 'half'` + `response.body` passthrough (no buffering)
- Gateway streams from object storage → no full-file buffering

## NFR1.2: BFF Proxy Overhead ≤100ms
**Design**: Minimal Next.js route
```ts
export async function GET(req, { params }) {
  const url = `${GATEWAY}/papers/${params.paperId}/assets/${params.assetId}`;
  const res = await fetch(url, { headers: { Cookie: req.headers.get('cookie') }, duplex: 'half' });
  return new Response(res.body, { headers: res.headers });
}
```
- No transformation, no buffering

## NFR1.3: Zoom/Pan 60fps
**Design**: CSS `transform` + `will-change` (GPU)
- `ZoomPanControls` uses `requestAnimationFrame` + direct DOM `transform`
- No React render cycle during interaction
- PDF.js: WASM backend + worker offload

## NFR1.4: Bundle ≤25KB gzipped
**Design**: Code-split PDF.js
- `AssetViewer` base: ~8KB
- PDF.js: Dynamic import `import('pdfjs-dist')` → separate chunk
- Images/Video: Native elements (0KB)

## Traceability
| NFR Requirement | Design Solution |
|-----------------|-----------------|
| NFR1.1 | BFF streaming proxy, no buffering |
| NFR1.2 | Minimal Next.js route, passthrough |
| NFR1.3 | CSS transform + RAF + PDF.js worker |
| NFR1.4 | Dynamic import PDF.js, native elements |
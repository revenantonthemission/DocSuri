# Infrastructure Specification — AssetViewer

## Frontend Infrastructure (Next.js)

### BFF Proxy Routes
| Route | Method | Upstream | Auth | Purpose |
|-------|--------|----------|------|---------|
| `/bff/api/papers/:paperId/assets/:assetId` | GET | Gateway GET | Cookie | Stream asset (PDF, image, video) |
| `/bff/api/papers/:paperId/assets/:assetId` | HEAD | Gateway HEAD | Cookie | Check asset exists/metadata |

### BFF Implementation (Streaming + Range Support)
```ts
// app/bff/api/papers/[paperId]/assets/[assetId]/route.ts
export async function GET(req: Request, { params }) {
  const gatewayUrl = `${process.env.DOCSURI_GATEWAY_URL}/papers/${params.paperId}/assets/${params.assetId}`;
  const range = req.headers.get('range');
  const headers: HeadersInit = { Cookie: req.headers.get('cookie') || '' };
  if (range) headers['Range'] = range;
  
  const response = await fetch(gatewayUrl, { headers, duplex: 'half' });
  
  // Forward relevant headers
  const resHeaders = new Headers();
  response.headers.forEach((v, k) => {
    if (['content-type', 'content-length', 'content-range', 'accept-ranges', 'cache-control', 'etag', 'last-modified'].includes(k)) {
      resHeaders.set(k, v);
    }
  });
  // Forward Set-Cookie
  response.headers.getSetCookie?.().forEach(c => resHeaders.append('Set-Cookie', c));
  
  return new Response(response.body, { status: response.status, headers: resHeaders });
}
```

### Client-Side Renderers
| Asset Type | Element | Streaming |
|------------|---------|-----------|
| PDF | `PDF.js` (dynamic import) | PDF.js handles byte-range |
| Image | `<img src="/bff/api/...">` | Browser native |
| Video | `<video src="/bff/api/...">` | Browser native (Range) |

### PDF.js Worker
- **Static File**: `/public/pdf.worker.min.mjs`
- **CDN**: Served via Next.js static optimization
- **Init**: `pdfjsLib.GlobalWorkerOptions.workerSrc = '/pdf.worker.min.mjs'`

### CSP Headers
```js
headers: [{
  source: '/:path*',
  headers: [
    { key: 'Content-Security-Policy', value: "img-src 'self' data:; media-src 'self'; frame-src 'self';" }
  ]
}]
```

### Environment Variables
| Variable | Source | Required |
|----------|--------|----------|
| `DOCSURI_GATEWAY_URL` | Platform secret | Yes |

## Traceability
| Logical Component | Infrastructure Need |
|-------------------|---------------------|
| AssetViewer | BFF asset route (GET/HEAD) |
| PDFRenderer | PDF.js worker static file |
| ImageRenderer | BFF asset route |
| VideoRenderer | BFF asset route + Range support |
| ZoomPanControls | Client-only (GPU) |
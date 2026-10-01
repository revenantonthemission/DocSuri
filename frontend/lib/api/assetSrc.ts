// Browser-side asset URL rewriting (REM-2 F07 / SECURITY-08).
//
// The asset manifest now returns a **same-origin delivery path** (`/api/papers/<id>/assets/<assetId>`)
// instead of a presigned object-storage URL, so the object key and storage host never reach the
// browser. That path is served by U7's backend — which is not a Next.js route — so the browser has
// to reach it through the server-side BFF (`/bff/*`), the same seam every other API call uses. That
// is the whole point: the hop carries the httpOnly session cookie, so the bytes are fetched *inside*
// an authenticated, authorized hop instead of by the page.
//
// Absent a rewrite the browser would request `/api/...` from the Next.js origin, which has no such
// route, and every figure would silently render as a broken image.

/** True for a canonical backend path that the browser must route through the BFF. */
function needsBffPrefix(url: string): boolean {
  return url.startsWith('/api/') || url.startsWith('/api?');
}

/**
 * The `<img src>` for a manifest asset: the delivery path rewritten onto the same-origin BFF.
 * Returns `undefined` when there is no URL so callers can branch on the result directly.
 */
export function browserAssetSrc(url: string | null | undefined): string | undefined {
  if (!url) return undefined;
  return needsBffPrefix(url) ? `/bff${url}` : url;
}
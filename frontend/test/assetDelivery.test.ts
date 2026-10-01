import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

// REM-2 corrective, Phase 0.4 / Phase 4 (F07 — SECURITY-08) — browser-side half of the
// same-origin asset delivery fix.
//
// The manifest used to hand the browser a **presigned object-storage URL**, and the browser fetched
// the bytes straight from storage. That had three consequences this file locks down:
//
//   * the internal object layout (``assets/<paper>/v<n>/<assetId>.webp``) and the storage host —
//     including ``AWS_ENDPOINT_URL_S3``, which is MinIO in every local environment — reached the
//     browser, then sat in the devtools network log, the HTTP cache and any referrer;
//   * the fetch happened **outside** every check the service makes, so a decision made when the
//     manifest was built (auth, license gate, asset ownership) was frozen into a string that kept
//     working for the full 600s presign TTL — long after license state or ownership could change;
//   * delivering bytes inline requires the CSP to allowlist the storage host, so the allowlist
//     became a standing hole in the page's image policy.
//
// The fix serves the bytes from the app's own origin (backend delivery endpoint + this BFF), so the
// browser never names the object store. These tests are the regression that fails if any of the
// three creeps back: a storage host in a CSP or an <img src>, a mangled/parsed image body, or a
// non-image response sneaking through the image hop.

vi.mock('server-only', () => ({}));

import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { NextRequest } from 'next/server';
import { GET } from '@/app/bff/[...path]/route';

const REPO_ROOT = join(__dirname, '..', '..');

/** A 1x1 WEBP — the real format U1 writes page crops in. */
const WEBP_BYTES = Buffer.from(
  'UklGRiQAAABXRUJQVlA4IBgAAAAwAQCdASoBAAEADsD+JaQAA3AAAAAA',
  'base64',
);

function assetRequest(path = ['api', 'papers', '2401.00001', 'assets', 'a0']): NextRequest {
  return new NextRequest(`http://localhost/bff/${path.join('/')}?version=1`, {
    method: 'GET',
    headers: { cookie: 'sid=session-secret' },
  });
}

describe('BFF asset image relay (REM-2 F07)', () => {
  beforeEach(() => {
    process.env.DOCSURI_GATEWAY_URL = 'https://gateway.internal.test';
  });

  afterEach(() => {
    delete process.env.DOCSURI_GATEWAY_URL;
    delete process.env.DOCSURI_BFF_ALLOW_MOCK;
    vi.unstubAllGlobals();
  });

  it('serves asset bytes verbatim instead of parsing them as JSON', async () => {
    const fetchMock = vi.fn(
      async () =>
        new Response(new Uint8Array(WEBP_BYTES), {
          status: 200,
          headers: { 'content-type': 'image/webp' },
        }),
    );
    vi.stubGlobal('fetch', fetchMock);

    const res = await GET(assetRequest(), { params: Promise.resolve({
      path: ['api', 'papers', '2401.00001', 'assets', 'a0'],
    }) });

    expect(res.status).toBe(200);
    // The bytes must survive byte-for-byte: JSON.parse on a WEBP body yields null, which is how a
    // naive proxy turns a working image into a broken-image icon.
    const body = Buffer.from(await res.arrayBuffer());
    expect(body.equals(WEBP_BYTES)).toBe(true);
    expect(res.headers.get('content-type')).toBe('image/webp');
  });

  it('forwards the session cookie server-side and never leaks the gateway URL to the browser', async () => {
    let seenUrl = '';
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      seenUrl = String(input);
      return new Response(new Uint8Array(WEBP_BYTES), {
        status: 200,
        headers: { 'content-type': 'image/webp' },
      });
    });
    vi.stubGlobal('fetch', fetchMock);

    const res = await GET(assetRequest(), {
      params: Promise.resolve({ path: ['api', 'papers', '2401.00001', 'assets', 'a0'] }),
    });
    await res.arrayBuffer();

    // The gateway hop carries the httpOnly cookie — the browser sends no token of its own.
    const init = (fetchMock as unknown as MockFn).mock.calls[0]?.[1] as RequestInit | undefined;
    expect(new Headers(init?.headers).get('cookie')).toBe('sid=session-secret');
    // The gateway host is a server-side detail and must not appear in anything the browser sees.
    expect(seenUrl).toContain('gateway.internal.test');
    expect(res.headers.get('location')).toBeNull();
    expect(JSON.stringify([...res.headers.entries()])).not.toContain('gateway.internal.test');
  });

  it('does not follow a redirect out of the same origin', async () => {
    const fetchMock = vi.fn(
      async () =>
        new Response(null, {
          status: 302,
          headers: { location: 'https://s3.ap-northeast-2.amazonaws.com/bkt/k.webp?X-Amz-Signature=leak' },
        }),
    );
    vi.stubGlobal('fetch', fetchMock);

    const res = await GET(assetRequest(), {
      params: Promise.resolve({ path: ['api', 'papers', '2401.00001', 'assets', 'a0'] }),
    });

    // A 3xx would hand the browser the storage URL we just removed — so this hop only ever
    // relays a 200 image and reports anything else as a miss.
    expect(res.status).toBe(404);
    expect(res.headers.get('location')).toBeNull();
  });

  it('refuses to relay a non-image body through the image hop', async () => {
    const fetchMock = vi.fn(
      async () =>
        new Response(JSON.stringify({ secret: 'internal-manifest' }), {
          status: 200,
          headers: { 'content-type': 'application/json' },
        }),
    );
    vi.stubGlobal('fetch', fetchMock);

    const res = await GET(assetRequest(), {
      params: Promise.resolve({ path: ['api', 'papers', '2401.00001', 'assets', 'a0'] }),
    });

    // Fail-closed: an HTML/JSON body served into an <img> context is either a broken image or a
    // content-type-confusion vector, and this hop has no legitimate reason to see one.
    expect(res.status).toBe(404);
    expect(await res.text()).not.toContain('internal-manifest');
  });

  it('relays a 404 miss as a 404 rather than inventing a body', async () => {
    const fetchMock = vi.fn(
      async () => new Response(JSON.stringify({ status: 'not_found' }), { status: 404 }),
    );
    vi.stubGlobal('fetch', fetchMock);

    const res = await GET(assetRequest(), {
      params: Promise.resolve({ path: ['api', 'papers', '2401.00001', 'assets', 'nope'] }),
    });

    expect(res.status).toBe(404);
  });
});

type MockFn = { mock: { calls: unknown[][] } };

describe('F07 browser surface: no object storage host, no object key', () => {
  const viewer = readFileSync(join(REPO_ROOT, 'frontend/components/DocModelViewer.tsx'), 'utf8');

  it('never points an <img> at object storage', () => {
    expect(viewer).not.toMatch(/amazonaws\.com/);
    expect(viewer).not.toMatch(/<img[^>]*src=\{[^}]*asset\.url\}/);
  });

  it('routes asset loads through the same-origin BFF', () => {
    // Every <img src> comes from browserAssetSrc(), which prefixes the canonical delivery path
    // with /bff so the hop carries the httpOnly cookie instead of the page naming the backend.
    expect(viewer).toContain('browserAssetSrc');
    expect(viewer).not.toMatch(/<img[^>]*src=\{asset\??\.url\}/);

    const helper = readFileSync(join(REPO_ROOT, 'frontend/lib/api/assetSrc.ts'), 'utf8');
    expect(helper).toContain('/bff');
  });

  it('keeps the CSP image policy same-origin only', () => {
    const middleware = readFileSync(join(REPO_ROOT, 'frontend/middleware.ts'), 'utf8');
    const directive = middleware
      .split('\n')
      .find((line) => line.includes('img-src'))
      ?.trim();
    expect(directive).toBeDefined();
    expect(directive).not.toContain('amazonaws.com');
    expect(directive).not.toContain('https://');
  });
});
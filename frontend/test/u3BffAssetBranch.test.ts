import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

// U3 secure asset viewing — BFF asset-branch contract conformance (C5, SEC-8/SEC-9).
//
// The relay must refuse redirects explicitly, pass only successful image content,
// preserve the private cache contract with a `private, max-age=60` fallback, relay
// real upstream session Set-Cookie values even on error (and fabricate none on a
// timeout), collapse denied/missing/non-image delivery to an empty no-store 404,
// and answer HEAD without a body under the recorded gateway timeout.

vi.mock('server-only', () => ({}));

import { NextRequest } from 'next/server';
import { GET, HEAD } from '@/app/bff/[...path]/route';

const ASSET_PATH = ['api', 'papers', '2401.00001', 'assets', 'a0'];

/** A 1x1 WEBP. */
const WEBP_BYTES = Buffer.from(
  'UklGRiQAAABXRUJQVlA4IBgAAAAwAQCdASoBAAEADsD+JaQAA3AAAAAA',
  'base64',
);

function assetRequest(method: 'GET' | 'HEAD' = 'GET'): NextRequest {
  return new NextRequest(`http://localhost/bff/${ASSET_PATH.join('/')}?version=1`, {
    method,
    headers: { cookie: 'sid=session-secret' },
  });
}

function ctx() {
  return { params: Promise.resolve({ path: ASSET_PATH }) };
}

type MockFn = { mock: { calls: unknown[][] } };

let fetchMock: ReturnType<typeof vi.fn>;

function stubFetch(handler: (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>): void {
  fetchMock = vi.fn(handler);
  vi.stubGlobal('fetch', fetchMock);
}

function lastFetchInit(): RequestInit | undefined {
  return (fetchMock as unknown as MockFn).mock.calls.at(-1)?.[1] as RequestInit | undefined;
}

describe('BFF asset branch — C5 conformance (u3)', () => {
  beforeEach(() => {
    process.env.DOCSURI_GATEWAY_URL = 'https://gateway.internal.test';
  });

  afterEach(() => {
    delete process.env.DOCSURI_GATEWAY_URL;
    delete process.env.DOCSURI_BFF_ALLOW_MOCK;
    vi.unstubAllGlobals();
  });

  it('refuses redirects explicitly instead of following them by default', async () => {
    stubFetch(async () => new Response(null, {
      status: 302,
      headers: { location: 'https://s3.ap-northeast-2.amazonaws.com/bkt/k.webp?X-Amz-Signature=leak' },
    }));

    const res = await GET(assetRequest(), ctx());

    // The upstream hop must be an explicit refusal, not undici's default follow.
    expect(lastFetchInit()?.redirect).toBe('manual');
    expect(res.status).toBe(404);
    expect(res.headers.get('location')).toBeNull();
    expect(res.headers.get('cache-control')).toBe('no-store');
  });

  it('relays session Set-Cookie from a real upstream error response', async () => {
    stubFetch(async () => new Response(JSON.stringify({ detail: 'forbidden' }), {
      status: 403,
      headers: { 'content-type': 'application/json', 'set-cookie': 'sid=rotated; Path=/; HttpOnly' },
    }));

    const res = await GET(assetRequest(), ctx());

    expect(res.status).toBe(404);
    expect(res.headers.get('set-cookie')).toContain('sid=rotated');
    // The denied upstream body never leaks into the browser-visible response.
    expect(await res.text()).not.toContain('forbidden');
  });

  it('fabricates no cookies when the upstream hop times out', async () => {
    stubFetch(async () => {
      throw new Error('network down');
    });

    const res = await GET(assetRequest(), ctx());

    expect(res.status).toBe(404);
    expect(res.headers.get('set-cookie')).toBeNull();
    expect(res.headers.get('cache-control')).toBe('no-store');
  });

  it('falls back to the contract cache constant when upstream is silent and preserves upstream values', async () => {
    stubFetch(async () => new Response(new Uint8Array(WEBP_BYTES), {
      status: 200,
      headers: { 'content-type': 'image/webp' },
    }));
    const silent = await GET(assetRequest(), ctx());
    expect(silent.status).toBe(200);
    expect(silent.headers.get('cache-control')).toBe('private, max-age=60');
    expect(silent.headers.get('x-content-type-options')).toBe('nosniff');

    stubFetch(async () => new Response(new Uint8Array(WEBP_BYTES), {
      status: 200,
      headers: { 'content-type': 'image/webp', 'cache-control': 'private, max-age=120' },
    }));
    const preserved = await GET(assetRequest(), ctx());
    expect(preserved.headers.get('cache-control')).toBe('private, max-age=120');
  });

  it('answers HEAD with no body and forwards the HEAD method upstream', async () => {
    stubFetch(async () => new Response(null, {
      status: 200,
      headers: { 'content-type': 'image/webp', 'cache-control': 'private, max-age=60' },
    }));

    const res = await HEAD(assetRequest('HEAD'), ctx());

    expect(lastFetchInit()?.method).toBe('HEAD');
    expect(lastFetchInit()?.redirect).toBe('manual');
    expect(res.status).toBe(200);
    expect(res.headers.get('content-type')).toBe('image/webp');
    expect(res.headers.get('x-content-type-options')).toBe('nosniff');
    expect((await res.arrayBuffer()).byteLength).toBe(0);
  });

  it('collapses a missing HEAD asset to the same empty no-store 404', async () => {
    stubFetch(async () => new Response(null, { status: 404 }));

    const res = await HEAD(assetRequest('HEAD'), ctx());

    expect(res.status).toBe(404);
    expect(res.headers.get('cache-control')).toBe('no-store');
    expect((await res.arrayBuffer()).byteLength).toBe(0);
  });

  it('still serves GET bytes verbatim with the explicit refusal in place', async () => {
    stubFetch(async () => new Response(new Uint8Array(WEBP_BYTES), {
      status: 200,
      headers: { 'content-type': 'image/webp' },
    }));

    const res = await GET(assetRequest(), ctx());

    expect(lastFetchInit()?.method).toBe('GET');
    expect(lastFetchInit()?.redirect).toBe('manual');
    expect(lastFetchInit()?.cache).toBe('no-store');
    expect(Buffer.from(await res.arrayBuffer()).equals(WEBP_BYTES)).toBe(true);
  });

  it('refuses non-canonical escaped segments instead of joining them into the upstream URL', async () => {
    stubFetch(async () => new Response(new Uint8Array(WEBP_BYTES), {
      status: 200,
      headers: { 'content-type': 'image/webp' },
    }));

    // Next decodes %2F inside a catch-all entry, so a segment can reach the
    // handler as `a/../../../foo`; an empty or `..` entry would also rewrite the
    // joined URL. Every such path must be refused before any upstream fetch.
    const escapes = [
      ['api', 'papers', 'a/../../../foo', 'assets', 'x'],
      ['api', 'papers', '..', 'assets', 'x'],
      ['api', 'papers', '', 'assets', 'x'],
      ['api', 'papers', 'a\\..\\..', 'assets', 'x'],
      ['api', 'papers', 'p\u00001', 'assets', 'x'],
    ];
    for (const bad of escapes) {
      const res = await GET(new NextRequest(`http://localhost/bff/${bad.join('/')}`, { method: 'GET' }), {
        params: Promise.resolve({ path: bad }),
      });
      expect(res.status).toBe(404);
    }
    // Nothing escaped to the gateway.
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

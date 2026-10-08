import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// The route imports the server-only HttpTransport; neutralize the guard so the
// handler runs under the jsdom test runtime.
vi.mock('server-only', () => ({}));

import { NextRequest } from 'next/server';
import { GET } from '@/app/bff/[...path]/route';

describe('BFF content-job routes', () => {
  beforeEach(() => {
    delete process.env.DOCSURI_GATEWAY_URL;
    delete process.env.DOCSURI_BFF_ALLOW_MOCK;
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it('streams content-job events with cursor and cookie fidelity', async () => {
    process.env.DOCSURI_GATEWAY_URL = 'https://api.example.test';
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      expect(String(input)).toBe(
        'https://api.example.test/api/content-jobs/job-1/events?lastEventId=evt-7',
      );
      const headers = new Headers(init?.headers);
      expect(headers.get('last-event-id')).toBe('evt-7');
      expect(headers.get('cookie')).toBe('session=abc');
      return new Response('id: evt-8\ndata: {"eventId":"evt-8","jobId":"job-1"}\n\n', {
        status: 200,
        headers: {
          'content-type': 'text/event-stream',
          'set-cookie': 'session=abc; Path=/',
        },
      });
    });
    vi.stubGlobal('fetch', fetchMock);

    const req = new NextRequest(
      'http://localhost/bff/api/content-jobs/job-1/events?lastEventId=evt-7',
      { headers: { cookie: 'session=abc', 'last-event-id': 'evt-7' } },
    );
    const res = await GET(req, {
      params: Promise.resolve({ path: ['api', 'content-jobs', 'job-1', 'events'] }),
    });

    expect(res.status).toBe(200);
    expect(res.headers.get('content-type')).toContain('text/event-stream');
    expect(res.headers.get('cache-control')).toBe('no-store');
    expect(res.headers.get('set-cookie')).toContain('session=abc');
    await expect(res.text()).resolves.toContain('evt-8');
  });

  it('fails soft to an empty no-store stream when the gateway is not configured', async () => {
    const req = new NextRequest('http://localhost/bff/api/content-jobs/job-1/events');
    const res = await GET(req, {
      params: Promise.resolve({ path: ['api', 'content-jobs', 'job-1', 'events'] }),
    });

    expect(res.status).toBe(204);
    expect(await res.text()).toBe('');
    expect(res.headers.get('content-type')).toBe('text/event-stream');
    expect(res.headers.get('cache-control')).toBe('no-store');
  });

  it('proxies job JSON with no-store caching and Set-Cookie relay', async () => {
    process.env.DOCSURI_GATEWAY_URL = 'https://api.example.test';
    const fetchMock = vi.fn(async () => {
      return new Response(JSON.stringify({ jobId: 'job-1', state: 'ACCEPTED' }), {
        status: 200,
        headers: {
          'content-type': 'application/json',
          'set-cookie': 'sid=1; Path=/',
        },
      });
    });
    vi.stubGlobal('fetch', fetchMock);

    const req = new NextRequest('http://localhost/bff/api/content-jobs/job-1/state', {
      headers: { cookie: 'session=abc' },
    });
    const res = await GET(req, {
      params: Promise.resolve({ path: ['api', 'content-jobs', 'job-1', 'state'] }),
    });

    expect(res.status).toBe(200);
    expect(res.headers.get('cache-control')).toBe('no-store');
    expect(res.headers.get('set-cookie')).toContain('sid=1');
    await expect(res.json()).resolves.toMatchObject({ state: 'ACCEPTED' });
  });
});

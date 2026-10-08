import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { jobFetch, submitJob } from '@/lib/api/contentJobApi';

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal('fetch', fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('content-job transport boundary', () => {
  it('pins same-origin credentials and no-store on every job fetch, preserving caller headers', async () => {
    fetchMock.mockResolvedValue(new Response('{}', { status: 200 }));

    await jobFetch('/bff/api/content-jobs/job-1/state', {
      method: 'GET',
      headers: { 'x-trace': 't1' },
    });

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/bff/api/content-jobs/job-1/state');
    expect(init.credentials).toBe('same-origin');
    expect(init.cache).toBe('no-store');
    expect(new Headers(init.headers).get('x-trace')).toBe('t1');
  });

  it('never layers retries on a failed job call (exactly one attempt)', async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify({ message: 'down' }), { status: 503 }));

    await expect(submitJob({ taskType: 'summarize', input: {} })).rejects.toMatchObject({
      kind: 'server',
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('maps 429 to rateLimited and keeps a short server message', async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ message: 'too many requests' }), { status: 429 }),
    );
    await expect(submitJob({ taskType: 'summarize', input: {} })).rejects.toMatchObject({
      kind: 'rateLimited',
      message: 'too many requests',
    });
  });

  it('scrubs an over-long server message back to the default copy', async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ message: 'x'.repeat(500) }), { status: 403 }),
    );
    await expect(submitJob({ taskType: 'summarize', input: {} })).rejects.toMatchObject({
      kind: 'forbidden',
      message: '접근 권한이 없습니다.',
    });
  });
});

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { UserFacingError } from '@/lib/api/errors';
import {
  CONTENT_JOB_API_BASE,
  getJobState,
  submitJob,
  subscribeJobEvents,
} from '@/lib/api/contentJobApi';

class FakeEventSource {
  static instances: FakeEventSource[] = [];
  readonly url: string;
  onopen: (() => void) | null = null;
  onmessage: ((event: MessageEvent<string>) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  closed = false;

  constructor(url: string) {
    this.url = url;
    FakeEventSource.instances.push(this);
  }

  close(): void {
    this.closed = true;
  }
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal('fetch', fetchMock);
  FakeEventSource.instances = [];
  vi.stubGlobal('EventSource', FakeEventSource);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('ContentJobApi (BFF-routed)', () => {
  it('submits through /bff with same-origin credentials and no-store caching', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ jobId: 'job-1', state: 'SUBMITTED' }));

    const result = await submitJob({
      taskType: 'summarize',
      input: { paperId: 'paper-1', version: 3 },
      idempotencyKey: 'c'.repeat(64),
    });

    expect(result).toEqual({ jobId: 'job-1', state: 'SUBMITTED' });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`${CONTENT_JOB_API_BASE}/submit`);
    expect(init.method).toBe('POST');
    expect(init.credentials).toBe('same-origin');
    expect(init.cache).toBe('no-store');
    expect(JSON.parse(String(init.body))).toMatchObject({
      taskType: 'summarize',
      idempotencyKey: 'c'.repeat(64),
    });
  });

  it('rejects a submission response without a usable identity', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ state: 'SUBMITTED' }));
    await expect(submitJob({ taskType: 'summarize', input: {} })).rejects.toMatchObject({
      name: 'UserFacingError',
      kind: 'unknown',
    });
  });

  it('normalizes HTTP failures into fail-closed user-facing kinds', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ message: 'nope' }, 401));
    const authError = await submitJob({ taskType: 'summarize', input: {} }).catch(
      (caught: unknown) => caught,
    );
    expect(authError).toBeInstanceOf(UserFacingError);
    expect(authError).toMatchObject({ kind: 'auth' });

    fetchMock.mockResolvedValueOnce(jsonResponse({ message: 'boom' }, 500));
    await expect(getJobState('job-1')).rejects.toMatchObject({ kind: 'server' });

    fetchMock.mockResolvedValueOnce(jsonResponse({ detail: [] }, 422));
    await expect(submitJob({ taskType: 'summarize', input: {} })).rejects.toMatchObject({
      kind: 'unknown',
    });
  });

  it('reads state from the encoded job path and rejects malformed state bodies', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ jobId: 'job-1', seq: 3, state: 'ACCEPTED' }));
    await expect(getJobState('job-1')).resolves.toEqual({ jobId: 'job-1', seq: 3, state: 'ACCEPTED' });
    expect(fetchMock.mock.calls[0]?.[0]).toBe(`${CONTENT_JOB_API_BASE}/job-1/state`);

    fetchMock.mockResolvedValueOnce(jsonResponse({ jobId: 'job-1', seq: 3, state: 'PROCESSING' }));
    await expect(getJobState('job-1')).rejects.toMatchObject({ kind: 'unknown' });
  });

  it('subscribes with the verified cursor and parses only valid frames', () => {
    const received: unknown[] = [];
    const opened = vi.fn();
    const failed = vi.fn();

    const unsubscribe = subscribeJobEvents(
      'job-1',
      { onEvent: (event) => received.push(event), onOpen: opened, onError: failed },
      'evt-7',
    );

    const source = FakeEventSource.instances[0]!;
    expect(source.url).toContain(`${CONTENT_JOB_API_BASE}/job-1/events`);
    expect(source.url).toContain('lastEventId=evt-7');

    source.onopen?.();
    expect(opened).toHaveBeenCalledTimes(1);

    source.onmessage?.({
      data: JSON.stringify({ eventId: 'evt-8', jobId: 'job-1', seq: 4, state: 'RUNNING', timestampUs: 8 }),
    } as MessageEvent<string>);
    expect(received).toHaveLength(1);

    // Malformed frames (bad JSON, invalid envelope) are dropped, never thrown.
    source.onmessage?.({ data: 'not json' } as MessageEvent<string>);
    source.onmessage?.({
      data: JSON.stringify({ jobId: 'job-1', seq: 4, state: 'RUNNING', timestampUs: 8 }),
    } as MessageEvent<string>);
    expect(received).toHaveLength(1);

    source.onerror?.(new Event('error'));
    expect(failed).toHaveBeenCalledTimes(1);

    unsubscribe();
    expect(source.closed).toBe(true);
  });

  it('keeps the function-form subscription compatible', () => {
    const received: unknown[] = [];
    const unsubscribe = subscribeJobEvents('job-2', (event) => received.push(event));
    const source = FakeEventSource.instances[0]!;
    expect(source.url).toContain(`${CONTENT_JOB_API_BASE}/job-2/events`);
    expect(source.url).not.toContain('lastEventId');
    unsubscribe();
    expect(source.closed).toBe(true);
    expect(received).toHaveLength(0);
  });
});

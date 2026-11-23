// U8 plan Step 42, JobLiveStatus (project rules; NFR9.5): the native stream resumes with
// Last-Event-ID on its own reconnect, polling takes over when it fails, an error boundary
// holds a render failure, and the end is announced once.
import React from 'react';
import { act, cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { JobLiveStatus, type EventSourceLike } from '../../src/u8-jobs/job-live-status';
import { POLL_MS, type JobSnapshot } from '../../src/u8-jobs/api';
import { advance, apiError, fakeClient, Fresh } from './helpers';

class FakeSource implements EventSourceLike {
  readyState = 1;
  closed = false;
  private listeners = new Map<string, ((event: Event) => void)[]>();

  constructor(readonly url: string) {}

  addEventListener(type: string, listener: (event: Event) => void) {
    this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener]);
  }

  close() {
    this.closed = true;
    this.readyState = 2;
  }

  emit(type: string, data?: unknown) {
    const event =
      data === undefined
        ? new Event(type)
        : new MessageEvent(type, { data: typeof data === 'string' ? data : JSON.stringify(data) });
    act(() => (this.listeners.get(type) ?? []).forEach((listener) => listener(event)));
  }
}

function snapshot(state: JobSnapshot['state'], seq: number): JobSnapshot {
  return {
    jobId: 'job-1',
    kind: 'research',
    state,
    seq,
    revision: `r${seq}`,
    acceptedAt: '2026-10-23T02:00:00Z',
  };
}

function mount(answer: () => unknown = () => snapshot('running', 1)) {
  const sources: FakeSource[] = [];
  const fake = fakeClient(() => answer());
  render(
    <Fresh>
      <JobLiveStatus
        client={fake.transport}
        jobId="job-1"
        createSource={(url) => {
          const source = new FakeSource(url);
          sources.push(source);
          return source;
        }}
      />
    </Fresh>,
  );
  return { ...fake, sources };
}

const announcer = () => screen.getByTestId('announcer');

/** Step 94: timing tests count reads per path, here the job's snapshot. */
const SNAPSHOT_PATH = '/api/v2/jobs/job-1';
function snapshotGets(get: { mock: { calls: unknown[][] } }): number {
  return get.mock.calls.filter(([path]) => path === SNAPSHOT_PATH).length;
}

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe('the event stream', () => {
  it('opens the job events once and leaves reconnects to the browser (Last-Event-ID)', () => {
    const { sources, get } = mount();
    expect(sources).toHaveLength(1);
    expect(sources[0]!.url).toBe('/api/v2/jobs/job-1/events');
    sources[0]!.emit('snapshot', snapshot('running', 1));
    expect(screen.getByTestId('job-live-state')).toHaveTextContent('진행 중');
    // A transient drop while the source reconnects (readyState CONNECTING) neither
    // opens a second source nor polls: the browser resends Last-Event-ID itself.
    sources[0]!.readyState = 0;
    sources[0]!.emit('error');
    expect(sources).toHaveLength(1);
    expect(screen.queryByTestId('job-live-partial')).toBeNull();
    expect(get).not.toHaveBeenCalled();
  });

  it('ignores malformed frames and closes the stream at the end', () => {
    const { sources } = mount();
    sources[0]!.emit('snapshot', 'not json');
    sources[0]!.emit('snapshot', { jobId: 'job-1' });
    expect(screen.getByTestId('job-live-state')).toHaveTextContent('상태를 확인하고 있습니다');
    sources[0]!.emit('snapshot', snapshot('succeeded', 2));
    expect(sources[0]!.closed).toBe(true);
  });

  it("stops on the server's own error frame", () => {
    const { sources } = mount();
    sources[0]!.emit('error', { code: 'NOT_FOUND' });
    expect(sources[0]!.closed).toBe(true);
    expect(screen.getByTestId('job-live-error')).toHaveTextContent(
      '작업 상태를 확인하지 못했습니다',
    );
  });
});

describe('the polling fallback', () => {
  it('polls every 2 s once the stream has closed, until the job ends', async () => {
    vi.useFakeTimers();
    expect(POLL_MS).toBe(2_000);
    let reads = 0;
    const { sources, get } = mount(() => {
      reads += 1;
      return snapshot(reads >= 3 ? 'failed' : 'running', 2 + reads);
    });
    expect(get).not.toHaveBeenCalled();
    sources[0]!.readyState = 2;
    sources[0]!.emit('error');
    expect(screen.getByTestId('job-live-partial')).toHaveTextContent(
      '실시간 연결이 끊겨 주기적으로 확인합니다',
    );
    // The first poll comes at the close.
    await advance(0);
    expect(snapshotGets(get)).toBe(1);
    expect(get).toHaveBeenLastCalledWith(SNAPSHOT_PATH);
    await advance(1_900);
    expect(snapshotGets(get)).toBe(1);
    await advance(200);
    expect(snapshotGets(get)).toBe(2);
    await advance(2_000);
    expect(snapshotGets(get)).toBe(3);
    expect(screen.getByTestId('job-live-state')).toHaveTextContent('실패');
    await advance(6_000);
    expect(snapshotGets(get)).toBe(3);
    expect(screen.queryByTestId('job-live-partial')).toBeNull();
    expect(announcer()).toHaveAttribute('role', 'status');
    expect(announcer()).toHaveAttribute('aria-live', 'polite');
    expect(announcer().textContent).toBe('작업이 끝났습니다: 실패');
  });

  it('polls when the stream cannot be opened, and shows a failed read', async () => {
    vi.useFakeTimers();
    const running = fakeClient(() => snapshot('running', 1));
    render(
      <Fresh>
        <JobLiveStatus
          client={running.transport}
          jobId="job-1"
          createSource={() => {
            throw new Error('no EventSource');
          }}
        />
      </Fresh>,
    );
    await advance(0);
    expect(snapshotGets(running.get)).toBe(1);
    expect(screen.getByTestId('job-live-state')).toHaveTextContent('진행 중');
    await advance(1_900);
    expect(snapshotGets(running.get)).toBe(1);
    await advance(200);
    expect(snapshotGets(running.get)).toBe(2);
    cleanup();
    vi.useRealTimers();
    // The failed-read case.
    const fake = fakeClient(() => apiError(503, 'UNAVAILABLE'));
    render(
      <Fresh>
        <JobLiveStatus
          client={fake.transport}
          jobId="job-1"
          createSource={() => {
            throw new Error('no EventSource');
          }}
        />
      </Fresh>,
    );
    expect(screen.getByTestId('job-live-partial')).toBeInTheDocument();
    expect(await screen.findByTestId('job-live-error')).toBeInTheDocument();
  });
});

describe('the error boundary', () => {
  it('holds a failure inside the live status and leaves the rest of the page standing', () => {
    vi.spyOn(console, 'error').mockImplementation(() => undefined);
    const fake = fakeClient(() => snapshot('running', 1));
    render(
      <Fresh>
        <JobLiveStatus
          client={fake.transport}
          jobId="job-1"
          createSource={() => ({
            readyState: 1,
            addEventListener: () => {
              throw new Error('broken source');
            },
            close: () => undefined,
          })}
        />
        <p data-testid="outside">outside</p>
      </Fresh>,
    );
    expect(screen.getByTestId('job-live-failed')).toHaveTextContent(
      '작업 상태를 표시하지 못했습니다. 화면을 다시 열어 주세요.',
    );
    expect(screen.queryByTestId('job-live-status')).toBeNull();
    expect(screen.getByTestId('outside')).toBeInTheDocument();
  });
});

describe('the announcements', () => {
  it('announces each change and the end exactly once', () => {
    const { sources } = mount();
    sources[0]!.emit('snapshot', snapshot('accepted', 1));
    expect(announcer().textContent).toBe('작업 상태: 대기 중');
    sources[0]!.emit('snapshot', snapshot('accepted', 2));
    expect(announcer().textContent).toBe('작업 상태: 대기 중');
    sources[0]!.emit('snapshot', snapshot('running', 3));
    expect(announcer().textContent).toBe('작업 상태: 진행 중');
    const span = announcer().firstElementChild;
    sources[0]!.emit('snapshot', snapshot('running', 4));
    expect(announcer().firstElementChild).toBe(span);
    sources[0]!.emit('snapshot', snapshot('succeeded', 5));
    expect(announcer().textContent).toBe('작업이 끝났습니다: 완료');
    const ended = announcer().firstElementChild;
    sources[0]!.emit('snapshot', snapshot('cancelled', 6));
    expect(announcer().firstElementChild).toBe(ended);
    expect(announcer().textContent).toBe('작업이 끝났습니다: 완료');
  });
});

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { SWRConfig } from 'swr';
import { JobStatus } from '@/components/JobStatus';

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

  emit(payload: unknown): void {
    this.onmessage?.({ data: JSON.stringify(payload) } as MessageEvent<string>);
  }
}

function renderStatus(jobId = 'job-1') {
  return render(
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
      <JobStatus jobId={jobId} onComplete={vi.fn()} />
    </SWRConfig>,
  );
}

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  FakeEventSource.instances = [];
  vi.stubGlobal('EventSource', FakeEventSource);
  fetchMock = vi.fn(async () => {
    return new Response(JSON.stringify({ jobId: 'job-1', seq: 5, state: 'ACCEPTED' }), {
      status: 200,
      headers: { 'content-type': 'application/json' },
    });
  });
  vi.stubGlobal('fetch', fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('JobStatus recreated-stream recovery (u2)', () => {
  it('recreates the stream with the verified cursor after an error and returns to live', async () => {
    renderStatus();

    const first = FakeEventSource.instances[0]!;
    first.onopen?.();
    first.emit({ eventId: 'evt-1', jobId: 'job-1', seq: 5, state: 'RUNNING', timestampUs: 1 });
    expect(await screen.findByTestId('job-state-label')).toHaveTextContent('처리중');

    first.onerror?.(new Event('error'));
    expect(await screen.findByText(/2초 간격으로 상태를 확인하고 있습니다/)).toBeInTheDocument();

    // One recreated EventSource, carrying the last accepted id as the cursor.
    await waitFor(() => expect(FakeEventSource.instances.length).toBe(2), { timeout: 3000 });
    const second = FakeEventSource.instances[1]!;
    expect(second.url).toContain('/bff/api/content-jobs/job-1/events');
    expect(second.url).toContain('lastEventId=evt-1');
    // The replaced stream is closed instead of left auto-retrying.
    expect(first.closed).toBe(true);

    second.onopen?.();
    await waitFor(() =>
      expect(screen.queryByText(/2초 간격으로 상태를 확인하고 있습니다/)).not.toBeInTheDocument(),
    );

    second.emit({ eventId: 'evt-2', jobId: 'job-1', seq: 6, state: 'QUEUED', timestampUs: 2 });
    expect(await screen.findByTestId('job-state-label')).toHaveTextContent('대기중');
  });

  it('does not recreate the stream once the job is terminal', async () => {
    renderStatus();

    const first = FakeEventSource.instances[0]!;
    first.onopen?.();
    first.emit({ eventId: 'evt-1', jobId: 'job-1', seq: 5, state: 'COMPLETED', timestampUs: 1 });
    await waitFor(() => expect(first.closed).toBe(true));

    await new Promise((resolve) => setTimeout(resolve, 2200));
    expect(FakeEventSource.instances).toHaveLength(1);
  });

  it('clears the view and cancels work on an access loss (401) without recreating the stream', async () => {
    fetchMock.mockImplementation(async () => {
      return new Response(JSON.stringify({ message: 'nope' }), {
        status: 401,
        headers: { 'content-type': 'application/json' },
      });
    });

    renderStatus();
    const first = FakeEventSource.instances[0]!;
    first.onopen?.();
    first.emit({ eventId: 'evt-1', jobId: 'job-1', seq: 5, state: 'RUNNING', timestampUs: 1 });
    expect(await screen.findByTestId('job-state-label')).toHaveTextContent('처리중');

    first.onerror?.(new Event('error'));
    expect(
      await screen.findByText(/접근 권한을 확인할 수 없어 작업 추적을 중지했습니다/),
    ).toBeInTheDocument();

    // Work is cancelled: the stream closes and no recreation is scheduled.
    await waitFor(() => expect(first.closed).toBe(true));
    await new Promise((resolve) => setTimeout(resolve, 2200));
    expect(FakeEventSource.instances).toHaveLength(1);
  });
});

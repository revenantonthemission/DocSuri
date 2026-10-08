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
  fetchMock = vi.fn();
  vi.stubGlobal('fetch', fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('JobStatus', () => {
  it('renders the live stream state, deduplicates repeats and closes on terminal', async () => {
    renderStatus();
    const source = FakeEventSource.instances[0]!;
    source.onopen?.();

    source.emit({ eventId: 'evt-1', jobId: 'job-1', seq: 5, state: 'RUNNING', timestampUs: 100 });
    expect(await screen.findByTestId('job-state-label')).toHaveTextContent('처리중');

    // Duplicate delivery must not duplicate history rows or announcements.
    source.emit({ eventId: 'evt-1', jobId: 'job-1', seq: 5, state: 'RUNNING', timestampUs: 100 });
    await waitFor(() => {
      expect(screen.getAllByText(/RUNNING @/)).toHaveLength(1);
    });

    // Older-than-watermark history is ignored.
    source.emit({ eventId: 'evt-0', jobId: 'job-1', seq: 3, state: 'QUEUED', timestampUs: 50 });
    expect(screen.queryByText(/QUEUED @/)).not.toBeInTheDocument();

    source.emit({
      eventId: 'evt-2',
      jobId: 'job-1',
      seq: 6,
      state: 'COMPLETED',
      timestampUs: 200,
      payload: { assetId: 'asset-1' },
    });
    expect(await screen.findByTestId('job-state-label')).toHaveTextContent('완료');
    expect(screen.getByText('asset-1')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '계속하기' })).toBeInTheDocument();

    // Terminal cleanup closes the stream and never polls.
    await waitFor(() => expect(source.closed).toBe(true));
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('switches to the fixed two-second SWR fallback when the stream fails', async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ jobId: 'job-1', seq: 1, state: 'ACCEPTED' }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }),
    );

    renderStatus();
    const source = FakeEventSource.instances[0]!;
    source.onopen?.();
    expect(fetchMock).not.toHaveBeenCalled();

    source.onerror?.(new Event('error'));

    expect(await screen.findByTestId('job-state-label')).toHaveTextContent('대기중');
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(String(fetchMock.mock.calls[0]?.[0])).toBe('/bff/api/content-jobs/job-1/state');
    expect(screen.getByText(/2초 간격으로 상태를 확인하고 있습니다/)).toBeInTheDocument();
  });

  it('never claims a stream state before one arrives and keeps a live region busy', () => {
    renderStatus();
    const busyRegion = screen.getByRole('status');
    expect(busyRegion).toHaveAttribute('aria-busy', 'true');
    expect(screen.getByText('작업 상태 로딩 중...')).toBeInTheDocument();
  });
});

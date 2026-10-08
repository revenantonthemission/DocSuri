import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { SWRConfig } from 'swr';
import { JobStatus } from '@/components/JobStatus';
import { SummaryModal } from '@/components/SummaryModal';

// Interaction-matrix slice: one polite live region with honest busy state,
// deduplicated announcements, and conditional focus continuity at the dialog.

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

function envelopeResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'content-type': 'application/json' },
  });
}

function translationEnvelope() {
  return {
    resultRef: 'opaque-1',
    preparedResult: {
      schemaVersion: 1,
      jobId: 'job-2',
      taskType: 'translate',
      preparedAt: '2026-10-03T00:00:00Z',
      expiresAt: '2026-10-03T01:00:00Z',
      content: {
        status: 'ok',
        task: 'translate',
        translation: {
          docModel: {
            meta: {
              paperId: 'paper-1',
              version: 1,
              title: '번역 결과 제목',
              provenance: {
                sourceTier: 'native_html',
                parserVersion: 'docmodel-parser@4',
                schemaVersion: '1',
                generatedAt: '2026-10-03T00:00:00Z',
              },
            },
            fullText: '번역된 본문입니다',
            sections: [],
          },
          keptTerms: [],
        },
      },
    },
  };
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

describe('interaction matrix (u2)', () => {
  it('keeps exactly one polite live region with an honest busy state', async () => {
    renderStatus();
    const source = FakeEventSource.instances[0]!;
    source.onopen?.();
    source.emit({ eventId: 'e1', jobId: 'job-1', seq: 5, state: 'RUNNING', timestampUs: 1 });

    expect(await screen.findByTestId('job-state-label')).toHaveTextContent('처리중');
    const regions = screen.getAllByRole('status');
    expect(regions).toHaveLength(1);
    expect(regions[0]).toHaveAttribute('aria-live', 'polite');
    expect(regions[0]).toHaveAttribute('aria-busy', 'true');
    expect(regions[0]?.textContent).toBe('처리중');
  });

  it('announces only state changes, not repeated frames', async () => {
    renderStatus();
    const source = FakeEventSource.instances[0]!;
    source.onopen?.();
    source.emit({ eventId: 'e1', jobId: 'job-1', seq: 5, state: 'RUNNING', timestampUs: 1 });
    await waitFor(() => expect(screen.getByRole('status').textContent).toBe('처리중'));

    // A same-state frame keeps the announcement unchanged.
    source.emit({ eventId: 'e2', jobId: 'job-1', seq: 6, state: 'RUNNING', timestampUs: 2 });
    expect(screen.getByRole('status').textContent).toBe('처리중');

    // A state change updates it once.
    source.emit({ eventId: 'e3', jobId: 'job-1', seq: 7, state: 'QUEUED', timestampUs: 3 });
    await waitFor(() => expect(screen.getByRole('status').textContent).toBe('대기중'));
  });

  it('moves initial focus into the result dialog when it opens', async () => {
    fetchMock.mockResolvedValue(envelopeResponse(translationEnvelope()));

    render(
      <SummaryModal
        paperId="paper-1"
        jobId="job-2"
        view="abstractTrans"
        onClose={vi.fn()}
        onAnchor={vi.fn()}
      />,
    );

    expect(await screen.findByTestId('translation-view')).toBeInTheDocument();
    expect(document.activeElement).toBe(screen.getByTestId('summary-modal'));
  });
});

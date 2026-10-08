import { webcrypto } from 'node:crypto';
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { PaperDetailIsland } from '@/components/PaperDetailIsland';

vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock('@/lib/usePaperMeta', () => ({
  usePaperMeta: () => ({
    status: 'done',
    meta: {
      title: '논문 제목',
      authors: ['저자'],
      year: 2024,
      abstract: '초록 내용',
      arxivUrl: 'https://arxiv.org/abs/2401.00001',
      sourceName: 'arXiv',
      sourceUrl: 'https://arxiv.org/abs/2401.00001',
    },
  }),
}));
vi.mock('@/components/session/SessionContext', () => ({
  useSession: () => ({
    status: 'authenticated',
    user: { userId: 'user-1', expiresAt: '2026-12-31T00:00:00Z' },
    signingOut: false,
    refresh: async () => {},
    signOut: async () => {},
  }),
}));

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

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

function summaryEnvelope() {
  return {
    resultRef: 'opaque-summary-1',
    preparedResult: {
      schemaVersion: 1,
      jobId: 'job-1',
      taskType: 'summarize',
      preparedAt: '2026-10-05T00:00:00Z',
      expiresAt: '2026-10-05T01:00:00Z',
      content: {
        status: 'ok',
        task: 'summary',
        summary: {
          tldr: '한 문장 요약입니다',
          contributions: ['첫 번째 기여'],
          method: '방법 설명',
          results: '결과 설명',
          limitations: '한계 설명',
          reproducibility: { code: '코드 공개', data: '데이터 공개' },
          anchors: [],
        },
      },
    },
  };
}

beforeAll(() => {
  if (!globalThis.crypto?.subtle) {
    Object.defineProperty(globalThis, 'crypto', { value: webcrypto, configurable: true });
  }
});

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  FakeEventSource.instances = [];
  vi.stubGlobal('EventSource', FakeEventSource);
  fetchMock = vi.fn();
  vi.stubGlobal('fetch', fetchMock);
  window.localStorage.clear();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('PaperDetailIsland job journey', () => {
  it('runs action → explicit submit → live tracking → query-only result with zero work beforehand', async () => {
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith('/submit')) return jsonResponse({ jobId: 'job-1', state: 'SUBMITTED' });
      if (url.endsWith('/result')) return jsonResponse(summaryEnvelope());
      throw new Error(`unexpected fetch: ${url}`);
    });

    render(<PaperDetailIsland paperId="paper-1" version={1} />);

    // Opening the action shows the submission form — still no request.
    expect(fetchMock).not.toHaveBeenCalled();
    fireEvent.click(screen.getByTestId('open-summary'));
    const start = await screen.findByRole('button', { name: '요약 시작' });
    expect(fetchMock).not.toHaveBeenCalled();

    // Only the explicit submit posts; the identity returned mounts tracking.
    fireEvent.click(start);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const [submitUrl, submitInit] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(submitUrl).toBe('/bff/api/content-jobs/submit');
    expect(JSON.parse(String(submitInit.body))).toMatchObject({ taskType: 'summarize' });
    const source = FakeEventSource.instances[0]!;
    expect(source.url).toContain('/bff/api/content-jobs/job-1/events');

    // Live progress, then the terminal state hands off to the result read.
    source.onopen?.();
    source.emit({ eventId: 'evt-1', jobId: 'job-1', seq: 1, state: 'RUNNING', timestampUs: 1 });
    expect(await screen.findByTestId('job-state-label')).toHaveTextContent('처리중');

    source.emit({ eventId: 'evt-2', jobId: 'job-1', seq: 2, state: 'COMPLETED', timestampUs: 2 });
    fireEvent.click(await screen.findByRole('button', { name: '계속하기' }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(String(fetchMock.mock.calls[1]?.[0])).toBe('/bff/api/content-jobs/job-1/result');
    expect(await screen.findByTestId('summary-view')).toBeInTheDocument();
    expect(screen.getByText('한 문장 요약입니다')).toBeInTheDocument();
  });
});

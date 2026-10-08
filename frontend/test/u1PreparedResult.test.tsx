import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { SummaryModal } from '@/components/SummaryModal';

// The prepared-result read path: every controlled availability state is its own
// surface, and retry is a re-READ of the same immutable payload — never a
// generation/enqueue call.

function envelopeResponse(envelope: unknown, status = 200): Response {
  return new Response(JSON.stringify(envelope), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

function validSummaryEnvelope() {
  return {
    resultRef: 'opaque-1',
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
          tldr: '요약',
          contributions: ['기여'],
          method: '방법',
          results: '결과',
          limitations: '한계',
          reproducibility: { code: '코드', data: '데이터' },
          anchors: [],
        },
      },
    },
  };
}

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal('fetch', fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function renderResult(jobId = 'job-1') {
  return render(
    <SummaryModal paperId="paper-1" jobId={jobId} view="summary" onClose={vi.fn()} onAnchor={vi.fn()} />,
  );
}

describe('prepared result read states', () => {
  it('surfaces not-ready (409) as a retryable state and retry re-reads the same route', async () => {
    fetchMock.mockResolvedValueOnce(envelopeResponse({ status: 'not_found' }, 409));
    fetchMock.mockResolvedValueOnce(envelopeResponse(validSummaryEnvelope()));

    renderResult();
    expect(await screen.findByTestId('state-view-degraded')).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('state-view-retry'));
    expect(await screen.findByTestId('summary-view')).toBeInTheDocument();

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(String(fetchMock.mock.calls[1]?.[0])).toBe('/bff/api/content-jobs/job-1/result');
  });

  it('reports an expired result (410) without a retry affordance', async () => {
    fetchMock.mockResolvedValue(envelopeResponse({ code: 'result_expired' }, 410));
    renderResult();

    expect(await screen.findByTestId('state-view-error')).toBeInTheDocument();
    expect(screen.getByText(/보관 기간/)).toBeInTheDocument();
    expect(screen.queryByTestId('state-view-retry')).not.toBeInTheDocument();
  });

  it('reports an unsupported/unavailable identity (422) as a controlled error', async () => {
    fetchMock.mockResolvedValue(envelopeResponse({ code: 'result_unavailable' }, 422));
    renderResult();

    expect(await screen.findByTestId('state-view-error')).toBeInTheDocument();
    expect(screen.getByText('이 결과를 표시할 수 없습니다.')).toBeInTheDocument();
  });

  it('reports a transient store failure (503) as retryable', async () => {
    fetchMock.mockResolvedValue(envelopeResponse({ status: 'unavailable' }, 503));
    renderResult();

    expect(await screen.findByTestId('state-view-error')).toBeInTheDocument();
    expect(screen.getByTestId('state-view-retry')).toBeInTheDocument();
  });

  it('fails closed on a malformed envelope instead of rendering partial content', async () => {
    fetchMock.mockResolvedValue(
      envelopeResponse({
        resultRef: 'opaque-1',
        preparedResult: { schemaVersion: 1, jobId: 'job-1', taskType: 'summarize', content: {} },
      }),
    );
    renderResult();

    expect(await screen.findByTestId('state-view-error')).toBeInTheDocument();
    expect(screen.getByText('이 결과를 표시할 수 없습니다.')).toBeInTheDocument();
    expect(screen.queryByTestId('summary-view')).not.toBeInTheDocument();
  });

  it('refuses an envelope for a different job identity', async () => {
    const foreign = validSummaryEnvelope();
    foreign.preparedResult.jobId = 'job-OTHER';
    fetchMock.mockResolvedValue(envelopeResponse(foreign));
    renderResult('job-1');

    expect(await screen.findByTestId('state-view-error')).toBeInTheDocument();
    expect(screen.queryByTestId('summary-view')).not.toBeInTheDocument();
  });

  it('keeps exact string fidelity — content renders as text, never markup', async () => {
    const envelope = validSummaryEnvelope();
    envelope.preparedResult.content.summary.tldr = '<b>주입</b> 시도 & 유니코드 ✓';
    fetchMock.mockResolvedValue(envelopeResponse(envelope));
    renderResult();

    const view = await screen.findByTestId('summary-view');
    expect(view.textContent).toContain('<b>주입</b> 시도 & 유니코드 ✓');
    expect(view.querySelector('b')).toBeNull();
  });
});

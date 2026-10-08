import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { SummaryModal } from '@/components/SummaryModal';

// Translation branch of the query-only result path: every controlled read
// state renders for translate, retry re-reads, and nothing generates.

function envelopeResponse(envelope: unknown, status = 200): Response {
  return new Response(JSON.stringify(envelope), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

function translationEnvelope() {
  return {
    resultRef: 'opaque-translation-1',
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
  fetchMock = vi.fn();
  vi.stubGlobal('fetch', fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function renderTranslateResult(jobId = 'job-2') {
  return render(
    <SummaryModal
      paperId="paper-1"
      jobId={jobId}
      view="abstractTrans"
      onClose={vi.fn()}
      onAnchor={vi.fn()}
    />,
  );
}

describe('translation prepared-result read states (u2)', () => {
  it('reads the exact prepared translation and initiates nothing', async () => {
    fetchMock.mockResolvedValue(envelopeResponse(translationEnvelope()));

    renderTranslateResult();

    expect(await screen.findByTestId('translation-view')).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit | undefined];
    expect(String(url)).toBe('/bff/api/content-jobs/job-2/result');
    expect(init?.method ?? 'GET').toBe('GET');
  });

  it('surfaces not-ready (409) as retryable and the retry re-reads the same route', async () => {
    fetchMock.mockResolvedValueOnce(envelopeResponse({ code: 'result_not_ready' }, 409));
    fetchMock.mockResolvedValueOnce(envelopeResponse(translationEnvelope()));

    renderTranslateResult();
    expect(await screen.findByTestId('state-view-degraded')).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('state-view-retry'));
    expect(await screen.findByTestId('translation-view')).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(String(fetchMock.mock.calls[1]?.[0])).toBe('/bff/api/content-jobs/job-2/result');
  });

  it('reports an expired translation result (410) without a retry affordance', async () => {
    fetchMock.mockResolvedValue(envelopeResponse({ code: 'result_expired' }, 410));
    renderTranslateResult();

    expect(await screen.findByTestId('state-view-error')).toBeInTheDocument();
    expect(screen.queryByTestId('state-view-retry')).not.toBeInTheDocument();
  });

  it('reports an unsupported translation identity (422) as a controlled error', async () => {
    fetchMock.mockResolvedValue(envelopeResponse({ code: 'result_unavailable' }, 422));
    renderTranslateResult();

    expect(await screen.findByTestId('state-view-error')).toBeInTheDocument();
    expect(screen.getByText('이 결과를 표시할 수 없습니다.')).toBeInTheDocument();
  });

  it('reports a transient failure (503) as retryable', async () => {
    fetchMock.mockResolvedValue(envelopeResponse({ status: 'unavailable' }, 503));
    renderTranslateResult();

    expect(await screen.findByTestId('state-view-error')).toBeInTheDocument();
    expect(screen.getByTestId('state-view-retry')).toBeInTheDocument();
  });

  it('fails closed on a malformed translation envelope instead of rendering partial content', async () => {
    const malformed = translationEnvelope();
    // The bare document must be present; a wrapper or missing docModel is not content.
    (malformed.preparedResult.content.translation as Record<string, unknown>).docModel = undefined;
    fetchMock.mockResolvedValue(envelopeResponse(malformed));
    renderTranslateResult();

    expect(await screen.findByTestId('state-view-error')).toBeInTheDocument();
    expect(screen.getByText('이 결과를 표시할 수 없습니다.')).toBeInTheDocument();
    expect(screen.queryByTestId('translation-view')).not.toBeInTheDocument();
  });

  it('refuses an envelope for a different job identity', async () => {
    const foreign = translationEnvelope();
    foreign.preparedResult.jobId = 'job-OTHER';
    fetchMock.mockResolvedValue(envelopeResponse(foreign));
    renderTranslateResult('job-2');

    expect(await screen.findByTestId('state-view-error')).toBeInTheDocument();
    expect(screen.queryByTestId('translation-view')).not.toBeInTheDocument();
  });
});

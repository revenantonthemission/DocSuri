import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { SummaryModal } from '@/components/SummaryModal';

// SummaryModal is the QUERY-ONLY completed-result surface: it reads the exact
// prepared payload for a completed job and never initiates work. These tests
// drive that read seam directly (stubbed fetch), not the removed request flow.

function envelopeResponse(envelope: unknown, status = 200): Response {
  return new Response(JSON.stringify(envelope), {
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
      submittedLevel: 'expert',
      preparedAt: '2026-10-05T00:00:00Z',
      expiresAt: '2026-10-05T01:00:00Z',
      content: {
        status: 'ok',
        task: 'summary',
        meta: {},
        cached: false,
        summary: {
          tldr: '한 문장 요약입니다',
          contributions: ['첫 번째 기여'],
          method: '방법 설명',
          results: '결과 설명',
          limitations: '한계 설명',
          reproducibility: { code: '코드 공개', data: '데이터 공개' },
          anchors: [{ field: 'method', target: 'section', span: '§2', label: '방법' }],
        },
      },
    },
  };
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
              title: '번역 제목',
              provenance: {
                sourceTier: 'native_html',
                parserVersion: 'docmodel-parser@4',
                schemaVersion: '1',
                generatedAt: '2026-10-03T00:00:00Z',
              },
            },
            fullText: '전체 번역 본문',
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

describe('SummaryModal (query-only result)', () => {
  it('reads the exact prepared summary for the completed job and initiates nothing', async () => {
    fetchMock.mockResolvedValue(envelopeResponse(summaryEnvelope()));

    render(
      <SummaryModal paperId="paper-1" jobId="job-1" view="summary" onClose={vi.fn()} onAnchor={vi.fn()} />,
    );

    expect(await screen.findByTestId('summary-view')).toBeInTheDocument();
    expect(screen.getByText('한 문장 요약입니다')).toBeInTheDocument();

    // Exactly one call, a GET of the result route — no generation POST.
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit | undefined];
    expect(String(url)).toBe('/bff/api/content-jobs/job-1/result');
    expect(init?.method ?? 'GET').toBe('GET');
  });

  it('renders the translation branch through the existing translation view', async () => {
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
  });

  it('closes on Escape and hands an anchor to the parent without re-requesting work', async () => {
    fetchMock.mockResolvedValue(envelopeResponse(summaryEnvelope()));
    const onClose = vi.fn();
    const onAnchor = vi.fn();

    render(
      <SummaryModal paperId="paper-1" jobId="job-1" view="summary" onClose={onClose} onAnchor={onAnchor} />,
    );

    await screen.findByTestId('summary-view');
    fireEvent.click(screen.getByRole('button', { name: /출처: 방법/ }));
    expect(onAnchor).toHaveBeenCalledWith(
      expect.objectContaining({ field: 'method', label: '방법' }),
    );
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledTimes(1);

    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(2);
  });
});

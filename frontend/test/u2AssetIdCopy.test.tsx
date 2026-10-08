import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { SummaryModal } from '@/components/SummaryModal';

function envelopeWithAsset(assetId?: string) {
  const prepared: Record<string, unknown> = {
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
  };
  if (assetId !== undefined) prepared.assetId = assetId;
  return { resultRef: 'opaque-1', preparedResult: prepared };
}

function envelopeResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'content-type': 'application/json' },
  });
}

let fetchMock: ReturnType<typeof vi.fn>;
let writeText: ReturnType<typeof vi.fn>;
let originalClipboard: PropertyDescriptor | undefined;

beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal('fetch', fetchMock);
  writeText = vi.fn(async () => {});
  originalClipboard = Object.getOwnPropertyDescriptor(navigator, 'clipboard');
  Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } });
});

afterEach(() => {
  vi.unstubAllGlobals();
  if (originalClipboard) {
    Object.defineProperty(navigator, 'clipboard', originalClipboard);
  } else {
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: undefined });
  }
});

function renderResult() {
  return render(
    <SummaryModal paperId="paper-1" jobId="job-2" view="abstractTrans" onClose={vi.fn()} onAnchor={vi.fn()} />,
  );
}

describe('authorized asset-ID copy (u2)', () => {
  it('copies the exact supplied identifier and confirms politely', async () => {
    fetchMock.mockResolvedValue(envelopeResponse(envelopeWithAsset('asset-9')));
    renderResult();

    const button = await screen.findByTestId('copy-asset-id');
    expect(button.tagName).toBe('BUTTON');
    expect(button).toHaveAttribute('type', 'button');
    fireEvent.click(button);

    await waitFor(() => expect(writeText).toHaveBeenCalledWith('asset-9'));
    expect(await screen.findByText('복사됨')).toBeInTheDocument();
  });

  it('renders no copy control when no asset id was supplied', async () => {
    fetchMock.mockResolvedValue(envelopeResponse(envelopeWithAsset()));
    renderResult();

    expect(await screen.findByTestId('translation-view')).toBeInTheDocument();
    expect(screen.queryByTestId('copy-asset-id')).not.toBeInTheDocument();
  });

  it('degrades quietly when the clipboard denies the copy', async () => {
    writeText.mockRejectedValueOnce(new DOMException('denied', 'NotAllowedError'));
    fetchMock.mockResolvedValue(envelopeResponse(envelopeWithAsset('asset-9')));
    renderResult();

    fireEvent.click(await screen.findByTestId('copy-asset-id'));
    await waitFor(() => expect(writeText).toHaveBeenCalledTimes(1));
    expect(screen.queryByText('복사됨')).not.toBeInTheDocument();
  });
});

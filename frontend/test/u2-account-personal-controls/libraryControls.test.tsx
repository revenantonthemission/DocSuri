import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { LibraryControls } from '../../src/library-controls';
import { ApiError, Transport } from '../../src/api';

const policy = { policyId: 'u2-synthetic-v1', revision: '1' };
const paper = { paperId: 'p', versionId: 'v', eligibilityRevision: 'e' };
const query = {
  query: 'attention',
  modeId: 'lexical',
  orderId: 'relevance',
  filters: [],
  vocabularyRevision: 'v1',
  policyRef: policy,
};
const saved = {
  savedPaperId: 'p',
  revision: 'saved1',
  savedTitle: '원래 제목',
  savedPaper: paper,
  resolvedPaper: paper,
  sourceDisposition: 'available',
};
const page = (items: unknown[] = [], extra = {}) => ({
  items,
  page: { snapshotRevision: 'snapshot' },
  ...extra,
});
const failed = (code = 'DEPENDENCY_UNAVAILABLE') =>
  new ApiError(503, { code, messageKey: 'request.error', requestId: 'req-1', retryable: true });

function setup(
  read = vi.fn().mockResolvedValue(page([saved])),
  post = vi.fn().mockResolvedValue({}),
) {
  const client = { read, post, generation: 1 };
  const open = vi.fn();
  const run = vi.fn();
  const view = render(
    <LibraryControls
      client={client as unknown as Transport}
      policy={policy}
      onOpenPaper={open}
      onRunQuery={run}
    />,
  );
  return { client, read, post, open, run, ...view };
}

describe('U2 Library controls', () => {
  it('opens the resolved saved paper only after an explicit action', async () => {
    const { open, post } = setup();
    expect(await screen.findByText('원래 제목')).toBeVisible();
    expect(open).not.toHaveBeenCalled();
    expect(post).not.toHaveBeenCalled();
    fireEvent.click(screen.getByTestId('library-open-paper'));
    expect(open).toHaveBeenCalledWith(paper);
  });

  it('preserves a withdrawn reference without offering unavailable content', async () => {
    const { open } = setup(
      vi
        .fn()
        .mockResolvedValue(
          page([{ ...saved, resolvedPaper: undefined, sourceDisposition: 'withdrawn' }]),
        ),
    );
    expect(await screen.findByText('원래 제목')).toBeVisible();
    expect(screen.getByText(/저장한 참조는 유지됩니다/)).toBeVisible();
    expect(screen.queryByTestId('library-open-paper')).toBeNull();
    expect(open).not.toHaveBeenCalled();
  });

  it('shows failed reads separately from an empty list and can refresh', async () => {
    const read = vi.fn().mockRejectedValueOnce(failed()).mockResolvedValueOnce(page());
    setup(read);
    expect(await screen.findByRole('alert')).toBeVisible();
    expect(screen.queryByTestId('library-empty')).toBeNull();
    fireEvent.click(screen.getByTestId('library-refresh'));
    expect(await screen.findByTestId('library-empty')).toBeVisible();
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('does not delete until confirmation and preserves the observed revision', async () => {
    const { post } = setup();
    fireEvent.click(await screen.findByTestId('library-remove'));
    expect(post).not.toHaveBeenCalled();
    expect(screen.getByTestId('library-confirm')).toHaveFocus();
    fireEvent.click(screen.getByTestId('library-confirm'));
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith(
        '/api/v2/c03/library-remove-saved-paper',
        { savedPaperId: 'p', expectedRevision: 'saved1' },
        expect.any(String),
      ),
    );
    expect(await screen.findByText('요청한 변경이 저장되었습니다.')).toBeVisible();
  });

  it('reconciles an unknown deletion using the original key and intent', async () => {
    const post = vi.fn().mockRejectedValueOnce(failed('UNKNOWN_OUTCOME')).mockResolvedValueOnce({});
    setup(undefined, post);
    fireEvent.click(await screen.findByTestId('library-remove'));
    fireEvent.click(screen.getByTestId('library-confirm'));
    expect(await screen.findByRole('alert')).toBeVisible();
    fireEvent.click(screen.getByTestId('library-confirm'));
    await waitFor(() => expect(post).toHaveBeenCalledTimes(2));
    expect(post.mock.calls[0]).toEqual(post.mock.calls[1]);
  });

  it('cancels a destructive action without a write', async () => {
    const { post } = setup();
    fireEvent.click(await screen.findByTestId('library-remove'));
    fireEvent.click(screen.getByTestId('library-cancel'));
    expect(screen.queryByTestId('library-confirmation')).toBeNull();
    expect(post).not.toHaveBeenCalled();
  });

  it('previews saved query context without executing it', async () => {
    const read = vi
      .fn()
      .mockResolvedValueOnce(page())
      .mockResolvedValue(page([{ savedSearchId: 'q1', revision: 'qrev', queryContext: query }]));
    const { run, post } = setup(read);
    await screen.findByTestId('library-empty');
    fireEvent.click(screen.getByTestId('library-view-queries'));
    fireEvent.click(await screen.findByTestId('library-preview-query'));
    expect(screen.getByTestId('library-query-preview')).toHaveTextContent('attention');
    expect(run).not.toHaveBeenCalled();
    expect(post).not.toHaveBeenCalled();
    fireEvent.click(screen.getByTestId('library-rerun-query'));
    expect(run).toHaveBeenCalledWith(query);
    fireEvent.click(screen.getByText('조건 닫기'));
    expect(screen.queryByTestId('library-query-preview')).toBeNull();
  });

  it('deletes a saved query by its own revision', async () => {
    const read = vi
      .fn()
      .mockResolvedValueOnce(page())
      .mockResolvedValue(
        page([{ savedSearchId: 'q1', revision: 'qrev', label: '조건', queryContext: query }]),
      );
    const { post } = setup(read);
    await screen.findByTestId('library-empty');
    fireEvent.click(screen.getByTestId('library-view-queries'));
    fireEvent.click(await screen.findByTestId('library-remove'));
    fireEvent.click(screen.getByTestId('library-confirm'));
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith(
        '/api/v2/c03/library-remove-saved-search',
        { savedSearchId: 'q1', expectedRevision: 'qrev' },
        expect.any(String),
      ),
    );
  });

  it('clears history with its returned boundary and explicitly preserves saves', async () => {
    const read = vi
      .fn()
      .mockResolvedValueOnce(page())
      .mockResolvedValue(page([], { clearBoundary: 'clear-7' }));
    const { post } = setup(read);
    await screen.findByTestId('library-empty');
    fireEvent.click(screen.getByTestId('library-view-history'));
    fireEvent.click(await screen.findByTestId('library-clear-history'));
    expect(screen.getByTestId('library-confirmation')).toHaveTextContent(
      '저장한 논문과 검색은 유지됩니다',
    );
    fireEvent.click(screen.getByTestId('library-confirm'));
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith(
        '/api/v2/c03/library-clear-history',
        { expectedRevision: 'clear-7', policyRef: policy },
        expect.any(String),
      ),
    );
  });

  it('appends a bounded page using the server cursor', async () => {
    const read = vi
      .fn()
      .mockResolvedValueOnce(
        page([saved], { page: { snapshotRevision: 's', nextCursor: 'opaque' } }),
      )
      .mockResolvedValueOnce(page([{ ...saved, savedPaperId: 'p2', savedTitle: '두 번째 논문' }]));
    setup(read);
    fireEvent.click(await screen.findByTestId('library-next-page'));
    expect(await screen.findByText('두 번째 논문')).toBeVisible();
    expect(screen.getByText('원래 제목')).toBeVisible();
    expect(read).toHaveBeenLastCalledWith('/api/v2/c03/library-list-saved-papers', {
      page: { limit: 20, cursor: 'opaque' },
    });
  });

  it('discards a late response from a replaced owner generation', async () => {
    let resolve!: (value: unknown) => void;
    const read = vi.fn(
      () =>
        new Promise((r) => {
          resolve = r;
        }),
    );
    const { client } = setup(read);
    client.generation++;
    await act(async () => {
      resolve(page([saved]));
    });
    expect(screen.queryByText('원래 제목')).toBeNull();
  });

  it('shows recent paper activity and current source restriction', async () => {
    const read = vi
      .fn()
      .mockResolvedValueOnce(page())
      .mockResolvedValue(
        page([{ paper, lastActivityAt: '2026-10-14T00:00:00Z', sourceDisposition: 'unavailable' }]),
      );
    const { open } = setup(read);
    await screen.findByTestId('library-empty');
    fireEvent.click(screen.getByTestId('library-view-recent'));
    expect(await screen.findByTestId('library-open-paper')).toBeDisabled();
    expect(open).not.toHaveBeenCalled();
  });
});

/** U3 discovery/results states: rendering, degradation, expiry, pagination. */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { SearchSection } from '../../src/u3-corpus/search-reading';
import { ContractDouble, apiError, searchResponse } from './helpers';

function build(handler = () => searchResponse()) {
  const client = new ContractDouble().on('/api/v2/c05/search', handler);
  render(<SearchSection client={client.asTransport()} onOpen={() => undefined} />);
  return client;
}

describe('U3 discovery surface', () => {
  it('renders snapshot-bound results with availability badges', async () => {
    const client = build(() =>
      searchResponse({
        outcome: 'degraded',
        effectiveModeId: 'lexical',
        limitations: ['의미 검색을 사용할 수 없어 어휘 검색으로 대체했습니다.'],
      }),
    );
    await userEvent.type(screen.getByTestId('search-query'), 'attention');
    await userEvent.click(screen.getByTestId('search-submit'));
    await waitFor(() => expect(screen.getByTestId('result-row')).toBeInTheDocument());
    expect(screen.getByTestId('result-availability')).toHaveTextContent('readable');
    expect(screen.getByTestId('snapshot-notice')).toHaveTextContent('의미 검색');
    expect(screen.getByTestId('snapshot-revision')).toBeInTheDocument();
    expect(client.calls[0].body).toMatchObject({
      query: { modeId: 'lexical', vocabularyRevision: 'u3-paper-options-1' },
    });
  });

  it('distinguishes an empty result from a retrieval failure', async () => {
    build(() => searchResponse({ hits: [] }));
    await userEvent.type(screen.getByTestId('search-query'), 'nothing');
    await userEvent.click(screen.getByTestId('search-submit'));
    await waitFor(() => expect(screen.getByTestId('search-status')).toHaveTextContent('검색 결과가 없어요'));
  });

  it('shows an explicit error state when retrieval fails', async () => {
    build(() => {
      throw apiError('DEPENDENCY_UNAVAILABLE', 503);
    });
    await userEvent.type(screen.getByTestId('search-query'), 'attention');
    await userEvent.click(screen.getByTestId('search-submit'));
    await waitFor(() =>
      expect(screen.getByTestId('search-status')).toHaveTextContent('검색을 완료하지 못했어요'),
    );
    expect(screen.getByTestId('status-line')).toHaveTextContent('일시적으로 사용할 수 없어요');
  });

  it('keeps previous results when invalid input is submitted', async () => {
    const client = build();
    await userEvent.type(screen.getByTestId('search-query'), 'attention');
    await userEvent.click(screen.getByTestId('search-submit'));
    await waitFor(() => expect(screen.getByTestId('result-row')).toBeInTheDocument());
    await userEvent.clear(screen.getByTestId('search-query'));
    await userEvent.click(screen.getByTestId('search-submit'));
    expect(screen.getByTestId('result-row')).toBeInTheDocument();
    expect(screen.getByText('검색어를 입력해 주세요')).toBeInTheDocument();
    expect(client.calls).toHaveLength(1);
  });

  it('requests the next page with the snapshot cursor', async () => {
    const client = new ContractDouble().on('/api/v2/c05/search', (body) => {
      const page = (body as { page: { cursor?: string } }).page;
      return page.cursor
        ? searchResponse({ hits: [], page: { nextCursor: undefined, snapshotRevision: 'r' } })
        : searchResponse({ page: { nextCursor: 'cursor-1', snapshotRevision: 'r' } });
    });
    render(<SearchSection client={client.asTransport()} onOpen={() => undefined} />);
    await userEvent.type(screen.getByTestId('search-query'), 'attention');
    await userEvent.click(screen.getByTestId('search-submit'));
    await waitFor(() => expect(screen.getByTestId('search-next')).toBeInTheDocument());
    await userEvent.click(screen.getByTestId('search-next'));
    await waitFor(() => expect(client.calls).toHaveLength(2));
    expect(client.calls[1].body).toMatchObject({ page: { cursor: 'cursor-1' } });
  });

  it('surfaces a snapshot-expired refusal without clearing the query', async () => {
    build(() => {
      throw apiError('SNAPSHOT_EXPIRED', 410);
    });
    await userEvent.type(screen.getByTestId('search-query'), 'attention');
    await userEvent.click(screen.getByTestId('search-submit'));
    await waitFor(() =>
      expect(screen.getByTestId('status-line')).toHaveTextContent('검색 결과가 변경되었어요'),
    );
    expect(screen.getByTestId('search-query')).toHaveValue('attention');
  });
});

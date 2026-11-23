/** U3 discovery/results states: rendering, degradation, expiry, pagination. */

import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { SearchSection } from '../../src/u3-corpus/search-reading';
import styles from '../../src/u3-corpus/search-reading.module.css';
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

  it("sizes each result's source link to at least 24×24 CSS px", async () => {
    build();
    await userEvent.type(screen.getByTestId('search-query'), 'attention');
    await userEvent.click(screen.getByTestId('search-submit'));
    await waitFor(() => expect(screen.getByTestId('result-row')).toBeInTheDocument());
    const link = screen.getByRole('link', { name: '원문 링크' });
    expect(link).toHaveAttribute('data-testid', 'result-source');
    expect(link).toHaveAttribute('rel', 'noreferrer noopener');
    // The link stands alone in its row, never inside a sentence, so no exemption applies.
    expect(link.parentElement?.tagName).toBe('LI');
    // U3's own CSS module sizes it; no inline style object is set.
    expect(link.getAttribute('style')).toBeNull();
    expect(styles.sourceLink).toBeTruthy();
    expect(link).toHaveClass(styles.sourceLink!);
    const rule = /\.sourceLink\s*\{([^}]*)\}/.exec(
      readFileSync(join(__dirname, '../../src/u3-corpus/search-reading.module.css'), 'utf8'),
    );
    const declarations = (rule?.[1] ?? '').replace(/\s+/g, ' ').trim();
    expect(declarations).toBe(
      'display: inline-flex; align-items: center; min-height: 24px; min-width: 24px;',
    );
  });

  it("names each result's open button 논문 열기 with the paper's visible title", async () => {
    build();
    await userEvent.type(screen.getByTestId('search-query'), 'attention');
    await userEvent.click(screen.getByTestId('search-submit'));
    await waitFor(() => expect(screen.getByTestId('result-row')).toBeInTheDocument());
    const open = screen.getByRole('button', { name: '논문 열기: 합성 논문 paper-alpha' });
    expect(open).toHaveAttribute('data-testid', 'result-open');
    // The visible title stays inside the accessible name (WCAG 2.5.3).
    expect(open).toHaveTextContent('합성 논문 paper-alpha');
    expect(open.getAttribute('aria-label')).toContain(open.textContent ?? '\u0000');
    expect(screen.queryByRole('button', { name: '합성 논문 paper-alpha' })).toBeNull();
  });

  it('distinguishes an empty result from a retrieval failure', async () => {
    build(() => searchResponse({ hits: [] }));
    await userEvent.type(screen.getByTestId('search-query'), 'nothing');
    await userEvent.click(screen.getByTestId('search-submit'));
    await waitFor(() =>
      expect(screen.getByTestId('search-status')).toHaveTextContent('검색 결과가 없어요'),
    );
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

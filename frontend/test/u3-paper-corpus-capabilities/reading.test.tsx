/** U3 reading states: exact version, anchors, figures and bounded dispositions. */

import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ReadingSection } from '../../src/u3-corpus/search-reading';
import { ContractDouble, apiError, paper, readyContent } from './helpers';

const hit = {
  paper,
  title: '합성 논문 paper-alpha',
  authors: ['연구자 A'],
  snippet: '첫 문단입니다.',
  sourceUrl: 'https://fixture.invalid/paper-alpha/v1',
  availability: 'readable',
  matchExplanation: '검색어 일치',
};

function build(content: unknown) {
  const client = new ContractDouble()
    .on('/api/v2/c04/read-content', () => content)
    .on('/api/v2/c05/explore-citations', () => ({
      snapshotId: 'snap-1',
      revision: 'r1',
      root: paper,
      nodes: [],
      edges: [],
      freshness: 'current',
      coverage: 'complete',
      limitations: [],
      page: { nextCursor: undefined, snapshotRevision: 'r1' },
    }));
  render(<ReadingSection client={client.asTransport()} hit={hit} signedIn={false} />);
  return client;
}

describe('U3 reading surface', () => {
  it('renders sections with anchors and figure captions for the exact version', async () => {
    const client = build(readyContent());
    await waitFor(() => expect(screen.getByTestId('reading-surface')).toBeInTheDocument());
    expect(screen.getByTestId('section-anchor')).toHaveTextContent('Introduction');
    expect(screen.getByTestId('figure-view')).toHaveTextContent('합성 그림');
    expect(screen.getByTestId('paper-identity')).toHaveTextContent('합성 논문 paper-alpha');
    expect(client.calls[0].body).toMatchObject({ paper: { versionId: 'paper-alpha:v1' } });
  });

  it.each([
    ['building', '자료를 준비하고 있어요', true],
    ['withdrawn', '게시가 중단된 자료예요', false],
    ['restricted', '접근이 제한된 자료예요', false],
    ['unsupported', '이 형식은 지원되지 않아요', false],
    ['failed', '자료를 불러오지 못했어요', false],
  ])('renders the %s disposition truthfully', async (availability, copy, retryable) => {
    build({
      availability,
      paper,
      reasonKey: `source.${availability}`,
      retryable,
    });
    await waitFor(() => expect(screen.getByTestId('content-state')).toBeInTheDocument());
    expect(screen.getByTestId('content-state')).toHaveTextContent(copy);
    expect(screen.queryByTestId('reading-surface')).toBeNull();
    if (retryable) {
      expect(screen.getByRole('button', { name: '다시 시도' })).toBeInTheDocument();
    }
  });

  it('never fabricates content for a failed read', async () => {
    const client = new ContractDouble().on('/api/v2/c04/read-content', () => {
      throw apiError('DEPENDENCY_UNAVAILABLE', 503);
    });
    render(<ReadingSection client={client.asTransport()} hit={hit} signedIn={false} />);
    await waitFor(() =>
      expect(screen.getByTestId('status-line')).toHaveTextContent('일시적으로 사용할 수 없어요'),
    );
    expect(screen.queryByTestId('reading-surface')).toBeNull();
    expect(screen.queryByTestId('content-state')).toBeNull();
  });

  it('hides the citation explorer from guests and shows it when signed in', async () => {
    const client = new ContractDouble().on('/api/v2/c04/read-content', () => readyContent());
    render(<ReadingSection client={client.asTransport()} hit={hit} signedIn />);
    await waitFor(() => expect(screen.getByTestId('citation-explorer')).toBeInTheDocument());
    expect(screen.getByTestId('citation-cited')).toBeInTheDocument();
  });
});

/** U3 corpus workspace composition: search → reading → back retains context. */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { CorpusWorkspace, CorpusUnavailable } from '../../src/u3-corpus/corpus-workspace';
import { ContractDouble, readyContent, searchResponse } from './helpers';

const glossary = {
  ownerId: 'owner-a',
  revision: 'empty:owner-a:u3-owner-glossary-v1',
  normalizationPolicy: { policyId: 'u3-owner-glossary', revision: '1' },
  terms: [],
};

function build() {
  return new ContractDouble()
    .on('/api/v2/c05/search', () => searchResponse())
    .on('/api/v2/c04/read-content', () => readyContent())
    .on('/api/v2/c06/read-glossary', () => glossary)
    .on('/api/v2/c06/read-assistance-options', () => {
      throw new Error('assistance options are not requested before content binds');
    });
}

describe('U3 corpus workspace', () => {
  it('composes search, reading and glossary, retaining the query on return', async () => {
    const client = build();
    render(<CorpusWorkspace client={client.asTransport()} signedIn={false} />);
    await userEvent.type(screen.getByTestId('search-query'), 'attention');
    await userEvent.click(screen.getByTestId('search-submit'));
    await waitFor(() => expect(screen.getByTestId('result-row')).toBeInTheDocument());
    await userEvent.click(
      screen.getByTestId('result-row').querySelector('button') as HTMLButtonElement,
    );
    await waitFor(() => expect(screen.getByTestId('reading-surface')).toBeInTheDocument());
    // The search region stays mounted (hidden) so context survives the visit.
    expect(screen.getByTestId('search-query')).toHaveValue('attention');
    await userEvent.click(screen.getByTestId('reading-back'));
    await expect(screen.getByTestId('search-query')).toBeVisible();
    expect(screen.getByTestId('result-row')).toBeInTheDocument();
  });

  it('renders the unavailable panel with an announced state', () => {
    render(<CorpusUnavailable />);
    expect(screen.getByTestId('corpus-unavailable')).toHaveTextContent('코퍼스 기능을 사용할 수 없어요');
  });
});

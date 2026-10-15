/** U3 glossary states: committed terms, save, conflict recovery, isolation. */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { GlossarySection } from '../../src/u3-corpus/assistance';
import { ContractDouble, apiError } from './helpers';

const empty = {
  ownerId: 'owner-a',
  revision: 'empty:owner-a:u3-owner-glossary-v1',
  normalizationPolicy: { policyId: 'u3-owner-glossary', revision: '1' },
  terms: [],
};
const written = {
  ...empty,
  revision: 'glossary-r2',
  terms: [{ termId: 't1', source: 'attention', preferred: '어텐션', languageId: 'ko' }],
};

function renderGlossary(replace: unknown) {
  const client = new ContractDouble()
    .on('/api/v2/c06/read-glossary', () => written)
    .on('/api/v2/c06/replace-glossary', () => {
      if (replace instanceof Error) throw replace;
      return replace;
    });
  render(<GlossarySection client={client.asTransport()} signedIn />);
  return client;
}

describe('U3 glossary surface', () => {
  it('renders committed terms with their revision', async () => {
    renderGlossary(written);
    await waitFor(() => expect(screen.getByTestId('glossary-term')).toBeInTheDocument());
    expect(screen.getByTestId('glossary-term')).toHaveTextContent('attention → 어텐션');
    expect(screen.getByTestId('glossary-revision')).toBeInTheDocument();
  });

  it('saves a new term and adopts the returned revision', async () => {
    const client = renderGlossary(written);
    await waitFor(() => expect(screen.getByTestId('glossary-source')).toBeInTheDocument());
    await userEvent.type(screen.getByTestId('glossary-source'), 'token');
    await userEvent.type(screen.getByTestId('glossary-preferred'), '토큰');
    await userEvent.click(screen.getByTestId('glossary-save'));
    await waitFor(() =>
      expect(screen.getByTestId('status-line')).toHaveTextContent('용어집을 저장했어요'),
    );
    const replace = client.calls.find((call) => call.path.endsWith('/replace-glossary'));
    expect(replace?.body).toMatchObject({ expectedRevision: 'glossary-r2' });
  });

  it('preserves committed terms and reloads on a conflict', async () => {
    renderGlossary(apiError('CONFLICT', 409));
    await waitFor(() => expect(screen.getByTestId('glossary-source')).toBeInTheDocument());
    await userEvent.type(screen.getByTestId('glossary-source'), 'token');
    await userEvent.type(screen.getByTestId('glossary-preferred'), '토큰');
    await userEvent.click(screen.getByTestId('glossary-save'));
    await waitFor(() =>
      expect(screen.getByTestId('glossary-conflict')).toHaveTextContent('다른 곳에서'),
    );
    // The committed glossary stays visible; nothing was silently overwritten.
    expect(screen.getByTestId('glossary-term')).toHaveTextContent('어텐션');
  });

  it('refuses empty terms locally without a request', async () => {
    const client = renderGlossary(written);
    await waitFor(() => expect(screen.getByTestId('glossary-save')).toBeInTheDocument());
    await userEvent.click(screen.getByTestId('glossary-save'));
    expect(screen.getByTestId('status-line')).toHaveTextContent('원어와 선호 용어를 모두 입력해 주세요');
    expect(client.calls.filter((call) => call.path.endsWith('/replace-glossary'))).toHaveLength(0);
  });

  it('keeps private state out of a signed-out view', () => {
    render(<GlossarySection client={new ContractDouble().asTransport()} signedIn={false} />);
    expect(screen.getByTestId('glossary-editor')).toHaveTextContent('로그인하면');
    expect(screen.queryByTestId('glossary-save')).toBeNull();
  });
});

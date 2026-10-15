/**
 * U3 shell composition: the capability-gated corpus workspace mount.
 *
 * This is the direct evidence for the only shared shell path U3 extended in
 * `src/App.tsx` — the `corpus.maintenance` capability branch that swaps the
 * legacy search surface for the U3 corpus workspace. The shared Transport and
 * the wider shell behavior stay covered by their own lanes.
 */

import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import App from '../../src/App';

const json = (value: unknown, status = 200) =>
  new Response(JSON.stringify(value), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

function server(capabilityIds: string[]) {
  const calls: string[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const path = new URL(String(input), 'https://local.invalid').pathname;
      calls.push(path);
      if (path === '/api/v2/session')
        return json({
          signedIn: false,
          accountId: null,
          authorityRevision: null,
          csrfToken: 'c'.repeat(64),
        });
      if (path === '/api/v2/capabilities')
        return json({
          revision: 'catalog-r1',
          capabilities: capabilityIds.map((id) => ({
            id,
            state: 'available',
            modeIds: [],
            languageIds: [],
            levelIds: [],
            formatIds: [],
            policy: { policyId: 'u3-synthetic-v1', revision: '1' },
          })),
        });
      if (path === '/api/v2/c01/host-resolve-navigation') return json({ items: [] });
      return json(
        { code: 'NOT_FOUND', requestId: 'local', retryable: false, messageKey: 'request.not_found' },
        404,
      );
    }),
  );
  return calls;
}

afterEach(() => vi.unstubAllGlobals());

describe('U3 shell composition', () => {
  it('mounts the corpus workspace when the corpus capability is installed', async () => {
    server(['corpus.maintenance', 'discovery.search']);
    render(<App />);
    await waitFor(() => expect(screen.getByTestId('corpus-workspace')).toBeInTheDocument());
    // The U3 query surface replaces the legacy search form in this assembly.
    expect(screen.getByTestId('search-query')).toBeInTheDocument();
    expect(screen.queryByTestId('search-form')).toBeNull();
  });

  it('keeps the legacy search surface when the corpus capability is absent', async () => {
    server(['account.controls']);
    render(<App />);
    await waitFor(() => expect(screen.getByTestId('search-form')).toBeInTheDocument());
    expect(screen.queryByTestId('corpus-workspace')).toBeNull();
  });
});

/**
 * U6's shell contribution in U3's lane (R-04).
 *
 * The owner-bound "내보내기" navigation entry, the export capability lookup and the
 * export view's render branch in `src/App.tsx`, exercised alongside the installed
 * corpus workspace: the entry appears only with the export capability and only when
 * signed in, and opening it shows the view heading.
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import App from '../../src/App';

const policy = { policyId: 'u6-synthetic-export', revision: '1' };

const json = (value: unknown, status = 200) =>
  new Response(JSON.stringify(value), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

function server(signedIn: boolean, capabilityIds: string[]) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const path = new URL(String(input), 'https://local.invalid').pathname;
      if (path === '/api/v2/session')
        return json({
          signedIn,
          accountId: signedIn ? 'owner-a' : null,
          authorityRevision: signedIn ? '1' : null,
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
            policy,
          })),
        });
      if (path === '/api/v2/c01/host-resolve-navigation')
        // The server lists the export entry only with its capability.
        return json({
          items: ['search', 'novelty', ...(capabilityIds.includes('export') ? ['export'] : [])].map(
            (routeId) => ({ routeId, titleKey: routeId, capabilityId: routeId, available: true }),
          ),
        });
      if (path === '/api/v2/c09/list-export-history')
        return json({ entries: [], nextCursor: null });
      return json(
        {
          code: 'NOT_FOUND',
          requestId: 'local',
          retryable: false,
          messageKey: 'request.not_found',
        },
        404,
      );
    }),
  );
}

afterEach(() => vi.unstubAllGlobals());

describe('U6 shell export entry (U3 lane)', () => {
  it('opens the export view beside the corpus workspace when signed in with the capability', async () => {
    server(true, ['corpus.maintenance', 'discovery.search', 'novelty', 'export']);
    render(<App />);
    await screen.findByTestId('corpus-workspace');
    await userEvent.click(await screen.findByTestId('nav-export'));
    expect(await screen.findByRole('heading', { level: 1, name: '내보내기' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 2, name: 'Notion 연결' })).toBeInTheDocument();
  });

  it('keeps the entry absent without the capability', async () => {
    server(true, ['corpus.maintenance', 'discovery.search', 'novelty']);
    render(<App />);
    await screen.findByTestId('nav-novelty');
    expect(screen.queryByTestId('nav-export')).toBeNull();
  });

  it('keeps the entry absent for a guest', async () => {
    server(false, ['corpus.maintenance', 'discovery.search', 'export']);
    render(<App />);
    await screen.findByTestId('corpus-workspace');
    expect(screen.queryByTestId('nav-export')).toBeNull();
  });
});

/** U6's shell contribution in U4's lane (R-04): the owner-bound "내보내기" entry appears
only with the export capability and only when signed in, opens the export view, and
hands the capability to the novelty workspace. */

import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import App from '../../src/App';
import { policy } from './fixtures';

const json = (value: unknown, status = 200) =>
  new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } });

function server(signedIn: boolean, ids: string[]) {
  const paths: string[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const path = new URL(String(input), 'https://local.invalid').pathname;
      paths.push(path);
      if (path === '/api/v2/session')
        return json({
          signedIn,
          accountId: signedIn ? 'owner-a' : null,
          authorityRevision: signedIn ? '1' : null,
          csrfToken: 'c'.repeat(64),
        });
      if (path === '/api/v2/capabilities')
        return json({
          revision: '1',
          capabilities: ids.map((id) => ({
            id,
            state: id === 'export' ? 'degraded' : 'available',
            modeIds: id === 'export' ? ['synthetic-only'] : [],
            languageIds: [],
            levelIds: [],
            formatIds: id === 'export' ? ['notion'] : [],
            policy,
          })),
        });
      if (path === '/api/v2/c01/host-resolve-navigation')
        // The server lists the export entry only with its capability.
        return json({
          items: ['search', 'novelty', ...(ids.includes('export') ? ['export'] : [])].map(
            (routeId) => ({ routeId, titleKey: routeId, capabilityId: routeId, available: true }),
          ),
        });
      if (path === '/api/v2/c03/settings-read')
        return json({ revision: '1', appearance: 'system', onboarding: 'complete' });
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
  return paths;
}

afterEach(() => {
  vi.unstubAllGlobals();
  window.history.replaceState(null, '', '/');
  window.localStorage.clear();
});

describe('shell export entry (U4 lane)', () => {
  it('opens the export view from the signed-in owner navigation', async () => {
    const paths = server(true, ['account.controls', 'novelty', 'export']);
    render(<App />);
    const entry = await screen.findByTestId('nav-export');
    expect(entry.textContent).toBe('내보내기');
    await userEvent.click(entry);
    expect(await screen.findByRole('heading', { level: 1, name: '내보내기' })).toBeInTheDocument();
    await screen.findByTestId('export-empty');
    expect(paths).toContain('/api/v2/c09/read-notion-connection');
    await userEvent.click(screen.getByTestId('nav-novelty'));
    expect(screen.getByTestId('workspace-novelty')).toBeVisible();
    expect(screen.queryByTestId('export-view')).toBeNull();
  });

  it('is absent without the export capability', async () => {
    server(true, ['account.controls', 'novelty']);
    render(<App />);
    await screen.findByTestId('nav-novelty');
    expect(screen.queryByTestId('nav-export')).toBeNull();
  });

  it('is absent for a guest', async () => {
    server(false, ['novelty', 'export']);
    render(<App />);
    await screen.findByTestId('search-form');
    expect(screen.queryByTestId('nav-export')).toBeNull();
    expect(screen.queryByTestId('export-view')).toBeNull();
  });
});

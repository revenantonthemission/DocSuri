import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, Transport, safeApiPath, dispositionCopy } from '../../src/api';
import { OperationStatus, useOperation } from '../../src/control-ui';
import { describeError, notice, StatusLine } from '../../src/ui';
const json = (value: unknown, status = 200) =>
  new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } });
const bootstrap = (account = 'a', revision = 'r1') => ({
  signedIn: true,
  accountId: account,
  authorityRevision: revision,
  csrfToken: `csrf-${account}`,
});
afterEach(() => vi.unstubAllGlobals());
describe('U2 authority-scoped transport', () => {
  it.each([
    'https://evil.example/api/v2/c02/access-login',
    '//evil.example/api/v2/session',
    '/api/v1/x',
    '/api/v2/c02/../secret',
    '/api/v2/c02/%2e%2e',
    '/api/v2/c02/a\\b',
    '/api/v2/c02/a#x',
  ])('rejects unsafe path %s before any request', async (path) => {
    const fetch = vi.fn();
    vi.stubGlobal('fetch', fetch);
    await expect(new Transport().get(path)).rejects.toBeInstanceOf(ApiError);
    expect(fetch).not.toHaveBeenCalled();
  });
  it.each([
    '/api/v2/session',
    '/api/v2/capabilities',
    '/api/v2/c03/settings-resets?view=history&limit=25&cursor=abc%3Adef',
    '/api/v2/c03/settings-resets/reset-a',
    '/api/v2/identity/callback/orcid?flow=f&state=s&code=c',
  ])('allows registered local path %s', (path) => expect(safeApiPath(path)).toBe(true));
  it('uses session CSRF and the caller stable operation key without storing input', async () => {
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(json(bootstrap()))
      .mockResolvedValueOnce(json({ saved: true }));
    vi.stubGlobal('fetch', fetch);
    const client = new Transport();
    await client.post('/api/v2/c03/settings-update', { secret: 'transient' }, 'operation-a');
    expect(fetch.mock.calls[1][1]).toEqual(
      expect.objectContaining({
        credentials: 'same-origin',
        cache: 'no-store',
        headers: expect.objectContaining({
          'X-CSRF-Token': 'csrf-a',
          'Idempotency-Key': 'operation-a',
        }),
      }),
    );
    expect(JSON.stringify(client)).not.toContain('transient');
  });
  it('drops a late response after owner switch', async () => {
    let release!: (value: Response) => void;
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(json(bootstrap('a')))
      .mockImplementationOnce(
        () =>
          new Promise<Response>((resolve) => {
            release = resolve;
          }),
      )
      .mockResolvedValueOnce(json(bootstrap('b')));
    vi.stubGlobal('fetch', fetch);
    const client = new Transport();
    await client.bootstrap();
    const old = client.read('/api/v2/c03/settings-read', {});
    await Promise.resolve();
    await client.bootstrap();
    release(json({ private: 'owner-a' }));
    await expect(old).rejects.toMatchObject({ envelope: { code: 'UNAUTHENTICATED' } });
  });
  it('drops a late response after same-owner authority revision changes', async () => {
    let release!: (value: Response) => void;
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(json(bootstrap()))
      .mockImplementationOnce(
        () =>
          new Promise<Response>((resolve) => {
            release = resolve;
          }),
      )
      .mockResolvedValueOnce(json(bootstrap('a', 'r2')));
    vi.stubGlobal('fetch', fetch);
    const client = new Transport();
    await client.bootstrap();
    const old = client.get('/api/v2/c03/settings-resets/reset-a');
    await client.bootstrap();
    release(json({ private: 'outdated' }));
    await expect(old).rejects.toBeInstanceOf(ApiError);
  });
  it('notifies subscribers and clears private authority on expiry', async () => {
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(json(bootstrap()))
      .mockResolvedValueOnce(
        json(
          { code: 'UNAUTHENTICATED', requestId: 'r', retryable: false, messageKey: 'expired' },
          401,
        ),
      );
    vi.stubGlobal('fetch', fetch);
    const client = new Transport();
    await client.bootstrap();
    const listener = vi.fn();
    const unsub = client.subscribe(listener);
    await expect(client.get('/api/v2/c03/settings-resets/reset-a')).rejects.toBeInstanceOf(
      ApiError,
    );
    expect(listener).toHaveBeenCalledOnce();
    unsub();
    client.invalidateBoundary();
    expect(listener).toHaveBeenCalledOnce();
  });
  it('labels network loss as unknown and never retries automatically', async () => {
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(json(bootstrap()))
      .mockRejectedValueOnce(new TypeError('network'));
    vi.stubGlobal('fetch', fetch);
    const client = new Transport();
    await expect(client.post('/api/v2/c03/settings-reset', {}, 'original')).rejects.toMatchObject({
      envelope: { code: 'UNKNOWN_OUTCOME', requestId: 'original' },
    });
    expect(fetch).toHaveBeenCalledTimes(2);
  });
  it('handles no-content responses and bounded malformed errors', async () => {
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
      .mockResolvedValueOnce(new Response('invalid', { status: 500 }));
    vi.stubGlobal('fetch', fetch);
    const client = new Transport();
    expect(await client.get('/api/v2/c03/settings-resets/reset-a')).toBeUndefined();
    await expect(client.get('/api/v2/c03/settings-resets/reset-a')).rejects.toMatchObject({
      envelope: { code: 'INTERNAL_ERROR' },
    });
  });
  it('rejects a bootstrap response that belongs to an invalidated generation', async () => {
    let release!: (value: Response) => void;
    vi.stubGlobal(
      'fetch',
      vi.fn(
        () =>
          new Promise<Response>((resolve) => {
            release = resolve;
          }),
      ),
    );
    const client = new Transport();
    const pending = client.bootstrap();
    client.invalidateBoundary();
    release(json(bootstrap()));
    await expect(pending).rejects.toBeInstanceOf(ApiError);
  });
  it('limits server errors to safe Korean copy', () => {
    for (const code of [
      'UNAUTHENTICATED',
      'FORBIDDEN',
      'NOT_FOUND',
      'NOT_READY',
      'POLICY_UNRESOLVED',
      'QUOTA_EXCEEDED',
      'RATE_LIMITED',
      'SNAPSHOT_EXPIRED',
      'CONFLICT',
      'STALE_REVISION',
      'DEPENDENCY_UNAVAILABLE',
      'UNKNOWN_OUTCOME',
      'DEADLINE_EXCEEDED',
      'INVALID_ARGUMENT',
      'SECRET',
    ])
      expect(dispositionCopy(code)).not.toContain('SECRET');
    const value = describeError(
      new ApiError(400, {
        code: 'INVALID_ARGUMENT',
        requestId: '1234567890',
        retryable: false,
        messageKey: 'SECRET',
      }),
    );
    render(<StatusLine value={value} />);
    expect(screen.getByRole('alert')).toHaveTextContent('입력을 확인');
    expect(screen.getByRole('alert')).not.toHaveTextContent('SECRET');
  });
});

import App from '../../src/App';
import { PaperWorkspace } from '../../src/paper';
import { fakeClient, policy, profile, settings, page as listPage } from './fixtures';
function appServer(overrides: Record<string, (body: Record<string, unknown>) => unknown> = {}) {
  let signedIn = true;
  let owner = 'account-a';
  const calls: { path: string; body: Record<string, unknown> }[] = [];
  const routes: Record<string, (body: Record<string, unknown>) => unknown> = {
    '/api/v2/session': () => ({
      signedIn,
      accountId: signedIn ? owner : undefined,
      authorityRevision: 'r1',
      csrfToken: 'csrf',
    }),
    '/api/v2/capabilities': () => ({
      revision: 'cap-r1',
      capabilities: [
        {
          id: 'account.controls',
          state: 'available',
          modeIds: [],
          languageIds: [],
          levelIds: ['synthetic-only'],
          formatIds: [],
          policy,
        },
      ],
    }),
    '/api/v2/c01/host-resolve-navigation': () => ({
      items: ['search', 'library', 'account', 'settings', 'usage'].map((routeId) => ({
        routeId,
        titleKey: routeId,
        capabilityId: 'account.controls',
        available: true,
      })),
    }),
    '/api/v2/c02/access-inspect-session': () =>
      signedIn
        ? {
            state: 'authenticated',
            session: {
              accountId: owner,
              sessionId: 's',
              authorityRevision: 'r1',
              authenticationLevel: 'primary',
            },
          }
        : { state: 'anonymous', requestId: 'r' },
    '/api/v2/c02/access-read-profile': () => ({ ...profile, accountId: owner }),
    '/api/v2/c03/settings-read': () => ({ ...settings, accountId: owner }),
    '/api/v2/c03/settings-update': (body) => ({ ...settings, ...body, revision: 'new-revision' }),
    '/api/v2/c02/access-list-consents': () => listPage(),
    '/api/v2/c02/access-list-identity-links': () => listPage(),
    '/api/v2/c03/settings-list-suggestions': () => listPage(),
    '/api/v2/c03/settings-resets?view=outstanding&limit=25': () => listPage(),
    '/api/v2/c03/library-list-saved-papers': () => listPage(),
    '/api/v2/c03/usage-inspect': () => listPage(),
    '/api/v2/c03/usage-list-records': () => listPage(),
    '/api/v2/c03/usage-read-plan': () => ({ tierId: 'synthetic-free', source: 'mock' }),
    '/api/v2/c02/access-logout': () => {
      signedIn = false;
      return {};
    },
    '/api/v2/c02/access-login': (body) => {
      signedIn = true;
      owner = body.email === 'b@example.test' ? 'account-b' : 'account-a';
      return { state: 'authenticated', session: {} };
    },
    '/api/v2/c05/search': (body) => ({
      query: body.query,
      hits: [],
      outcome: 'complete',
      effectiveModeId: 'lexical',
      limitations: [],
      page: {},
    }),
    ...overrides,
  };
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      const body = init?.body ? JSON.parse(String(init.body)) : {};
      calls.push({ path: url, body });
      const value = await routes[url]?.(body);
      return value instanceof Response ? value : json(value ?? {});
    }),
  );
  return {
    calls,
    expire: () => {
      signedIn = false;
    },
  };
}
describe('U2 integrated shell', () => {
  it('offers explicit email-change completion for an already authenticated return', async () => {
    window.history.replaceState(
      null,
      '',
      '/?action=email-change&challengeId=c&flowBinding=f&proof=p',
    );
    const { calls } = appServer();
    render(<App />);
    expect(await screen.findByLabelText('인증 코드')).toHaveValue('p');
    expect(window.location.search).toBe('');
    fireEvent.click(screen.getByTestId('entry-submit'));
    await waitFor(() =>
      expect(calls.some((call) => call.path === '/api/v2/c02/access-complete-email-change')).toBe(
        true,
      ),
    );
    await waitFor(() => expect(screen.queryByLabelText('인증 코드')).toBeNull());
  });

  it('mounts account controls from the current capability catalog', async () => {
    appServer();
    render(<App />);
    fireEvent.click(await screen.findByTestId('nav-account'));
    expect(await screen.findByDisplayValue('연구자 A')).toBeVisible();
  });
  it('opens personal controls and usage in the shared workspace', async () => {
    appServer();
    render(<App />);
    fireEvent.click(await screen.findByTestId('nav-settings'));
    expect(await screen.findByTestId('personal-controls')).toBeVisible();
    fireEvent.click(screen.getByTestId('nav-usage'));
    expect(await screen.findByTestId('usage-controls')).toBeVisible();
  });
  it('preserves safe search context when returning from settings', async () => {
    appServer();
    render(<App />);
    const query = await screen.findByTestId('search-query');
    fireEvent.change(query, { target: { value: 'Transformer' } });
    fireEvent.click(screen.getByTestId('search-submit'));
    await screen.findByText('일치하는 논문이 없어요');
    fireEvent.click(screen.getByTestId('nav-settings'));
    await screen.findByTestId('personal-controls');
    fireEvent.click(screen.getByTestId('nav-search'));
    expect(screen.getByTestId('search-query')).toHaveValue('Transformer');
  });
  it('clears private controls on logout and never automatically repeats a write', async () => {
    const { calls } = appServer();
    render(<App />);
    fireEvent.click(await screen.findByTestId('nav-account'));
    await screen.findByDisplayValue('연구자 A');
    fireEvent.click(screen.getByTestId('logout'));
    expect(await screen.findByTestId('entry-panel')).toBeVisible();
    expect(screen.queryByDisplayValue('연구자 A')).toBeNull();
    expect(calls.filter((call) => call.path === '/api/v2/c02/access-update-profile')).toHaveLength(
      0,
    );
  });
  it('mounts a fresh owner workspace after account switching', async () => {
    appServer();
    render(<App />);
    fireEvent.click(await screen.findByTestId('logout'));
    await screen.findByTestId('entry-panel');
    fireEvent.change(screen.getByLabelText('이메일'), { target: { value: 'b@example.test' } });
    fireEvent.change(screen.getByLabelText('비밀번호'), { target: { value: 'secret' } });
    fireEvent.click(screen.getByTestId('entry-submit'));
    await waitFor(() =>
      expect(screen.getByTestId('app-shell')).toHaveAttribute('data-account', 'account-b'),
    );
    expect(screen.queryByTestId('entry-panel')).toBeNull();
  });
  it('labels a failed appearance save as temporary', async () => {
    appServer({
      '/api/v2/c03/settings-update': () =>
        json({ code: 'CONFLICT', requestId: 'r', retryable: false, messageKey: 'stale' }, 409),
    });
    render(<App />);
    await screen.findByTestId('nav-account');
    fireEvent.change(screen.getByTestId('appearance-select'), { target: { value: 'dark' } });
    expect(await screen.findByText(/임시 변경이에요/)).toBeVisible();
  });
  it('invalidates private rendered state on pagehide', async () => {
    appServer();
    render(<App />);
    fireEvent.click(await screen.findByTestId('nav-account'));
    await screen.findByDisplayValue('연구자 A');
    act(() => window.dispatchEvent(new PageTransitionEvent('pagehide')));
    expect(screen.queryByDisplayValue('연구자 A')).toBeNull();
  });
  it('uses the U2 library panel without starting a search', async () => {
    const { calls } = appServer();
    render(<App />);
    fireEvent.click(await screen.findByTestId('nav-library'));
    expect(await screen.findByTestId('library-empty')).toBeVisible();
    expect(calls.filter((call) => call.path === '/api/v2/c05/search')).toHaveLength(0);
  });
});
describe('U2 paper-save consumer binding', () => {
  it.each([undefined, policy])(
    'retains explicit profile-specific policy %j',
    async (libraryPolicy) => {
      const client = fakeClient();
      client.read.mockResolvedValue({
        availability: 'available',
        content: {
          title: 'Paper',
          sections: [],
          limitations: [],
          sourceUrls: [],
          coverage: 'complete',
        },
        paper: { paperId: 'p', versionId: 'v', eligibilityRevision: 'e' },
      });
      client.post.mockImplementation(async (path: string) =>
        path.includes('read-content')
          ? {
              availability: 'available',
              content: {
                title: 'Paper',
                sections: [],
                limitations: [],
                sourceUrls: [],
                coverage: 'complete',
              },
              paper: { paperId: 'p', versionId: 'v', eligibilityRevision: 'e' },
            }
          : path.includes('list-') || path.includes('history')
            ? { items: [] }
            : path.includes('options')
              ? { revision: '1', options: [], limitations: [] }
              : {},
      );
      render(
        <PaperWorkspace
          transport={client.transport}
          paper={{ paperId: 'p', versionId: 'v', eligibilityRevision: 'e' }}
          signedIn
          onBack={vi.fn()}
          libraryPolicy={libraryPolicy}
        />,
      );
      const button = await screen.findByTestId('save-paper');
      fireEvent.click(button);
      await waitFor(() =>
        expect(client.post).toHaveBeenCalledWith(
          '/api/v2/c03/library-save-paper',
          expect.objectContaining({
            policyRef: libraryPolicy ?? { policyId: 'synthetic-local-library', revision: '1' },
          }),
        ),
      );
    },
  );
});

describe('bootstrap admission ordering', () => {
  it('shares concurrent initial reads so a rotated cookie cannot invalidate the saved CSRF token', async () => {
    let finish!: (response: Response) => void;
    const fetcher = vi.fn(
      () =>
        new Promise<Response>((resolve) => {
          finish = resolve;
        }),
    );
    vi.stubGlobal('fetch', fetcher);
    const client = new Transport();
    const first = client.bootstrap();
    const second = client.bootstrap();
    expect(fetcher).toHaveBeenCalledOnce();
    finish(json({ signedIn: false, csrfToken: 'one-anonymous-flow' }));
    expect(await first).toEqual(await second);
    expect(client.generation).toBe(1);
  });
});

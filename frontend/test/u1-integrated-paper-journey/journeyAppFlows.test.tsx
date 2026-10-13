/**
 * Remaining U1 shell flows for measured App.tsx coverage: registration and
 * verification, logout, navigation, library mutations, rerun, appearance
 * persistence to the account, and the pre-session bootstrapping state.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import React from 'react';

import App from '../../src/App';

type Outcome = { status: number; json: unknown };
type Handler = (body: Record<string, unknown>) => Outcome | Promise<Outcome>;
type Routes = Record<string, Handler>;

const NAVIGATION = {
  items: [
    { routeId: 'search', titleKey: 'nav.search', capabilityId: 'discovery.search', available: true },
    { routeId: 'library', titleKey: 'nav.library', capabilityId: 'library.saved-work', available: true },
  ],
};

const ERROR = {
  code: 'CONFLICT',
  requestId: 'req-conflict',
  retryable: false,
  messageKey: 'conflict',
};

function serve(routes: Routes) {
  const calls: { path: string; body: Record<string, unknown> }[] = [];
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input);
    const body = init?.body ? (JSON.parse(String(init.body)) as Record<string, unknown>) : {};
    calls.push({ path, body });
    const handler = routes[path];
    const outcome: Outcome = handler
      ? await handler(body)
      : { status: 404, json: { ...ERROR, code: 'NOT_FOUND' } };
    return new Response(JSON.stringify(outcome.json), {
      status: outcome.status,
      headers: { 'Content-Type': 'application/json' },
    });
  });
  vi.stubGlobal('fetch', fetchMock);
  return calls;
}

function baseRoutes(overrides: Routes = {}): Routes {
  return {
    '/api/v2/session': () => ({
      status: 200,
      json: { signedIn: true, accountId: 'acct-a', authorityRevision: 'r1', csrfToken: 'csrf' },
    }),
    '/api/v2/c01/host-resolve-navigation': () => ({ status: 200, json: NAVIGATION }),
    '/api/v2/c03/settings-read': () => ({
      status: 200,
      json: { revision: 's1', appearance: 'system', onboarding: 'not_started' },
    }),
    ...overrides,
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  window.history.replaceState({}, '', '/');
});

beforeEach(() => {
  try {
    window.localStorage.clear();
  } catch {
    /* jsdom storage may be unavailable */
  }
});

describe('entry flows', () => {
  it('shows the bootstrapping state until authority is known', async () => {
    const resolvers: ((value: Outcome) => void)[] = [];
    serve(
      baseRoutes({
        '/api/v2/session': () =>
          new Promise<Outcome>((resolve) => {
            resolvers.push(resolve);
          }),
      }),
    );
    render(<App />);
    expect(screen.getByTestId('bootstrapping')).toHaveTextContent('세션을 확인하고 있어요');
    expect(screen.queryByTestId('entry-panel')).not.toBeInTheDocument();
    // Every pending session read (mount, StrictMode and the lazy CSRF path)
    // resolves; authority is then known and the entry surface appears.
    await waitFor(() => expect(resolvers.length).toBeGreaterThan(0));
    for (const resolve of [...resolvers]) {
      resolve({ status: 200, json: { signedIn: false, csrfToken: 'csrf' } });
    }
    await screen.findByTestId('entry-panel');
  });

  it('registers, verifies from the mail link and rejects a malformed login', async () => {
    window.history.replaceState(
      {},
      '',
      '/verify-email?action=verify-email&challengeId=c1&proof=p1&flowBinding=f1',
    );
    const calls = serve(
      baseRoutes({
        '/api/v2/session': () => ({ status: 200, json: { signedIn: false, csrfToken: 'csrf' } }),
        '/api/v2/c02/access-register': () => ({
          status: 200,
          json: { requestId: 'r1', acknowledgement: 'accepted', messageKey: 'access.check' },
        }),
        '/api/v2/c02/access-verify-email': () => ({
          status: 200,
          json: { resourceId: 'a1', revision: 'r1', requestId: 'r2' },
        }),
        '/api/v2/c02/access-login': () => ({
          status: 401,
          json: { code: 'UNAUTHENTICATED', requestId: 'r3', retryable: false, messageKey: 'x' },
        }),
      }),
    );
    render(<App />);
    // Verification form comes from the mail link's own parameters.
    const verification = await screen.findByTestId('verification-form');
    expect(within(verification).getByLabelText('인증 코드')).toHaveValue('p1');
    fireEvent.click(within(verification).getByRole('button', { name: '인증 완료' }));
    await screen.findByText(/이메일 인증을 마쳤어요/);
    expect(calls.some((call) => call.path === '/api/v2/c02/access-verify-email')).toBe(true);
    // Empty credentials are refused client-side; a server refusal is shown.
    fireEvent.click(screen.getByTestId('entry-submit'));
    await screen.findByText('이메일과 비밀번호를 확인해 주세요');
    fireEvent.click(screen.getByTestId('entry-switch'));
    fireEvent.change(screen.getByTestId('entry-email'), { target: { value: 'new@example.com' } });
    fireEvent.change(screen.getByTestId('entry-password'), { target: { value: 'pw' } });
    fireEvent.click(screen.getByTestId('entry-submit'));
    await screen.findByText(/인증 메일을 보냈어요/);
    fireEvent.click(screen.getByTestId('entry-switch'));
    fireEvent.change(screen.getByTestId('entry-email'), { target: { value: 'user@example.com' } });
    fireEvent.change(screen.getByTestId('entry-password'), { target: { value: 'pw' } });
    fireEvent.click(screen.getByTestId('entry-submit'));
    await waitFor(() => expect(screen.getByTestId('status-line')).toHaveTextContent('다시 로그인해 주세요'));
  });

  it('logs out, clears private state and re-bootstraps the session', async () => {
    let account = 'acct-a';
    const calls = serve(
      baseRoutes({
        '/api/v2/session': () => ({
          status: 200,
          json: { signedIn: true, accountId: account, authorityRevision: 'r1', csrfToken: 'csrf' },
        }),
        '/api/v2/c02/access-logout': () => ({
          status: 200,
          json: { resourceId: 'a1', revision: 'r', requestId: 'q' },
        }),
        '/api/v2/c03/library-list-saved-papers': () => ({
          status: 200,
          json: {
            items: [
              {
                savedPaperId: '1706.03762',
                revision: 'v1',
                savedTitle: 'Attention Is All You Need',
                sourceDisposition: 'available',
                savedPaper: { paperId: '1706.03762', versionId: '1706.03762v7', eligibilityRevision: 'e' },
              },
            ],
          },
        }),
        '/api/v2/c03/library-list-saved-searches': () => ({ status: 200, json: { items: [] } }),
        '/api/v2/c03/library-list-history': () => ({
          status: 200,
          json: { items: [], clearBoundary: 'b1' },
        }),
        '/api/v2/c03/usage-inspect': () => ({
          status: 200,
          json: {
            items: [
              {
                state: 'known',
                allocated: 4,
                used: 0,
                reserved: 0,
                remaining: 4,
                periodId: 'synthetic-environment-retention',
              },
            ],
          },
        }),
      }),
    );
    render(<App />);
    fireEvent.click(await screen.findByTestId('nav-library'));
    await screen.findByText('Attention Is All You Need');
    expect(screen.getByTestId('usage-value')).toHaveTextContent('남은 사용량 4 / 4');
    account = 'guest';
    fireEvent.click(screen.getByTestId('logout'));
    await waitFor(() =>
      expect(screen.getByTestId('app-shell')).toHaveAttribute('data-account', 'guest'),
    );
    expect(screen.getByTestId('search-workspace')).toBeInTheDocument();
    expect(calls.some((call) => call.path === '/api/v2/c02/access-logout')).toBe(true);
  });
});

describe('library mutations and rerun', () => {
  it('removes a saved paper, clears history after confirmation and reruns a saved query', async () => {
    const marker = 'browser-marker';
    let cleared = false;
    const calls = serve(
      baseRoutes({
        '/api/v2/c03/library-list-saved-papers': () => ({
          status: 200,
          json: {
            items: cleared
              ? []
              : [
                  {
                    savedPaperId: '1706.03762',
                    revision: 'v1',
                    savedTitle: 'Attention Is All You Need',
                    sourceDisposition: 'available',
                    savedPaper: {
                      paperId: '1706.03762',
                      versionId: '1706.03762v7',
                      eligibilityRevision: 'e',
                    },
                  },
                ],
          },
        }),
        '/api/v2/c03/library-list-saved-searches': () => ({
          status: 200,
          json: {
            items: [
              {
                savedSearchId: 'q1',
                revision: 'sq1',
                queryContext: { query: marker, modeId: 'lexical', orderId: 'relevance' },
              },
            ],
          },
        }),
        '/api/v2/c03/library-list-history': () => ({
          status: 200,
          json: {
            items: cleared
              ? []
              : [
                  {
                    historyId: 'h1',
                    queryContext: { query: 'first search', modeId: 'lexical', orderId: 'relevance' },
                    recordedAt: '2026-10-13T00:00:00Z',
                  },
                ],
            clearBoundary: 'b1',
          },
        }),
        '/api/v2/c03/usage-inspect': () => ({
          status: 200,
          json: { items: [{ state: 'unknown', reasonKey: 'usage.unknown' }] },
        }),
        '/api/v2/c03/library-remove-saved-paper': () => ({
          status: 200,
          json: { resourceId: '1706.03762', revision: 'v2', requestId: 'q' },
        }),
        '/api/v2/c03/library-clear-history': () => {
          cleared = true;
          return {
            status: 200,
            json: {
              ack: { resourceId: 'a', revision: 'b2', requestId: 'q' },
              checkpoint: { ownerId: 'a', admissionSequence: 2, revision: 'b2' },
              clearBoundary: 'b2',
            },
          };
        },
      }),
    );
    render(<App />);
    fireEvent.click(await screen.findByTestId('nav-library'));
    await screen.findByText('Attention Is All You Need');
    fireEvent.click(screen.getByTestId('remove-saved-paper'));
    await waitFor(() =>
      expect(calls.some((call) => call.path === '/api/v2/c03/library-remove-saved-paper')).toBe(true),
    );
    fireEvent.click(screen.getByTestId('clear-history'));
    const confirm = await screen.findByTestId('history-confirm');
    expect(confirm).toHaveTextContent('저장한 논문과 검색 조건은 그대로 남아요');
    fireEvent.click(screen.getByTestId('confirm-clear'));
    await screen.findByText('검색 기록을 지웠어요');
    fireEvent.click(screen.getByTestId('rerun-query'));
    const query = await screen.findByTestId('search-query');
    await waitFor(() => expect(query).toHaveValue(marker));
  });

  it('keeps a failed history clear truthful and preserves the saved work', async () => {
    serve(
      baseRoutes({
        '/api/v2/c03/library-list-saved-papers': () => ({ status: 200, json: { items: [] } }),
        '/api/v2/c03/library-list-saved-searches': () => ({ status: 200, json: { items: [] } }),
        '/api/v2/c03/library-list-history': () => ({
          status: 200,
          json: {
            items: [
              {
                historyId: 'h1',
                queryContext: { query: 'first search', modeId: 'lexical', orderId: 'relevance' },
                recordedAt: '2026-10-13T00:00:00Z',
              },
            ],
            clearBoundary: 'b1',
          },
        }),
        '/api/v2/c03/usage-inspect': () => ({ status: 200, json: { items: [] } }),
        '/api/v2/c03/library-clear-history': () => ({ status: 409, json: ERROR }),
      }),
    );
    render(<App />);
    fireEvent.click(await screen.findByTestId('nav-library'));
    fireEvent.click(await screen.findByTestId('clear-history'));
    fireEvent.click(await screen.findByTestId('confirm-clear'));
    await waitFor(() =>
      expect(screen.getByTestId('status-line')).toHaveTextContent('다른 곳에서 변경되었어요'),
    );
    expect(await screen.findByText('first search')).toBeInTheDocument();
  });

  it('saves a submitted query and reports a refusal truthfully', async () => {
    let attempt = 0;
    serve(
      baseRoutes({
        '/api/v2/c05/search': () => ({
          status: 200,
          json: {
            executionId: 'e1',
            hits: [
              {
                paper: { paperId: '1706.03762', versionId: '1706.03762v7', eligibilityRevision: 'e' },
                title: 'Attention Is All You Need',
                authors: ['Vaswani'],
                snippet: 'attention',
                sourceUrl: 'https://arxiv.org/html/1706.03762v7',
                availability: 'readable',
                matchExplanation: 'title',
              },
            ],
            page: { snapshotRevision: 'p1' },
            outcome: 'complete',
            effectiveModeId: 'lexical',
            limitations: [],
          },
        }),
        '/api/v2/c03/library-save-search': () => {
          attempt += 1;
          if (attempt === 1) {
            return {
              status: 200,
              json: {
                savedSearchId: 'q1',
                revision: 'sq1',
                queryContext: { query: 'saved', modeId: 'lexical', orderId: 'relevance' },
              },
            };
          }
          return { status: 503, json: { ...ERROR, code: 'DEPENDENCY_UNAVAILABLE' } };
        },
      }),
    );
    render(<App />);
    fireEvent.change(await screen.findByTestId('search-query'), { target: { value: 'saved' } });
    fireEvent.click(screen.getByTestId('search-submit'));
    await screen.findByTestId('search-results');
    fireEvent.click(screen.getByTestId('save-search'));
    await screen.findByText(/검색 조건을 저장했어요/);
    fireEvent.click(screen.getByTestId('save-search'));
    await waitFor(() =>
      expect(screen.getAllByText(/일시적으로 사용할 수 없어요/).length).toBeGreaterThan(0),
    );
  });

  it('persists an appearance choice to the account when signed in', async () => {
    const calls = serve(
      baseRoutes({
        '/api/v2/c03/settings-update': () => ({
          status: 200,
          json: { revision: 's2', appearance: 'dark', onboarding: 'not_started' },
        }),
      }),
    );
    render(<App />);
    await screen.findByTestId('search-workspace');
    fireEvent.change(screen.getByTestId('appearance-select'), { target: { value: 'dark' } });
    await waitFor(() =>
      expect(calls.some((call) => call.path === '/api/v2/c03/settings-update')).toBe(true),
    );
    const update = calls.find((call) => call.path === '/api/v2/c03/settings-update');
    expect(update?.body).toMatchObject({ appearance: 'dark', expectedRevision: 's1' });
  });
});

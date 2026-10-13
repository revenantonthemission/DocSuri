/**
 * U1 workspace component behaviour over the canonical browser bindings.
 *
 * The transport is stubbed at the fetch boundary; every case asserts a real
 * user-visible disposition (controls preserved, stale response discarded,
 * truthful save/job/result states, account-switch isolation).
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import React from 'react';

import App from '../../src/App';

type Outcome = { status: number; json: unknown };
type Handler = (body: Record<string, unknown>) => Outcome | Promise<Outcome>;
type Routes = Record<string, Handler>;

const ERROR = {
  code: 'DEPENDENCY_UNAVAILABLE',
  requestId: 'req-1',
  retryable: true,
  messageKey: 'request.dependency_unavailable',
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

const NAVIGATION = {
  items: [
    { routeId: 'search', titleKey: 'nav.search', capabilityId: 'discovery.search', available: true },
    { routeId: 'library', titleKey: 'nav.library', capabilityId: 'library.saved-work', available: true },
    { routeId: 'jobs', titleKey: 'nav.jobs', capabilityId: 'assistance.summary', available: false, reasonKey: 'nav.capabilityPending' },
  ],
};

const PAPER = {
  paper: { paperId: '1706.03762', versionId: '1706.03762v7', eligibilityRevision: 'rev-1' },
  title: 'Attention Is All You Need',
  authors: ['Vaswani'],
  snippet: 'scaled dot-product attention',
  sourceUrl: 'https://arxiv.org/html/1706.03762v7',
  availability: 'readable',
  matchExplanation: 'title match',
};

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
    '/api/v2/c05/search': () => ({
      status: 200,
      json: {
        executionId: 'e1',
        hits: [PAPER],
        page: { snapshotRevision: 'p1' },
        outcome: 'complete',
        effectiveModeId: 'lexical',
        limitations: [],
      },
    }),
    ...overrides,
  };
}

async function renderApp(routes: Routes) {
  const calls = serve(routes);
  render(<App />);
  await screen.findByTestId('search-workspace');
  return calls;
}

beforeEach(() => {
  try {
    window.localStorage.clear();
  } catch {
    /* jsdom storage may be unavailable */
  }
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('search workspace', () => {
  it('finds papers, labels the confirmed result count and keeps query controls', async () => {
    const calls = await renderApp(baseRoutes());
    fireEvent.change(screen.getByTestId('search-query'), { target: { value: 'transformer' } });
    fireEvent.click(screen.getByTestId('search-submit'));
    const results = await screen.findByTestId('search-results');
    expect(within(results).getByText('Attention Is All You Need')).toBeInTheDocument();
    expect(screen.getByTestId('search-status')).toHaveTextContent('1개의 결과를 찾았어요');
    expect(screen.getByTestId('search-query')).toBeInTheDocument();
    expect(screen.getByTestId('filter-author')).toBeInTheDocument();
    const search = calls.find((call) => call.path === '/api/v2/c05/search');
    expect(search?.body).toMatchObject({ query: { query: 'transformer', modeId: 'lexical' } });
  });

  it('shows a truthful empty state only after a successful retrieval', async () => {
    await renderApp(
      baseRoutes({
        '/api/v2/c05/search': () => ({
          status: 200,
          json: {
            executionId: 'e1',
            hits: [],
            page: { snapshotRevision: 'p1' },
            outcome: 'complete',
            effectiveModeId: 'lexical',
            limitations: [],
          },
        }),
      }),
    );
    fireEvent.change(screen.getByTestId('search-query'), { target: { value: 'nothing here' } });
    fireEvent.click(screen.getByTestId('search-submit'));
    await waitFor(() =>
      expect(screen.getByTestId('search-status')).toHaveTextContent('일치하는 논문이 없어요'),
    );
    expect(screen.queryByTestId('search-results')).not.toBeInTheDocument();
  });

  it('keeps failure recoverable: the submitted context and controls survive and retry works', async () => {
    let attempt = 0;
    const calls = await renderApp(
      baseRoutes({
        '/api/v2/c05/search': () => {
          attempt += 1;
          if (attempt === 1) return { status: 503, json: ERROR };
          return {
            status: 200,
            json: {
              executionId: 'e2',
              hits: [PAPER],
              page: { snapshotRevision: 'p1' },
              outcome: 'complete',
              effectiveModeId: 'lexical',
              limitations: [],
            },
          };
        },
      }),
    );
    fireEvent.change(screen.getByTestId('search-query'), { target: { value: 'attention' } });
    fireEvent.click(screen.getByTestId('search-submit'));
    await screen.findByRole('alert');
    expect(screen.getByTestId('search-query')).toHaveValue('attention');
    const retry = screen.getByTestId('search-retry');
    expect(retry).toBeEnabled();
    fireEvent.click(retry);
    await screen.findByTestId('search-results');
    expect(calls.filter((call) => call.path === '/api/v2/c05/search')).toHaveLength(2);
  });

  it('never lets a superseded slow response replace the active result set', async () => {
    const resolvers: ((value: Outcome) => void)[] = [];
    await renderApp(
      baseRoutes({
        '/api/v2/c05/search': () =>
          new Promise<Outcome>((resolve) => {
            resolvers.push(resolve);
          }),
      }),
    );
    fireEvent.change(screen.getByTestId('search-query'), { target: { value: 'first' } });
    fireEvent.click(screen.getByTestId('search-submit'));
    fireEvent.change(screen.getByTestId('search-query'), { target: { value: 'second' } });
    fireEvent.click(screen.getByTestId('search-submit'));
    await waitFor(() => expect(resolvers).toHaveLength(2));
    resolvers[1]({
      status: 200,
      json: {
        executionId: 'e-second',
        hits: [{ ...PAPER, title: '두 번째 결과' }],
        page: { snapshotRevision: 'p2' },
        outcome: 'complete',
        effectiveModeId: 'lexical',
        limitations: [],
      },
    });
    await screen.findByText('두 번째 결과');
    resolvers[0]({
      status: 200,
      json: {
        executionId: 'e-first',
        hits: [{ ...PAPER, title: '첫 번째 결과' }],
        page: { snapshotRevision: 'p1' },
        outcome: 'complete',
        effectiveModeId: 'lexical',
        limitations: [],
      },
    });
    await waitFor(() => expect(screen.getByTestId('search-status')).toHaveTextContent('1개의 결과'));
    expect(screen.queryByText('첫 번째 결과')).not.toBeInTheDocument();
    expect(screen.getByText('두 번째 결과')).toBeInTheDocument();
  });
});

describe('paper, save and result reads', () => {
  const CONTENT = {
    availability: 'ready',
    content: {
      paper: PAPER.paper,
      contentRevision: 'c1',
      contentHash: 'a'.repeat(64),
      sections: [
        { sectionId: 's1', heading: '3.2 Attention', text: 'softmax(QK^T/sqrt(d_k))V', anchor: 'anchor-1' },
      ],
      sourceUrls: ['https://arxiv.org/html/1706.03762v7'],
      coverage: 'complete',
      limitations: [],
    },
  };

  it('reads the exact version, saves with an acknowledged state and offers read-only result opening', async () => {
    const calls = await renderApp(
      baseRoutes({
        '/api/v2/c04/read-content': () => ({ status: 200, json: CONTENT }),
        '/api/v2/c03/library-list-saved-papers': () => ({ status: 200, json: { items: [] } }),
        '/api/v2/c06/read-assistance-options': () => ({
          status: 200,
          json: { revision: 'o1', options: [], limitations: ['요약 모델의 품질 근거가 아직 확인되지 않았어요'] },
        }),
        '/api/v2/c06/read-assistance-history': () => ({ status: 200, json: { items: [] } }),
        '/api/v2/c03/library-save-paper': () => ({
          status: 200,
          json: {
            savedPaperId: '1706.03762',
            revision: 'saved-1',
            savedTitle: 'Attention Is All You Need',
            sourceDisposition: 'available',
            savedPaper: PAPER.paper,
          },
        }),
      }),
    );
    fireEvent.change(screen.getByTestId('search-query'), { target: { value: 'attention' } });
    fireEvent.click(screen.getByTestId('search-submit'));
    fireEvent.click(await screen.findByText('Attention Is All You Need'));
    await screen.findByTestId('reading-surface');
    expect(screen.getByTestId('paper-identity')).toHaveTextContent('1706.03762v7');
    expect(screen.getByText(/softmax/)).toBeInTheDocument();
    // The assistance panel truthfully explains the unavailable option instead
    // of offering fabricated work.
    expect(screen.getByTestId('assistance-unavailable')).toHaveTextContent(
      '현재 이 작업을 사용할 수 없어요',
    );
    fireEvent.click(screen.getByTestId('save-paper'));
    await screen.findByText('저장됨');
    const save = calls.find((call) => call.path === '/api/v2/c03/library-save-paper');
    expect(save?.body).toMatchObject({ paper: PAPER.paper });

    // The unavailable local option is explained and no work is offered; no
    // acceptance call is made anywhere in this read journey.
    expect(screen.queryByTestId('start-summary')).not.toBeInTheDocument();
    expect(calls.filter((call) => call.path === '/api/v2/c06/accept-assistance')).toHaveLength(0);
  });

  it('opens a previously retained result read-only without starting work', async () => {
    const calls = await renderApp(
      baseRoutes({
        '/api/v2/c04/read-content': () => ({ status: 200, json: CONTENT }),
        '/api/v2/c03/library-list-saved-papers': () => ({ status: 200, json: { items: [] } }),
        '/api/v2/c06/read-assistance-options': () => ({
          status: 200,
          json: { revision: 'o1', options: [], limitations: [] },
        }),
        '/api/v2/c06/read-assistance-history': () => ({
          status: 200,
          json: {
            items: [
              {
                jobId: 'job-retained',
                availability: 'ready',
                operation: 'summary',
                state: 'succeeded',
                createdAt: '2026-10-13T00:00:00Z',
              },
            ],
          },
        }),
        '/api/v2/jobs/job-retained/result': () => ({
          status: 200,
          json: {
            availability: 'ready',
            jobId: 'job-retained',
            prepared: {
              result: { resultId: 'res-1', revision: 'r1' },
              sections: [{ sectionId: 's1', heading: '요약', text: '어텐션 요약', anchor: 'a1' }],
              coverage: 'partial',
              limitations: ['선택한 원문 구간에 대한 결과입니다.'],
              operation: 'summary',
              optionId: 'key-sections-summary',
              paper: PAPER.paper,
            },
          },
        }),
      }),
    );
    fireEvent.change(screen.getByTestId('search-query'), { target: { value: 'attention' } });
    fireEvent.click(screen.getByTestId('search-submit'));
    fireEvent.click(await screen.findByText('Attention Is All You Need'));
    await screen.findByTestId('prior-assistance');
    fireEvent.click(screen.getByText('결과 다시 읽기'));
    await screen.findByTestId('prepared-result');
    expect(screen.getByText('어텐션 요약')).toBeInTheDocument();
    expect(screen.getByText(/선택한 원문 구간/)).toBeInTheDocument();
    expect(calls.filter((call) => call.path === '/api/v2/c06/accept-assistance')).toHaveLength(0);
  });

  it('shows a changed-intent conflict truthfully without losing the committed state', async () => {
    await renderApp(
      baseRoutes({
        '/api/v2/c04/read-content': () => ({ status: 200, json: CONTENT }),
        '/api/v2/c03/library-list-saved-papers': () => ({ status: 200, json: { items: [] } }),
        '/api/v2/c06/read-assistance-options': () => ({
          status: 200,
          json: { revision: 'o1', options: [], limitations: [] },
        }),
        '/api/v2/c06/read-assistance-history': () => ({ status: 200, json: { items: [] } }),
        '/api/v2/c03/library-save-paper': () => ({
          status: 409,
          json: { code: 'CONFLICT', requestId: 'req-2', retryable: false, messageKey: 'conflict' },
        }),
      }),
    );
    fireEvent.change(screen.getByTestId('search-query'), { target: { value: 'attention' } });
    fireEvent.click(screen.getByTestId('search-submit'));
    fireEvent.click(await screen.findByText('Attention Is All You Need'));
    await screen.findByTestId('reading-surface');
    fireEvent.click(screen.getByTestId('save-paper'));
    await waitFor(() =>
      expect(screen.getByTestId('save-state')).toHaveTextContent('다른 곳에서 변경되었어요'),
    );
    expect(screen.queryByText('저장됨')).not.toBeInTheDocument();
  });

  it('reports an unknown save outcome without claiming success', async () => {
    await renderApp(
      baseRoutes({
        '/api/v2/c04/read-content': () => ({ status: 200, json: CONTENT }),
        '/api/v2/c03/library-list-saved-papers': () => ({ status: 200, json: { items: [] } }),
        '/api/v2/c06/read-assistance-options': () => ({
          status: 200,
          json: { revision: 'o1', options: [], limitations: [] },
        }),
        '/api/v2/c06/read-assistance-history': () => ({ status: 200, json: { items: [] } }),
        '/api/v2/c03/library-save-paper': () => ({
          status: 409,
          json: {
            code: 'UNKNOWN_OUTCOME',
            requestId: 'req-3',
            retryable: false,
            messageKey: 'unknown',
          },
        }),
      }),
    );
    fireEvent.change(screen.getByTestId('search-query'), { target: { value: 'attention' } });
    fireEvent.click(screen.getByTestId('search-submit'));
    fireEvent.click(await screen.findByText('Attention Is All You Need'));
    await screen.findByTestId('reading-surface');
    fireEvent.click(screen.getByTestId('save-paper'));
    await waitFor(() =>
      expect(screen.getByTestId('save-state')).toHaveTextContent('저장 여부 확인 중'),
    );
    expect(screen.queryByText('저장됨')).not.toBeInTheDocument();
  });

  it('keeps a broken stream separate from work state and recovers by polling', async () => {
    const sources: FakeEventSource[] = [];
    class FakeEventSource {
      listeners: Record<string, ((event: MessageEvent) => void)[]> = {};
      onerror: (() => void) | null = null;
      closed = false;

      constructor(readonly url: string) {
        sources.push(this);
      }

      addEventListener(name: string, handler: (event: MessageEvent) => void) {
        (this.listeners[name] ??= []).push(handler);
      }

      close() {
        this.closed = true;
      }

      emit(name: string, payload: unknown) {
        for (const handler of this.listeners[name] ?? []) {
          handler({ data: JSON.stringify(payload) } as MessageEvent);
        }
      }

      fail() {
        this.onerror?.();
      }
    }
    vi.stubGlobal('EventSource', FakeEventSource);
    let polls = 0;
    await renderApp(
      baseRoutes({
        '/api/v2/c04/read-content': () => ({ status: 200, json: CONTENT }),
        '/api/v2/c03/library-list-saved-papers': () => ({ status: 200, json: { items: [] } }),
        '/api/v2/c06/read-assistance-options': () => ({
          status: 200,
          json: {
            revision: 'o1',
            options: [
              {
                optionId: 'key-sections-summary',
                operation: 'summary',
                sourceLanguageId: 'en',
                targetLanguageId: 'en',
                labelKey: 'summary',
              },
            ],
            limitations: [],
          },
        }),
        '/api/v2/c06/read-assistance-history': () => ({ status: 200, json: { items: [] } }),
        '/api/v2/c06/read-glossary': () => ({ status: 200, json: { revision: 'g1' } }),
        '/api/v2/c06/accept-assistance': () => ({
          status: 200,
          json: { jobId: 'job-1', revision: 'r1', seq: 1, state: 'accepted', acceptedAt: 't' },
        }),
        '/api/v2/jobs/job-1': () => {
          polls += 1;
          if (polls === 1) {
            return {
              status: 200,
              json: {
                jobId: 'job-1',
                state: 'accepted',
                revision: 'r1',
                seq: 1,
                acceptedAt: 't',
                progress: { mode: 'indeterminate' },
              },
            };
          }
          return {
            status: 200,
            json: {
              jobId: 'job-1',
              state: 'succeeded',
              revision: 'r3',
              seq: 3,
              acceptedAt: 't',
              progress: { mode: 'determinate', current: 1, total: 1 },
            },
          };
        },
      }),
    );
    fireEvent.change(screen.getByTestId('search-query'), { target: { value: 'attention' } });
    fireEvent.click(screen.getByTestId('search-submit'));
    fireEvent.click(await screen.findByText('Attention Is All You Need'));
    await screen.findByTestId('reading-surface');
    fireEvent.click(screen.getByTestId('start-summary'));
    const card = await screen.findByTestId('activity-card');
    expect(card).toHaveTextContent('요청을 접수했어요');
    // The stream confirms a newer authoritative sequence.
    await waitFor(() => expect(sources).toHaveLength(1));
    sources[0].emit('snapshot', { jobId: 'job-1', state: 'running', revision: 'r2', seq: 2 });
    await waitFor(() => expect(card).toHaveTextContent('결과를 만들고 있어요'));
    // A closed stream marks only the connection stale; polling recovers state.
    sources[0].fail();
    await waitFor(() => expect(card).toHaveTextContent('연결이 끊겼어요'));
    await waitFor(() => expect(card).toHaveTextContent('준비된 결과가 있어요'), { timeout: 5000 });
    expect(card).not.toHaveTextContent('연결이 끊겼어요');
    expect(
      screen.getAllByTestId('activity-card').length,
    ).toBe(1);
  });
});

describe('account switching and preferences', () => {
  it('clears prior-owner private state when the account changes', async () => {
    let account = 'acct-a';
    await renderApp(
      baseRoutes({
        '/api/v2/session': () => ({
          status: 200,
          json: { signedIn: true, accountId: account, authorityRevision: 'r1', csrfToken: 'csrf' },
        }),
        '/api/v2/c03/library-list-history': () => ({
          status: 200,
          json: {
            items:
              account === 'acct-a'
                ? [
                    {
                      historyId: 'h1',
                      queryContext: { query: 'owner-a-private-query' },
                      recordedAt: '2026-10-13T00:00:00Z',
                    },
                  ]
                : [],
            clearBoundary: 'b1',
          },
        }),
        '/api/v2/c03/library-list-saved-papers': () => ({ status: 200, json: { items: [] } }),
        '/api/v2/c03/library-list-saved-searches': () => ({ status: 200, json: { items: [] } }),
        '/api/v2/c03/usage-inspect': () => ({
          status: 200,
          json: { items: [{ state: 'unknown', reasonKey: 'usage.unknown' }] },
        }),
        '/api/v2/c02/access-logout': () => ({ status: 200, json: { resourceId: 'x', revision: 'r', requestId: 'q' } }),
      }),
    );
    fireEvent.click(screen.getByTestId('nav-library'));
    await screen.findByText('owner-a-private-query');
    account = 'acct-b';
    fireEvent.click(screen.getByTestId('logout'));
    await waitFor(() => expect(screen.getByTestId('app-shell')).toHaveAttribute('data-account', 'acct-b'));
    // Logout clears the prior owner's private view; no A query text survives.
    expect(screen.getByTestId('search-workspace')).toBeInTheDocument();
    expect(screen.queryByText('owner-a-private-query')).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId('nav-library'));
    await waitFor(() =>
      expect(screen.getByTestId('usage-value')).toHaveTextContent('사용량을 확인할 수 없어요'),
    );
    expect(screen.queryByText('owner-a-private-query')).not.toBeInTheDocument();
  });

  it('keeps a usable appearance selection when browser storage fails', async () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('storage disabled');
    });
    await renderApp(baseRoutes());
    fireEvent.change(screen.getByTestId('appearance-select'), { target: { value: 'dark' } });
    expect(document.documentElement.dataset.theme).toBe('dark');
    fireEvent.change(screen.getByTestId('appearance-select'), { target: { value: 'system' } });
    expect(document.documentElement.dataset.theme).toBeUndefined();
  });
});

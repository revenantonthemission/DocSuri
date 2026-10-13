/**
 * U1 Korean research workspace shell.
 *
 * One find → understand → save → revisit journey over the canonical C13
 * browser bindings. Private state is scoped to the current account: an account
 * change remounts the workspace, so a late A response can never populate B.
 */

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ENTRY_POLICY,
  LIBRARY_POLICY,
  PaperRef,
  QueryContext,
  SEARCH_POLICY,
  SETTINGS_POLICY,
  SessionBootstrap,
  Transport,
  VOCABULARY,
} from './api';
import { Notice, Panel, StatusLine, describeError, focusHeading, notice } from './ui';
import { PaperWorkspace, SavedPaper } from './paper';

type Appearance = 'light' | 'dark' | 'system';
type NavigationItem = {
  routeId: string;
  titleKey: string;
  capabilityId: string;
  available: boolean;
  reasonKey?: string;
};
type SearchHit = {
  paper: PaperRef;
  title: string;
  authors: string[];
  snippet: string;
  sourceUrl: string;
  availability: string;
};
type SearchResponse = {
  hits: SearchHit[];
  page: { nextCursor?: string; snapshotRevision: string };
  outcome: string;
  effectiveModeId: string;
  limitations: string[];
};
type SavedSearch = {
  savedSearchId: string;
  revision: string;
  queryContext: QueryContext;
  label?: string;
};
type HistoryRow = {
  historyId: string;
  queryContext: QueryContext;
  recordedAt: string;
};
type Measure = {
  state: string;
  allocated?: number;
  used?: number;
  reserved?: number;
  remaining?: number;
  periodId?: string;
  reasonKey?: string;
};
type Settings = { revision: string; appearance: Appearance; onboarding: string };

const NAV_COPY: Record<string, string> = {
  search: '검색',
  paper: '논문',
  library: '내 서재',
  settings: '설정',
  usage: '사용량',
  jobs: '작업',
  account: '계정',
};
const OWNER_BOUND = new Set(['library', 'settings', 'usage', 'jobs']);
const APPEARANCE_KEY = 'docsuri.u1.appearance';

function storedAppearance(): Appearance {
  try {
    const value = window.localStorage.getItem(APPEARANCE_KEY);
    return value === 'light' || value === 'dark' || value === 'system' ? value : 'system';
  } catch {
    return 'system';
  }
}

function applyAppearance(value: Appearance) {
  if (value === 'system') delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = value;
}

export default function App({ transport }: { transport?: Transport }) {
  const client = useMemo(() => transport ?? new Transport(), [transport]);
  const [bootstrap, setBootstrap] = useState<SessionBootstrap | null>(null);
  const [bootstrapped, setBootstrapped] = useState(false);
  const [navigation, setNavigation] = useState<NavigationItem[]>([]);
  const [view, setView] = useState<'search' | 'paper' | 'library'>('search');
  const [paper, setPaper] = useState<PaperRef | null>(null);
  const [rerun, setRerun] = useState<QueryContext | null>(null);
  const [appearance, setAppearance] = useState<Appearance>(storedAppearance);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [entryNotice, setEntryNotice] = useState<Notice | null>(null);
  const mainHeading = useRef<HTMLHeadingElement | null>(null);

  const refreshSession = useCallback(async () => {
    const value = await client.bootstrap();
    setBootstrap(value);
    return value;
  }, [client]);

  useEffect(() => {
    applyAppearance(appearance);
  }, [appearance]);

  useEffect(() => {
    refreshSession()
      .catch((error) => setEntryNotice(describeError(error)))
      .finally(() => setBootstrapped(true));
  }, [refreshSession]);

  const signedIn = bootstrap?.signedIn === true;
  const accountId = bootstrap?.accountId ?? 'guest';

  useEffect(() => {
    let active = true;
    client
      .post<{ items: NavigationItem[] }>('/api/v2/c01/host-resolve-navigation', {
        routeId: 'search',
      })
      .then((value) => {
        if (active) setNavigation(value.items);
      })
      .catch(() => {
        if (active) setNavigation([]);
      });
    return () => {
      active = false;
    };
  }, [client, signedIn, accountId]);

  useEffect(() => {
    if (!signedIn) {
      setSettings(null);
      return;
    }
    let active = true;
    client
      .post<Settings>('/api/v2/c03/settings-read', {})
      .then((value) => {
        if (!active) return;
        setSettings(value);
        setAppearance(value.appearance);
        applyAppearance(value.appearance);
      })
      .catch(() => {
        if (active) setSettings(null);
      });
    return () => {
      active = false;
    };
  }, [client, signedIn, accountId]);

  const chooseAppearance = async (value: Appearance) => {
    setAppearance(value);
    try {
      window.localStorage.setItem(APPEARANCE_KEY, value);
    } catch {
      /* storage failure keeps a usable temporary selection, no persistence promise */
    }
    if (signedIn && settings) {
      try {
        const updated = await client.post<Settings>('/api/v2/c03/settings-update', {
          appearance: value,
          policyRef: SETTINGS_POLICY,
          expectedRevision: settings.revision,
        });
        setSettings((current) => (current ? { ...current, ...updated } : current));
      } catch {
        /* the local selection stays; the account preference was not confirmed */
      }
    }
  };

  const openPaper = (value: PaperRef) => {
    setPaper(value);
    setView('paper');
    window.requestAnimationFrame(() => mainHeading.current?.focus());
  };

  const navigationItems = navigation.length
    ? navigation
    : Object.keys(NAV_COPY).map((routeId) => ({ routeId, titleKey: routeId, capabilityId: '', available: routeId === 'search' }));

  return (
    <div className="shell" data-testid="app-shell" data-account={accountId}>
      <a className="skip" href="#main">
        본문으로 건너뛰기
      </a>
      <header className="topbar">
        <p className="brand">DocSuri 연구 공간</p>
        <nav aria-label="주요 이동" data-testid="navigation">
          {navigationItems
            .filter((item) => !OWNER_BOUND.has(item.routeId) || signedIn)
            .map((item) => (
              <button
                key={item.routeId}
                type="button"
                className={view === item.routeId ? 'nav active' : 'nav'}
                aria-current={view === item.routeId ? 'page' : undefined}
                aria-disabled={!item.available}
                disabled={!item.available}
                onClick={() => {
                  if (item.routeId === 'search') setView('search');
                  else if (item.routeId === 'library') setView('library');
                }}
                data-testid={`nav-${item.routeId}`}
              >
                {NAV_COPY[item.routeId] ?? item.titleKey}
              </button>
            ))}
        </nav>
        <div className="session">
          <label className="visually-hidden" htmlFor="appearance-select">
            화면 모드
          </label>
          <select
            id="appearance-select"
            value={appearance}
            onChange={(event) => void chooseAppearance(event.target.value as Appearance)}
            data-testid="appearance-select"
          >
            <option value="system">시스템 설정</option>
            <option value="light">밝게</option>
            <option value="dark">어둡게</option>
          </select>
          {signedIn ? (
            <button
              type="button"
              onClick={async () => {
                try {
                  await client.post('/api/v2/c02/access-logout', {});
                } catch {
                  /* local private state still clears below */
                }
                setBootstrap(null);
                setSettings(null);
                setPaper(null);
                setRerun(null);
                setView('search');
                await refreshSession().catch(() => undefined);
              }}
              data-testid="logout"
            >
              로그아웃
            </button>
          ) : null}
        </div>
      </header>
      <main id="main" tabIndex={-1} ref={mainHeading}>
        {!bootstrapped ? (
          <Panel title="시작하기" titleRef={mainHeading} testId="bootstrapping">
            <p role="status">세션을 확인하고 있어요</p>
          </Panel>
        ) : (
          <>
            {!signedIn ? (
              <EntryPanel client={client} noticeValue={entryNotice} onSignedIn={refreshSession} />
            ) : null}
            {/* Account change remounts the workspace: no prior-owner private state. */}
            <div key={accountId}>
              {view === 'search' ? (
                <SearchWorkspace
                  client={client}
                  signedIn={signedIn}
                  initialQuery={rerun}
                  onOpenPaper={openPaper}
                />
              ) : null}
              {view === 'paper' && paper ? (
                <PaperWorkspace
                  transport={client}
                  paper={paper}
                  signedIn={signedIn}
                  onBack={() => setView('search')}
                />
              ) : null}
              {view === 'library' ? (
                <LibraryWorkspace
                  client={client}
                  signedIn={signedIn}
                  onOpenPaper={openPaper}
                  onRerun={(queryContext) => {
                    setRerun(queryContext);
                    setView('search');
                  }}
                />
              ) : null}
            </div>
          </>
        )}
      </main>
    </div>
  );
}

function EntryPanel({
  client,
  noticeValue,
  onSignedIn,
}: {
  client: Transport;
  noticeValue: Notice | null;
  onSignedIn: () => Promise<SessionBootstrap>;
}) {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [local, setLocal] = useState<Notice | null>(null);
  const [verification, setVerification] = useState<{ challengeId: string; flowBinding: string } | null>(
    null,
  );
  const [proof, setProof] = useState('');
  const heading = useRef<HTMLHeadingElement | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get('action') === 'verify-email') {
      setVerification({
        challengeId: params.get('challengeId') ?? '',
        flowBinding: params.get('flowBinding') ?? '',
      });
      setProof(params.get('proof') ?? '');
    }
  }, []);

  useEffect(() => {
    focusHeading(heading);
  }, []);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!email.trim() || !password) {
      setLocal(notice('alert', '이메일과 비밀번호를 확인해 주세요'));
      return;
    }
    try {
      if (mode === 'login') {
        await client.post('/api/v2/c02/access-login', {
          email,
          password,
          policyRef: ENTRY_POLICY,
        });
        await onSignedIn();
        setPassword('');
      } else {
        await client.post('/api/v2/c02/access-register', {
          email,
          password,
          displayName: '연구자',
          policyRef: ENTRY_POLICY,
        });
        setLocal(
          notice(
            'polite',
            '인증 메일을 보냈어요. 메일의 인증 링크를 열어 주세요 (로컬 메일 저장소)',
          ),
        );
        setPassword('');
      }
    } catch (error) {
      setLocal(describeError(error));
    }
  };

  const verify = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!verification) return;
    try {
      await client.post('/api/v2/c02/access-verify-email', {
        verification: {
          challengeId: verification.challengeId,
          proof,
          flowBinding: verification.flowBinding,
        },
      });
      window.history.replaceState({}, '', window.location.pathname);
      setVerification(null);
      setProof('');
      setLocal(notice('polite', '이메일 인증을 마쳤어요. 로그인해 주세요'));
    } catch (error) {
      setLocal(describeError(error));
    }
  };

  return (
    <Panel title="시작하기" titleRef={heading} testId="entry-panel">
      <StatusLine value={noticeValue ?? local} />
      {verification ? (
        <form onSubmit={verify} className="stack" data-testid="verification-form">
          <p>인증을 완료해 주세요</p>
          <label htmlFor="proof">인증 코드</label>
          <input id="proof" value={proof} onChange={(event) => setProof(event.target.value)} required />
          <button type="submit">인증 완료</button>
        </form>
      ) : (
        <form onSubmit={submit} className="stack">
          <p className="muted">
            게스트로도 검색하고 논문을 읽을 수 있어요. 저장과 요약은 로그인 후 사용할 수 있어요.
          </p>
          <label htmlFor="entry-email">이메일</label>
          <input
            id="entry-email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            data-testid="entry-email"
          />
          <label htmlFor="entry-password">비밀번호</label>
          <input
            id="entry-password"
            type="password"
            autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            data-testid="entry-password"
          />
          <div className="row">
            <button type="submit" data-testid="entry-submit">
              {mode === 'login' ? '로그인' : '가입하기'}
            </button>
            <button
              type="button"
              className="link"
              onClick={() => setMode(mode === 'login' ? 'register' : 'login')}
              data-testid="entry-switch"
            >
              {mode === 'login' ? '처음이신가요? 가입하기' : '이미 계정이 있나요? 로그인'}
            </button>
          </div>
        </form>
      )}
    </Panel>
  );
}

function SearchWorkspace({
  client,
  signedIn,
  initialQuery,
  onOpenPaper,
}: {
  client: Transport;
  signedIn: boolean;
  initialQuery: QueryContext | null;
  onOpenPaper: (paper: PaperRef) => void;
}) {
  const heading = useRef<HTMLHeadingElement | null>(null);
  const [draft, setDraft] = useState(initialQuery?.query ?? '');
  const [order, setOrder] = useState(initialQuery?.orderId ?? 'relevance');
  const [author, setAuthor] = useState('');
  const [yearFrom, setYearFrom] = useState('');
  const [yearTo, setYearTo] = useState('');
  const [submitted, setSubmitted] = useState<QueryContext | null>(null);
  const [response, setResponse] = useState<SearchResponse | null>(null);
  const [state, setState] = useState<'idle' | 'loading' | 'ready' | 'empty' | 'error'>('idle');
  const [error, setError] = useState<Notice | null>(null);
  const [savedSearch, setSavedSearch] = useState<Notice | null>(null);
  const sequence = useRef(0);

  useEffect(() => {
    if (initialQuery) {
      setDraft(initialQuery.query);
      setOrder(initialQuery.orderId);
      setState('idle');
      setResponse(null);
    }
    focusHeading(heading);
  }, [initialQuery]);

  const runSearch = async (event?: React.FormEvent) => {
    event?.preventDefault();
    if (!draft.trim()) {
      setError(notice('alert', '검색어를 입력해 주세요'));
      return;
    }
    const filters: QueryContext['filters'] = [];
    if (author.trim()) {
      filters.push({ filterId: 'author', operatorId: 'contains', values: [author.trim()] });
    }
    const from = Number.parseInt(yearFrom, 10);
    const to = Number.parseInt(yearTo, 10);
    if (Number.isInteger(from) && Number.isInteger(to) && from <= to) {
      filters.push({ filterId: 'year', operatorId: 'between', values: [from, to] });
    }
    const query: QueryContext = {
      query: draft,
      modeId: 'lexical',
      orderId: order,
      filters,
      vocabularyRevision: VOCABULARY,
      policyRef: SEARCH_POLICY,
    };
    const request = ++sequence.current;
    setSubmitted(query);
    setState('loading');
    setError(null);
    try {
      const value = await client.post<SearchResponse>('/api/v2/c05/search', {
        query,
        page: { limit: 10 },
      });
      // A late response for a superseded search never replaces the active set.
      if (request !== sequence.current) return;
      setResponse(value);
      setState(value.hits.length === 0 ? 'empty' : 'ready');
    } catch (failure) {
      if (request !== sequence.current) return;
      setResponse(null);
      setState('error');
      setError(describeError(failure));
    }
  };

  const saveSearch = async () => {
    if (!submitted) return;
    try {
      await client.post<SavedSearch>('/api/v2/c03/library-save-search', {
        queryContext: submitted,
      });
      setSavedSearch(notice('polite', '검색 조건을 저장했어요'));
    } catch (failure) {
      setSavedSearch(describeError(failure));
    }
  };

  return (
    <Panel title="논문 검색" titleRef={heading} testId="search-workspace">
      <form className="stack" onSubmit={runSearch} data-testid="search-form">
        <label htmlFor="search-query">검색어</label>
        <input
          id="search-query"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          data-testid="search-query"
        />
        <div className="row">
          <label htmlFor="search-mode">검색 방식</label>
          <select id="search-mode" value="lexical" data-testid="search-mode">
            <option value="lexical">어휘 검색</option>
          </select>
          <label htmlFor="search-order">정렬</label>
          <select
            id="search-order"
            value={order}
            onChange={(event) => setOrder(event.target.value)}
            data-testid="search-order"
          >
            <option value="relevance">관련도</option>
            <option value="newest">최신순</option>
          </select>
        </div>
        <details data-testid="search-filters">
          <summary>검색 필터</summary>
          <div className="row">
            <label htmlFor="filter-author">저자</label>
            <input
              id="filter-author"
              value={author}
              onChange={(event) => setAuthor(event.target.value)}
              data-testid="filter-author"
            />
            <label htmlFor="filter-year-from">연도</label>
            <input
              id="filter-year-from"
              inputMode="numeric"
              value={yearFrom}
              onChange={(event) => setYearFrom(event.target.value)}
              data-testid="filter-year-from"
            />
            <span aria-hidden="true">–</span>
            <label className="visually-hidden" htmlFor="filter-year-to">
              연도 끝
            </label>
            <input
              id="filter-year-to"
              inputMode="numeric"
              value={yearTo}
              onChange={(event) => setYearTo(event.target.value)}
              data-testid="filter-year-to"
            />
          </div>
        </details>
        <div className="row">
          <button type="submit" data-testid="search-submit">
            검색
          </button>
          <button
            type="button"
            onClick={() => void runSearch()}
            data-testid="search-retry"
            disabled={state !== 'error'}
          >
            검색 다시 시도
          </button>
          <button
            type="button"
            onClick={saveSearch}
            disabled={!signedIn || !submitted || state === 'loading'}
            data-testid="save-search"
          >
            검색 조건 저장
          </button>
        </div>
      </form>
      <StatusLine value={error} />
      {savedSearch ? <p role="status">{savedSearch.text}</p> : null}
      <div aria-live="polite" data-testid="search-status">
        {state === 'loading' ? '검색 중이에요' : null}
        {state === 'empty' ? '일치하는 논문이 없어요' : null}
        {state === 'ready' && response ? `${response.hits.length}개의 결과를 찾았어요` : null}
      </div>
      {response && (state === 'ready' || state === 'loading') ? (
        <div data-testid="search-results">
          {state === 'loading' ? <p className="muted">이전 검색 결과예요</p> : null}
          {response.outcome !== 'complete' || response.effectiveModeId !== 'lexical' ? (
            <p className="muted">일부 결과만 표시하고 있어요 ({response.effectiveModeId})</p>
          ) : null}
          <ul>
            {response.hits.map((hit) => (
              <li key={hit.paper.versionId} data-testid="result-item">
                <button type="button" onClick={() => onOpenPaper(hit.paper)}>
                  {hit.title}
                </button>
                <p className="muted">
                  {hit.authors.join(', ')} · {hit.paper.versionId} · {hit.availability}
                </p>
                <p>{hit.snippet}</p>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </Panel>
  );
}

function LibraryWorkspace({
  client,
  signedIn,
  onOpenPaper,
  onRerun,
}: {
  client: Transport;
  signedIn: boolean;
  onOpenPaper: (paper: PaperRef) => void;
  onRerun: (query: QueryContext) => void;
}) {
  const heading = useRef<HTMLHeadingElement | null>(null);
  const [papers, setPapers] = useState<SavedPaper[]>([]);
  const [searches, setSearches] = useState<SavedSearch[]>([]);
  const [history, setHistory] = useState<HistoryRow[]>([]);
  const [boundary, setBoundary] = useState<string | null>(null);
  const [measure, setMeasure] = useState<Measure | null>(null);
  const [error, setError] = useState<Notice | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [local, setLocal] = useState<Notice | null>(null);

  useEffect(() => {
    focusHeading(heading);
  }, []);

  const load = useCallback(async () => {
    if (!signedIn) return;
    try {
      const [paperPage, searchPage, historyPage, usage] = await Promise.all([
        client.post<{ items: SavedPaper[] }>('/api/v2/c03/library-list-saved-papers', {
          page: { limit: 20 },
        }),
        client.post<{ items: SavedSearch[] }>('/api/v2/c03/library-list-saved-searches', {
          page: { limit: 20 },
        }),
        client.post<{ items: HistoryRow[]; clearBoundary: string }>('/api/v2/c03/library-list-history', {
          page: { limit: 20 },
        }),
        client.post<{ items: Measure[] }>('/api/v2/c03/usage-inspect', { page: {} }),
      ]);
      setPapers(paperPage.items);
      setSearches(searchPage.items);
      setHistory(historyPage.items);
      setBoundary(historyPage.clearBoundary);
      setMeasure(usage.items[0] ?? null);
    } catch (failure) {
      setError(describeError(failure));
    }
  }, [client, signedIn]);

  useEffect(() => {
    void load();
  }, [load]);

  const removePaper = async (record: SavedPaper) => {
    try {
      await client.post('/api/v2/c03/library-remove-saved-paper', {
        savedPaperId: record.savedPaperId,
        expectedRevision: record.revision,
      });
      await load();
    } catch (failure) {
      setLocal(describeError(failure));
      await load();
    }
  };

  const clearHistory = async () => {
    if (!boundary) return;
    try {
      await client.post('/api/v2/c03/library-clear-history', {
        policyRef: LIBRARY_POLICY,
        expectedRevision: boundary,
      });
      setConfirming(false);
      setLocal(notice('polite', '검색 기록을 지웠어요'));
      await load();
    } catch (failure) {
      setLocal(describeError(failure));
      setConfirming(false);
      await load();
    }
  };

  if (!signedIn) {
    return (
      <Panel title="내 서재" titleRef={heading} testId="library-panel">
        <p>로그인하면 저장한 논문과 검색 조건을 다시 볼 수 있어요.</p>
      </Panel>
    );
  }

  return (
    <Panel title="내 서재" titleRef={heading} testId="library-panel">
      <StatusLine value={error ?? local} />
      <h3>저장한 논문</h3>
      {papers.length === 0 ? <p className="muted">저장한 논문이 없어요</p> : null}
      <ul data-testid="saved-papers">
        {papers.map((record) => (
          <li key={record.savedPaperId} data-testid="saved-paper">
            <button
              type="button"
              onClick={() => record.savedPaper && onOpenPaper(record.savedPaper)}
            >
              {record.savedTitle ?? record.savedPaperId}
            </button>
            <span className="muted"> · {record.sourceDisposition}</span>
            <button type="button" onClick={() => void removePaper(record)} data-testid="remove-saved-paper">
              저장 취소
            </button>
          </li>
        ))}
      </ul>
      <h3>저장한 검색 조건</h3>
      {searches.length === 0 ? <p className="muted">저장한 검색 조건이 없어요</p> : null}
      <ul data-testid="saved-searches">
        {searches.map((record) => (
          <li key={record.savedSearchId} data-testid="saved-search">
            <span>{record.queryContext.query}</span>
            <button type="button" onClick={() => onRerun(record.queryContext)} data-testid="rerun-query">
              다시 검색
            </button>
          </li>
        ))}
      </ul>
      <h3>검색 기록</h3>
      {history.length === 0 ? <p className="muted">검색 기록이 없어요</p> : null}
      <ul data-testid="history-list">
        {history.map((row) => (
          <li key={row.historyId}>{row.queryContext.query}</li>
        ))}
      </ul>
      {history.length > 0 && !confirming ? (
        <button type="button" onClick={() => setConfirming(true)} data-testid="clear-history">
          기록 지우기
        </button>
      ) : null}
      {confirming ? (
        <div role="group" aria-label="검색 기록 지우기 확인" data-testid="history-confirm">
          <p>검색 기록만 지워요. 저장한 논문과 검색 조건은 그대로 남아요.</p>
          <button type="button" onClick={() => setConfirming(false)}>
            취소
          </button>
          <button type="button" onClick={() => void clearHistory()} data-testid="confirm-clear">
            기록 지우기
          </button>
        </div>
      ) : null}
      <h3>사용량</h3>
      <p data-testid="usage-value">
        {measure?.state === 'known'
          ? `남은 사용량 ${measure.remaining} / ${measure.allocated} (${measure.periodId})`
          : '사용량을 확인할 수 없어요'}
      </p>
    </Panel>
  );
}

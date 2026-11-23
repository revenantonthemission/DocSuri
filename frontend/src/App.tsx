/**
 * Korean research workspace shell.
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
  retryTransient,
} from './api';
import { Notice, Panel, StatusLine, describeError, focusHeading, notice } from './ui';
import { PaperWorkspace, SavedPaper } from './paper';

import type { WorkspaceCapabilityCatalog } from '../types/wire/dtos';
import { AuthenticationPanel, takeProofLink } from './auth';
import { AccountControls, LifecycleProgress } from './account-controls';
import { PersonalControls } from './personal-controls';
import { UsageControls } from './usage-controls';
import { LibraryControls } from './library-controls';
import { setLibraryPolicy } from './u3-corpus/api';
import { CorpusWorkspace } from './u3-corpus/corpus-workspace';
import { ResearchWorkspace } from './u4-research/research-workspace';
import { readJobLink } from './u4-research/jobs';
import { TopicsView } from './u5-topics/topics-view';
import { findExportCapability } from './u6-export/api';
import { ExportView } from './u6-export/export-view';
import { AnnouncerProvider } from './u8-shell/announcer';
import { isCompleteAnswer, isPublicPage, statesOf } from './u8-shell/capabilities';
import {
  EARLIER_ASSEMBLY,
  captureReturn,
  claimRouteFocus,
  restoreReturn,
  returnTarget,
  useRouteFocus,
  type FocusRequest,
  type ReturnPoint,
} from './u8-shell/focus';
import { Footer } from './u8-shell/footer';
import { WorkspaceNavigation, type NavigationStatus } from './u8-shell/navigation';
import { useOwnerBoundary } from './u8-shell/owner-boundary';
import type { NavItem } from './u8-shell/reasons';
import shellStyles from './u8-shell/shell.module.css';
import { JobsView } from './u8-jobs/jobs-view';
import { OperationsView } from './u8-operations/operations-view';
import { CallbackPage, takeCallbackArrival } from './u8-entry/callback-page';
import { EmailChangeProof } from './u8-entry/email-change-proof';
import {
  CompleteEntry,
  controlPolicyFor,
  takeFragmentProof,
  type Proof,
} from './u8-entry/entry-panel';
import { AdminMfaPrompt } from './u8-entry/first-sign-in';

type Appearance = 'light' | 'dark' | 'system';
type NavigationItem = NavItem;
type View =
  | 'search'
  | 'paper'
  | 'library'
  | 'account'
  | 'settings'
  | 'usage'
  | 'research'
  | 'novelty'
  | 'topics'
  | 'export'
  | 'jobs'
  | 'operations';
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

const APPEARANCE_KEY = 'docsuri.u1.appearance';
const AUTHORITY_CHANNEL = 'docsuri.authority-boundary';
type AuthorityNotice = { kind: 'authority-changed'; nonce: string };

function isAuthorityNotice(value: unknown): value is AuthorityNotice {
  if (!value || typeof value !== 'object') return false;
  const candidate = value as Partial<AuthorityNotice>;
  return (
    Object.keys(candidate).length === 2 &&
    candidate.kind === 'authority-changed' &&
    typeof candidate.nonce === 'string' &&
    /^[a-f\d-]{36}$/i.test(candidate.nonce)
  );
}

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
  const [catalogReady, setCatalogReady] = useState(false);
  const [catalog, setCatalog] = useState<WorkspaceCapabilityCatalog | null>(null);
  // The raw capability answer: the complete assembly answers a caller with no full
  // session with the public projection (BR5.9), which carries no catalog rows.
  const [capabilityAnswer, setCapabilityAnswer] = useState<unknown>(null);
  const complete = isCompleteAnswer(capabilityAnswer);
  const capabilityStates = useMemo(() => statesOf(capabilityAnswer), [capabilityAnswer]);
  const [navStatus, setNavStatus] = useState<NavigationStatus>('loading');
  const [navAttempt, setNavAttempt] = useState(0);
  // The provider's answer leaves the address in this first render, before the first commit
  // and before the capability, session and navigation reads (L1-15).
  const [callbackProvider, setCallbackProvider] = useState<string | null>(takeCallbackArrival);
  // An email link's proof leaves the address in this first render too, whatever the
  // session (L1-1). A kept proof waits for one owner change only (`proofWait`).
  const [emailProof, setEmailProof] = useState<Proof | null>(takeFragmentProof);
  const proofWait = useRef({ baseline: null as string | null, waited: false, shown: false });
  const [completeNotice, setCompleteNotice] = useState<Notice | null>(null);
  const [focusRequest, setFocusRequest] = useState<FocusRequest | null>(null);
  const requestFocus = useCallback((testId?: string) => {
    setFocusRequest((current) => ({
      id: (current?.id ?? 0) + 1,
      ...(testId !== undefined ? { testId } : {}),
    }));
  }, []);
  const [arrival, setArrival] = useState<unknown>(undefined);
  const returnPoint = useRef<ReturnPoint | null>(null);
  const [boundary, setBoundary] = useState(0);
  const [lifecycleId, setLifecycleId] = useState<string | null>(null);
  const [initialProof, setInitialProof] = useState(takeProofLink);
  const [proofActive, setProofActive] = useState(() => !!initialProof);
  const [appearanceNotice, setAppearanceNotice] = useState<Notice | null>(null);
  const [bootstrap, setBootstrap] = useState<SessionBootstrap | null>(null);
  const [bootstrapped, setBootstrapped] = useState(false);
  const [navigation, setNavigation] = useState<NavigationItem[]>([]);
  const [view, setView] = useState<View>(() => {
    const job = readJobLink();
    return job ? (job.kind === 'research-turn' ? 'research' : 'novelty') : 'search';
  });
  useEffect(() => {
    const followResearchLink = () => {
      const target = readJobLink();
      if (target) setView(target.kind === 'research-turn' ? 'research' : 'novelty');
    };
    window.addEventListener('hashchange', followResearchLink);
    return () => window.removeEventListener('hashchange', followResearchLink);
  }, []);
  const [paper, setPaper] = useState<PaperRef | null>(null);
  const [rerun, setRerun] = useState<QueryContext | null>(null);
  const searchContext = useRef<QueryContext | null>(null);
  const [appearance, setAppearance] = useState<Appearance>(storedAppearance);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [entryNotice, setEntryNotice] = useState<Notice | null>(null);
  const mainHeading = useRef<HTMLHeadingElement | null>(null);
  const authorityChannel = useRef<BroadcastChannel | null>(null);

  const controlPolicy = catalog?.capabilities.find(
    (value) => value.id === 'account.controls' && value.state === 'available',
  )?.policy;
  const isControls = !!controlPolicy;
  // The complete workspace's citation save sends the reading page's own library policy
  // (U8, the person's decision of 2026-10-23); every earlier realm keeps U3's built one.
  setLibraryPolicy(complete ? controlPolicy : undefined);
  const researchCapability = catalog?.capabilities.find(
    (value) => value.id === 'research' && ['available', 'degraded'].includes(value.state),
  );
  const noveltyCapability = catalog?.capabilities.find(
    (value) => value.id === 'novelty' && ['available', 'degraded'].includes(value.state),
  );
  const topicsCapability = catalog?.capabilities.find(
    (value) => value.id === 'topics.digest' && ['available', 'degraded'].includes(value.state),
  );
  const exportCapability = findExportCapability(catalog);
  const operationsPolicy = catalog?.capabilities.find(
    (value) => value.id === 'operations.ledger',
  )?.policy;
  // The U3 corpus workspace replaces the live search/reading surfaces when the
  // corpus owner capabilities are installed in this realm.
  const isCorpusWorkspace =
    catalog?.capabilities.some(
      (value) => value.id === 'corpus.maintenance' && value.state === 'available',
    ) ?? false;

  const readCapabilities = useCallback(
    () =>
      client
        .get<unknown>('/api/v2/capabilities')
        .then((value) => {
          setCapabilityAnswer(value);
          setCatalog(isPublicPage(value) ? null : (value as WorkspaceCapabilityCatalog));
        })
        .catch(() => {
          setCapabilityAnswer(null);
          setCatalog(null);
        }),
    [client],
  );
  useEffect(() => {
    void readCapabilities().finally(() => setCatalogReady(true));
  }, [readCapabilities]);
  useEffect(
    () =>
      client.subscribe(() => {
        setBoundary(client.generation);
        setBootstrap(null);
        setSettings(null);
        setPaper(null);
        setRerun(null);
        searchContext.current = null;
      }),
    [client],
  );

  const refreshSession = useCallback(async () => {
    const value = await client.bootstrap();
    setBootstrap(value);
    return value;
  }, [client]);

  const announceAuthorityChange = useCallback(() => {
    const event: AuthorityNotice = { kind: 'authority-changed', nonce: crypto.randomUUID() };
    try {
      if (authorityChannel.current) authorityChannel.current.postMessage(event);
      else {
        // The fallback event contains no identity, session, proof or form data.
        window.localStorage.setItem(AUTHORITY_CHANNEL, JSON.stringify(event));
        window.localStorage.removeItem(AUTHORITY_CHANNEL);
      }
    } catch {
      // Restricted storage cannot prevent local invalidation; foreground checks remain.
    }
  }, []);

  const authorityChanged = useCallback(async () => {
    client.invalidateBoundary();
    announceAuthorityChange();
    const value = await refreshSession();
    // A completion or failure notice belongs to the entry that just ended;
    // a signed-in session clears it rather than replaying stale text.
    if (value.signedIn) setEntryNotice(null);
    return value;
  }, [client, announceAuthorityChange, refreshSession]);

  useEffect(() => {
    let active = true;
    const recheck = () => {
      void refreshSession().catch((error) => {
        if (active) setEntryNotice(describeError(error));
      });
    };
    const receive = (value: unknown) => {
      if (!isAuthorityNotice(value)) return;
      // Remount protected forms immediately, before a possibly delayed network read.
      client.invalidateBoundary();
      setLifecycleId(null);
      setInitialProof(null);
      setProofActive(false);
      setAppearanceNotice(null);
      recheck();
    };
    let channel: BroadcastChannel | null = null;
    try {
      if (typeof window.BroadcastChannel === 'function') {
        channel = new window.BroadcastChannel(AUTHORITY_CHANNEL);
        channel.onmessage = (event: MessageEvent<unknown>) => receive(event.data);
        authorityChannel.current = channel;
      }
    } catch {
      // A disabled channel uses the same non-secret storage-event fallback.
    }
    const storage = (event: StorageEvent) => {
      if (event.key !== AUTHORITY_CHANNEL || !event.newValue || event.newValue.length > 160) return;
      try {
        receive(JSON.parse(event.newValue));
      } catch {
        // Ignore malformed notifications; never interpret them as account data.
      }
    };
    const leave = () => {
      client.invalidateBoundary();
    };
    const restore = (event: PageTransitionEvent) => {
      if (event.persisted) recheck();
    };
    const foreground = () => {
      if (document.visibilityState === 'visible') recheck();
    };
    window.addEventListener('storage', storage);
    window.addEventListener('focus', foreground);
    document.addEventListener('visibilitychange', foreground);
    window.addEventListener('pagehide', leave);
    window.addEventListener('pageshow', restore);
    return () => {
      active = false;
      channel?.close();
      if (authorityChannel.current === channel) authorityChannel.current = null;
      window.removeEventListener('storage', storage);
      window.removeEventListener('focus', foreground);
      document.removeEventListener('visibilitychange', foreground);
      window.removeEventListener('pagehide', leave);
      window.removeEventListener('pageshow', restore);
    };
  }, [client, refreshSession]);

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
    retryTransient(() =>
      client.post<{ items: NavigationItem[] }>('/api/v2/c01/host-resolve-navigation', {
        routeId: 'search',
      }),
    )
      .then((value) => {
        if (!active) return;
        setNavigation(value.items);
        setNavStatus('resolved');
      })
      .catch(() => {
        if (!active) return;
        setNavigation([]);
        setNavStatus('error');
      });
    return () => {
      active = false;
    };
  }, [client, signedIn, accountId, navAttempt]);

  // The complete assembly answers by session (BR5.9), so its capability list is read
  // again whenever the owner changes; earlier assemblies keep their single read.
  const owner = `${signedIn ? 'member' : 'guest'}:${accountId}`;
  const seenOwner = useRef(owner);
  useEffect(() => {
    if (seenOwner.current === owner) return;
    seenOwner.current = owner;
    if (complete) void readCapabilities();
  }, [owner, complete, readCapabilities]);
  const clearOwnerViews = useCallback(() => {
    returnPoint.current = null;
    setArrival(undefined);
  }, []);
  useOwnerBoundary(complete ? owner : EARLIER_ASSEMBLY, clearOwnerViews);
  // A kept email-link proof waits for one owner change only: an email change for the next
  // sign-in, the other kinds for the next sign-out. Any other owner change, and any owner
  // change after the proof was shown, drops it, so it never reaches another account's
  // session (Step 91(l)). The first settled owner is the baseline, not a change.
  useEffect(() => {
    if (!complete || !bootstrapped || !catalogReady) return;
    const wait = proofWait.current;
    if (wait.baseline === null || wait.baseline === owner) {
      wait.baseline = owner;
      return;
    }
    wait.baseline = owner;
    if (!emailProof) return;
    const expected = emailProof.action === 'email-change' ? signedIn : !signedIn;
    if (wait.shown || wait.waited || !expected) setEmailProof(null);
    else wait.waited = true;
  }, [owner, signedIn, complete, bootstrapped, catalogReady, emailProof]);
  const showEmailChange = complete && signedIn && emailProof?.action === 'email-change';
  // Once shown, the proof is dropped at the next owner change; the entry that sign-out
  // mounts in that same render must not start from it (Step 92(j)).
  const [proofShown, setProofShown] = useState(false);
  useEffect(() => {
    if (!showEmailChange || proofWait.current.shown) return;
    proofWait.current.shown = true;
    setProofShown(true);
    requestFocus('email-change-proof');
  }, [showEmailChange, requestFocus]);
  useRouteFocus(complete ? view : EARLIER_ASSEMBLY, complete ? focusRequest : null);

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
    if (signedIn) {
      try {
        const currentSettings =
          settings ?? (await client.post<Settings>('/api/v2/c03/settings-read', {}));
        const updated = await client.post<Settings>('/api/v2/c03/settings-update', {
          appearance: value,
          policyRef: SETTINGS_POLICY,
          expectedRevision: currentSettings.revision,
        });
        setSettings((current) => (current ? { ...current, ...updated } : current));
        setAppearance(value);
        setAppearanceNotice(notice('polite', '화면 모드를 저장했어요'));
      } catch {
        setAppearanceNotice(
          notice('alert', '화면 모드는 임시 변경이에요. 계정에 저장되지 않았어요'),
        );
      }
    }
  };

  const openPaper = (value: PaperRef) => {
    // BR5.8: a paper opened from a result returns to that result's place and focus.
    if (complete && view !== 'paper') returnPoint.current = captureReturn(view);
    setPaper(value);
    setView('paper');
    window.requestAnimationFrame(() => mainHeading.current?.focus());
  };

  const closePaper = () => {
    const point = returnPoint.current;
    returnPoint.current = null;
    if (!point) {
      setView('search');
      return;
    }
    setView(point.view === 'library' ? 'library' : 'search');
    // The route change returns focus to the result the paper was opened from (BR5.8).
    claimRouteFocus(returnTarget(point));
    restoreReturn(point);
  };

  const selectRoute = (routeId: string) => {
    if (routeId === 'search') setView('search');
    else if (routeId === 'library') setView('library');
    else if (isControls && ['account', 'settings', 'usage'].includes(routeId))
      setView(routeId as 'account' | 'settings' | 'usage');
    else if (['research', 'novelty'].includes(routeId)) setView(routeId as 'research' | 'novelty');
    else if (routeId === 'topics' && topicsCapability) setView('topics');
    else if (routeId === 'export' && exportCapability) setView('export');
    else if (complete && (routeId === 'jobs' || routeId === 'operations')) setView(routeId);
    focusHeading(mainHeading);
  };

  // An entry that needs a session takes the person to the sign-in form (BR5.2).
  const requireSignIn = () => {
    // When the view changes, the route change lands on the sign-in field, not on the
    // heading the search view focuses as it mounts (Step 91(f)).
    if (complete && view !== 'search')
      claimRouteFocus(() => document.getElementById('entry-email'));
    setView('search');
    window.requestAnimationFrame(() => document.getElementById('entry-email')?.focus());
  };

  const leaveCallback = useCallback((answer?: unknown) => {
    window.history.replaceState(null, '', '/search');
    setCallbackProvider(null);
    if (answer !== undefined) setArrival(answer);
  }, []);
  const arrive = useCallback((answer: unknown) => leaveCallback(answer), [leaveCallback]);
  // The arrival page leaves with its focused callback-back: the entry's heading takes the
  // focus, or the view's first heading for a signed-in person (Step 91(g)).
  const returnFromCallback = useCallback(() => {
    leaveCallback();
    if (signedIn) requestFocus();
    else requestFocus('complete-entry');
  }, [leaveCallback, requestFocus, signedIn]);
  // The arrival page's maintenance notice leaves with its 관리자 로그인 for the sign-in
  // form, its email field focused (NFR1.3). It requests no heading focus, so the route
  // focus does not take the focus back from the field; the sign-in form is asked for one
  // frame later, after the search view that mounts in the page's place has focused its
  // own heading in its first frame.
  const signInAsAdministratorFromCallback = () => {
    leaveCallback();
    window.requestAnimationFrame(requireSignIn);
  };

  const signOut = async () => {
    try {
      await client.post('/api/v2/c02/access-logout', {});
    } catch {
      /* local private state still clears below */
    }
    client.invalidateBoundary();
    announceAuthorityChange();
    setBootstrap(null);
    setLifecycleId(null);
    setSettings(null);
    setPaper(null);
    setRerun(null);
    setView('search');
    if (window.location.hash.startsWith('#research-job?'))
      window.history.replaceState(null, '', window.location.pathname);
    await refreshSession().catch(() => undefined);
    // The session read remounts the workspace; focus then lands on the entry's heading,
    // even when the view was already search (Step 91(g)).
    if (complete) requestFocus('complete-entry');
  };

  // An administrator's setup-only session reads only the public projection until the
  // second factor is enrolled (BR3.8); it sees the enrollment prompt and nothing else.
  const setupOnly = complete && signedIn && isPublicPage(capabilityAnswer);
  const entryPolicy = controlPolicy ?? controlPolicyFor(window.location.origin);

  const shell = (
    <div className="shell" data-testid="app-shell" data-account={accountId}>
      <a className="skip" href="#main">
        본문으로 건너뛰기
      </a>
      <header className="topbar">
        <p className="brand">DocSuri 연구 공간</p>
        <WorkspaceNavigation
          items={navigation}
          status={navStatus}
          current={view}
          signedIn={signedIn}
          catalogReady={catalogReady}
          complete={complete}
          onSelect={selectRoute}
          onRequireSignIn={requireSignIn}
          onRetry={() => {
            setNavStatus('loading');
            setNavAttempt((value) => value + 1);
          }}
        />
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
            <button type="button" onClick={() => void signOut()} data-testid="logout">
              로그아웃
            </button>
          ) : null}
        </div>
      </header>
      <main id="main" tabIndex={-1} ref={mainHeading}>
        {!bootstrapped || !catalogReady ? (
          <Panel title="시작하기" titleRef={mainHeading} testId="bootstrapping">
            <p role="status">세션을 확인하고 있어요</p>
          </Panel>
        ) : callbackProvider ? (
          <CallbackPage
            client={client}
            provider={callbackProvider}
            onArrived={arrive}
            onBack={returnFromCallback}
            states={capabilityStates}
            onAdministratorSignIn={signInAsAdministratorFromCallback}
          />
        ) : setupOnly ? (
          <AdminMfaPrompt
            client={client}
            policy={entryPolicy}
            mode="setup"
            onSignInAgain={() => void signOut()}
          />
        ) : (
          <>
            {complete && !signedIn ? (
              <CompleteEntry
                client={client}
                states={capabilityStates}
                {...(arrival !== undefined ? { initialAnswer: arrival } : {})}
                initialProof={proofShown ? null : emailProof}
                initialNotice={completeNotice}
                onProofTaken={() => setEmailProof(null)}
                onSignedIn={async () => {
                  const value = await authorityChanged();
                  await readCapabilities();
                  setCompleteNotice(null);
                  // The completed sign-in lands on the destination's first heading; a kept
                  // email-change proof takes the focus itself as it shows (Step 91(g), (l)).
                  if (emailProof?.action !== 'email-change') requestFocus();
                  return value;
                }}
              />
            ) : // The complete assembly no longer shows U2's sign-in panel for a query-string
            // proof (your answer of 2026-11-11, "Stop showing it"): its links arrive in the
            // fragment. Every earlier assembly keeps this branch as built.
            !signedIn || (!complete && isControls && proofActive) ? (
              isControls ? (
                <AuthenticationPanel
                  key={`entry-${boundary}`}
                  client={client}
                  policy={controlPolicy!}
                  noticeValue={entryNotice}
                  onSignedIn={authorityChanged}
                  onLifecycle={setLifecycleId}
                  initialProof={initialProof}
                  // A pending protected link survives the bootstrap boundary
                  // remount; it clears only when its flow actually completes.
                  onProofConsumed={() => setProofActive(true)}
                  onProofComplete={() => {
                    setInitialProof(null);
                    setProofActive(false);
                    // The authority refresh remounts this panel; the completion
                    // notice survives at the shell so it is never lost.
                    setEntryNotice(
                      notice('polite', '인증 요청을 확인했어요. 필요한 경우 다시 로그인해 주세요'),
                    );
                  }}
                />
              ) : (
                <EntryPanel
                  client={client}
                  noticeValue={entryNotice}
                  onSignedIn={authorityChanged}
                  initialProof={initialProof}
                  onProofConsumed={() => setInitialProof(null)}
                />
              )
            ) : null}
            {/* Account change remounts the workspace: no prior-owner private state. */}
            <div key={`${accountId}:${boundary}`} className="workspace-content">
              {showEmailChange && emailProof ? (
                <EmailChangeProof
                  client={client}
                  proof={emailProof}
                  onDone={() => {
                    // The route ended the session: ask for a sign-in with the new address.
                    setEmailProof(null);
                    setCompleteNotice(
                      notice(
                        'polite',
                        '이메일 변경을 확인했습니다. 새 이메일 주소로 다시 로그인해 주세요.',
                      ),
                    );
                    void authorityChanged()
                      .catch(() => undefined)
                      .finally(() => requestFocus('complete-entry'));
                  }}
                  onOpenAccount={() => {
                    // Opening 계정 from the panel lands on its first heading even when the
                    // view was already 계정 and so does not change (Step 91(g)).
                    setEmailProof(null);
                    setView('account');
                    requestFocus();
                  }}
                  onLeave={() => {
                    // The panel leaves with its focused 닫기: the view's first heading, else
                    // #main, takes the focus, never the page body (Step 91(g)).
                    setEmailProof(null);
                    requestFocus();
                  }}
                />
              ) : null}
              <StatusLine value={appearanceNotice} />
              {isControls && lifecycleId ? (
                <LifecycleProgress client={client} id={lifecycleId} />
              ) : null}
              {signedIn && isControls && view === 'account' ? (
                <AccountControls
                  client={client}
                  policy={controlPolicy!}
                  onAuthorityChange={authorityChanged}
                  onLifecycle={setLifecycleId}
                  {...(complete ? { isCompleteApp: true } : {})}
                />
              ) : null}
              {signedIn && isControls && view === 'settings' ? (
                <PersonalControls
                  client={client}
                  policy={controlPolicy!}
                  onAppearance={setAppearance}
                />
              ) : null}
              {signedIn && isControls && view === 'usage' ? (
                <UsageControls client={client} policy={controlPolicy!} />
              ) : null}
              {signedIn && researchCapability ? (
                <ResearchWorkspace
                  client={client}
                  purpose="research"
                  policy={researchCapability.policy}
                  degraded={researchCapability.state === 'degraded'}
                  synthetic={researchCapability.modeIds.includes('synthetic-only')}
                  active={view === 'research'}
                />
              ) : null}
              {signedIn && noveltyCapability ? (
                <ResearchWorkspace
                  client={client}
                  purpose="novelty"
                  policy={noveltyCapability.policy}
                  degraded={noveltyCapability.state === 'degraded'}
                  synthetic={noveltyCapability.modeIds.includes('synthetic-only')}
                  active={view === 'novelty'}
                  exportCapability={exportCapability}
                />
              ) : null}
              {signedIn && topicsCapability && view === 'topics' ? (
                <TopicsView
                  client={client}
                  degraded={topicsCapability.state === 'degraded'}
                  synthetic={topicsCapability.modeIds.includes('synthetic-only')}
                />
              ) : null}
              {signedIn && exportCapability && view === 'export' ? (
                <ExportView client={client} capability={exportCapability} />
              ) : null}
              {signedIn && complete && view === 'jobs' ? (
                <JobsView
                  client={client}
                  onOpenResearch={() => setView('research')}
                  onOpenView={(kind) => setView(kind)}
                />
              ) : null}
              {signedIn && complete && view === 'operations' && operationsPolicy ? (
                <OperationsView
                  client={client}
                  account={accountId}
                  controlPolicy={entryPolicy}
                  operationsPolicy={operationsPolicy}
                  onSignInAgain={() => void signOut()}
                />
              ) : null}
              {view === 'search' && isCorpusWorkspace ? (
                <CorpusWorkspace client={client} signedIn={signedIn} />
              ) : null}
              {view === 'search' && !isCorpusWorkspace ? (
                <SearchWorkspace
                  client={client}
                  signedIn={signedIn}
                  initialQuery={rerun ?? searchContext.current}
                  onContext={(query) => {
                    searchContext.current = query;
                  }}
                  onOpenPaper={openPaper}
                />
              ) : null}
              {view === 'paper' && paper ? (
                <PaperWorkspace
                  transport={client}
                  {...(controlPolicy ? { libraryPolicy: controlPolicy } : {})}
                  paper={paper}
                  signedIn={signedIn}
                  onBack={closePaper}
                />
              ) : null}
              {view === 'library' && signedIn && isControls ? (
                <LibraryControls
                  client={client}
                  policy={controlPolicy!}
                  onOpenPaper={openPaper}
                  onRunQuery={(query) => {
                    setRerun(query);
                    setView('search');
                  }}
                />
              ) : null}
              {view === 'library' && !isControls ? (
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
      {complete ? <Footer /> : null}
    </div>
  );
  // Only the complete assembly carries the shell's live region, emptied at each owner
  // change (L1-26), and the wrapper whose request id takes its line's colour (L1-40);
  // earlier assemblies keep their own status regions and styles unchanged.
  return complete ? (
    <AnnouncerProvider owner={owner}>
      <div className={shellStyles.completeShell}>{shell}</div>
    </AnnouncerProvider>
  ) : (
    shell
  );
}

function EntryPanel({
  initialProof,
  onProofConsumed,
  client,
  noticeValue,
  onSignedIn,
}: {
  client: Transport;
  noticeValue: Notice | null;
  onSignedIn: () => Promise<SessionBootstrap>;
  initialProof?: ReturnType<typeof takeProofLink>;
  onProofConsumed?: () => void;
}) {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [local, setLocal] = useState<Notice | null>(null);
  const [verification, setVerification] = useState<{
    challengeId: string;
    flowBinding: string;
  } | null>(null);
  const [proof, setProof] = useState('');
  const heading = useRef<HTMLHeadingElement | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (initialProof?.action === 'verify-email') {
      setVerification(initialProof.verification);
      setProof(initialProof.verification.proof);
      onProofConsumed?.();
    } else if (params.get('action') === 'verify-email') {
      setVerification({
        challengeId: params.get('challengeId') ?? '',
        flowBinding: params.get('flowBinding') ?? '',
      });
      setProof(params.get('proof') ?? '');
    }
  }, [initialProof, onProofConsumed]);

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
          <input
            id="proof"
            value={proof}
            onChange={(event) => setProof(event.target.value)}
            required
          />
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
  onContext,
  client,
  signedIn,
  initialQuery,
  onOpenPaper,
}: {
  client: Transport;
  signedIn: boolean;
  initialQuery: QueryContext | null;
  onContext?: (query: QueryContext) => void;
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

  // initialQuery seeds a fresh mount only (the state initializers above): the shell
  // remounts this workspace on every view or authority change. While mounted, a shell
  // re-render hands back the context this workspace just submitted, and re-applying it
  // would wipe the visible results.
  useEffect(() => {
    focusHeading(heading);
  }, []);

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
    onContext?.(query);
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
        client.post<{ items: HistoryRow[]; clearBoundary: string }>(
          '/api/v2/c03/library-list-history',
          {
            page: { limit: 20 },
          },
        ),
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
            <button
              type="button"
              onClick={() => void removePaper(record)}
              data-testid="remove-saved-paper"
            >
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
            <button
              type="button"
              onClick={() => onRerun(record.queryContext)}
              data-testid="rerun-query"
            >
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

// The complete assembly's shell journeys through App (U8 plan Steps 41–42): the public
// projection with the complete entry, the identity arrival page, an administrator's
// setup-only session, a member's jobs and operations views, the navigation error and
// retry, and a paper's return context. The U3 and U4 lanes each run them so every
// changed App.tsx line is measured in both (their src/App.tsx floors).
import React from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import App from '../../src/App';
import { json, notFound } from './helpers';

export type Session = 'guest' | 'member' | 'setup';
export type World = {
  session: Session;
  navigationFails: number;
  calls: string[];
  bodies: Record<string, unknown[]>;
  /** The page's address at each request, so a test can show no proof rode along. */
  hrefs: string[];
  /** An earlier assembly's catalog (no ServiceOperations row; `controls` carries U2's
   * account controls), or a failed read. */
  capabilities?: 'earlier' | 'controls' | 'failing';
  logoutFails?: boolean;
  /** The email change's answer: refused with a 403 instead of completed. */
  emailChange?: 'refused';
  /** The provider callback's answer: a failure instead of a session. */
  callback?: 'failing';
  /** Admission is maintainer-only: the projection names account.entry's reason. */
  admission?: 'maintainer-only';
};

const POLICY = { policyId: 'u8-synthetic-v1', revision: '1' };
const OPERATIONS = { policyId: 'u8-operations-synthetic', revision: '1' };
const row = (id: string, policy = POLICY) => ({
  id,
  state: 'available',
  modeIds: [],
  languageIds: [],
  levelIds: [],
  formatIds: [],
  policy,
});
const PROJECTION = {
  manifestRevision: 'manifest-1',
  items: [
    { capabilityId: 'provider.google', state: 'available', reasonKey: 'capability.available' },
    { capabilityId: 'provider.orcid', state: 'pending', reasonKey: 'capability.pending' },
  ],
};
const CATALOG = {
  revision: 'catalog-1',
  capabilities: [row('account.controls'), row('operations.ledger', OPERATIONS)],
};
const entry = (routeId: string, available: boolean, reasonKey?: string) => ({
  routeId,
  titleKey: `nav.${routeId}`,
  capabilityId: routeId,
  available,
  placement: 'primary',
  ...(reasonKey ? { reasonKey } : {}),
});
const HIT = {
  paper: { paperId: 'paper-1', versionId: 'paper-1v1' },
  title: '돌아오기 실험',
  authors: ['연구자'],
  snippet: '요약',
  sourceUrl: 'https://arxiv.org/abs/0000.00001',
  availability: 'available',
};

function navigationFor(session: Session) {
  if (session !== 'member')
    return [entry('search', true), entry('library', false, 'nav.authenticationRequired')];
  return [
    entry('search', true),
    entry('library', true),
    entry('jobs', true),
    entry('operations', true),
    entry('account', true),
  ];
}

const EMPTY_PAGE = { items: [], page: { snapshotRevision: 's' } };
const PROFILE = {
  accountId: 'account-member',
  email: 'member@example.test',
  emailVerified: true,
  revision: 'p1',
  lifecycleRevision: 'l1',
  fieldVocabularyRevision: 'v1',
  definitions: [],
  fields: [],
};
const forbidden = () =>
  json({ code: 'FORBIDDEN', requestId: 'r', retryable: false, messageKey: 'x' }, 403);

function respond(world: World, path: string, method: string): Response {
  if (path === '/api/v2/session')
    return json({
      signedIn: world.session !== 'guest',
      accountId: world.session === 'guest' ? null : `account-${world.session}`,
      authorityRevision: world.session === 'guest' ? null : 'r1',
      csrfToken: crypto.randomUUID().replace(/-/g, '').repeat(2), // per run (L1-36)
    });
  if (path === '/api/v2/capabilities') {
    if (world.capabilities === 'failing')
      return json({ code: 'UNAVAILABLE', requestId: 'r', retryable: false, messageKey: 'x' }, 503);
    if (world.capabilities === 'earlier') return json({ revision: 'catalog-0', capabilities: [] });
    if (world.capabilities === 'controls')
      return json({ revision: 'catalog-u2', capabilities: [row('account.controls')] });
    if (world.session === 'member') return json(CATALOG);
    if (world.admission !== 'maintainer-only') return json(PROJECTION);
    return json({
      ...PROJECTION,
      items: [
        ...PROJECTION.items,
        {
          capabilityId: 'account.entry',
          state: 'degraded',
          reasonKey: 'admission-maintainer-only',
        },
      ],
    });
  }
  if (path === '/api/v2/c01/host-resolve-navigation') {
    if (world.navigationFails > 0) {
      world.navigationFails -= 1;
      return json({ code: 'UNAVAILABLE', requestId: 'r', retryable: false, messageKey: 'x' }, 503);
    }
    return json({ items: navigationFor(world.session) });
  }
  if (path === '/api/v2/identity/callback/google') {
    if (world.callback === 'failing')
      return json({ code: 'UNAVAILABLE', requestId: 'r', retryable: false, messageKey: 'x' }, 503);
    world.session = 'member';
    return json({ state: 'authenticated', session: { authenticationLevel: 'mfa' } });
  }
  if (path === '/api/v2/c02/access-logout') {
    world.session = 'guest';
    if (world.logoutFails)
      return json({ code: 'UNAVAILABLE', requestId: 'r', retryable: false, messageKey: 'x' }, 503);
    return json({});
  }
  if (path === '/api/v2/c11/request-recovery')
    return json({ jobId: 'request-9', revision: '1', state: 'accepted' });
  if (path === '/api/v2/c02/access-login') {
    world.session = 'member';
    return json({ state: 'authenticated', session: { authenticationLevel: 'primary' } });
  }
  if (path === '/api/v2/c02/access-complete-email-change') {
    if (world.emailChange === 'refused') return forbidden();
    // The route ends the session once the change is done.
    world.session = 'guest';
    return json({});
  }
  if (path === '/api/v2/c02/access-read-profile') return json(PROFILE);
  if (path === '/api/v2/c02/access-list-identity-links') return json(EMPTY_PAGE);
  if (path === '/api/v2/c02/access-list-consents') return json(EMPTY_PAGE);
  if (path === '/api/v2/c03/settings-read')
    return json({ revision: 's1', appearance: 'system', onboarding: 'done' });
  if (path === '/api/v2/c07/list-research-jobs')
    return json({
      items: [
        {
          jobId: 'job-1',
          kind: 'novelty',
          label: '참신성 질문',
          state: 'succeeded',
          createdAt: '2026-10-23T02:00:00Z',
          updatedAt: '2026-10-23T02:00:00Z',
          resultAvailable: true,
        },
      ],
      nextCursor: null,
    });
  if (path === '/api/v2/c11/read-dashboard')
    return json({ items: [], page: { nextCursor: null, snapshotRevision: 's' } });
  if (path === '/api/v2/c11/list-incidents') return json({ items: [], page: { nextCursor: null } });
  if (path === '/api/v2/c05/search' && method === 'POST')
    return json({
      hits: [HIT],
      page: { snapshotRevision: 's' },
      outcome: 'complete',
      effectiveModeId: 'lexical',
      limitations: [],
    });
  return notFound();
}

/** Stub `fetch` with a world answering the complete assembly's routes for `session`. */
export function serve(session: Session, navigationFails = 0, extra: Partial<World> = {}): World {
  const world: World = { session, navigationFails, calls: [], bodies: {}, hrefs: [], ...extra };
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = new URL(String(input), 'https://local.invalid').pathname;
      world.calls.push(path);
      world.hrefs.push(window.location.href);
      if (init?.body)
        world.bodies[path] = [...(world.bodies[path] ?? []), JSON.parse(String(init.body))];
      return respond(world, path, init?.method ?? 'GET');
    }),
  );
  return world;
}

/** An email link of `kind` with distinctive proof values in its fragment. */
export const LINK = (kind: string) => `/account/${kind}#challenge=ch-7&proof=pr-7&flow=fl-7`;
/** U2's query-string form of a proof link. */
const QUERY_LINK = '/?action=password-reset&challengeId=ch-7&flowBinding=fl-7&proof=pr-7';

export function immediateFrames() {
  vi.spyOn(window, 'requestAnimationFrame').mockImplementation((callback) => {
    callback(0);
    return 1;
  });
}

export function describeCompleteShell() {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    window.history.replaceState(null, '', '/');
    window.sessionStorage.clear();
  });

  describe('the complete assembly shell', () => {
    it('serves a signed-out visitor the complete entry, the resolved navigation and the footer', async () => {
      immediateFrames();
      serve('guest');
      render(<App />);
      expect(await screen.findByTestId('complete-entry')).toBeInTheDocument();
      expect(await screen.findByTestId('nav-menu-toggle')).toBeInTheDocument();
      expect(screen.getByTestId('footer')).toBeInTheDocument();
      expect(screen.getByTestId('announcer')).toBeInTheDocument();
      expect(screen.getByTestId('provider-orcid')).toBeDisabled();
      fireEvent.click(screen.getByTestId('nav-library'));
      expect(screen.getByTestId('entry-email')).toHaveFocus();
    });

    it('shows the navigation error with a retry that resolves again', async () => {
      serve('guest', 1);
      render(<App />);
      fireEvent.click(await screen.findByTestId('nav-retry'));
      await waitFor(() => expect(screen.queryByTestId('nav-error')).toBeNull());
      expect(screen.getByTestId('nav-library')).toBeInTheDocument();
    });

    it('takes a provider arrival through the callback page into a signed-in workspace', async () => {
      window.history.replaceState(null, '', '/sign-in/callback/google?flow=f&state=s&code=c');
      const world = serve('guest');
      render(<App />);
      await waitFor(() => expect(world.calls).toContain('/api/v2/identity/callback/google'));
      await waitFor(() => expect(window.location.pathname).toBe('/search'));
      expect(await screen.findByTestId('logout')).toBeInTheDocument();
      expect(await screen.findByTestId('nav-jobs')).toBeInTheDocument();
    });

    it('returns from a cancelled arrival to the entry', async () => {
      window.history.replaceState(null, '', '/sign-in/callback/google?error=access_denied');
      serve('guest');
      render(<App />);
      fireEvent.click(await screen.findByTestId('callback-back'));
      expect(await screen.findByTestId('complete-entry')).toBeInTheDocument();
      expect(window.location.pathname).toBe('/search');
    });

    // Step 91(g): callback-back unmounts with its focus; the landing is never the body.
    it.each([
      ['cancelled', '/sign-in/callback/google?error=access_denied', {}],
      ['failed', '/sign-in/callback/google?flow=f&state=s&code=c', { callback: 'failing' }],
    ] as const)(
      'callback-back on the %s arrival page lands on the entry heading',
      async (_kind, address, extra) => {
        immediateFrames();
        window.history.replaceState(null, '', address);
        serve('guest', 0, extra);
        const user = userEvent.setup();
        render(<App />);
        const back = await screen.findByTestId('callback-back');
        back.focus();
        await user.keyboard('{Enter}');
        expect(await screen.findByTestId('complete-entry')).toBeInTheDocument();
        await waitFor(() => expect(screen.getByRole('heading', { name: '로그인' })).toHaveFocus());
        expect(document.activeElement).not.toBe(document.body);
      },
    );

    it("callback-back for a signed-in person lands on the view's first heading", async () => {
      immediateFrames();
      window.history.replaceState(null, '', '/sign-in/callback/google?error=access_denied');
      serve('member');
      const user = userEvent.setup();
      render(<App />);
      const back = await screen.findByTestId('callback-back');
      back.focus();
      await user.keyboard('{Enter}');
      await waitFor(() => expect(screen.queryByTestId('callback-back')).toBeNull());
      // The arrival page always leaves to 검색, and SearchWorkspace focuses its own heading
      // as it mounts (App.tsx's mount effect). That mount focus carries this landing, so this
      // scenario holds with or without returnFromCallback's requestFocus() for a signed-in
      // person; it shows the exact landing, not that request.
      await waitFor(() => expect(screen.getByRole('heading', { name: '논문 검색' })).toHaveFocus());
    });

    it('a maintainer-only arrival shows the notice, and its 관리자 로그인 leads to the email field', async () => {
      window.history.replaceState(null, '', '/sign-in/callback/google?error=access_denied&state=s');
      const world = serve('guest', 0, { admission: 'maintainer-only' });
      render(<App />);
      const cancelled = await screen.findByTestId('callback-cancelled');
      expect(within(cancelled).getByTestId('maintenance-banner')).toBeInTheDocument();
      fireEvent.click(within(cancelled).getByTestId('maintenance-admin-sign-in'));
      const entryPanel = await screen.findByTestId('complete-entry');
      expect(within(entryPanel).getByTestId('maintenance-banner')).toBeInTheDocument();
      expect(window.location.pathname).toBe('/search');
      // Real animation frames: requireSignIn focuses the field in the next frame.
      await waitFor(() => expect(screen.getByTestId('entry-email')).toHaveFocus());
      expect(world.calls).not.toContain('/api/v2/identity/callback/google');
    });

    it("routes an administrator's setup-only session to the MFA prompt", async () => {
      const world = serve('setup');
      render(<App />);
      expect(await screen.findByTestId('admin-mfa-prompt')).toBeInTheDocument();
      fireEvent.click(screen.getByTestId('admin-mfa-sign-in-again'));
      await waitFor(() => expect(world.calls).toContain('/api/v2/c02/access-logout'));
      expect(await screen.findByTestId('complete-entry')).toBeInTheDocument();
    });

    it("opens a member's jobs and operations views and signs out", async () => {
      immediateFrames();
      const world = serve('member');
      render(<App />);
      fireEvent.click(await screen.findByTestId('nav-jobs'));
      expect(await screen.findByTestId('jobs-view')).toBeInTheDocument();
      // The route change lands on the destination's heading (Step 91(f)).
      await waitFor(() => expect(screen.getByRole('heading', { name: '작업' })).toHaveFocus());
      expect(await screen.findByText(/참신성 질문/)).toBeInTheDocument();
      fireEvent.click(screen.getByTestId('jobs-item-open'));
      fireEvent.click(screen.getByTestId('jobs-open-view'));
      await waitFor(() => expect(screen.queryByTestId('jobs-view')).toBeNull());
      fireEvent.click(screen.getByTestId('nav-operations'));
      expect(await screen.findByTestId('operations-view')).toBeInTheDocument();
      expect(world.calls).toContain('/api/v2/c11/read-dashboard');
      fireEvent.click(screen.getByTestId('logout'));
      await waitFor(() => expect(world.calls).toContain('/api/v2/c02/access-logout'));
      expect(await screen.findByTestId('complete-entry')).toBeInTheDocument();
      // Signing out lands on the entry's 로그인 heading (Step 91(g)).
      await waitFor(() => expect(screen.getByRole('heading', { name: '로그인' })).toHaveFocus());
    });

    it("a guest's route changes end on the destination's heading", async () => {
      immediateFrames();
      vi.spyOn(window, 'scrollTo').mockImplementation(() => undefined);
      serve('guest');
      render(<App />);
      await screen.findByTestId('nav-library');
      fireEvent.change(screen.getByTestId('search-query'), { target: { value: '돌아오기' } });
      await act(async () => fireEvent.submit(screen.getByTestId('search-form')));
      fireEvent.click(await screen.findByRole('button', { name: /돌아오기 실험/ }));
      await screen.findByTestId('back-to-search');
      await waitFor(() => {
        const active = document.activeElement as HTMLElement;
        expect(active.tagName).toMatch(/^H[12]$/);
        expect(active.closest('.workspace-content')).not.toBeNull();
      });
      expect(document.activeElement).not.toBe(screen.getByRole('heading', { name: '로그인' }));
      // On that paper, a member entry lands on the sign-in field.
      fireEvent.click(screen.getByTestId('nav-library'));
      await waitFor(() => expect(screen.getByTestId('entry-email')).toHaveFocus());
    });

    it('takes an email link out of the address in the first render, signed in or out', async () => {
      for (const session of ['guest', 'member'] as const) {
        immediateFrames();
        window.history.replaceState(null, '', LINK('password-reset'));
        const world = serve(session);
        render(<App />);
        expect(window.location.hash).toBe('');
        if (session === 'guest') {
          expect(await screen.findByTestId('proof-password')).toBeInTheDocument();
        } else {
          await screen.findByTestId('logout');
          expect(screen.queryByTestId('proof-form')).toBeNull();
          fireEvent.click(screen.getByTestId('logout'));
          expect(await screen.findByTestId('proof-password')).toBeInTheDocument();
        }
        expect(world.hrefs.length).toBeGreaterThan(0);
        expect(world.hrefs.some((href) => href.includes('pr-7'))).toBe(false);
        cleanup();
        vi.unstubAllGlobals();
        vi.restoreAllMocks();
      }
    });

    it('completes an email change while signed in, then asks to sign in again', async () => {
      immediateFrames();
      window.history.replaceState(null, '', LINK('email-change'));
      const world = serve('member');
      render(<App />);
      expect(await screen.findByTestId('email-change-proof')).toBeInTheDocument();
      await waitFor(() =>
        expect(screen.getByRole('heading', { name: '이메일 변경 확인' })).toHaveFocus(),
      );
      fireEvent.click(screen.getByTestId('proof-submit'));
      expect(await screen.findByTestId('complete-entry')).toHaveTextContent(
        '이메일 변경을 확인했습니다. 새 이메일 주소로 다시 로그인해 주세요.',
      );
      expect(world.bodies['/api/v2/c02/access-complete-email-change']).toEqual([
        { verification: { challengeId: 'ch-7', proof: 'pr-7', flowBinding: 'fl-7' } },
      ]);
      await waitFor(() => expect(screen.getByRole('heading', { name: '로그인' })).toHaveFocus());
    });

    it('continues an email change after signing in', async () => {
      immediateFrames();
      window.history.replaceState(null, '', LINK('email-change'));
      const world = serve('guest');
      render(<App />);
      expect(await screen.findByTestId('email-change-sign-in-first')).toHaveTextContent(
        '이메일 변경을 마치려면 변경을 요청한 브라우저에서 같은 계정으로 로그인해 주세요. 로그인하면 변경 확인으로 이어집니다.',
      );
      expect(screen.queryByTestId('proof-form')).toBeNull();
      fireEvent.change(screen.getByTestId('entry-email'), {
        target: { value: 'member@example.test' },
      });
      fireEvent.change(screen.getByTestId('entry-password'), {
        target: { value: crypto.randomUUID() },
      });
      fireEvent.click(screen.getByTestId('entry-submit'));
      expect(await screen.findByTestId('email-change-proof')).toBeInTheDocument();
      expect(world.calls).not.toContain('/api/v2/c02/access-complete-email-change');
    });

    it('signing out drops an unused email-change proof', async () => {
      immediateFrames();
      window.history.replaceState(null, '', LINK('email-change'));
      const world = serve('member');
      render(<App />);
      expect(await screen.findByTestId('email-change-proof')).toBeInTheDocument();
      fireEvent.click(screen.getByTestId('logout'));
      await waitFor(() => expect(world.calls).toContain('/api/v2/c02/access-logout'));
      expect(await screen.findByTestId('complete-entry')).toBeInTheDocument();
      expect(screen.queryByTestId('proof-form')).toBeNull();
      expect(screen.queryByTestId('email-change-sign-in-first')).toBeNull();
      expect(screen.queryByTestId('email-change-proof')).toBeNull();
    });

    it('a refused email change offers 계정 and opens it by Enter, dropping the proof', async () => {
      immediateFrames();
      window.history.replaceState(null, '', LINK('email-change'));
      serve('member', 0, { emailChange: 'refused' });
      const user = userEvent.setup();
      render(<App />);
      expect(await screen.findByTestId('email-change-proof')).toBeInTheDocument();
      await waitFor(() =>
        expect(screen.getByRole('heading', { name: '이메일 변경 확인' })).toHaveFocus(),
      );
      fireEvent.click(screen.getByTestId('proof-submit'));
      expect(
        await screen.findByText(
          '이 이메일 변경 링크는 변경을 요청한 브라우저에서, 요청한 계정으로 로그인한 상태에서만 쓸 수 있습니다. 이미 사용했거나 유효 기간이 지난 링크도 쓸 수 없습니다. 이 브라우저에서 계정 화면의 ‘비밀번호와 이메일’에서 ‘이메일 변경 인증 요청’을 다시 눌러 주세요.',
        ),
      ).toBeInTheDocument();
      await waitFor(() => expect(screen.getByTestId('proof-ask-again')).toHaveFocus());
      await user.keyboard('{Enter}');
      expect(await screen.findByTestId('account-controls')).toBeInTheDocument();
      expect(screen.queryByTestId('email-change-proof')).toBeNull();
      await waitFor(() => expect(document.activeElement).not.toBe(document.body));
    });

    it("closing the email change drops the proof and lands on the view's heading", async () => {
      immediateFrames();
      window.history.replaceState(null, '', LINK('email-change'));
      const world = serve('member');
      const user = userEvent.setup();
      render(<App />);
      expect(await screen.findByTestId('email-change-proof')).toBeInTheDocument();
      // The panel takes the focus as it shows; only then is 닫기 focused and pressed.
      await waitFor(() =>
        expect(screen.getByRole('heading', { name: '이메일 변경 확인' })).toHaveFocus(),
      );
      screen.getByTestId('proof-back').focus();
      await user.keyboard('{Enter}');
      await waitFor(() => expect(screen.queryByTestId('email-change-proof')).toBeNull());
      await waitFor(() => expect(screen.getByRole('heading', { name: '논문 검색' })).toHaveFocus());
      expect(world.calls).not.toContain('/api/v2/c02/access-complete-email-change');
    });

    // Step 91(g): proof-ask-again unmounts with its focus even when the person already
    // opened 계정, so the view does not change; the 계정 heading still takes the focus.
    it('a refused email change opened over 계정 lands on its heading by Enter', async () => {
      immediateFrames();
      window.history.replaceState(null, '', LINK('email-change'));
      serve('member', 0, { emailChange: 'refused' });
      const user = userEvent.setup();
      render(<App />);
      expect(await screen.findByTestId('email-change-proof')).toBeInTheDocument();
      await waitFor(() =>
        expect(screen.getByRole('heading', { name: '이메일 변경 확인' })).toHaveFocus(),
      );
      fireEvent.click(screen.getByTestId('nav-account'));
      expect(await screen.findByTestId('account-controls')).toBeInTheDocument();
      expect(screen.getByTestId('email-change-proof')).toBeInTheDocument();
      fireEvent.click(screen.getByTestId('proof-submit'));
      await waitFor(() => expect(screen.getByTestId('proof-ask-again')).toHaveFocus());
      await user.keyboard('{Enter}');
      await waitFor(() => expect(screen.queryByTestId('email-change-proof')).toBeNull());
      await waitFor(() => expect(screen.getByRole('heading', { name: '계정 설정' })).toHaveFocus());
      expect(document.activeElement).not.toBe(document.body);
    });

    it("the complete app's 계정 view says what it does", async () => {
      immediateFrames();
      serve('member');
      render(<App />);
      fireEvent.click(await screen.findByTestId('nav-account'));
      const controls = await screen.findByTestId('account-controls');
      await waitFor(() =>
        expect(controls).toHaveTextContent(
          '이메일은 전달받은 인증을 완료한 뒤 변경돼요. 메일의 링크는 이 브라우저에서 로그인한 상태에서 열어 주세요.',
        ),
      );
      expect(controls).toHaveTextContent('새 Google·ORCID 연결은 아직 이 화면에서 할 수 없어요.');
      expect(screen.queryAllByRole('button', { name: /시험 연결/ })).toHaveLength(0);
    });

    // Your answer of 2026-11-11, "Stop showing it" (Step 91(l)): a signed-in person whose
    // address carried a query-string proof sees no AuthenticationPanel in the complete app,
    // while an earlier assembly with U2's controls still shows it.
    it('shows a signed-in person no sign-in panel for a query-string proof', async () => {
      window.history.replaceState(null, '', QUERY_LINK);
      serve('member');
      render(<App />);
      expect(window.location.search).toBe('');
      expect(await screen.findByTestId('logout')).toBeInTheDocument();
      await screen.findByTestId('nav-account');
      expect(screen.queryByTestId('entry-panel')).toBeNull();
      expect(screen.queryByTestId('complete-entry')).toBeNull();
      expect(window.location.search).toBe('');
    });

    it('an earlier assembly still shows its sign-in panel for that proof', async () => {
      window.history.replaceState(null, '', QUERY_LINK);
      serve('member', 0, { capabilities: 'controls' });
      render(<App />);
      expect(window.location.search).toBe('');
      expect(await screen.findByTestId('entry-panel')).toBeInTheDocument();
      expect(screen.queryByTestId('footer')).toBeNull();
    });

    it('returns from a paper to the result it was opened from', async () => {
      immediateFrames();
      const scroll = vi.spyOn(window, 'scrollTo').mockImplementation(() => undefined);
      serve('member');
      render(<App />);
      await screen.findByTestId('nav-jobs');
      fireEvent.change(screen.getByTestId('search-query'), { target: { value: '돌아오기' } });
      await act(async () => fireEvent.submit(screen.getByTestId('search-form')));
      const open = await screen.findByRole('button', { name: /돌아오기 실험/ });
      open.focus();
      fireEvent.click(open);
      fireEvent.click(await screen.findByTestId('back-to-search'));
      expect(await screen.findByTestId('search-form')).toBeInTheDocument();
      expect(scroll).toHaveBeenCalled();
    });

    it('signs out even when the sign-out request fails', async () => {
      const world = serve('member', 0, { logoutFails: true });
      render(<App />);
      fireEvent.click(await screen.findByTestId('logout'));
      await waitFor(() => expect(world.calls).toContain('/api/v2/c02/access-logout'));
      expect(await screen.findByTestId('complete-entry')).toBeInTheDocument();
    });
  });

  describe('earlier assemblies', () => {
    it('keep their entry, navigation and plain return to search', async () => {
      const scroll = vi.spyOn(window, 'scrollTo').mockImplementation(() => undefined);
      serve('guest', 0, { capabilities: 'earlier' });
      render(<App />);
      fireEvent.change(await screen.findByTestId('search-query'), {
        target: { value: '돌아오기' },
      });
      await act(async () => fireEvent.submit(screen.getByTestId('search-form')));
      fireEvent.click(await screen.findByRole('button', { name: /돌아오기 실험/ }));
      fireEvent.click(await screen.findByTestId('back-to-search'));
      expect(await screen.findByTestId('search-form')).toBeInTheDocument();
      expect(screen.queryByTestId('footer')).toBeNull();
      expect(screen.queryByTestId('complete-entry')).toBeNull();
      expect(scroll).not.toHaveBeenCalled();
    });

    it('treat a failed capability read as an earlier assembly', async () => {
      serve('guest', 0, { capabilities: 'failing' });
      render(<App />);
      expect(await screen.findByTestId('search-form')).toBeInTheDocument();
      expect(screen.queryByTestId('complete-entry')).toBeNull();
      expect(screen.queryByTestId('footer')).toBeNull();
    });
  });
}

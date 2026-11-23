// U8 plan Step 42, the notices (BR9.6, BR7.2, BR6.4, BR5.3, BR5.9): MovedNotice dismissal
// per device with storage failures handled, ProviderStateNotice, the maintenance banner,
// the footer, and the capability answer's two shapes.
import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { Panel } from '../../src/ui';
import { DISMISSED_KEY, MovedNotice } from '../../src/u8-shell/moved-notice';
import { ProviderStateNotice, serves } from '../../src/u8-shell/provider-notice';
import { MaintenanceBanner, maintainerOnly } from '../../src/u8-shell/maintenance-banner';
import { Footer } from '../../src/u8-shell/footer';
import { isCompleteAnswer, isPublicPage, statesOf } from '../../src/u8-shell/capabilities';
import { forgetArrival, keepFlow } from '../../src/u8-entry/callback-page';
import App from '../../src/App';
import { LINK, serve, type World } from './app-shell-scenarios';
import { json, notFound } from './helpers';

afterEach(() => {
  vi.restoreAllMocks();
  window.localStorage.removeItem(DISMISSED_KEY);
});

describe('MovedNotice', () => {
  it('stays dismissed on this device once closed', () => {
    const first = render(<MovedNotice />);
    expect(screen.getByTestId('moved-notice')).toHaveTextContent(
      'DocSuri가 새 버전으로 옮겨졌습니다',
    );
    fireEvent.click(screen.getByTestId('moved-notice-dismiss'));
    expect(screen.queryByTestId('moved-notice')).toBeNull();
    expect(window.localStorage.getItem(DISMISSED_KEY)).toBe('1');
    first.unmount();
    render(<MovedNotice />);
    expect(screen.queryByTestId('moved-notice')).toBeNull();
  });

  it('stays shown when storage refuses to read, and closes for the page when it refuses to write', () => {
    window.localStorage.setItem(DISMISSED_KEY, '1');
    // The storage's own prototype: jsdom's Storage, or the setup file's stand-in.
    const storage = Object.getPrototypeOf(window.localStorage) as Storage;
    const read = vi.spyOn(storage, 'getItem').mockImplementation(() => {
      throw new Error('denied');
    });
    const write = vi.spyOn(storage, 'setItem').mockImplementation(() => {
      throw new Error('denied');
    });
    render(<MovedNotice />);
    expect(screen.getByTestId('moved-notice')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('moved-notice-dismiss'));
    expect(screen.queryByTestId('moved-notice')).toBeNull();
    expect(read).toHaveBeenCalled();
    expect(write).toHaveBeenCalled();
  });
});

describe('the moved notice by keyboard', () => {
  it('dismissing the moved notice by keyboard keeps focus on a visible element', async () => {
    const user = userEvent.setup();
    render(
      <main id="main" tabIndex={-1}>
        <Panel title="로그인">
          <MovedNotice />
        </Panel>
      </main>,
    );
    const dismiss = screen.getByTestId('moved-notice-dismiss');
    for (let step = 0; step < 5 && document.activeElement !== dismiss; step += 1) await user.tab();
    expect(dismiss).toHaveFocus();
    await user.keyboard('{Enter}');
    expect(screen.queryByTestId('moved-notice')).toBeNull();
    expect(document.activeElement).toBe(screen.getByRole('heading', { name: '로그인' }));
  });

  it('keyboard parity for the notices', async () => {
    for (const key of ['{Enter}', ' ']) {
      window.localStorage.removeItem(DISMISSED_KEY);
      const user = userEvent.setup();
      const view = render(<MovedNotice />);
      screen.getByTestId('moved-notice-dismiss').focus();
      await user.keyboard(key);
      expect(screen.queryByTestId('moved-notice')).toBeNull();
      view.unmount();
      render(<MovedNotice />);
      expect(screen.queryByTestId('moved-notice')).toBeNull();
      cleanup();
    }
    const user = userEvent.setup();
    const onAdministratorSignIn = vi.fn();
    render(
      <MaintenanceBanner
        states={{ 'account.entry': { state: 'degraded', reasonKey: 'admission-maintainer-only' } }}
        onAdministratorSignIn={onAdministratorSignIn}
      />,
    );
    screen.getByTestId('maintenance-admin-sign-in').focus();
    await user.keyboard('{Enter}');
    expect(onAdministratorSignIn).toHaveBeenCalledTimes(1);
  });
});

describe('ProviderStateNotice', () => {
  it('shows the mail notice only while the mail provider reads unavailable', () => {
    const view = render(
      <ProviderStateNotice
        states={{ 'provider.resend': { state: 'unavailable' } }}
        feature="mail"
      />,
    );
    expect(screen.getByTestId('provider-notice-mail')).toHaveTextContent(
      '지금은 이메일을 보낼 수 없습니다. 나중에 다시 시도해 주세요.',
    );
    // Capability changes are announced only through the shell's region (L1-26).
    expect(screen.getByTestId('provider-notice-mail')).not.toHaveAttribute('role');
    expect(screen.getByTestId('provider-notice-mail')).not.toHaveAttribute('aria-live');
    view.rerender(
      <ProviderStateNotice states={{ 'provider.resend': { state: 'degraded' } }} feature="mail" />,
    );
    expect(screen.queryByTestId('provider-notice-mail')).toBeNull();
    for (const state of ['stale', 'unknown', 'available']) {
      view.rerender(
        <ProviderStateNotice states={{ 'provider.resend': { state } }} feature="mail" />,
      );
      expect(screen.queryByTestId('provider-notice-mail')).toBeNull();
    }
    view.rerender(<ProviderStateNotice states={{}} feature="mail" />);
    expect(screen.queryByTestId('provider-notice-mail')).toBeNull();
  });

  it('shows the assistance notice while assistance waits on its model', () => {
    render(
      <ProviderStateNotice
        states={{ 'assistance.summary': { state: 'pending' } }}
        feature="assistance"
      />,
    );
    expect(screen.getByTestId('provider-notice-assistance')).toHaveTextContent(
      '요약·번역 기능을 준비 중입니다',
    );
    expect(serves({ x: { state: 'available' } }, 'x')).toBe(true);
    expect(serves({}, 'x')).toBe(false);
  });
});

describe('the maintenance banner', () => {
  it('shows while admission is maintainer-only, with the administrator sign-in', () => {
    const onAdministratorSignIn = vi.fn();
    const states = {
      'account.entry': { state: 'degraded', reasonKey: 'admission-maintainer-only' },
    };
    const view = render(
      <MaintenanceBanner states={states} onAdministratorSignIn={onAdministratorSignIn} />,
    );
    expect(screen.getByTestId('maintenance-banner')).toHaveTextContent(
      'DocSuri를 점검하고 있습니다. 잠시 후 다시 접속해 주세요.',
    );
    expect(screen.getByTestId('maintenance-banner')).not.toHaveAttribute('role');
    expect(screen.getByTestId('maintenance-banner')).not.toHaveAttribute('aria-live');
    fireEvent.click(screen.getByTestId('maintenance-admin-sign-in'));
    expect(onAdministratorSignIn).toHaveBeenCalledTimes(1);
    view.rerender(
      <MaintenanceBanner
        states={{ 'account.entry': { state: 'available' } }}
        onAdministratorSignIn={onAdministratorSignIn}
      />,
    );
    expect(screen.queryByTestId('maintenance-banner')).toBeNull();
    expect(maintainerOnly({})).toBe(false);
  });
});

// NFR1.3: every page a caller sees before the password or identity check succeeds. The
// host serves /privacy and /terms as script-free documents without the notice
// (integration/test_static_routes.py).
describe('the maintenance notice on every page a signed-out visitor opens', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    forgetArrival();
    window.sessionStorage.clear();
    window.history.replaceState(null, '', '/');
  });

  it.each([
    ['/', 'complete-entry', {}],
    ['/search', 'complete-entry', {}],
    ['/#research-job?jobId=job-1&kind=research-turn&contextId=context-1', 'complete-entry', {}],
    [LINK('verify-email'), 'complete-entry', {}],
    ['/sign-in/callback/google?error=access_denied&state=s', 'callback-cancelled', {}],
    ['/sign-in/callback/google?state=s&code=c', 'callback-page', { callback: 'failing' }],
    // Step 170(c): the addresses the staged Chromium test opens (L4-15). Each destination
    // of the registry but the two legal pages, and a path the shell does not know.
    ...[
      '/library',
      '/research',
      '/novelty',
      '/jobs',
      '/topics',
      '/export',
      '/settings',
      '/usage',
      '/account',
      '/operations',
      '/paper',
      '/no-such-page',
    ].map((path): [string, string, Partial<World>] => [path, 'complete-entry', {}]),
    ['/#research-job?jobId=job-2&kind=novelty-analysis&contextId=context-2', 'complete-entry', {}],
    [LINK('password-reset'), 'complete-entry', {}],
    [LINK('reactivate'), 'complete-entry', {}],
    [LINK('email-change'), 'complete-entry', {}],
    ['/account/password-reset', 'complete-entry', {}],
    ['/account/verify-email', 'complete-entry', {}],
    ['/account/email-change', 'complete-entry', {}],
    ['/account/reactivate', 'complete-entry', {}],
    ['/sign-in/callback/orcid?error=access_denied&state=s', 'callback-cancelled', {}],
    ['/sign-in/callback/orcid?state=s&code=c', 'callback-page', { callback: 'failing' }],
    // An arrival with a missing or repeated answer, or with no flow kept in this tab, for
    // each provider. The pending arrival has no row here: the scenarios' `serve` cannot
    // hold the callback read, and the Chromium tests hold it for both providers.
    ...['google', 'orcid'].flatMap((provider) =>
      [
        'code=c',
        'state=s',
        'flow=f&state=s',
        'state=s&state=t&code=c',
        'state=s&code=c&code=d',
        'flow=a&flow=b&state=s&code=c',
      ].map((answer): [string, string, Partial<World>] => [
        `/sign-in/callback/${provider}?${answer}`,
        'callback-cancelled',
        {},
      ]),
    ),
  ] as [string, string, Partial<World>][])(
    '%s shows exactly one notice, inside %s',
    async (address, panelId, extra) => {
      const provider = address.includes('/callback/orcid') ? 'orcid' : 'google';
      if (panelId === 'callback-page') keepFlow(provider, 'flow-kept');
      window.history.replaceState(null, '', address);
      serve('guest', 0, { admission: 'maintainer-only', ...extra });
      render(<App />);
      const panel = await screen.findByTestId(panelId);
      if (panelId === 'callback-page') await within(panel).findByTestId('callback-back');
      await waitFor(() => expect(screen.getAllByTestId('maintenance-banner')).toHaveLength(1));
      expect(within(panel).getByTestId('maintenance-banner')).toBeInTheDocument();
    },
  );
});

describe('the footer', () => {
  it('links the legal pages', () => {
    render(<Footer />);
    expect(screen.getByTestId('footer-privacy')).toHaveAttribute('href', '/privacy');
    expect(screen.getByTestId('footer-terms')).toHaveAttribute('href', '/terms');
    expect(screen.getByRole('navigation', { name: '법적 고지' })).toBeInTheDocument();
  });
});

describe('the capability answer', () => {
  it('tells the public projection from a catalog and maps both to states', () => {
    const projection = {
      manifestRevision: 'm1',
      items: [{ capabilityId: 'provider.google', state: 'available', reasonKey: 'ok' }],
    };
    expect(isPublicPage(projection)).toBe(true);
    expect(isPublicPage(null)).toBe(false);
    expect(isCompleteAnswer(projection)).toBe(true);
    expect(statesOf(projection)).toEqual({
      'provider.google': { state: 'available', reasonKey: 'ok' },
    });
    const catalog = {
      revision: 'r',
      capabilities: [{ id: 'operations.ledger', state: 'available' }],
    };
    expect(isCompleteAnswer(catalog)).toBe(true);
    expect(
      isCompleteAnswer({ revision: 'r', capabilities: [{ id: 'library', state: 'available' }] }),
    ).toBe(false);
    expect(isCompleteAnswer(null)).toBe(false);
    expect(statesOf(catalog)).toEqual({ 'operations.ledger': { state: 'available' } });
    expect(statesOf(null)).toEqual({});
  });
});

// Your answer of 2026-11-13, "Add mail to the list": the signed-out capability list (BR5.9)
// carries provider.resend, so the entry's mail notice warns before a reset or verification
// link is asked for.
describe('the signed-out entry and the mail provider', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    window.history.replaceState(null, '', '/');
  });

  function signedOut(resend: string) {
    const projection = {
      manifestRevision: 'manifest-1',
      items: [
        { capabilityId: 'account.entry', state: 'available', reasonKey: 'available' },
        { capabilityId: 'provider.google', state: 'available', reasonKey: 'available' },
        { capabilityId: 'provider.orcid', state: 'available', reasonKey: 'available' },
        {
          capabilityId: 'provider.resend',
          state: resend,
          reasonKey: resend === 'available' ? 'available' : 'provider-unreachable',
        },
      ],
    };
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const path = new URL(String(input), 'https://local.invalid').pathname;
        if (path === '/api/v2/session')
          return json({ signedIn: false, accountId: null, authorityRevision: null });
        if (path === '/api/v2/capabilities') return json(projection);
        if (path === '/api/v2/c01/host-resolve-navigation') return json({ items: [] });
        return notFound();
      }),
    );
    return render(<App />);
  }

  // The realm gives provider.resend signed out as `available` or `unavailable` alone (the
  // person's answer of 2026-11-13, "Working or not, no reasons"); the notice shows exactly
  // while it reads not serving.
  it('shows provider-notice-mail with its text while provider.resend reads not serving', async () => {
    signedOut('unavailable');
    expect(await screen.findByTestId('complete-entry')).toBeInTheDocument();
    const notice = await screen.findByTestId('provider-notice-mail');
    expect(notice.textContent).toBe('지금은 이메일을 보낼 수 없습니다. 나중에 다시 시도해 주세요.');
    expect(screen.getByTestId('complete-entry')).toContainElement(notice);
  });

  it.each(['available', 'degraded', 'stale', 'unknown'])(
    'hides provider-notice-mail while provider.resend reads %s',
    async (state) => {
      signedOut(state);
      expect(await screen.findByTestId('complete-entry')).toBeInTheDocument();
      expect(await screen.findByTestId('provider-google')).toBeEnabled();
      expect(screen.queryByTestId('provider-notice-mail')).toBeNull();
    },
  );
});

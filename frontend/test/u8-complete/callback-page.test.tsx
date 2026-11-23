// U8 plan Step 42, the identity arrival page (A8, D3): the address is cleaned with
// replaceState before the API call; an error return, a repeated answer key or a missing
// state, code or flow shows "로그인이 취소되었습니다" and calls nothing; a key the page
// does not read is ignored (Step 109, R-09).
import React from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import App from '../../src/App';
import { serve } from './app-shell-scenarios';
import {
  CallbackPage,
  FLOW_KEY,
  keepFlow,
  takeArrival,
  forgetArrival,
} from '../../src/u8-entry/callback-page';
import type { CapabilityStateMap } from '../../src/u8-shell/provider-notice';
import { apiError, fakeClient, Fresh } from './helpers';

function arriveAt(address: string) {
  window.history.pushState(null, '', address);
}

function mount(
  provider: string,
  answer: () => unknown = () => ({ state: 'authenticated' }),
  states: CapabilityStateMap = {},
) {
  const fake = fakeClient(() => answer());
  const handlers = { onArrived: vi.fn(), onBack: vi.fn(), onAdministratorSignIn: vi.fn() };
  render(
    <Fresh>
      <CallbackPage client={fake.transport} provider={provider} states={states} {...handlers} />
    </Fresh>,
  );
  return { ...fake, ...handlers };
}

afterEach(() => {
  vi.restoreAllMocks();
  window.sessionStorage.clear();
  forgetArrival();
  window.history.replaceState(null, '', '/');
});

describe('a provider answer', () => {
  it('removes the query with replaceState before it calls the API route', async () => {
    arriveAt('/sign-in/callback/google?flow=flow-1&state=state-1&code=code-1');
    const replace = vi.spyOn(window.history, 'replaceState');
    const fake = mount('google');
    await waitFor(() => expect(fake.onArrived).toHaveBeenCalledWith({ state: 'authenticated' }));
    expect(replace).toHaveBeenCalledWith(null, '', '/sign-in/callback/google');
    expect(replace.mock.invocationCallOrder[0]!).toBeLessThan(
      fake.get.mock.invocationCallOrder[0]!,
    );
    expect(fake.get).toHaveBeenCalledWith(
      '/api/v2/identity/callback/google?flow=flow-1&state=state-1&code=code-1',
    );
    expect(fake.get).toHaveBeenCalledTimes(1);
    expect(window.location.search).toBe('');
    expect(screen.getByTestId('callback-page')).toHaveTextContent('로그인을 확인하고 있습니다');
  });

  it('takes the flow kept by the page that began the sign-in, for that provider only', async () => {
    keepFlow('orcid', 'flow-kept');
    arriveAt('/sign-in/callback/orcid?state=s&code=c');
    const fake = mount('orcid');
    await waitFor(() =>
      expect(fake.get).toHaveBeenCalledWith(
        '/api/v2/identity/callback/orcid?flow=flow-kept&state=s&code=c',
      ),
    );
    expect(window.sessionStorage.getItem(FLOW_KEY)).toBeNull();
  });

  it('shows a failed callback with a way back', async () => {
    arriveAt('/sign-in/callback/google?flow=f&state=s&code=c');
    const fake = mount('google', () => apiError(409, 'CONFLICT'));
    fireEvent.click(await screen.findByTestId('callback-back'));
    expect(fake.onBack).toHaveBeenCalledTimes(1);
    expect(fake.onArrived).not.toHaveBeenCalled();
  });

  it('reads the same answer twice in one render (StrictMode) and afresh after', () => {
    arriveAt('/sign-in/callback/google?flow=f&state=s&code=c');
    const first = takeArrival('google');
    expect(takeArrival('google')).toBe(first);
    forgetArrival();
    expect(takeArrival('google')).toEqual({ kind: 'cancelled' });
  });
});

describe('keys the page does not read', () => {
  it("proceeds on Google's own return and sends exactly flow, state and code", async () => {
    keepFlow('google', 'flow-kept');
    arriveAt(
      '/sign-in/callback/google?state=s&code=c&scope=email%20openid&authuser=0&prompt=consent' +
        '&hd=example.org&iss=https%3A%2F%2Faccounts.google.com',
    );
    const fake = mount('google');
    await waitFor(() => expect(fake.onArrived).toHaveBeenCalledWith({ state: 'authenticated' }));
    expect(fake.get).toHaveBeenCalledTimes(1);
    expect(fake.get).toHaveBeenCalledWith(
      '/api/v2/identity/callback/google?flow=flow-kept&state=s&code=c',
    );
    expect(window.location.search).toBe('');
    expect(window.sessionStorage.getItem(FLOW_KEY)).toBeNull();
    expect(screen.getByTestId('callback-page')).toHaveTextContent('로그인을 확인하고 있습니다');
  });

  it('proceeds on a return of only state, code and scope', async () => {
    keepFlow('google', 'flow-kept');
    arriveAt('/sign-in/callback/google?state=s&code=c&scope=openid%20email');
    const fake = mount('google');
    await waitFor(() => expect(fake.get).toHaveBeenCalledTimes(1));
    expect(fake.get).toHaveBeenCalledWith(
      '/api/v2/identity/callback/google?flow=flow-kept&state=s&code=c',
    );
  });

  it('ignores a key it does not read beside a whole answer', async () => {
    arriveAt('/sign-in/callback/google?flow=f&state=s&code=c&extra=1');
    const fake = mount('google');
    await waitFor(() => expect(fake.get).toHaveBeenCalledTimes(1));
    expect(fake.get).toHaveBeenCalledWith('/api/v2/identity/callback/google?flow=f&state=s&code=c');
  });

  it('ignores a repeated key it does not read', async () => {
    arriveAt('/sign-in/callback/orcid?flow=f&state=s&code=c&scope=a&scope=b');
    const fake = mount('orcid');
    await waitFor(() => expect(fake.get).toHaveBeenCalledTimes(1));
    expect(fake.get).toHaveBeenCalledWith('/api/v2/identity/callback/orcid?flow=f&state=s&code=c');
  });
});

describe('the maintainer-only notice', () => {
  const MAINTAINER_ONLY: CapabilityStateMap = {
    'account.entry': { state: 'degraded', reasonKey: 'admission-maintainer-only' },
  };
  const NOTICE = 'DocSuri를 점검하고 있습니다. 잠시 후 다시 접속해 주세요.';

  function expectNotice(panel: HTMLElement) {
    const banner = within(panel).getByTestId('maintenance-banner');
    expect(banner).toHaveTextContent(NOTICE);
    expect(within(banner).getByTestId('maintenance-admin-sign-in')).toHaveTextContent(
      '관리자 로그인',
    );
  }

  it('shows the maintenance notice on the arrival page while admission is maintainer-only', async () => {
    keepFlow('google', 'flow-kept');
    arriveAt('/sign-in/callback/google?state=s&code=c');
    const fake = mount('google', () => new Promise(() => undefined), MAINTAINER_ONLY);
    expectNotice(screen.getByTestId('callback-page'));
    await waitFor(() => expect(fake.get).toHaveBeenCalledTimes(1));
    expect(fake.get).toHaveBeenCalledWith(
      '/api/v2/identity/callback/google?flow=flow-kept&state=s&code=c',
    );
  });

  it('shows it on a cancelled arrival too', () => {
    arriveAt('/sign-in/callback/google?error=access_denied&state=s');
    const fake = mount('google', undefined, MAINTAINER_ONLY);
    const panel = screen.getByTestId('callback-cancelled');
    expectNotice(panel);
    expect(panel).toHaveTextContent('로그인이 취소되었습니다');
    expect(fake.get).not.toHaveBeenCalled();
  });

  it('shows it beside a failed arrival', async () => {
    arriveAt('/sign-in/callback/google?flow=f&state=s&code=c');
    mount('google', () => apiError(503, 'DEPENDENCY_UNAVAILABLE'), MAINTAINER_ONLY);
    const back = await screen.findByTestId('callback-back');
    const panel = screen.getByTestId('callback-page');
    expect(panel).toContainElement(back);
    expectNotice(panel);
  });

  it.each([
    ['open admission', { 'account.entry': { state: 'available' } }],
    ['no states', {}],
  ] as [string, CapabilityStateMap][])('shows no notice once admission opens (%s)', (_, states) => {
    arriveAt('/sign-in/callback/google?error=access_denied&state=s');
    mount('google', undefined, states);
    expect(screen.queryByTestId('maintenance-banner')).not.toBeInTheDocument();
    cleanup();
    forgetArrival();
    arriveAt('/sign-in/callback/google?flow=f&state=s&code=c');
    mount('google', () => new Promise(() => undefined), states);
    expect(screen.getByTestId('callback-page')).toBeInTheDocument();
    expect(screen.queryByTestId('maintenance-banner')).not.toBeInTheDocument();
  });

  it('its 관리자 로그인 asks for the administrator sign-in, not the way back', () => {
    arriveAt('/sign-in/callback/google?error=access_denied&state=s');
    const fake = mount('google', undefined, MAINTAINER_ONLY);
    fireEvent.click(screen.getByTestId('maintenance-admin-sign-in'));
    expect(fake.onAdministratorSignIn).toHaveBeenCalledTimes(1);
    expect(fake.onBack).not.toHaveBeenCalled();
  });

  it.each([
    ['an authenticated answer', (settle: Settle) => settle.resolve({ state: 'authenticated' })],
    ['a 503', (settle: Settle) => settle.reject(apiError(503, 'DEPENDENCY_UNAVAILABLE'))],
  ] as [string, (settle: Settle) => void][])(
    'ignores an arrival answer that comes after 관리자 로그인 (%s)',
    async (_, late) => {
      let settle: Settle | undefined;
      const pending = new Promise<unknown>((resolve, reject) => {
        settle = { resolve, reject };
      });
      arriveAt('/sign-in/callback/google?flow=f&state=s&code=c');
      const fake = mount('google', () => pending, MAINTAINER_ONLY);
      await waitFor(() => expect(fake.get).toHaveBeenCalledTimes(1));
      fireEvent.click(screen.getByTestId('maintenance-admin-sign-in'));
      expect(fake.onAdministratorSignIn).toHaveBeenCalledTimes(1);
      await act(async () => {
        late(settle!);
        await pending.catch(() => undefined);
      });
      expect(fake.onArrived).not.toHaveBeenCalled();
      expect(screen.queryByTestId('callback-back')).not.toBeInTheDocument();
    },
  );
});

type Settle = { resolve: (value: unknown) => void; reject: (reason: unknown) => void };

describe('the arrival in App', () => {
  // Wrap `serve`'s stub to record the address's query and the request at each call.
  function recording() {
    const inner = globalThis.fetch;
    const seen: { search: string; url: string }[] = [];
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        seen.push({ search: window.location.search, url: String(input) });
        return inner(input, init);
      }),
    );
    return seen;
  }

  afterEach(() => vi.unstubAllGlobals());

  it("App takes the provider's answer out of the address in its first render, before any request", async () => {
    window.history.replaceState(null, '', '/sign-in/callback/google?flow=f&state=s&code=c');
    serve('guest');
    const seen = recording();
    render(<App />);
    expect(window.location.search).toBe('');
    expect(window.location.pathname).toBe('/sign-in/callback/google');
    await waitFor(() =>
      expect(seen.some((call) => call.url.includes('/api/v2/identity/callback/'))).toBe(true),
    );
    expect(seen.length).toBeGreaterThan(0);
    expect(seen.every((call) => call.search === '')).toBe(true);
    const callbacks = seen.filter((call) => call.url.includes('/api/v2/identity/callback/'));
    expect(callbacks).toHaveLength(1);
    expect(callbacks[0]!.url).toContain('/api/v2/identity/callback/google?flow=f&state=s&code=c');
    // The arrival's answer is followed to a signed-in shell before the stub goes away.
    expect(await screen.findByTestId('logout')).toBeInTheDocument();
  });

  it("App takes Google's own return out of the address in its first render and sends only flow, state and code", async () => {
    keepFlow('google', 'flow-kept');
    window.history.replaceState(
      null,
      '',
      '/sign-in/callback/google?state=s&code=c&scope=email%20openid&authuser=0&prompt=consent',
    );
    serve('guest');
    const seen = recording();
    render(<App />);
    expect(window.location.search).toBe('');
    await waitFor(() =>
      expect(seen.some((call) => call.url.includes('/api/v2/identity/callback/'))).toBe(true),
    );
    expect(seen.every((call) => call.search === '')).toBe(true);
    const callbacks = seen.filter((call) => call.url.includes('/api/v2/identity/callback/'));
    expect(callbacks).toHaveLength(1);
    expect(callbacks[0]!.url).toContain(
      '/api/v2/identity/callback/google?flow=flow-kept&state=s&code=c',
    );
    expect(seen.some((call) => /scope=|authuser=|prompt=/.test(call.url))).toBe(false);
    expect(await screen.findByTestId('logout')).toBeInTheDocument();
  });

  it('a cancelled return leaves the address in the first render and calls no callback route', async () => {
    window.history.replaceState(null, '', '/sign-in/callback/google?error=access_denied&state=s');
    serve('guest');
    const seen = recording();
    render(<App />);
    expect(window.location.search).toBe('');
    expect(await screen.findByTestId('callback-cancelled')).toBeInTheDocument();
    expect(seen.some((call) => call.url.includes('/api/v2/identity/callback/'))).toBe(false);
  });
});

describe('keyboard parity for the callback pages', () => {
  it('callback-back acts by Enter after Tab on the cancelled and the failed pending page', async () => {
    for (const [address, answer] of [
      ['/sign-in/callback/google?error=access_denied', () => ({})],
      ['/sign-in/callback/google?flow=f&state=s&code=c', () => apiError(409, 'CONFLICT')],
    ] as const) {
      arriveAt(address);
      const user = userEvent.setup();
      const fake = mount('google', answer);
      const back = await screen.findByTestId('callback-back');
      for (let step = 0; step < 5 && document.activeElement !== back; step += 1) await user.tab();
      expect(back).toHaveFocus();
      await user.keyboard('{Enter}');
      expect(fake.onBack).toHaveBeenCalledTimes(1);
      cleanup();
      forgetArrival();
    }
  });
});

describe('a cancelled, repeated or incomplete return', () => {
  const cases: [string, string][] = [
    ['an error return', '/sign-in/callback/google?error=access_denied&state=s'],
    ['a repeated parameter', '/sign-in/callback/google?flow=f&state=s&state=t&code=c'],
    ['a missing code', '/sign-in/callback/google?flow=f&state=s'],
    ['an unknown provider', '/sign-in/callback/github?flow=f&state=s&code=c'],
    [
      'an error beside a whole answer',
      '/sign-in/callback/google?flow=f&state=s&code=c&error=access_denied',
    ],
    ['a repeated code', '/sign-in/callback/google?flow=f&state=s&code=c&code=d'],
    ['a repeated flow', '/sign-in/callback/google?flow=f&flow=g&state=s&code=c'],
    ['a missing state', '/sign-in/callback/google?flow=f&code=c'],
    ['no flow in the address and none kept', '/sign-in/callback/google?state=s&code=c&scope=email'],
    ['only keys the page does not read', '/sign-in/callback/google?scope=email&authuser=0'],
  ];
  it.each(cases)('%s shows the cancelled message and calls nothing', (_, address) => {
    arriveAt(address);
    const provider = address.split('/')[3]!.split('?')[0]!;
    const fake = mount(provider);
    expect(screen.getByTestId('callback-cancelled')).toHaveTextContent('로그인이 취소되었습니다');
    expect(fake.get).not.toHaveBeenCalled();
    expect(window.location.search).toBe('');
    fireEvent.click(screen.getByTestId('callback-back'));
    expect(fake.onBack).toHaveBeenCalledTimes(1);
  });

  it('reads as cancelled when storage refuses the kept flow', () => {
    // The storage's own prototype: jsdom's Storage, or the setup file's stand-in.
    const storage = Object.getPrototypeOf(window.sessionStorage) as Storage;
    vi.spyOn(storage, 'getItem').mockImplementation(() => {
      throw new Error('denied');
    });
    vi.spyOn(storage, 'setItem').mockImplementation(() => {
      throw new Error('denied');
    });
    keepFlow('google', 'flow-x');
    arriveAt('/sign-in/callback/google?state=s&code=c');
    const fake = mount('google');
    expect(screen.getByTestId('callback-cancelled')).toBeInTheDocument();
    expect(fake.get).not.toHaveBeenCalled();
  });
});

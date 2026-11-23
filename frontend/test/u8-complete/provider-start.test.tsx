// U8 plan Step 20 item 11 (the person's decision of 2026-10-25, "Count every start, free
// places at once"): the entry panel keeps its provider buttons disabled once it is leaving
// for the provider and enables them on a return from the page cache; a refused provider
// start shows the wait read from `Retry-After` and the email sign-in hint; and the
// transport copies `Retry-After` into the refusal of a 429 whose body names no wait.
import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, retryAfterHeader, Transport } from '../../src/api';
import { CompleteEntry, providerWaitText } from '../../src/u8-entry/entry-panel';
import type { CapabilityStateMap } from '../../src/u8-shell/provider-notice';
import { fakeClient, Fresh, json, type Answer } from './helpers';

const AVAILABLE: CapabilityStateMap = {
  'provider.google': { state: 'available' },
  'provider.orcid': { state: 'available' },
};

afterEach(() => {
  vi.restoreAllMocks();
  window.sessionStorage.clear();
});

function leavingTo(assign: (address: string) => void) {
  vi.spyOn(window, 'location', 'get').mockReturnValue({
    ...window.location,
    origin: 'http://127.0.0.1:18109',
    pathname: '/',
    hash: '',
    assign,
  } as Location);
}

function entry(answer: Answer) {
  const fake = fakeClient(answer);
  render(
    <Fresh>
      <CompleteEntry
        client={fake.transport}
        states={AVAILABLE}
        onSignedIn={vi.fn(async () => undefined)}
      />
    </Fresh>,
  );
  return fake;
}

function pageShow(persisted: boolean) {
  const event = new Event('pageshow');
  Object.defineProperty(event, 'persisted', { value: persisted });
  window.dispatchEvent(event);
}

function limited(retryAfterSeconds?: number, messageKey = 'request.rate_limited'): ApiError {
  return new ApiError(429, {
    code: 'RATE_LIMITED',
    requestId: 'req-start-1',
    retryable: true,
    messageKey,
    ...(retryAfterSeconds !== undefined ? { retryAfterSeconds } : {}),
  });
}

// The person's decision of 2026-10-25, "Different text for site-wide": both wordings,
// copied exactly from the plan, with N the wait from `Retry-After`.
const NETWORK_TEXT = (n: number) =>
  `같은 네트워크에서 진행 중인 Google·ORCID 로그인이 많아요. ${n}초 뒤에 다시 시도하거나 이메일로 로그인해 주세요`;
const SITE_TEXT = (n: number) =>
  `지금 Google·ORCID 로그인을 하려는 사람이 많아요. ${n}초 뒤에 다시 시도하거나 이메일로 로그인해 주세요`;

describe('leaving for the provider', () => {
  it('keeps both provider buttons disabled after the page leaves, so a second tap sends nothing', async () => {
    const assign = vi.fn();
    leavingTo(assign);
    const fake = entry(() => ({
      authorizationUrl: 'https://accounts.example.test/a',
      flowId: 'f1',
    }));
    fireEvent.click(screen.getByTestId('provider-google'));
    await waitFor(() => expect(assign).toHaveBeenCalledTimes(1));
    expect(screen.getByTestId('provider-google')).toBeDisabled();
    expect(screen.getByTestId('provider-orcid')).toBeDisabled();
    fireEvent.click(screen.getByTestId('provider-google'));
    fireEvent.click(screen.getByTestId('provider-orcid'));
    expect(fake.post).toHaveBeenCalledTimes(1);
  });

  it('enables the buttons again on a return from the page cache, and not on a fresh show', async () => {
    const assign = vi.fn();
    leavingTo(assign);
    const fake = entry(() => ({
      authorizationUrl: 'https://accounts.example.test/a',
      flowId: 'f2',
    }));
    fireEvent.click(screen.getByTestId('provider-orcid'));
    await waitFor(() => expect(assign).toHaveBeenCalledTimes(1));
    pageShow(false);
    expect(screen.getByTestId('provider-orcid')).toBeDisabled();
    pageShow(true);
    await waitFor(() => expect(screen.getByTestId('provider-orcid')).toBeEnabled());
    // Back from Google or ORCID, another try starts again.
    fireEvent.click(screen.getByTestId('provider-google'));
    await waitFor(() => expect(fake.post).toHaveBeenCalledTimes(2));
  });
});

describe('a refused provider start', () => {
  it('shows the wait from Retry-After and the email sign-in hint, and stays on the entry', async () => {
    const assign = vi.fn();
    leavingTo(assign);
    entry(() => limited(42));
    fireEvent.click(screen.getByTestId('provider-google'));
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent(providerWaitText(42));
    expect(alert).toHaveTextContent('42초 뒤에 다시 시도하거나 이메일로 로그인해 주세요');
    expect(screen.getByTestId('provider-google')).toBeEnabled();
    expect(screen.getByTestId('entry-email')).toBeInTheDocument();
    expect(assign).not.toHaveBeenCalled();
  });

  it('keeps the generic busy copy when the refusal names no wait', async () => {
    leavingTo(vi.fn());
    entry(() => limited());
    fireEvent.click(screen.getByTestId('provider-google'));
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('요청이 많아요. 잠시 후 다시 시도해 주세요');
    expect(alert).not.toHaveTextContent('이메일로 로그인');
  });

  it('keeps the generic busy copy for a site-wide reason that names no wait', async () => {
    leavingTo(vi.fn());
    entry(() => limited(undefined, 'identity-start.site-places'));
    fireEvent.click(screen.getByTestId('provider-orcid'));
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('요청이 많아요. 잠시 후 다시 시도해 주세요');
    expect(alert).not.toHaveTextContent('Google·ORCID 로그인');
  });
});

describe('the busy text follows the refusal reason', () => {
  const NETWORK_REASONS = ['places', 'unfinished-starts', 'starts'];
  const SITE_REASONS = ['site-places', 'site-starts', 'conflict'];

  it.each(NETWORK_REASONS)('shows the network text for %s', async (reason) => {
    const assign = vi.fn();
    leavingTo(assign);
    entry(() => limited(30, `identity-start.${reason}`));
    fireEvent.click(screen.getByTestId('provider-google'));
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent(NETWORK_TEXT(30));
    expect(alert).not.toHaveTextContent('하려는 사람이 많아요');
    expect(screen.getByTestId('provider-google')).toBeEnabled();
    expect(assign).not.toHaveBeenCalled();
  });

  it.each(SITE_REASONS)('shows the site text for %s', async (reason) => {
    const assign = vi.fn();
    leavingTo(assign);
    entry(() => limited(12, `identity-start.${reason}`));
    fireEvent.click(screen.getByTestId('provider-orcid'));
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent(SITE_TEXT(12));
    expect(alert).not.toHaveTextContent('같은 네트워크에서');
    expect(screen.getByTestId('entry-email')).toBeInTheDocument();
    expect(assign).not.toHaveBeenCalled();
  });

  it('falls back to the network text for an unknown or a built message key', async () => {
    for (const key of ['identity-start.something-new', 'request.rate_limited', 'site-places']) {
      leavingTo(vi.fn());
      const view = entry(() => limited(5, key));
      fireEvent.click(screen.getByTestId('provider-google'));
      const alert = await screen.findByRole('alert');
      expect(alert).toHaveTextContent(NETWORK_TEXT(5));
      expect(view.post).toHaveBeenCalledTimes(1);
      cleanup();
    }
  });

  it('builds each wording exactly, with the wait in seconds', () => {
    expect(providerWaitText(1)).toBe(NETWORK_TEXT(1));
    expect(providerWaitText(300, 'identity-start.places')).toBe(NETWORK_TEXT(300));
    expect(providerWaitText(30, 'identity-start.site-places')).toBe(SITE_TEXT(30));
    expect(providerWaitText(1, 'identity-start.conflict')).toBe(SITE_TEXT(1));
    expect(providerWaitText(9, 'identity-start.site-starts')).toBe(SITE_TEXT(9));
  });
});

describe('the transport and Retry-After', () => {
  function answering(status: number, body: unknown, headers: Record<string, string> = {}) {
    return vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const path = typeof input === 'string' ? input : (input as Request).url;
      if (path.endsWith('/api/v2/session'))
        return json({ signedIn: false, csrfToken: crypto.randomUUID() });
      return new Response(JSON.stringify(body), {
        status,
        headers: { 'Content-Type': 'application/json', ...headers },
      });
    });
  }

  async function refusalOf(): Promise<ApiError> {
    const failure = await new Transport()
      .post('/api/v2/c02/access-begin-identity-flow', { provider: 'google' })
      .catch((error: unknown) => error);
    expect(failure).toBeInstanceOf(ApiError);
    return failure as ApiError;
  }

  const busyBody = {
    code: 'RATE_LIMITED',
    requestId: 'r1',
    retryable: true,
    messageKey: 'request.rate_limited',
  };

  it('copies the header into a 429 whose body names no wait', async () => {
    answering(429, busyBody, { 'Retry-After': '17' });
    expect((await refusalOf()).envelope.retryAfterSeconds).toBe(17);
  });

  it("keeps the body's own wait, and copies nothing for another status or a malformed header", async () => {
    answering(429, { ...busyBody, retryAfterSeconds: 5 }, { 'Retry-After': '17' });
    expect((await refusalOf()).envelope.retryAfterSeconds).toBe(5);
    vi.restoreAllMocks();
    answering(503, { ...busyBody, code: 'DEPENDENCY_UNAVAILABLE' }, { 'Retry-After': '17' });
    expect((await refusalOf()).envelope.retryAfterSeconds).toBeUndefined();
    vi.restoreAllMocks();
    answering(429, busyBody, { 'Retry-After': 'Wed, 21 Oct 2026 07:28:00 GMT' });
    expect((await refusalOf()).envelope.retryAfterSeconds).toBeUndefined();
  });

  it('reads only a whole number of seconds', () => {
    // Up to seven digits, so a month's wait (at most 2,678,400 s) is read (Step 91(d)).
    expect(retryAfterHeader('30')).toBe(30);
    expect(retryAfterHeader(' 1 ')).toBe(1);
    expect(retryAfterHeader('2678400')).toBe(2678400);
    expect(retryAfterHeader('1234567')).toBe(1234567);
    for (const value of [null, '', '-1', '1.5', 'soon', '12345678']) {
      expect(retryAfterHeader(value)).toBeUndefined();
    }
  });
});

describe('keyboard parity for the provider buttons', () => {
  it('begins an available provider by Enter and by Space, and Tab skips a disabled one', async () => {
    for (const key of ['{Enter}', ' ']) {
      const assign = vi.fn();
      leavingTo(assign);
      const user = userEvent.setup();
      const fake = fakeClient(() => ({
        authorizationUrl: 'https://accounts.example.test/a',
        flowId: 'f-key',
      }));
      render(
        <Fresh>
          <CompleteEntry
            client={fake.transport}
            states={{
              'provider.google': { state: 'available' },
              'provider.orcid': { state: 'unavailable' },
            }}
            onSignedIn={vi.fn(async () => undefined)}
          />
        </Fresh>,
      );
      const google = screen.getByTestId('provider-google');
      const orcid = screen.getByTestId('provider-orcid');
      expect(orcid).toBeDisabled();
      expect(screen.getByText(/ORCID 로그인을 사용할 수 없습니다/)).toBeInTheDocument();
      google.focus();
      await user.keyboard(key);
      await waitFor(() => expect(assign).toHaveBeenCalledWith('https://accounts.example.test/a'));
      expect(fake.post).toHaveBeenCalledWith(
        '/api/v2/c02/access-begin-identity-flow',
        expect.objectContaining({ provider: 'google', intent: 'sign_in' }),
      );
      cleanup();
      vi.restoreAllMocks();
    }
  });

  it('skips a natively disabled provider button with Tab', async () => {
    const user = userEvent.setup();
    const fake = fakeClient(() => ({}));
    render(
      <Fresh>
        <CompleteEntry
          client={fake.transport}
          states={{
            'provider.google': { state: 'available' },
            'provider.orcid': { state: 'unavailable' },
          }}
          onSignedIn={vi.fn(async () => undefined)}
        />
      </Fresh>,
    );
    screen.getByTestId('provider-google').focus();
    await user.tab();
    expect(screen.getByTestId('provider-orcid')).not.toHaveFocus();
    expect(document.activeElement).not.toBe(document.body);
  });
});

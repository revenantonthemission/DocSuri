// U8 plan Step 92(f): account mail refused at its limit (L1-10) and while none can be sent
// (L1-53). Every screen that asks for account mail says when email can be sent again, or
// that it cannot be sent now, in one text, never the request's acknowledgement.
import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, Transport, accountMailLimitText } from '../../src/api';
import { describeError } from '../../src/ui';
import { AccountControls } from '../../src/account-controls';
import { AuthenticationPanel } from '../../src/auth';
import { CompleteEntry } from '../../src/u8-entry/entry-panel';
import { ProviderStateNotice } from '../../src/u8-shell/provider-notice';
import { fakeClient as accountClient, policy } from '../u2-account-personal-controls/fixtures';
import { apiError, fakeClient, Fresh, json, type Answer } from './helpers';

vi.mock('qrcode', () => ({ default: { toCanvas: vi.fn().mockResolvedValue(undefined) } }));

const DAY_TEXT =
  '지금은 이메일을 보낼 수 없습니다. 11월 2일 오전 9시(한국 시간)부터 다시 보낼 수 있습니다.';
const MONTH_TEXT =
  '지금은 이메일을 보낼 수 없습니다. 11월 1일 오전 9시(한국 시간)부터 다시 보낼 수 있습니다.';
const NO_WAIT_TEXT =
  '지금은 이메일을 보낼 수 없습니다. 이메일 발송 한도에 도달했습니다. 발송 한도가 초기화되면 다시 요청해 주세요.';
const HELD_TEXT = '지금은 이메일을 보낼 수 없습니다. 나중에 다시 시도해 주세요.';

function limit(retryAfterSeconds?: number): ApiError {
  return new ApiError(429, {
    code: 'RATE_LIMITED',
    requestId: 'req-limit-1',
    retryable: true,
    messageKey: 'account-mail.allowance-exhausted',
    ...(retryAfterSeconds !== undefined ? { retryAfterSeconds } : {}),
  });
}

function unavailable(): ApiError {
  return new ApiError(429, {
    code: 'RATE_LIMITED',
    requestId: 'req-held-1',
    retryable: true,
    messageKey: 'account-mail.unavailable',
  });
}

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  window.history.replaceState(null, '', '/');
});

function atNovemberFirst() {
  vi.useFakeTimers({ toFake: ['Date'] });
  vi.setSystemTime(new Date('2026-11-01T14:30:00Z'));
}

describe('the limit text', () => {
  it("says when email can be sent again for the day's and the month's limit", () => {
    const now = Date.parse('2026-11-01T14:30:00Z');
    expect(accountMailLimitText(34200, now)).toBe(DAY_TEXT);
    expect(accountMailLimitText(34199, now)).toBe(DAY_TEXT);
    expect(accountMailLimitText(2322000, Date.parse('2026-10-05T03:00:00Z'))).toBe(MONTH_TEXT);
    const without = accountMailLimitText(undefined);
    expect(without).toBe(NO_WAIT_TEXT);
    expect(without).not.toMatch(/\d+월|\d+일|오전|오후|\d+시/);
  });

  it('answers the limit in describeError for every screen', () => {
    atNovemberFirst();
    const shown = describeError(limit(34200));
    expect(shown.tone).toBe('alert');
    expect(shown.text).toBe(DAY_TEXT);
    expect(shown.requestId).toBe('req-limit-1');
    const busy = describeError(
      new ApiError(429, {
        code: 'RATE_LIMITED',
        requestId: 'req-busy',
        retryable: true,
        messageKey: 'request.rate_limited',
      }),
    );
    expect(busy.text).toBe('요청이 많아요. 잠시 후 다시 시도해 주세요');
  });
});

function accountView() {
  const client = accountClient();
  render(
    <AccountControls
      client={client.transport}
      policy={policy}
      onAuthorityChange={vi.fn().mockResolvedValue({})}
      onLifecycle={vi.fn()}
    />,
  );
  return client;
}

async function requestEmailChange() {
  await screen.findByDisplayValue('연구자 A');
  fireEvent.click(screen.getByText('비밀번호와 이메일'));
  fireEvent.change(screen.getByLabelText('현재 비밀번호'), {
    target: { value: crypto.randomUUID() },
  });
  fireEvent.change(screen.getByLabelText('새 이메일'), {
    target: { value: 'next@example.test' },
  });
  fireEvent.click(screen.getByText('이메일 변경 인증 요청'));
}

function registerPanel(answer: Answer) {
  const fake = fakeClient(answer);
  render(
    <AuthenticationPanel
      client={fake.transport}
      policy={policy}
      onSignedIn={vi.fn()}
      onLifecycle={vi.fn()}
    />,
  );
  return fake;
}

async function requestVerification() {
  fireEvent.click(screen.getByRole('button', { name: '가입하기' }));
  fireEvent.change(screen.getByLabelText('이메일'), { target: { value: 'x@example.test' } });
  fireEvent.click(screen.getByText('인증 안내 다시 요청'));
}

describe("U2's screens at the limit", () => {
  it('the email change and the verification request say when email can be sent again', async () => {
    atNovemberFirst();
    const client = accountView();
    client.post.mockRejectedValueOnce(limit(34200));
    await requestEmailChange();
    expect(await screen.findByText(new RegExp(DAY_TEXT.slice(0, 18)))).toHaveTextContent(DAY_TEXT);
    expect(screen.queryByText('요청 결과를 확인했어요')).toBeNull();
    cleanup();

    registerPanel((path) =>
      path === '/api/v2/c02/access-request-verification' ? limit(34200) : { state: 'anonymous' },
    );
    await requestVerification();
    expect(await screen.findByText(new RegExp(DAY_TEXT.slice(0, 18)))).toHaveTextContent(DAY_TEXT);
    expect(screen.queryByText(/인증 안내를 요청했어요/)).toBeNull();
  });
});

describe('the transport', () => {
  it("reads a month's wait from Retry-After", async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        if (String(input).endsWith('/api/v2/session'))
          return json({ signedIn: false, csrfToken: crypto.randomUUID() });
        return new Response(
          JSON.stringify({
            code: 'RATE_LIMITED',
            requestId: 'r-month',
            retryable: true,
            messageKey: 'account-mail.allowance-exhausted',
          }),
          {
            status: 429,
            headers: { 'Content-Type': 'application/json', 'Retry-After': '2322000' },
          },
        );
      }),
    );
    const failure = await new Transport()
      .post('/api/v2/c02/access-request-password-reset', { email: 'x@example.test' })
      .catch((error: unknown) => error);
    expect(failure).toBeInstanceOf(ApiError);
    expect((failure as ApiError).envelope.retryAfterSeconds).toBe(2322000);
  });
});

const HELD_ABSENT = [
  '요청을 접수했습니다',
  '요청 결과를 확인했어요',
  '인증 안내를 요청했어요',
  '요청이 많아요',
  '오전',
  '한국 시간',
];

function expectHeldOnly() {
  const page = document.body.textContent ?? '';
  expect(page).toContain(HELD_TEXT);
  for (const absent of HELD_ABSENT) expect(page).not.toContain(absent);
}

function completeEntry(answer: Answer) {
  const fake = fakeClient(answer);
  render(
    <Fresh>
      <CompleteEntry
        client={fake.transport}
        states={{}}
        onSignedIn={vi.fn(async () => undefined)}
      />
    </Fresh>,
  );
  return fake;
}

describe('account mail held or Resend down (L1-53)', () => {
  it('says email cannot be sent now in describeError', () => {
    const shown = describeError(unavailable());
    expect(shown.tone).toBe('alert');
    expect(shown.text).toBe(HELD_TEXT);
    expect(shown.requestId).toBe('req-held-1');
  });

  it.each(['entry-reset', 'entry-reactivate'])(
    "CompleteEntry's %s says email cannot be sent now",
    async (testId) => {
      const fake = completeEntry(() => unavailable());
      fireEvent.change(screen.getByTestId('entry-email'), {
        target: { value: 'x@example.test' },
      });
      fireEvent.click(screen.getByTestId(testId));
      await waitFor(() => expect(fake.post).toHaveBeenCalledTimes(1));
      expect(await screen.findByRole('alert')).toHaveTextContent(HELD_TEXT);
      expectHeldOnly();
    },
  );

  it("verify-email's ask-again says email cannot be sent now", async () => {
    window.history.replaceState(
      null,
      '',
      '/account/verify-email#challenge=ch-7&proof=pr-7&flow=fl-7',
    );
    completeEntry((path) =>
      path === '/api/v2/c02/access-request-verification'
        ? unavailable()
        : apiError(403, 'FORBIDDEN'),
    );
    fireEvent.click(screen.getByTestId('proof-submit'));
    fireEvent.change(await screen.findByTestId('proof-ask-email'), {
      target: { value: 'x@example.test' },
    });
    fireEvent.click(screen.getByTestId('proof-ask-again'));
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent(HELD_TEXT));
    expectHeldOnly();
  });

  it("U2's email change says email cannot be sent now", async () => {
    const client = accountView();
    client.post.mockRejectedValueOnce(unavailable());
    await requestEmailChange();
    await screen.findByText(new RegExp(HELD_TEXT.slice(0, 18)));
    expectHeldOnly();
  });

  it("U2's verification request says email cannot be sent now", async () => {
    registerPanel((path) =>
      path === '/api/v2/c02/access-request-verification' ? unavailable() : { state: 'anonymous' },
    );
    await requestVerification();
    await screen.findByText(new RegExp(HELD_TEXT.slice(0, 18)));
    expectHeldOnly();
  });

  it('the mail notice says the same sentence while Resend reads unavailable', () => {
    render(
      <ProviderStateNotice
        states={{
          'provider.resend': { state: 'unavailable', reasonKey: 'provider.observed-down' },
        }}
        feature="mail"
      />,
    );
    expect(screen.getByTestId('provider-notice-mail').textContent).toBe(HELD_TEXT);
  });

  it('the notice and the refusal both show while Resend is observed down', async () => {
    const fake = fakeClient(() => unavailable());
    render(
      <Fresh>
        <CompleteEntry
          client={fake.transport}
          states={{
            'provider.resend': { state: 'unavailable', reasonKey: 'provider.observed-down' },
          }}
          onSignedIn={vi.fn(async () => undefined)}
        />
      </Fresh>,
    );
    fireEvent.change(screen.getByTestId('entry-email'), { target: { value: 'x@example.test' } });
    fireEvent.click(screen.getByTestId('entry-reset'));
    expect(await screen.findByRole('alert')).toHaveTextContent(HELD_TEXT);
    expect(screen.getByTestId('provider-notice-mail').textContent).toBe(HELD_TEXT);
  });
});

// U8 plan Step 42, the first-sign-in steps (BR8.6, A3, BR3.8): the required consents and
// their message, the reset notices, the MFA prompt, and the complete entry that follows
// each sign-in answer, reads email-link proofs from the fragment and begins a provider.
import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  AdminMfaPrompt,
  ConsentStep,
  RESET_NOT_SENT,
  ResetRequiredNotice,
} from '../../src/u8-entry/first-sign-in';
import { EmailChangeProof } from '../../src/u8-entry/email-change-proof';
import { ApiError } from '../../src/api';
import {
  CompleteEntry,
  controlPolicyFor,
  FRESH_BROWSER,
  PRODUCTION_ORIGIN,
  RESET_REQUESTED,
} from '../../src/u8-entry/entry-panel';
import { FLOW_KEY } from '../../src/u8-entry/callback-page';
import type { CapabilityStateMap } from '../../src/u8-shell/provider-notice';
import { apiError, fakeClient, Fresh, type Answer } from './helpers';

const POLICY = { policyId: 'u8-synthetic-v1', revision: '1' };
const FULL = {
  revision: 'catalog-r1',
  capabilities: [{ id: 'operations.ledger', state: 'available' }],
};
const PUBLIC = { manifestRevision: 'm1', items: [] };
// The passwords these tests type, generated per run (L1-36).
const SIGN_IN_VALUE = `pass-${crypto.randomUUID().slice(0, 8)}-1`;
const NEW_VALUE = `new-${crypto.randomUUID().slice(0, 8)}-1`;

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
  window.sessionStorage.clear();
  window.history.replaceState(null, '', '/');
});

describe('ConsentStep', () => {
  function consent(
    answer: Answer = () => ({
      items: [{ purposeId: 'local-research', decision: 'revoked', revision: '4' }],
    }),
  ) {
    const fake = fakeClient(answer);
    const onComplete = vi.fn();
    render(
      <ConsentStep
        client={fake.transport}
        policy={POLICY}
        purposes={['local-research', 'personalization']}
        onComplete={onComplete}
      />,
    );
    return { ...fake, onComplete };
  }

  it('refuses to continue without the required consent and says so', () => {
    const fake = consent();
    expect(screen.getByRole('heading', { name: '처리 동의' })).toHaveFocus();
    expect(screen.getByTestId('consent-local-research')).toHaveAttribute('aria-required', 'true');
    fireEvent.click(screen.getByTestId('consent-continue'));
    expect(screen.getByRole('alert')).toHaveTextContent('필수 항목에 동의해야 계속할 수 있습니다');
    expect(screen.getByTestId('consent-summary')).toHaveFocus();
    expect(fake.read).not.toHaveBeenCalled();
  });

  it('records each shown purpose against its revision, the optional one left off', async () => {
    const fake = consent();
    fireEvent.click(screen.getByTestId('consent-local-research'));
    fireEvent.click(screen.getByTestId('consent-continue'));
    await waitFor(() => expect(fake.onComplete).toHaveBeenCalledTimes(1));
    expect(fake.post).toHaveBeenCalledWith('/api/v2/c02/access-update-consent', {
      purposeId: 'local-research',
      decision: 'granted',
      policyRef: POLICY,
      expectedRevision: '4',
    });
    expect(fake.post).toHaveBeenCalledWith('/api/v2/c02/access-update-consent', {
      purposeId: 'personalization',
      decision: 'revoked',
      policyRef: POLICY,
      expectedRevision: '0',
    });
  });

  it('keeps the choices when recording fails', async () => {
    const fake = consent(() => apiError(503, 'UNAVAILABLE'));
    fireEvent.click(screen.getByTestId('consent-local-research'));
    fireEvent.click(screen.getByTestId('consent-continue'));
    await waitFor(() => expect(screen.getByTestId('consent-summary')).toHaveFocus());
    expect(screen.getByTestId('consent-local-research')).toBeChecked();
    expect(fake.onComplete).not.toHaveBeenCalled();
  });
});

describe('ResetRequiredNotice', () => {
  it('shows the reset notices', () => {
    const view = render(<ResetRequiredNotice delivery="accepted" />);
    const notice = () => screen.getByTestId('reset-required').textContent ?? '';
    expect(notice()).toBe(
      '보안을 위해 비밀번호를 다시 설정해야 합니다. 이메일로 재설정 링크를 보냈습니다.',
    );
    view.rerender(<ResetRequiredNotice delivery="held" />);
    expect(notice()).toBe(
      '보안을 위해 비밀번호를 다시 설정해야 합니다. 지금은 이메일을 보낼 수 없습니다. 나중에 다시 시도해 주세요.',
    );
    expect(notice()).not.toContain('잠시 후');
    view.rerender(<ResetRequiredNotice delivery="over_allowance" />);
    expect(notice()).toBe(
      '보안을 위해 비밀번호를 다시 설정해야 합니다. 지금은 이메일 발송 한도에 도달해 재설정 링크를 보내지 못했습니다. 발송 한도가 초기화된 뒤 다시 로그인해 주세요.',
    );
    expect(notice()).not.toContain('잠시 후');
    expect(notice()).not.toMatch(/\d+월|\d+일|오전|오후/);
  });
});

describe('AdminMfaPrompt', () => {
  it('offers enrolment in setup mode and asks to sign in again', () => {
    const fake = fakeClient(() => ({}));
    const onSignInAgain = vi.fn();
    render(
      <AdminMfaPrompt
        client={fake.transport}
        policy={POLICY}
        mode="setup"
        onSignInAgain={onSignInAgain}
      />,
    );
    expect(screen.getByRole('heading', { name: '관리자 추가 인증' })).toHaveFocus();
    expect(screen.getByTestId('admin-mfa-prompt')).toHaveTextContent('추가 인증(MFA)을 등록해야');
    expect(screen.getByText('추가 인증(MFA)')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('admin-mfa-sign-in-again'));
    expect(onSignInAgain).toHaveBeenCalledTimes(1);
  });
});

function entry(answer: Answer, states: CapabilityStateMap = {}, initialAnswer?: unknown) {
  const fake = fakeClient(answer);
  const onSignedIn = vi.fn(async () => undefined);
  render(
    <Fresh>
      <CompleteEntry
        client={fake.transport}
        states={states}
        onSignedIn={onSignedIn}
        {...(initialAnswer !== undefined ? { initialAnswer } : {})}
      />
    </Fresh>,
  );
  return { ...fake, onSignedIn };
}

function signIn() {
  fireEvent.change(screen.getByTestId('entry-email'), { target: { value: 'member@example.test' } });
  fireEvent.change(screen.getByTestId('entry-password'), { target: { value: SIGN_IN_VALUE } });
  fireEvent.click(screen.getByTestId('entry-submit'));
}

describe('the complete entry', () => {
  it('chooses the control policy by origin', () => {
    expect(controlPolicyFor(PRODUCTION_ORIGIN).policyId).toBe('docsuri-production-v1');
    expect(controlPolicyFor('http://127.0.0.1:18109').policyId).toBe('u8-synthetic-v1');
  });

  it('validates the form, then signs a member in', async () => {
    const fake = entry((path) =>
      path === '/api/v2/c02/access-login'
        ? { state: 'authenticated', session: { authenticationLevel: 'primary' } }
        : FULL,
    );
    fireEvent.click(screen.getByTestId('entry-submit'));
    expect(screen.getByText('이메일과 비밀번호를 확인해 주세요')).toBeInTheDocument();
    signIn();
    await waitFor(() => expect(fake.onSignedIn).toHaveBeenCalledTimes(1));
    expect(fake.post).toHaveBeenCalledWith(
      '/api/v2/c02/access-login',
      expect.objectContaining({ email: 'member@example.test', password: SIGN_IN_VALUE }),
    );
    expect(fake.get).toHaveBeenCalledWith('/api/v2/capabilities');
  });

  it('follows the second factor, then signs in', async () => {
    const fake = entry((path) => {
      if (path === '/api/v2/c02/access-login')
        return { state: 'mfa_required', challengeId: 'ch-1', flowBinding: 'fb-1' };
      if (path === '/api/v2/c02/access-verify-mfa') return {};
      return FULL;
    });
    signIn();
    fireEvent.change(await screen.findByTestId('entry-factor'), { target: { value: '123456' } });
    fireEvent.click(screen.getByTestId('mfa-submit'));
    await waitFor(() => expect(fake.onSignedIn).toHaveBeenCalled());
    expect(fake.post).toHaveBeenCalledWith('/api/v2/c02/access-verify-mfa', {
      factorKind: 'totp',
      verification: { challengeId: 'ch-1', flowBinding: 'fb-1', proof: '123456' },
    });
    // The limited session's CSRF token is read before the second factor is sent.
    const verifyAt = fake.post.mock.calls.findIndex(
      ([path]) => path === '/api/v2/c02/access-verify-mfa',
    );
    expect(fake.bootstrap).toHaveBeenCalledTimes(1);
    expect(fake.bootstrap.mock.invocationCallOrder[0]).toBeLessThan(
      fake.post.mock.invocationCallOrder[verifyAt]!,
    );
  });

  it('shows the consent step for a migrated account', async () => {
    const fake = entry((path) =>
      path === '/api/v2/c02/access-login'
        ? { state: 'consent_pending', consentPurposeIds: ['local-research'] }
        : { items: [] },
    );
    signIn();
    expect(await screen.findByTestId('consent-step')).toBeInTheDocument();
    expect(screen.queryByTestId('consent-personalization')).toBeNull();
    // The consent-pending session's CSRF token is read before its consents are listed.
    expect(fake.bootstrap).toHaveBeenCalledTimes(1);
    const listed = fake.read.mock.invocationCallOrder[0] ?? fake.post.mock.invocationCallOrder[1];
    if (listed !== undefined)
      expect(fake.bootstrap.mock.invocationCallOrder[0]).toBeLessThan(listed);
  });

  it('shows the reset notice when a password reset is required', async () => {
    entry(() => ({ state: 'reset_required', delivery: 'held' }));
    signIn();
    expect(await screen.findByTestId('reset-required')).toHaveTextContent(RESET_NOT_SENT);
  });

  it('routes an administrator setup-only session to the MFA prompt', async () => {
    const fake = entry((path) =>
      path === '/api/v2/c02/access-login'
        ? { state: 'authenticated', session: { authenticationLevel: 'primary' } }
        : PUBLIC,
    );
    signIn();
    expect(await screen.findByTestId('admin-mfa-prompt')).toHaveTextContent('등록해야');
    expect(fake.onSignedIn).not.toHaveBeenCalled();
    fireEvent.click(screen.getByTestId('admin-mfa-sign-in-again'));
    await waitFor(() => expect(fake.onSignedIn).toHaveBeenCalledTimes(1));
  });

  it("follows an identity callback's answer handed on by the arrival page", async () => {
    entry(
      () => PUBLIC,
      {},
      { state: 'mfa_required', mfaChallenge: { challengeId: 'c', flowBinding: 'f' } },
    );
    expect(await screen.findByTestId('mfa-form')).toBeInTheDocument();
  });

  it('requests a password reset and says so without saying whether the account exists', async () => {
    const fake = entry(() => ({}));
    fireEvent.click(screen.getByTestId('entry-reset'));
    expect(screen.getByText('이메일을 입력해 주세요')).toBeInTheDocument();
    fireEvent.change(screen.getByTestId('entry-email'), { target: { value: 'x@example.test' } });
    fireEvent.click(screen.getByTestId('entry-reset'));
    expect(await screen.findByText(RESET_REQUESTED)).toBeInTheDocument();
    expect(fake.post).toHaveBeenCalledWith('/api/v2/c02/access-request-password-reset', {
      email: 'x@example.test',
      policyRef: POLICY,
    });
  });

  it('shows the mail notice and the maintenance banner from the capability states', () => {
    entry(() => ({}), {
      'provider.resend': { state: 'unavailable' },
      'account.entry': { state: 'degraded', reasonKey: 'admission-maintainer-only' },
    });
    expect(screen.getByTestId('provider-notice-mail')).toBeInTheDocument();
    expect(screen.getByTestId('maintenance-banner')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('maintenance-admin-sign-in'));
    expect(screen.getByTestId('entry-email')).toHaveFocus();
  });

  it("the notice's 관리자 로그인 leaves a proof form for the sign-in form", async () => {
    atLink('verify-email');
    entry(
      (path) =>
        path === '/api/v2/c02/access-login'
          ? { state: 'mfa_required', challengeId: 'ch-1', flowBinding: 'fb-1' }
          : {},
      { 'account.entry': { state: 'degraded', reasonKey: 'admission-maintainer-only' } },
    );
    // A proof form holds no sign-in field: the old handler had nothing to focus.
    expect(screen.getByTestId('proof-form')).toBeInTheDocument();
    expect(screen.queryByTestId('entry-email')).toBeNull();
    fireEvent.click(screen.getByTestId('maintenance-admin-sign-in'));
    await waitFor(() => expect(screen.getByTestId('entry-email')).toHaveFocus());
    expect(screen.queryByTestId('proof-form')).toBeNull();
    expect(screen.getAllByTestId('maintenance-banner')).toHaveLength(1);
    // The same from the second-factor form, which replaces the sign-in form.
    signIn();
    expect(await screen.findByTestId('mfa-form')).toBeInTheDocument();
    expect(screen.queryByTestId('entry-email')).toBeNull();
    fireEvent.click(screen.getByTestId('maintenance-admin-sign-in'));
    await waitFor(() => expect(screen.getByTestId('entry-email')).toHaveFocus());
    expect(screen.queryByTestId('mfa-form')).toBeNull();
  });

  it("the notice's 관리자 로그인 takes a refused code's message away with the second-factor form", async () => {
    const refused = new ApiError(403, {
      code: 'FORBIDDEN',
      requestId: 'local',
      retryable: false,
      messageKey: 'request.forbidden',
    } as ConstructorParameters<typeof ApiError>[1]);
    entry(
      (path) => {
        if (path === '/api/v2/c02/access-login')
          return { state: 'mfa_required', challengeId: 'ch-1', flowBinding: 'fb-1' };
        return path === '/api/v2/c02/access-verify-mfa' ? refused : {};
      },
      { 'account.entry': { state: 'degraded', reasonKey: 'admission-maintainer-only' } },
    );
    signIn();
    fireEvent.change(await screen.findByTestId('entry-factor'), { target: { value: '000000' } });
    fireEvent.click(screen.getByTestId('mfa-submit'));
    expect(await screen.findByRole('alert')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('maintenance-admin-sign-in'));
    await waitFor(() => expect(screen.getByTestId('entry-email')).toHaveFocus());
    expect(screen.queryByTestId('mfa-form')).toBeNull();
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('begins a provider sign-in, keeping its flow in this tab, only to an https address', async () => {
    const assign = vi.fn();
    vi.spyOn(window, 'location', 'get').mockReturnValue({
      ...window.location,
      origin: 'http://127.0.0.1:18109',
      pathname: '/',
      hash: '',
      assign,
    } as Location);
    const address = 'https://accounts.example.test/authorize?x=1';
    const fake = entry(() => ({ authorizationUrl: address, flowId: 'flow-7' }), {
      'provider.google': { state: 'available' },
      'provider.orcid': { state: 'unavailable' },
    });
    expect(screen.getByTestId('provider-orcid')).toBeDisabled();
    expect(screen.getByText(/ORCID 로그인을 사용할 수 없습니다/)).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('provider-google'));
    await waitFor(() => expect(assign).toHaveBeenCalledWith(address));
    expect(JSON.parse(window.sessionStorage.getItem(FLOW_KEY) ?? '{}')).toEqual({
      provider: 'google',
      flowId: 'flow-7',
    });
    expect(fake.post).toHaveBeenCalledWith(
      '/api/v2/c02/access-begin-identity-flow',
      expect.objectContaining({ provider: 'google', intent: 'sign_in' }),
    );
    // Leaving for the provider: a second tap sends no second start.
    expect(screen.getByTestId('provider-google')).toBeDisabled();
  });

  it('refuses a provider address that is not https and stays on the entry', async () => {
    const assign = vi.fn();
    vi.spyOn(window, 'location', 'get').mockReturnValue({
      ...window.location,
      origin: 'http://127.0.0.1:18109',
      pathname: '/',
      hash: '',
      assign,
    } as Location);
    const fake = entry(
      () => ({ authorizationUrl: 'http://accounts.example.test/authorize', flowId: 'flow-8' }),
      { 'provider.google': { state: 'available' } },
    );
    fireEvent.click(screen.getByTestId('provider-google'));
    await waitFor(() => expect(fake.post).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(screen.getByTestId('provider-google')).toBeEnabled());
    expect(assign).not.toHaveBeenCalled();
  });
});

describe('email-link proofs in the fragment', () => {
  it('reads the reset proof from the fragment, clears it, and completes the reset', async () => {
    window.history.replaceState(null, '', '/account/password-reset#challenge=ch&proof=pr&flow=fl');
    const fake = entry(() => ({}));
    expect(window.location.hash).toBe('');
    fireEvent.change(screen.getByTestId('proof-password'), { target: { value: NEW_VALUE } });
    fireEvent.click(screen.getByTestId('proof-submit'));
    expect(
      await screen.findByText('확인했습니다. 필요한 경우 다시 로그인해 주세요.'),
    ).toBeInTheDocument();
    expect(fake.post).toHaveBeenCalledWith('/api/v2/c02/access-complete-password-reset', {
      verification: { challengeId: 'ch', proof: 'pr', flowBinding: 'fl' },
      newPassword: NEW_VALUE,
    });
  });

  it.each(['password-reset', 'verify-email'] as const)(
    'moves focus from the completed proof to the sign-in address, never the body (%s)',
    async (kind) => {
      atLink(kind);
      const user = userEvent.setup();
      entry(() => ({}));
      if (kind === 'password-reset')
        fireEvent.change(screen.getByTestId('proof-password'), {
          target: { value: NEW_VALUE },
        });
      screen.getByTestId('proof-submit').focus();
      await user.keyboard('{Enter}');
      expect(
        await screen.findByText('확인했습니다. 필요한 경우 다시 로그인해 주세요.'),
      ).toBeInTheDocument();
      expect(screen.queryByTestId('proof-form')).toBeNull();
      await waitFor(() => expect(screen.getByTestId('entry-email')).toHaveFocus());
      expect(document.activeElement).not.toBe(document.body);
    },
  );

  it('tells a fresh browser it cannot finish a reset requested elsewhere', async () => {
    window.history.replaceState(null, '', '/account/password-reset#challenge=ch&proof=pr&flow=fl');
    entry(() => apiError(403, 'FORBIDDEN'));
    fireEvent.change(screen.getByTestId('proof-password'), { target: { value: NEW_VALUE } });
    fireEvent.click(screen.getByTestId('proof-submit'));
    expect(await screen.findByText(FRESH_BROWSER)).toBeInTheDocument();
  });

  it('completes an email verification and an email change without a password', async () => {
    window.history.replaceState(null, '', '/account/verify-email#challenge=a&proof=b&flow=c');
    const first = entry(() => ({}));
    expect(screen.getByText('이메일 인증을 완료해 주세요')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('proof-submit'));
    await waitFor(() =>
      expect(first.post).toHaveBeenCalledWith('/api/v2/c02/access-verify-email', {
        verification: { challengeId: 'a', proof: 'b', flowBinding: 'c' },
      }),
    );
  });

  it('ignores an incomplete fragment and a path that carries no proof', () => {
    window.history.replaceState(null, '', '/account/email-change#challenge=a');
    entry(() => ({}));
    expect(screen.queryByTestId('proof-form')).toBeNull();
    expect(screen.getByTestId('sign-in-form')).toBeInTheDocument();
  });
});

// Step 91(c)'s texts, copied from the plan (L1-1).
const REFUSED: Readonly<Record<'password-reset' | 'verify-email', string>> = {
  'password-reset':
    '이 비밀번호 재설정 링크는 재설정을 요청한 브라우저에서만 쓸 수 있습니다. 이미 사용했거나 유효 기간이 지난 링크도 쓸 수 없습니다. 이 브라우저에서 비밀번호 재설정을 다시 요청해 주세요.',
  'verify-email':
    '이 이메일 인증 링크는 인증을 요청한 브라우저에서만 쓸 수 있습니다. 이미 사용했거나 유효 기간이 지난 링크도 쓸 수 없습니다. 이 브라우저에서 인증 메일을 다시 요청해 주세요.',
};
const REQUESTED: Readonly<Record<'password-reset' | 'verify-email', string>> = {
  'password-reset':
    '요청을 접수했습니다. 계정이 있으면 재설정 링크를 이메일로 보냅니다. 메일의 링크는 이 브라우저에서 열어 주세요.',
  'verify-email':
    '요청을 접수했습니다. 인증이 필요한 계정이 있으면 인증 링크를 이메일로 보냅니다. 메일의 링크는 이 브라우저에서 열어 주세요.',
};
const EMAIL_CHANGE_REFUSED_TEXT =
  '이 이메일 변경 링크는 변경을 요청한 브라우저에서, 요청한 계정으로 로그인한 상태에서만 쓸 수 있습니다. 이미 사용했거나 유효 기간이 지난 링크도 쓸 수 없습니다. 이 브라우저에서 계정 화면의 ‘비밀번호와 이메일’에서 ‘이메일 변경 인증 요청’을 다시 눌러 주세요.';
const LIMIT_TEXT =
  '지금은 이메일을 보낼 수 없습니다. 11월 2일 오전 9시(한국 시간)부터 다시 보낼 수 있습니다.';
const PROOF = { challengeId: 'ch-7', proof: 'pr-7', flowBinding: 'fl-7' };

/** Account mail at its limit: a 429 whose wait reaches the next 00:00 UTC (L1-10). */
function mailLimit(retryAfterSeconds?: number): ApiError {
  return new ApiError(429, {
    code: 'RATE_LIMITED',
    requestId: 'req-mail-1',
    retryable: true,
    messageKey: 'account-mail.allowance-exhausted',
    ...(retryAfterSeconds !== undefined ? { retryAfterSeconds } : {}),
  });
}

function atLink(kind: string) {
  window.history.replaceState(null, '', `/account/${kind}#challenge=ch-7&proof=pr-7&flow=fl-7`);
}

describe('a refused email link', () => {
  it.each(['password-reset', 'verify-email'] as const)(
    'each email link refused shows that it works only in the asking browser and offers to ask again here (%s)',
    async (kind) => {
      atLink(kind);
      let submits = 0;
      const fake = entry((path) => {
        if (path.includes('access-request-')) return {};
        submits += 1;
        return apiError(403, 'FORBIDDEN');
      });
      expect(screen.getByTestId('proof-binding-note')).toHaveTextContent(
        '이 링크는 요청한 브라우저에서만 쓸 수 있습니다.',
      );
      if (kind === 'password-reset')
        fireEvent.change(screen.getByTestId('proof-password'), {
          target: { value: NEW_VALUE },
        });
      fireEvent.click(screen.getByTestId('proof-submit'));
      expect(await screen.findByText(REFUSED[kind])).toBeInTheDocument();
      expect(submits).toBe(1);
      if (kind === 'password-reset') expect(screen.getByTestId('proof-password')).toHaveValue('');
      await waitFor(() => expect(screen.getByTestId('proof-ask-email')).toHaveFocus());
      // An empty address sends nothing.
      fireEvent.click(screen.getByTestId('proof-ask-again'));
      expect(screen.getByText('이메일을 입력해 주세요')).toBeInTheDocument();
      expect(fake.post.mock.calls.some(([path]) => String(path).includes('access-request-'))).toBe(
        false,
      );
      fireEvent.change(screen.getByTestId('proof-ask-email'), {
        target: { value: 'x@example.test' },
      });
      fireEvent.click(screen.getByTestId('proof-ask-again'));
      expect(await screen.findByText(REQUESTED[kind])).toBeInTheDocument();
      expect(fake.post).toHaveBeenLastCalledWith(
        kind === 'password-reset'
          ? '/api/v2/c02/access-request-password-reset'
          : '/api/v2/c02/access-request-verification',
        kind === 'password-reset'
          ? { email: 'x@example.test', policyRef: { policyId: 'u8-synthetic-v1', revision: '1' } }
          : {
              email: 'x@example.test',
              policyRef: { policyId: 'synthetic-local-entry', revision: '1' },
            },
      );
      expect(screen.getByTestId('sign-in-form')).toBeInTheDocument();
      await waitFor(() => expect(screen.getByTestId('entry-email')).toHaveFocus());
    },
  );

  it('keeps the plain error for any other failure', async () => {
    atLink('verify-email');
    entry(() => apiError(503, 'DEPENDENCY_UNAVAILABLE'));
    fireEvent.click(screen.getByTestId('proof-submit'));
    expect(await screen.findByText(/일시적으로 사용할 수 없어요/)).toBeInTheDocument();
    expect(screen.queryByText(REFUSED['verify-email'])).toBeNull();
    expect(screen.queryByTestId('proof-ask-again')).toBeNull();
  });

  it('keeps proof-submit focusable while a submit is pending, and ignores a second press', async () => {
    atLink('verify-email');
    const user = userEvent.setup();
    let release: (value: unknown) => void = () => undefined;
    const fake = entry(() => new Promise((resolve) => (release = resolve)));
    const submit = screen.getByTestId('proof-submit');
    await user.click(submit);
    expect(submit).toHaveAttribute('aria-disabled', 'true');
    expect(submit).not.toHaveAttribute('disabled');
    expect(submit).toHaveFocus();
    await user.keyboard('{Enter}');
    await user.click(submit);
    expect(fake.post).toHaveBeenCalledTimes(1);
    release({});
    await waitFor(() => expect(screen.queryByTestId('proof-form')).toBeNull());
  });
});

describe('account mail at its limit', () => {
  it('says when email can be sent again when account mail is at its limit', async () => {
    vi.useFakeTimers({ toFake: ['Date'] });
    vi.setSystemTime(new Date('2026-11-01T14:30:00Z'));
    entry(() => mailLimit(34200));
    fireEvent.change(screen.getByTestId('entry-email'), { target: { value: 'x@example.test' } });
    fireEvent.click(screen.getByTestId('entry-reset'));
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent(LIMIT_TEXT);
    for (const absent of ['요청을 접수했습니다', '잠시 후', '요청이 많아요', '내일'])
      expect(alert).not.toHaveTextContent(absent);
  });

  it("answers verify-email's ask-again with the same text", async () => {
    vi.useFakeTimers({ toFake: ['Date'] });
    vi.setSystemTime(new Date('2026-11-01T14:30:00Z'));
    atLink('verify-email');
    entry((path) =>
      path.includes('access-request-') ? mailLimit(34200) : apiError(403, 'FORBIDDEN'),
    );
    fireEvent.click(screen.getByTestId('proof-submit'));
    fireEvent.change(await screen.findByTestId('proof-ask-email'), {
      target: { value: 'x@example.test' },
    });
    fireEvent.click(screen.getByTestId('proof-ask-again'));
    expect(await screen.findByText(new RegExp(LIMIT_TEXT.slice(0, 20)))).toHaveTextContent(
      LIMIT_TEXT,
    );
    expect(screen.queryByText(/요청을 접수했습니다/)).toBeNull();
  });

  it("names the month's reset for the month's limit", async () => {
    vi.useFakeTimers({ toFake: ['Date'] });
    vi.setSystemTime(new Date('2026-10-05T03:00:00Z'));
    entry(() => mailLimit(2322000));
    fireEvent.change(screen.getByTestId('entry-email'), { target: { value: 'x@example.test' } });
    fireEvent.click(screen.getByTestId('entry-reset'));
    expect(await screen.findByRole('alert')).toHaveTextContent(
      '지금은 이메일을 보낼 수 없습니다. 11월 1일 오전 9시(한국 시간)부터 다시 보낼 수 있습니다.',
    );
  });
});

describe('an email change while signed out', () => {
  it('asks a signed-out person to sign in first for an email change', () => {
    const fake = fakeClient(() => ({}));
    const onProofTaken = vi.fn();
    render(
      <Fresh>
        <CompleteEntry
          client={fake.transport}
          states={{}}
          initialProof={{ action: 'email-change', verification: PROOF }}
          onProofTaken={onProofTaken}
          onSignedIn={vi.fn(async () => undefined)}
        />
      </Fresh>,
    );
    expect(screen.queryByTestId('proof-form')).toBeNull();
    expect(screen.getByTestId('email-change-sign-in-first')).toHaveTextContent(
      '이메일 변경을 마치려면 변경을 요청한 브라우저에서 같은 계정으로 로그인해 주세요. 로그인하면 변경 확인으로 이어집니다.',
    );
    expect(fake.post).not.toHaveBeenCalled();
    expect(fake.read).not.toHaveBeenCalled();
    expect(fake.get).not.toHaveBeenCalled();
    expect(onProofTaken).not.toHaveBeenCalled();
  });
});

describe('the signed-in email change', () => {
  function proofPanel(answer: Answer) {
    const fake = fakeClient(answer);
    const handlers = { onDone: vi.fn(), onOpenAccount: vi.fn(), onLeave: vi.fn() };
    render(
      <Fresh>
        <EmailChangeProof
          client={fake.transport}
          proof={{ action: 'email-change', verification: PROOF }}
          {...handlers}
        />
      </Fresh>,
    );
    return { ...fake, ...handlers };
  }

  it('sends the change with the session and hands its end to the shell', async () => {
    const fake = proofPanel(() => ({}));
    expect(screen.getByTestId('proof-binding-note')).toHaveTextContent(
      '이 링크는 요청한 브라우저에서, 요청한 계정으로 로그인한 상태에서만 쓸 수 있습니다.',
    );
    fireEvent.click(screen.getByTestId('proof-submit'));
    await waitFor(() => expect(fake.onDone).toHaveBeenCalledTimes(1));
    expect(fake.post).toHaveBeenCalledWith('/api/v2/c02/access-complete-email-change', {
      verification: PROOF,
    });
  });

  it('a refused change says why and offers to ask again from the account view', async () => {
    const user = userEvent.setup();
    const fake = proofPanel(() => apiError(403, 'FORBIDDEN'));
    fireEvent.click(screen.getByTestId('proof-submit'));
    expect(await screen.findByText(EMAIL_CHANGE_REFUSED_TEXT)).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId('proof-ask-again')).toHaveFocus());
    await user.keyboard('{Enter}');
    expect(fake.onOpenAccount).toHaveBeenCalledTimes(1);
    expect(fake.onDone).not.toHaveBeenCalled();
  });

  it('moves focus to proof-ask-again at every refusal, not only the first', async () => {
    const user = userEvent.setup();
    const fake = proofPanel(() => apiError(403, 'FORBIDDEN'));
    const submit = screen.getByTestId('proof-submit');
    submit.focus();
    await user.keyboard('{Enter}');
    await waitFor(() => expect(screen.getByTestId('proof-ask-again')).toHaveFocus());
    submit.focus();
    await user.keyboard('{Enter}');
    await waitFor(() => expect(fake.post).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(screen.getByTestId('proof-ask-again')).toHaveFocus());
    expect(screen.getByRole('alert')).toHaveTextContent(EMAIL_CHANGE_REFUSED_TEXT);
    expect(fake.onOpenAccount).not.toHaveBeenCalled();
  });

  it('another failure keeps the plain error', async () => {
    const fake = proofPanel(() => apiError(503, 'DEPENDENCY_UNAVAILABLE'));
    fireEvent.click(screen.getByTestId('proof-submit'));
    expect(await screen.findByText(/일시적으로 사용할 수 없어요/)).toBeInTheDocument();
    expect(screen.queryByText(EMAIL_CHANGE_REFUSED_TEXT)).toBeNull();
    expect(fake.onDone).not.toHaveBeenCalled();
  });

  it('closing drops the proof', async () => {
    const user = userEvent.setup();
    const fake = proofPanel(() => ({}));
    screen.getByTestId('proof-back').focus();
    await user.keyboard('{Enter}');
    expect(fake.onLeave).toHaveBeenCalledTimes(1);
  });

  it('stays focusable while it sends', async () => {
    const user = userEvent.setup();
    let release: (value: unknown) => void = () => undefined;
    const fake = proofPanel(() => new Promise((resolve) => (release = resolve)));
    const submit = screen.getByTestId('proof-submit');
    await user.click(submit);
    expect(submit).toHaveAttribute('aria-disabled', 'true');
    expect(submit).not.toHaveAttribute('disabled');
    expect(submit).toHaveFocus();
    await user.click(submit);
    await user.keyboard('{Enter}');
    expect(fake.post).toHaveBeenCalledTimes(1);
    release({});
    await waitFor(() => expect(fake.onDone).toHaveBeenCalledTimes(1));
  });
});

describe('keyboard parity for the consent step and the second-factor prompt', () => {
  async function consentRun(byKeyboard: boolean) {
    const user = userEvent.setup();
    const fake = fakeClient(() => ({
      items: [{ purposeId: 'local-research', decision: 'revoked', revision: '4' }],
    }));
    const onComplete = vi.fn();
    const view = render(
      <ConsentStep
        client={fake.transport}
        policy={POLICY}
        purposes={['local-research', 'personalization']}
        onComplete={onComplete}
      />,
    );
    const required = screen.getByTestId('consent-local-research');
    if (byKeyboard) {
      for (let step = 0; step < 6 && document.activeElement !== required; step += 1)
        await user.tab();
      expect(required).toHaveFocus();
      await user.keyboard(' ');
      expect(required).toBeChecked();
      await user.tab();
      expect(screen.getByTestId('consent-personalization')).toHaveFocus();
      await user.keyboard(' ');
      await user.keyboard(' ');
      expect(screen.getByTestId('consent-personalization')).not.toBeChecked();
      screen.getByTestId('consent-continue').focus();
      await user.keyboard('{Enter}');
    } else {
      await user.click(required);
      await user.click(screen.getByTestId('consent-continue'));
    }
    await waitFor(() => expect(onComplete).toHaveBeenCalledTimes(1));
    const sent = fake.post.mock.calls;
    view.unmount();
    return sent;
  }

  it('toggles and submits by keyboard as by a click, and the MFA prompt acts by Enter', async () => {
    const byKeyboard = await consentRun(true);
    const byClick = await consentRun(false);
    expect(byKeyboard).toEqual(byClick);
    expect(byKeyboard).toHaveLength(2);
    const user = userEvent.setup();
    const onSignInAgain = vi.fn();
    render(
      <AdminMfaPrompt
        client={fakeClient(() => ({})).transport}
        policy={POLICY}
        mode="reverify"
        onSignInAgain={onSignInAgain}
      />,
    );
    screen.getByTestId('admin-mfa-sign-in-again').focus();
    await user.keyboard('{Enter}');
    expect(onSignInAgain).toHaveBeenCalledTimes(1);
  });
});

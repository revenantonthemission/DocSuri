import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { AuthenticationPanel, takeProofLink } from '../../src/auth';
import {
  AccountControls,
  ConsentControls,
  MfaControls,
  LifecycleProgress,
} from '../../src/account-controls';
import { fakeClient, failed, page, policy, profile } from './fixtures';
vi.mock('qrcode', () => ({ default: { toCanvas: vi.fn().mockResolvedValue(undefined) } }));
vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({
  clearRect: vi.fn(),
} as unknown as CanvasRenderingContext2D);
const input = (label: string, value: string) =>
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
const open = (text: string) => fireEvent.click(screen.getByText(text));
function auth(overrides = {}, initialProof?: ReturnType<typeof takeProofLink>) {
  const client = fakeClient({
    '/api/v2/c02/access-inspect-session': { state: 'anonymous', requestId: 'r' },
    ...overrides,
  });
  const signed = vi.fn().mockResolvedValue({ signedIn: true, csrfToken: 'csrf' });
  const lifecycle = vi.fn();
  render(
    <AuthenticationPanel
      client={client.transport}
      policy={policy}
      onSignedIn={signed}
      onLifecycle={lifecycle}
      initialProof={initialProof}
    />,
  );
  return { client, signed, lifecycle };
}
function account(overrides = {}) {
  const client = fakeClient(overrides);
  const changed = vi.fn().mockResolvedValue({});
  const lifecycle = vi.fn();
  render(
    <AccountControls
      client={client.transport}
      policy={policy}
      onAuthorityChange={changed}
      onLifecycle={lifecycle}
    />,
  );
  return { client, changed, lifecycle };
}
describe('U2 account flows', () => {
  it('uses the guarded local identity sign-in callback without external navigation', async () => {
    const { client, signed } = auth({
      '/api/v2/c02/access-begin-identity-flow': {
        authorizationUrl: '/api/v2/identity/callback/google?code=fixture',
      },
    });
    client.post.mockResolvedValue({
      authorizationUrl: '/api/v2/identity/callback/google?code=fixture',
    });
    open('google 시험 로그인');
    await waitFor(() => expect(signed).toHaveBeenCalledOnce());
    expect(client.post).toHaveBeenCalledWith(
      '/api/v2/c02/access-begin-identity-flow',
      { provider: 'google', intent: 'sign_in', returnRouteId: 'search', policyRef: policy },
      expect.any(String),
    );
    expect(client.get).toHaveBeenCalledWith('/api/v2/identity/callback/google?code=fixture');
  });
  it('refuses an external identity redirect', async () => {
    const { client, signed } = auth({
      '/api/v2/c02/access-begin-identity-flow': {
        authorizationUrl: 'https://external.example/callback',
      },
    });
    client.post.mockResolvedValue({ authorizationUrl: 'https://external.example/callback' });
    open('google 시험 로그인');
    await screen.findByRole('alert');
    expect(client.get).not.toHaveBeenCalled();
    expect(signed).not.toHaveBeenCalled();
  });

  it('logs in with the entry policy and clears the password', async () => {
    const { client, signed } = auth();
    client.post.mockResolvedValue({ state: 'authenticated', session: {} });
    input('이메일', 'a@example.test');
    input('비밀번호', 'secret');
    fireEvent.click(screen.getByTestId('entry-submit'));
    await waitFor(() => expect(signed).toHaveBeenCalledOnce());
    expect(client.post.mock.calls[0][1]).toEqual({
      email: 'a@example.test',
      password: 'secret',
      policyRef: { policyId: 'synthetic-local-entry', revision: '1' },
    });
    expect(screen.getByLabelText('비밀번호')).toHaveValue('');
  });
  it('registers with neutral local-delivery feedback and supports resend', async () => {
    const { client } = auth();
    open('가입하기');
    input('이메일', 'a@example.test');
    input('비밀번호', 'password');
    input('표시 이름', '연구원');
    fireEvent.click(screen.getByTestId('entry-submit'));
    expect(await screen.findByText(/대상과 조건이 맞으면/)).toBeVisible();
    open('인증 안내 다시 요청');
    await waitFor(() =>
      expect(client.post).toHaveBeenLastCalledWith(
        '/api/v2/c02/access-request-verification',
        expect.objectContaining({ email: 'a@example.test' }),
        expect.any(String),
      ),
    );
  });
  it('requests password reset without asserting account existence', async () => {
    const { client } = auth();
    open('비밀번호를 잊었나요?');
    input('이메일', 'unknown@example.test');
    fireEvent.click(screen.getByTestId('entry-submit'));
    await waitFor(() =>
      expect(client.post).toHaveBeenCalledWith(
        '/api/v2/c02/access-request-password-reset',
        { email: 'unknown@example.test', policyRef: policy },
        expect.any(String),
      ),
    );
  });
  it('requests reactivation separately from login', async () => {
    const { client } = auth();
    open('탈퇴 계정 재활성화');
    input('이메일', 'a@example.test');
    fireEvent.click(screen.getByTestId('entry-submit'));
    await waitFor(() =>
      expect(client.post).toHaveBeenCalledWith(
        '/api/v2/c02/access-request-reactivation',
        expect.objectContaining({ email: 'a@example.test' }),
        expect.any(String),
      ),
    );
  });
  it.each(['verify-email', 'email-change', 'password-reset', 'reactivate'] as const)(
    'consumes %s proof only on explicit submit',
    async (action) => {
      const verification = { challengeId: 'challenge', flowBinding: 'flow', proof: 'proof' };
      const { client, lifecycle } = auth({}, { action, verification });
      client.post.mockResolvedValue({
        lifecycleRequestId: action === 'reactivate' ? 'life-1' : undefined,
      });
      expect(client.post).not.toHaveBeenCalled();
      if (action === 'password-reset') input('새 비밀번호', 'replacement');
      fireEvent.click(screen.getByTestId('entry-submit'));
      await waitFor(() => expect(client.post).toHaveBeenCalledOnce());
      expect(client.post.mock.calls[0][1]).toEqual(expect.objectContaining({ verification }));
      if (action === 'reactivate')
        await waitFor(() => expect(lifecycle).toHaveBeenCalledWith('life-1'));
    },
  );
  it('removes proof material from the URL immediately', () => {
    window.history.replaceState(
      null,
      '',
      '/?action=verify-email&challengeId=c&flowBinding=f&proof=p',
    );
    expect(takeProofLink()).toEqual({
      action: 'verify-email',
      verification: { challengeId: 'c', flowBinding: 'f', proof: 'p' },
    });
    expect(window.location.search).toBe('');
    expect(takeProofLink()).toBeNull();
  });
  it('restores limited MFA continuation and requires factor verification', async () => {
    const { client, signed } = auth({
      '/api/v2/c02/access-inspect-session': {
        state: 'mfa_required',
        challengeId: 'c',
        flowBinding: 'f',
        expiresAt: '2099-01-01T00:00:00Z',
      },
    });
    input(await screen.findByLabelText('인증 앱 코드').then(() => '인증 앱 코드'), '123456');
    fireEvent.click(screen.getByTestId('entry-submit'));
    await waitFor(() => expect(signed).toHaveBeenCalledOnce());
    expect(client.post).toHaveBeenCalledWith(
      '/api/v2/c02/access-verify-mfa',
      { factorKind: 'totp', verification: { challengeId: 'c', flowBinding: 'f', proof: '123456' } },
      expect.any(String),
    );
  });
  it('retries an unknown login with the same operation identity', async () => {
    const { client } = auth();
    client.post
      .mockRejectedValueOnce(failed('UNKNOWN_OUTCOME'))
      .mockResolvedValueOnce({ state: 'authenticated', session: {} });
    input('이메일', 'a@example.test');
    input('비밀번호', 'secret');
    fireEvent.click(screen.getByTestId('entry-submit'));
    open(await screen.findByText('같은 요청의 결과 확인').then(() => '같은 요청의 결과 확인'));
    await waitFor(() => expect(client.post).toHaveBeenCalledTimes(2));
    expect(client.post.mock.calls[0]).toEqual(client.post.mock.calls[1]);
  });
  it('keeps entered profile values through a stale revision failure', async () => {
    const { client } = account();
    await screen.findByDisplayValue('연구자 A');
    client.post.mockRejectedValueOnce(failed('STALE_REVISION'));
    input('표시 이름', '수정한 이름');
    open('프로필 저장');
    expect(await screen.findByText('다른 곳에서 변경되었어요')).toBeVisible();
    expect(screen.getByLabelText('표시 이름')).toHaveValue('수정한 이름');
    expect(client.post.mock.calls[0][1]).toEqual(
      expect.objectContaining({ expectedRevision: 'profile-r1' }),
    );
  });
  it('saves only mutable profile fields using the returned vocabulary', async () => {
    const { client } = account();
    await screen.findByDisplayValue('연구자 A');
    client.post.mockResolvedValue(profile);
    open('프로필 저장');
    await waitFor(() => expect(client.post).toHaveBeenCalledOnce());
    expect(
      client.post.mock.calls[0][1].changes.map((v: { fieldId: string }) => v.fieldId),
    ).not.toContain('role');
  });
  it('changes password and returns to fresh authentication', async () => {
    const { client, changed } = account();
    await screen.findByDisplayValue('연구자 A');
    open('비밀번호와 이메일');
    input('현재 비밀번호', 'old');
    input('새 비밀번호', 'new');
    open('비밀번호 변경 후 다시 로그인');
    await waitFor(() => expect(changed).toHaveBeenCalledOnce());
    expect(client.post.mock.calls[0][1]).toEqual({ currentPassword: 'old', newPassword: 'new' });
  });
  it('requests email change without changing the displayed email', async () => {
    const { client } = account();
    await screen.findByDisplayValue('연구자 A');
    open('비밀번호와 이메일');
    input('현재 비밀번호', 'old');
    input('새 이메일', 'next@example.test');
    open('이메일 변경 인증 요청');
    await waitFor(() => expect(client.post).toHaveBeenCalledOnce());
    expect(screen.getByText(/a@example.test/)).toBeVisible();
  });
  it('uses consent-specific revisions and does not promise cleanup completion', async () => {
    const client = fakeClient();
    render(<ConsentControls client={client.transport} policy={policy} />);
    open('개인정보와 처리 동의');
    open(await screen.findByText('동의 철회').then(() => '동의 철회'));
    await waitFor(() =>
      expect(client.post).toHaveBeenCalledWith(
        '/api/v2/c02/access-update-consent',
        {
          purposeId: 'personalization',
          decision: 'revoked',
          expectedRevision: 'consent-r1',
          policyRef: policy,
        },
        expect.any(String),
      ),
    );
    expect(screen.getByText(/기존 데이터 삭제와 처리 완료 여부는 별도/)).toBeVisible();
  });
  it('rejects a provider URL outside the local callback allowlist', async () => {
    const { client } = account();
    await screen.findByDisplayValue('연구자 A');
    open('Google · ORCID 연결');
    client.post.mockResolvedValue({ authorizationUrl: 'https://evil.example/callback' });
    open('google 시험 연결');
    await waitFor(() => expect(client.post).toHaveBeenCalledOnce());
    expect(client.get).not.toHaveBeenCalled();
  });
  it('follows a local fixture callback then reloads links', async () => {
    const { client } = account();
    await screen.findByDisplayValue('연구자 A');
    open('Google · ORCID 연결');
    client.post.mockResolvedValue({
      authorizationUrl: '/api/v2/identity/callback/google?flow=f&state=s&code=c',
    });
    open('google 시험 연결');
    await waitFor(() =>
      expect(client.get).toHaveBeenCalledWith(
        '/api/v2/identity/callback/google?flow=f&state=s&code=c',
      ),
    );
  });
  it('unlinks a selected identity using that link revision', async () => {
    const { client } = account({
      '/api/v2/c02/access-list-identity-links': page([
        {
          identityLinkId: 'link-a',
          provider: 'orcid',
          providerSubject: 'fixture',
          revision: 'link-r1',
          profileAvailable: true,
        },
      ]),
    });
    await screen.findByDisplayValue('연구자 A');
    open('Google · ORCID 연결');
    open('연결 해제');
    await waitFor(() =>
      expect(client.post).toHaveBeenCalledWith(
        '/api/v2/c02/access-unlink-identity',
        { identityLinkId: 'link-a', expectedRevision: 'link-r1' },
        expect.any(String),
      ),
    );
  });
  it('prepares lifecycle proof but requires a second explicit confirmation', async () => {
    const { client, lifecycle, changed } = account();
    await screen.findByDisplayValue('연구자 A');
    open('탈퇴와 데이터 삭제');
    input('계정 처리용 현재 비밀번호', 'secret');
    client.post
      .mockResolvedValueOnce({ confirmationRef: 'confirmation-a', action: 'withdraw' })
      .mockResolvedValueOnce({ lifecycleRequestId: 'life-a' });
    open('처리 범위 확인 준비');
    expect(await screen.findByText('확인하고 접수')).toBeVisible();
    expect(client.post).toHaveBeenCalledTimes(1);
    open('확인하고 접수');
    await waitFor(() => expect(lifecycle).toHaveBeenCalledWith('life-a'));
    expect(changed).toHaveBeenCalledOnce();
  });
  it('displays incomplete lifecycle work separately from access revocation', async () => {
    const client = fakeClient({
      '/api/v2/c02/lifecycle-inspect': {
        lifecycleRequestId: 'life-a',
        state: 'blocked',
        revocation: 'effective',
        participants: [{ participantId: 'Library', state: 'blocked' }],
      },
    });
    render(<LifecycleProgress client={client.transport} id="life-a" />);
    expect(await screen.findByText(/아직 완료되지/)).toBeVisible();
    expect(screen.getByText('접근 중지: effective')).toBeVisible();
    expect(client.post).not.toHaveBeenCalled();
  });
  it('retrieves MFA material once and clears it when hidden', async () => {
    const client = fakeClient();
    client.post
      .mockResolvedValueOnce({
        enrollmentId: 'enroll-a',
        deliveryReference: 'delivery-a',
        expiresAt: '2099-01-01T00:00:00Z',
        nextAction: 'confirm_factor',
      })
      .mockResolvedValueOnce({
        enrollmentId: 'enroll-a',
        seed: 'PRIVATE-SEED',
        provisioningUri: 'otpauth://totp/test?secret=PRIVATE',
        recoveryCodes: ['RECOVERY-1'],
        expiresAt: new Date(Date.now() + 60_000).toISOString(),
      });
    render(<MfaControls client={client.transport} policy={policy} />);
    open('추가 인증(MFA)');
    input('MFA 설정용 현재 비밀번호', 'secret');
    open('새 MFA 등록 준비');
    await screen.findByText('설정 키 한 번 보기');
    input('MFA 설정용 현재 비밀번호', 'secret');
    open('설정 키 한 번 보기');
    expect(await screen.findByText('PRIVATE-SEED')).toBeVisible();
    open('설정 자료 숨기기');
    expect(screen.queryByText('PRIVATE-SEED')).toBeNull();
    expect(window.localStorage.length).toBe(0);
  });
  it('confirms MFA with the current full session binding', async () => {
    const client = fakeClient();
    client.post
      .mockResolvedValueOnce({
        enrollmentId: 'enroll-a',
        deliveryReference: 'delivery-a',
        expiresAt: '2099-01-01T00:00:00Z',
        nextAction: 'confirm_factor',
      })
      .mockResolvedValue({});
    render(<MfaControls client={client.transport} policy={policy} />);
    open('추가 인증(MFA)');
    input('MFA 설정용 현재 비밀번호', 'secret');
    open('새 MFA 등록 준비');
    await screen.findByText('등록 확인 코드');
    input('등록 확인 코드', '123456');
    open('MFA 등록 확인');
    await waitFor(() => expect(client.post).toHaveBeenCalledTimes(2));
    expect(client.post.mock.calls[1][1]).toEqual({
      enrollmentId: 'enroll-a',
      verification: { challengeId: 'enroll-a', flowBinding: 'session-a', proof: '123456' },
    });
  });
});

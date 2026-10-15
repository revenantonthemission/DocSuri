import React, { useEffect, useRef, useState } from 'react';
import { ENTRY_POLICY, PolicyRef, SessionBootstrap, Transport } from './api';
import { Notice, Panel, StatusLine, notice } from './ui';
import { Field, OperationStatus, useOperation } from './control-ui';

export type SessionStatus =
  | { state: 'anonymous' }
  | {
      state: 'authenticated';
      session: {
        accountId: string;
        sessionId: string;
        authorityRevision: string;
        authenticationLevel: 'primary' | 'mfa';
      };
    }
  | { state: 'mfa_required'; challengeId: string; flowBinding: string; expiresAt: string };
type Proof = { challengeId: string; flowBinding: string; proof: string };
export type ProofAction = 'verify-email' | 'password-reset' | 'email-change' | 'reactivate';
export function takeProofLink(): { action: ProofAction; verification: Proof } | null {
  const params = new URLSearchParams(window.location.search);
  const action = params.get('action') ?? params.get('purpose');
  if (!['verify-email', 'password-reset', 'email-change', 'reactivate'].includes(action ?? ''))
    return null;
  const verification = {
    challengeId: params.get('challengeId') ?? '',
    flowBinding: params.get('flowBinding') ?? '',
    proof: params.get('proof') ?? '',
  };
  window.history.replaceState(null, '', window.location.pathname);
  return { action: action as ProofAction, verification };
}
export function AuthenticationPanel({
  client,
  policy,
  onSignedIn,
  onLifecycle,
  initialProof,
  onProofConsumed,
  onProofComplete,
  noticeValue,
}: {
  client: Transport;
  policy: PolicyRef;
  onSignedIn: () => Promise<SessionBootstrap>;
  onLifecycle: (id: string) => void;
  initialProof?: ReturnType<typeof takeProofLink>;
  onProofConsumed?: () => void;
  onProofComplete?: () => void;
  noticeValue?: Notice | null;
}) {
  const [mode, setMode] = useState<'login' | 'register' | 'password-reset' | 'reactivate'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('연구자');
  const [factor, setFactor] = useState('');
  const [continuation, setContinuation] = useState<Extract<
    SessionStatus,
    { state: 'mfa_required' }
  > | null>(null);
  const [proofLink, setProofLink] = useState(initialProof ?? null);
  useEffect(() => {
    if (initialProof) onProofConsumed?.();
  }, [initialProof, onProofConsumed]);
  const [copy, setCopy] = useState<Notice | null>(null);
  const operation = useOperation();
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    client
      .read<SessionStatus>('/api/v2/c02/access-inspect-session', {})
      .then((value) => {
        if (alive.current && value.state === 'mfa_required') setContinuation(value);
      })
      .catch(() => undefined);
    return () => {
      alive.current = false;
    };
  }, [client]);
  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    void operation.run(async (key) => {
      if (continuation) {
        await client.post(
          '/api/v2/c02/access-verify-mfa',
          {
            factorKind: 'totp',
            verification: {
              challengeId: continuation.challengeId,
              flowBinding: continuation.flowBinding,
              proof: factor,
            },
          },
          key,
        );
        setFactor('');
        setContinuation(null);
        await onSignedIn();
        return;
      }
      if (proofLink) {
        const action = proofLink.action;
        const path =
          action === 'verify-email'
            ? 'access-verify-email'
            : action === 'password-reset'
              ? 'access-complete-password-reset'
              : action === 'email-change'
                ? 'access-complete-email-change'
                : 'lifecycle-reactivate';
        const result = await client.post<{ lifecycleRequestId?: string }>(
          `/api/v2/c02/${path}`,
          {
            verification: proofLink.verification,
            ...(action === 'password-reset' ? { newPassword: password } : {}),
            ...(action === 'reactivate'
              ? { policyRef: policy, confirmationRef: proofLink.verification.challengeId }
              : {}),
          },
          key,
        );
        setProofLink(null);
        onProofComplete?.();
        setPassword('');
        setCopy(notice('polite', '인증 요청을 확인했어요. 필요한 경우 다시 로그인해 주세요'));
        if (result.lifecycleRequestId) onLifecycle(result.lifecycleRequestId);
        await onSignedIn();
        return;
      }
      if (!email.trim()) throw new Error('email required');
      if (mode === 'login') {
        const result = await client.post<SessionStatus>(
          '/api/v2/c02/access-login',
          { email, password, policyRef: ENTRY_POLICY },
          key,
        );
        setPassword('');
        await onSignedIn();
        if (result.state === 'mfa_required') setContinuation(result);
      } else {
        await client.post(
          `/api/v2/c02/${mode === 'register' ? 'access-register' : mode === 'reactivate' ? 'access-request-reactivation' : 'access-request-password-reset'}`,
          {
            email,
            ...(mode === 'register'
              ? { password, displayName, policyRef: ENTRY_POLICY }
              : { policyRef: policy }),
          },
          key,
        );
        setPassword('');
        setCopy(
          notice(
            'polite',
            '요청을 접수했어요. 대상과 조건이 맞으면 로컬 인증 전달함에 안내가 준비돼요. 실제 이메일 발송은 제공하지 않아요',
          ),
        );
      }
    });
  };
  const switchMode = (next: typeof mode) => {
    setMode(next);
    setPassword('');
    setFactor('');
    setProofLink(null);
    setCopy(null);
  };
  return (
    <Panel title="시작하기" testId="entry-panel">
      <p className="muted">
        게스트로 검색과 읽기를 사용할 수 있어요. 계정 기능은 격리된 로컬 시험 환경이에요.
      </p>
      <StatusLine value={noticeValue ?? copy} />
      <OperationStatus operation={operation} />
      <form className="stack" onSubmit={submit}>
        <fieldset disabled={operation.busy || operation.unknown}>
          {continuation ? (
            <>
              <p>추가 인증이 필요해요. 인증 앱의 코드를 입력해 주세요.</p>
              <Field
                id="mfa-factor"
                label="인증 앱 코드"
                value={factor}
                onChange={setFactor}
                autoComplete="one-time-code"
              />
              <p>MFA 복구는 승인된 복구 정책이 준비될 때까지 사용할 수 없어요.</p>
            </>
          ) : proofLink ? (
            <>
              <p>
                {proofLink.action === 'password-reset'
                  ? '새 비밀번호를 입력해 주세요'
                  : '전달받은 인증을 완료해 주세요'}
              </p>
              <Field
                id="proof"
                label="인증 코드"
                value={proofLink.verification.proof}
                onChange={(proof) =>
                  setProofLink({ ...proofLink, verification: { ...proofLink.verification, proof } })
                }
                autoComplete="one-time-code"
              />
              {proofLink.action === 'password-reset' ? (
                <Field
                  id="reset-password"
                  label="새 비밀번호"
                  secret
                  value={password}
                  onChange={setPassword}
                  autoComplete="new-password"
                />
              ) : null}
            </>
          ) : (
            <>
              <Field
                id="entry-email"
                label="이메일"
                type="email"
                value={email}
                onChange={setEmail}
                autoComplete="email"
              />
              {mode === 'login' || mode === 'register' ? (
                <Field
                  id="entry-password"
                  label="비밀번호"
                  secret
                  value={password}
                  onChange={setPassword}
                  autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                />
              ) : null}
              {mode === 'register' ? (
                <Field
                  id="entry-display-name"
                  label="표시 이름"
                  value={displayName}
                  onChange={setDisplayName}
                  autoComplete="nickname"
                />
              ) : null}
            </>
          )}
          <button type="submit" data-testid="entry-submit">
            {continuation
              ? '추가 인증 완료'
              : proofLink
                ? '인증 완료'
                : {
                    login: '로그인',
                    register: '가입하기',
                    'password-reset': '비밀번호 재설정 요청',
                    reactivate: '재활성화 요청',
                  }[mode]}
          </button>
        </fieldset>
      </form>
      <div className="row">
        {(['login', 'register', 'password-reset', 'reactivate'] as const)
          .filter((value) => value !== mode)
          .map((value) => (
            <button
              type="button"
              key={value}
              disabled={operation.busy || operation.unknown}
              onClick={() => switchMode(value)}
              data-testid={value === 'register' || value === 'login' ? 'entry-switch' : undefined}
            >
              {
                {
                  login: '로그인으로 돌아가기',
                  register: '가입하기',
                  'password-reset': '비밀번호를 잊었나요?',
                  reactivate: '탈퇴 계정 재활성화',
                }[value]
              }
            </button>
          ))}
      </div>
      {mode === 'register' ? (
        <button
          type="button"
          disabled={operation.busy || !email}
          onClick={() =>
            void operation.run(async (key) => {
              await client.post(
                '/api/v2/c02/access-request-verification',
                { email, policyRef: ENTRY_POLICY },
                key,
              );
              setCopy(
                notice(
                  'polite',
                  '인증 안내를 요청했어요. 조건이 맞으면 로컬 전달함을 확인해 주세요',
                ),
              );
            })
          }
        >
          인증 안내 다시 요청
        </button>
      ) : null}
      {!continuation && !proofLink && mode === 'login' ? (
        <section aria-label="시험 제공자 로그인">
          <p>로컬 시험용 Google·ORCID 로그인이에요. 실제 제공자 로그인은 아직 사용할 수 없어요.</p>
          {(['google', 'orcid'] as const).map((provider) => (
            <button
              key={provider}
              type="button"
              disabled={operation.busy || operation.unknown}
              onClick={() =>
                void operation.run(async (key) => {
                  const result = await client.post<{ authorizationUrl: string }>(
                    '/api/v2/c02/access-begin-identity-flow',
                    { provider, intent: 'sign_in', returnRouteId: 'search', policyRef: policy },
                    key,
                  );
                  const url = new URL(result.authorizationUrl, window.location.origin);
                  if (
                    url.origin !== window.location.origin ||
                    url.pathname !== `/api/v2/identity/callback/${provider}`
                  )
                    throw new Error('unapproved identity return');
                  await client.get(url.pathname + url.search);
                  const status = await client.read<SessionStatus>(
                    '/api/v2/c02/access-inspect-session',
                    {},
                  );
                  if (status.state === 'mfa_required') setContinuation(status);
                  await onSignedIn();
                })
              }
            >
              {provider} 시험 로그인
            </button>
          ))}
        </section>
      ) : null}
      <p className="muted">입력 중인 비밀번호와 인증 코드는 저장되지 않아요.</p>
    </Panel>
  );
}

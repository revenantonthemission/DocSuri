/**
 * The complete assembly's entry (BR6.4, BR8.6, BR9.6, D1, D3): password sign-in with C02
 * 4.0.0's `AccessSignInResult` (a second factor, a consent-pending first sign-in, a
 * reset-required account, an administrator's setup-only session), Google and ORCID through
 * their real authorization pages, the password-reset and reactivation requests, and the
 * four email links, whose proofs arrive in the address's fragment at
 * `/account/password-reset`, `/account/verify-email`, `/account/email-change` and
 * `/account/reactivate` (reactivation by your decision of 2026-10-23). Registration stays
 * closed.
 *
 * AccountAccess's control policy is named by the deployment's origin: a caller with no
 * session reads only the public capability projection, which carries no policy (BR5.9).
 */
import React, { useEffect, useRef, useState } from 'react';
import { ApiError, ENTRY_POLICY, type PolicyRef, type Transport } from '../api';
import { describeError, notice, Panel, StatusLine, type Notice } from '../ui';
import { isPublicPage } from '../u8-shell/capabilities';
import { MaintenanceBanner } from '../u8-shell/maintenance-banner';
import { MovedNotice } from '../u8-shell/moved-notice';
import styles from '../u8-shell/shell.module.css';
import {
  ProviderSignInButtons,
  ProviderStateNotice,
  type CapabilityStateMap,
  type IdentityProvider,
} from '../u8-shell/provider-notice';
import { keepFlow } from './callback-page';
import {
  AdminMfaPrompt,
  ConsentStep,
  ResetRequiredNotice,
  type ResetDelivery,
} from './first-sign-in';

export const PRODUCTION_ORIGIN = 'https://docsuri.rvnnt.dev';
export function controlPolicyFor(origin: string): PolicyRef {
  return origin === PRODUCTION_ORIGIN
    ? { policyId: 'docsuri-production-v1', revision: '1' }
    : { policyId: 'u8-synthetic-v1', revision: '1' };
}

export type ProofAction = 'password-reset' | 'verify-email' | 'email-change' | 'reactivate';
export const PROOF_PATHS: Readonly<Record<string, ProofAction>> = {
  '/account/password-reset': 'password-reset',
  '/account/verify-email': 'verify-email',
  '/account/email-change': 'email-change',
  '/account/reactivate': 'reactivate',
};
// L1-1: an email link works only in the browser that asked (U2's built protection). Each
// kind's refusal names that browser, a used or expired link, and the way forward from
// this browser; it follows a refused submit (L1-54, "Explain after a refused submit").
export const FRESH_BROWSER =
  '이 비밀번호 재설정 링크는 재설정을 요청한 브라우저에서만 쓸 수 있습니다. 이미 사용했거나 유효 기간이 지난 링크도 쓸 수 없습니다. 이 브라우저에서 비밀번호 재설정을 다시 요청해 주세요.';
export const VERIFICATION_REFUSED =
  '이 이메일 인증 링크는 인증을 요청한 브라우저에서만 쓸 수 있습니다. 이미 사용했거나 유효 기간이 지난 링크도 쓸 수 없습니다. 이 브라우저에서 인증 메일을 다시 요청해 주세요.';
export const EMAIL_CHANGE_REFUSED =
  '이 이메일 변경 링크는 변경을 요청한 브라우저에서, 요청한 계정으로 로그인한 상태에서만 쓸 수 있습니다. 이미 사용했거나 유효 기간이 지난 링크도 쓸 수 없습니다. 이 브라우저에서 계정 화면의 ‘비밀번호와 이메일’에서 ‘이메일 변경 인증 요청’을 다시 눌러 주세요.';
/** The binding, stated on arrival before anything is typed (`proof-binding-note`). */
export const BINDING_NOTE = '이 링크는 요청한 브라우저에서만 쓸 수 있습니다.';
export const RESET_REQUESTED =
  '요청을 접수했습니다. 계정이 있으면 재설정 링크를 이메일로 보냅니다. 메일의 링크는 이 브라우저에서 열어 주세요.';
// The same answer whatever the account: it never says whether one exists or was withdrawn.
export const REACTIVATION_REQUESTED =
  '요청을 접수했습니다. 탈퇴한 계정이 있으면 재활성화 링크를 이메일로 보냅니다. 메일의 링크는 이 브라우저에서 열어 주세요.';
export const VERIFICATION_REQUESTED =
  '요청을 접수했습니다. 인증이 필요한 계정이 있으면 인증 링크를 이메일로 보냅니다. 메일의 링크는 이 브라우저에서 열어 주세요.';
/** A signed-out email-change link: the change finishes only in a session (Step 91(l)). */
export const EMAIL_CHANGE_SIGN_IN_FIRST =
  '이메일 변경을 마치려면 변경을 요청한 브라우저에서 같은 계정으로 로그인해 주세요. 로그인하면 변경 확인으로 이어집니다.';
export const REACTIVATION_ACCEPTED =
  '재활성화를 접수했습니다. 처리가 끝나면 다시 로그인할 수 있습니다.';
/** A new password the password policy refuses: the answer's `messageKey` `password.policy`
 * (your answer of 2026-11-11, "Say the password is too weak"). */
export const WEAK_PASSWORD =
  '이 비밀번호는 사용할 수 없습니다. 더 길고 추측하기 어려운 비밀번호를 입력해 주세요.';
export const REACTIVATION_REFUSED =
  '이 재활성화 링크는 재활성화를 요청한 브라우저에서만 쓸 수 있습니다. 이미 사용했거나 유효 기간이 지난 링크도 쓸 수 없습니다. 이 브라우저에서 재활성화를 다시 요청해 주세요.';
/** One refusal text per kind of email link (L1-1). */
export const LINK_REFUSED: Readonly<Record<ProofAction, string>> = {
  'password-reset': FRESH_BROWSER,
  'verify-email': VERIFICATION_REFUSED,
  'email-change': EMAIL_CHANGE_REFUSED,
  reactivate: REACTIVATION_REFUSED,
};
/** The ask-again control for the three kinds the sign-in form asks again for. */
const ASK_AGAIN: Readonly<Record<Exclude<ProofAction, 'email-change'>, string>> = {
  'password-reset': '이 브라우저에서 비밀번호 재설정 다시 요청',
  'verify-email': '이 브라우저에서 인증 메일 다시 요청',
  reactivate: '이 브라우저에서 재활성화 다시 요청',
};
/** The busy answer's `messageKey` for the site-wide start limits and a conflict (the
 * person's decision of 2026-10-25, "Different text for site-wide"). */
export const SITE_WIDE_START_KEYS: ReadonlySet<string> = new Set([
  'identity-start.site-places',
  'identity-start.site-starts',
  'identity-start.conflict',
]);

/** A refused provider sign-in start (the person's decisions of 2026-10-25, "Count every
 * start, free places at once" and "Different text for site-wide"): the wait from
 * `Retry-After`, and email sign-in. The site text answers the site-wide limits and a
 * conflict; the address and account limits, and any other or missing key, keep the
 * network text. Both wordings go to the person at the U8 checkpoint. */
export function providerWaitText(seconds: number, messageKey?: string): string {
  if (messageKey !== undefined && SITE_WIDE_START_KEYS.has(messageKey)) {
    return `지금 Google·ORCID 로그인을 하려는 사람이 많아요. ${seconds}초 뒤에 다시 시도하거나 이메일로 로그인해 주세요`;
  }
  return `같은 네트워크에서 진행 중인 Google·ORCID 로그인이 많아요. ${seconds}초 뒤에 다시 시도하거나 이메일로 로그인해 주세요`;
}

/** An email link's proof, read from the fragment. */
export type Proof = {
  action: ProofAction;
  verification: { challengeId: string; proof: string; flowBinding: string };
};

/** The email link's proof from the fragment, removed from the address at once. */
export function takeFragmentProof(): Proof | null {
  const action = PROOF_PATHS[window.location.pathname];
  if (!action || !window.location.hash) return null;
  const params = new URLSearchParams(window.location.hash.slice(1));
  window.history.replaceState(null, '', window.location.pathname);
  const challengeId = params.get('challenge') ?? '';
  const proof = params.get('proof') ?? '';
  const flowBinding = params.get('flow') ?? '';
  if (!challengeId || !proof || !flowBinding) return null;
  return { action, verification: { challengeId, proof, flowBinding } };
}

type Answer =
  | { state: 'authenticated'; session: { authenticationLevel: 'primary' | 'mfa' } }
  | { state: 'signed_in' }
  | { state: 'mfa_required'; challengeId?: string; flowBinding?: string; mfaChallenge?: Challenge }
  | { state: 'consent_pending'; consentPurposeIds: string[] }
  | { state: 'reset_required'; delivery: ResetDelivery };
type Challenge = { challengeId: string; flowBinding: string };
type Step =
  | { kind: 'form' }
  | { kind: 'mfa'; challenge: Challenge }
  | { kind: 'consent'; purposes: string[] }
  | { kind: 'reset'; delivery: ResetDelivery }
  | { kind: 'setup' };

function Input({
  id,
  label,
  value,
  onChange,
  secret = false,
  autoComplete,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  secret?: boolean;
  autoComplete: string;
}) {
  return (
    <label className="control-field" htmlFor={id}>
      {label}
      <input
        id={id}
        type={secret ? 'password' : 'text'}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        autoComplete={autoComplete}
        maxLength={secret ? 1024 : 4096}
        data-testid={id}
      />
    </label>
  );
}

function challengeOf(answer: Extract<Answer, { state: 'mfa_required' }>): Challenge {
  return (
    answer.mfaChallenge ?? {
      challengeId: answer.challengeId ?? '',
      flowBinding: answer.flowBinding ?? '',
    }
  );
}

/** Focus an element by id once it has rendered. */
function focusById(id: string): void {
  document.getElementById(id)?.focus();
}

/** The proof CompleteEntry starts from: App's (`initialProof`), else the fragment's, as
 * built. An email-change proof never shows a form here: it finishes only signed in. */
function startingProof(initialProof: Proof | null | undefined): {
  proof: Proof | null;
  signInFirst: boolean;
} {
  const source = initialProof !== undefined ? initialProof : takeFragmentProof();
  if (source?.action === 'email-change') return { proof: null, signInFirst: true };
  return { proof: source, signInFirst: false };
}

export function CompleteEntry({
  client,
  states,
  initialAnswer,
  initialProof,
  initialNotice,
  onProofTaken,
  onSignedIn,
}: {
  client: Transport;
  states: CapabilityStateMap;
  /** An identity callback's answer, handed on by the arrival page. */
  initialAnswer?: unknown;
  /** The email link's proof App took in its first render; omitted, the fragment is read. */
  initialProof?: Proof | null;
  /** A notice App hands on, such as a confirmed email change's. */
  initialNotice?: Notice | null;
  /** Called once this entry holds a password-reset, verify-email or reactivate proof. */
  onProofTaken?: () => void;
  onSignedIn: () => Promise<unknown>;
}) {
  const policy = controlPolicyFor(window.location.origin);
  const email = useRef<HTMLInputElement | null>(null);
  const [step, setStep] = useState<Step>({ kind: 'form' });
  const [address, setAddress] = useState('');
  const [password, setPassword] = useState('');
  const [factor, setFactor] = useState('');
  const [start] = useState(() => startingProof(initialProof));
  const [proof, setProof] = useState<Proof | null>(start.proof);
  const [busy, setBusy] = useState(false);
  // The busy rule: controls stay focusable while busy (aria-disabled) and ignore presses.
  const busyNow = useRef(false);
  // After a refused proof: the ask-again controls, and a focus request for each refusal.
  const [askAgain, setAskAgain] = useState(false);
  const [askAddress, setAskAddress] = useState('');
  const [askFocus, setAskFocus] = useState(0);
  const [emailFocus, setEmailFocus] = useState(0);
  // Leaving for the provider's page: its buttons stay disabled, so a second tap sends no
  // second start; a return from the page cache enables them again.
  const [leaving, setLeaving] = useState(false);
  const [message, setMessage] = useState<Notice | null>(initialNotice ?? null);

  useEffect(() => {
    const returned = (event: PageTransitionEvent) => {
      if (event.persisted) setLeaving(false);
    };
    window.addEventListener('pageshow', returned);
    return () => window.removeEventListener('pageshow', returned);
  }, []);

  useEffect(() => {
    if (start.proof && onProofTaken) onProofTaken();
    // App's kept proof is handed over once, when this entry first holds it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (askFocus > 0) focusById('proof-ask-email');
  }, [askFocus]);

  useEffect(() => {
    if (emailFocus > 0) email.current?.focus();
  }, [emailFocus]);

  // The password step's answer replaces the sign-in form with the second factor's: focus
  // moves to its field, never to the page body (Step 91(g)).
  useEffect(() => {
    if (step.kind === 'mfa') focusById('entry-factor');
  }, [step.kind]);

  const follow = async (answer: unknown) => {
    const value = answer as Answer;
    if (value.state === 'mfa_required')
      return setStep({ kind: 'mfa', challenge: challengeOf(value) });
    if (value.state === 'consent_pending') {
      // The sign-in issued a consent-pending session with its own CSRF token; the
      // transport still holds the guest's, which the consent routes refuse (the migration
      // journey found the refusal), as the second factor's check does.
      await client.bootstrap();
      return setStep({ kind: 'consent', purposes: value.consentPurposeIds });
    }
    if (value.state === 'reset_required')
      return setStep({ kind: 'reset', delivery: value.delivery });
    // Signed in: a full session, or an administrator's setup-only session, which reads
    // only the public projection until the second factor is enrolled.
    const capabilities = await client.get<unknown>('/api/v2/capabilities');
    if (isPublicPage(capabilities)) return setStep({ kind: 'setup' });
    setStep({ kind: 'form' });
    await onSignedIn();
    return undefined;
  };

  useEffect(() => {
    if (initialAnswer !== undefined) void follow(initialAnswer);
    // The arrival's answer is followed once, as it was handed on.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialAnswer]);

  /** Run one request; while it runs every press is ignored. `refusal` may answer a failure
   * with its own notice; otherwise a policy-refused password or `describeError`. */
  const run = async (
    work: () => Promise<void>,
    refusal?: (error: unknown) => Notice | null,
  ): Promise<void> => {
    if (busyNow.current) return;
    busyNow.current = true;
    setBusy(true);
    setMessage(null);
    try {
      await work();
    } catch (error) {
      const weak = error instanceof ApiError && error.envelope.messageKey === 'password.policy';
      setMessage(
        weak ? notice('alert', WEAK_PASSWORD) : (refusal?.(error) ?? describeError(error)),
      );
    } finally {
      busyNow.current = false;
      setBusy(false);
    }
  };

  const signIn = (event: React.FormEvent) => {
    event.preventDefault();
    if (busyNow.current) return;
    if (!address.trim() || !password) {
      setMessage(notice('alert', '이메일과 비밀번호를 확인해 주세요'));
      return;
    }
    void run(async () => {
      const answer = await client.post<Answer>('/api/v2/c02/access-login', {
        email: address,
        password,
        policyRef: ENTRY_POLICY,
      });
      setPassword('');
      await follow(answer);
    });
  };

  const verifyFactor = (event: React.FormEvent) => {
    event.preventDefault();
    if (step.kind !== 'mfa' || busyNow.current) return;
    void run(async () => {
      // The password step issued a new limited session with its own CSRF token; the
      // transport still holds the guest's, which the second factor's check refuses.
      await client.bootstrap();
      await client.post('/api/v2/c02/access-verify-mfa', {
        factorKind: 'totp',
        verification: { ...step.challenge, proof: factor },
      });
      setFactor('');
      await follow({ state: 'authenticated', session: { authenticationLevel: 'mfa' } });
    });
  };

  // A refused link (403): its kind's text, the typed new password cleared, and the
  // ask-again controls under the proof form, with focus on their address field (L1-1).
  const refuseProof = (action: ProofAction) => (error: unknown) => {
    if (!(error instanceof ApiError) || error.status !== 403) return null;
    setPassword('');
    setAskAgain(true);
    setAskFocus((value) => value + 1);
    return notice('alert', LINK_REFUSED[action]);
  };

  const completeProof = (event: React.FormEvent) => {
    event.preventDefault();
    if (!proof || busyNow.current) return;
    void run(async () => {
      if (proof.action === 'reactivate') {
        await client.post('/api/v2/c02/lifecycle-reactivate', {
          confirmationRef: proof.verification.challengeId,
          verification: proof.verification,
          policyRef: policy,
        });
        setProof(null);
        setAskAgain(false);
        setMessage(notice('polite', REACTIVATION_ACCEPTED));
        // The sign-in form replaces the proof form: focus lands on its address field,
        // never on the page body (Step 91(g)).
        setEmailFocus((value) => value + 1);
        return;
      }
      const path = {
        'password-reset': 'access-complete-password-reset',
        'verify-email': 'access-verify-email',
        'email-change': 'access-complete-email-change',
      }[proof.action];
      await client.post(`/api/v2/c02/${path}`, {
        verification: proof.verification,
        ...(proof.action === 'password-reset' ? { newPassword: password } : {}),
      });
      setPassword('');
      setProof(null);
      setAskAgain(false);
      setMessage(notice('polite', '확인했습니다. 필요한 경우 다시 로그인해 주세요.'));
      setEmailFocus((value) => value + 1);
    }, refuseProof(proof.action));
  };

  // Asking again from this browser after a refused link. The answer is the same whatever
  // the account; the stale proof is dropped and the sign-in form takes focus.
  const requestAgain = () => {
    if (!proof || proof.action === 'email-change' || busyNow.current) return;
    if (!askAddress.trim()) {
      setMessage(notice('alert', '이메일을 입력해 주세요'));
      return;
    }
    const kind = proof.action;
    void run(async () => {
      if (kind === 'password-reset') {
        await client.post('/api/v2/c02/access-request-password-reset', {
          email: askAddress,
          policyRef: policy,
        });
      } else if (kind === 'verify-email') {
        // The verification request's route requires the entry policy.
        await client.post('/api/v2/c02/access-request-verification', {
          email: askAddress,
          policyRef: ENTRY_POLICY,
        });
      } else {
        await client.post('/api/v2/c02/access-request-reactivation', {
          email: askAddress,
          policyRef: policy,
        });
      }
      setProof(null);
      setAskAgain(false);
      setPassword('');
      setMessage(
        notice(
          'polite',
          kind === 'password-reset'
            ? RESET_REQUESTED
            : kind === 'verify-email'
              ? VERIFICATION_REQUESTED
              : REACTIVATION_REQUESTED,
        ),
      );
      setEmailFocus((value) => value + 1);
    });
  };

  const requestReactivation = () => {
    if (busyNow.current) return;
    if (!address.trim()) {
      setMessage(notice('alert', '이메일을 입력해 주세요'));
      return;
    }
    void run(async () => {
      await client.post('/api/v2/c02/access-request-reactivation', {
        email: address,
        policyRef: policy,
      });
      setMessage(notice('polite', REACTIVATION_REQUESTED));
    });
  };

  const leaveProof = () => {
    if (busyNow.current) return;
    setProof(null);
    setAskAgain(false);
    setPassword('');
    setMessage(null);
    // The abandoned proof's form leaves with the focused control: the sign-in form's
    // address field takes the focus (Step 91(g)).
    setEmailFocus((value) => value + 1);
  };

  // The notice's 관리자 로그인 (BR6.4, L4-15): from a proof form or the second-factor form
  // it leaves that form for the sign-in form, as the form's own way back does, and the
  // address field then takes the focus.
  const administratorSignIn = () => {
    if (busyNow.current) return;
    if (proof) return leaveProof();
    if (step.kind === 'mfa') {
      // As the proof form's way back does: the code and a refused code's message go too.
      setFactor('');
      setMessage(null);
      setStep({ kind: 'form' });
    }
    setEmailFocus((value) => value + 1);
  };

  const requestReset = () => {
    if (busyNow.current) return;
    if (!address.trim()) {
      setMessage(notice('alert', '이메일을 입력해 주세요'));
      return;
    }
    void run(async () => {
      await client.post('/api/v2/c02/access-request-password-reset', {
        email: address,
        policyRef: policy,
      });
      setMessage(notice('polite', RESET_REQUESTED));
    });
  };

  const beginProvider = (provider: IdentityProvider) =>
    void run(async () => {
      // The provider buttons stay natively disabled while busy, as built.
      let begun: { authorizationUrl: string; flowId: string };
      try {
        begun = await client.post('/api/v2/c02/access-begin-identity-flow', {
          provider,
          intent: 'sign_in',
          returnRouteId: 'search',
          policyRef: policy,
        });
      } catch (error) {
        const wait = error instanceof ApiError ? error.envelope.retryAfterSeconds : undefined;
        if (error instanceof ApiError && error.status === 429 && wait !== undefined) {
          setMessage(
            notice(
              'alert',
              providerWaitText(wait, error.envelope.messageKey),
              error.envelope.requestId,
            ),
          );
          return;
        }
        throw error;
      }
      const target = new URL(begun.authorizationUrl);
      if (target.protocol !== 'https:') throw new Error('unapproved authorization address');
      keepFlow(provider, begun.flowId);
      setLeaving(true);
      window.location.assign(target.toString());
    });

  if (step.kind === 'consent') {
    return (
      <ConsentStep
        client={client}
        policy={policy}
        purposes={step.purposes}
        onComplete={() =>
          void follow({ state: 'authenticated', session: { authenticationLevel: 'primary' } })
        }
      />
    );
  }
  if (step.kind === 'setup') {
    return (
      <AdminMfaPrompt
        client={client}
        policy={policy}
        mode="setup"
        onSignInAgain={() => {
          setStep({ kind: 'form' });
          void onSignedIn();
        }}
      />
    );
  }
  return (
    <Panel title="로그인" testId="complete-entry">
      <MovedNotice />
      <MaintenanceBanner states={states} onAdministratorSignIn={administratorSignIn} />
      <StatusLine value={message} />
      {step.kind === 'reset' ? <ResetRequiredNotice delivery={step.delivery} /> : null}
      {proof ? (
        <form className="stack" onSubmit={completeProof} data-testid="proof-form">
          <p>
            {
              {
                'password-reset': '새 비밀번호를 입력해 주세요',
                'verify-email': '이메일 인증을 완료해 주세요',
                'email-change': '새 이메일 주소를 확인해 주세요',
                reactivate: '탈퇴한 계정의 재활성화를 확인해 주세요',
              }[proof.action]
            }
          </p>
          <p data-testid="proof-binding-note">{BINDING_NOTE}</p>
          {proof.action === 'password-reset' ? (
            <Input
              id="proof-password"
              label="새 비밀번호"
              secret
              value={password}
              onChange={setPassword}
              autoComplete="new-password"
            />
          ) : null}
          <button type="submit" aria-disabled={busy} data-testid="proof-submit">
            확인
          </button>
          {proof.action === 'reactivate' ? (
            <button
              type="button"
              aria-disabled={busy}
              onClick={leaveProof}
              data-testid="proof-back"
            >
              로그인 화면으로 돌아가기
            </button>
          ) : null}
        </form>
      ) : step.kind === 'mfa' ? (
        <form className="stack" onSubmit={verifyFactor} data-testid="mfa-form">
          <p>추가 인증이 필요합니다. 인증 앱의 코드를 입력해 주세요.</p>
          <Input
            id="entry-factor"
            label="인증 앱 코드"
            value={factor}
            onChange={setFactor}
            autoComplete="one-time-code"
          />
          <button type="submit" aria-disabled={busy} data-testid="mfa-submit">
            추가 인증 완료
          </button>
        </form>
      ) : (
        <form className="stack" onSubmit={signIn} data-testid="sign-in-form">
          {start.signInFirst ? (
            <p data-testid="email-change-sign-in-first">{EMAIL_CHANGE_SIGN_IN_FIRST}</p>
          ) : null}
          <label htmlFor="entry-email">이메일</label>
          <input
            ref={email}
            id="entry-email"
            type="email"
            autoComplete="email"
            value={address}
            onChange={(event) => setAddress(event.target.value)}
            data-testid="entry-email"
          />
          <Input
            id="entry-password"
            label="비밀번호"
            secret
            value={password}
            onChange={setPassword}
            autoComplete="current-password"
          />
          <div className="row">
            <button type="submit" aria-disabled={busy} data-testid="entry-submit">
              로그인
            </button>
            <button
              type="button"
              className="link"
              aria-disabled={busy}
              onClick={requestReset}
              data-testid="entry-reset"
            >
              비밀번호를 잊었나요?
            </button>
            <button
              type="button"
              className="link"
              aria-disabled={busy}
              onClick={requestReactivation}
              data-testid="entry-reactivate"
            >
              재활성화 요청
            </button>
          </div>
          <ProviderStateNotice states={states} feature="mail" />
        </form>
      )}
      {proof && askAgain && proof.action !== 'email-change' ? (
        // Under the proof form, outside it: Enter in the address field asks again rather
        // than sending the refused proof once more.
        <form
          className="stack"
          onSubmit={(event) => {
            event.preventDefault();
            requestAgain();
          }}
          data-testid="proof-ask"
        >
          <Input
            id="proof-ask-email"
            label="이메일"
            value={askAddress}
            onChange={setAskAddress}
            autoComplete="email"
          />
          <button type="submit" aria-disabled={busy} data-testid="proof-ask-again">
            {ASK_AGAIN[proof.action]}
          </button>
        </form>
      ) : null}
      {!proof && step.kind === 'form' ? (
        <ProviderSignInButtons states={states} busy={busy || leaving} onBegin={beginProvider} />
      ) : null}
      <p className="muted">
        <a href="/privacy" className={styles.target} data-testid="entry-privacy">
          개인정보 처리방침
        </a>{' '}
        ·{' '}
        <a href="/terms" className={styles.target} data-testid="entry-terms">
          이용약관
        </a>
      </p>
    </Panel>
  );
}

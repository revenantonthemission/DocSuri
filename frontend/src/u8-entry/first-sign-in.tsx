/**
 * FirstSignInSteps (frontend-components.md; BR8.6, A3): ConsentStep after a migrated
 * account's first sign-in, ResetRequiredNotice when an account must set a new password,
 * and AdminMfaPrompt before any 운영 data or action for an administrator without a
 * current second factor.
 */
import React, { useEffect, useRef, useState } from 'react';
import { MAIL_HELD_TEXT, type PolicyRef, type Transport } from '../api';
import { MfaControls } from '../account-controls';
import { describeError, Panel, StatusLine, type Notice } from '../ui';

type ConsentRecord = { purposeId: string; decision: 'granted' | 'revoked'; revision: string };

export const CONSENT_REQUIRED = '필수 항목에 동의해야 계속할 수 있습니다';
// v2's consent purposes, with the sign-up wording; `local-research` is required and
// `personalization` optional, starting off.
export const PURPOSES: readonly { id: string; label: string; required: boolean }[] = [
  {
    id: 'local-research',
    label: '논문 검색·읽기·연구 기능 제공을 위한 처리에 동의합니다 (필수)',
    required: true,
  },
  {
    id: 'personalization',
    label: '이용 기록을 바탕으로 한 개인화 추천에 동의합니다 (선택)',
    required: false,
  },
];

export function ConsentStep({
  client,
  policy,
  purposes,
  onComplete,
}: {
  client: Transport;
  policy: PolicyRef;
  purposes: readonly string[];
  onComplete: () => void;
}) {
  const heading = useRef<HTMLHeadingElement | null>(null);
  const summary = useRef<HTMLDivElement | null>(null);
  const [chosen, setChosen] = useState<Record<string, boolean>>({});
  const [missing, setMissing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<Notice | null>(null);
  const shown = PURPOSES.filter((purpose) => purposes.includes(purpose.id));
  useEffect(() => {
    heading.current?.focus();
  }, []);
  useEffect(() => {
    if (missing || failure) summary.current?.focus();
  }, [missing, failure]);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (shown.some((purpose) => purpose.required && !chosen[purpose.id])) {
      setMissing(true);
      return;
    }
    setMissing(false);
    setBusy(true);
    setFailure(null);
    try {
      const page = await client.read<{ items: ConsentRecord[] }>(
        '/api/v2/c02/access-list-consents',
        { page: { limit: 25 } },
      );
      const revisions = Object.fromEntries(
        page.items.map((item) => [item.purposeId, item.revision]),
      );
      for (const purpose of shown) {
        await client.post('/api/v2/c02/access-update-consent', {
          purposeId: purpose.id,
          decision: chosen[purpose.id] ? 'granted' : 'revoked',
          policyRef: policy,
          expectedRevision: revisions[purpose.id] ?? '0',
        });
      }
      onComplete();
    } catch (error) {
      // The choices made stay as they were.
      setFailure(describeError(error));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Panel title="처리 동의" titleRef={heading} testId="consent-step">
      <p>
        새 버전에서 계속 이용하려면 아래 항목을 확인해 주세요. 동의하기 전에는 개인 정보를 불러오지
        않습니다.
      </p>
      <div ref={summary} tabIndex={-1} data-testid="consent-summary">
        {missing ? <p role="alert">{CONSENT_REQUIRED}</p> : null}
        <StatusLine value={failure} />
      </div>
      <form className="stack" onSubmit={submit}>
        <fieldset disabled={busy}>
          <legend>동의 항목</legend>
          {shown.map((purpose) => (
            <label key={purpose.id}>
              <input
                type="checkbox"
                checked={chosen[purpose.id] ?? false}
                aria-required={purpose.required || undefined}
                onChange={(event) =>
                  setChosen((current) => ({ ...current, [purpose.id]: event.target.checked }))
                }
                data-testid={`consent-${purpose.id}`}
              />{' '}
              {purpose.label}
            </label>
          ))}
          <button type="submit" data-testid="consent-continue">
            계속
          </button>
        </fieldset>
      </form>
    </Panel>
  );
}

export type ResetDelivery = 'accepted' | 'held' | 'over_allowance';
export const RESET_SENT =
  '보안을 위해 비밀번호를 다시 설정해야 합니다. 이메일로 재설정 링크를 보냈습니다.';
// `held`: ends with the refusal's own sentence, so the two cannot drift (L1-53).
export const RESET_NOT_SENT = `보안을 위해 비밀번호를 다시 설정해야 합니다. ${MAIL_HELD_TEXT}`;
// `over_allowance`: names no time, and asks for a sign-in once the limit resets (L1-10).
export const RESET_OVER_ALLOWANCE =
  '보안을 위해 비밀번호를 다시 설정해야 합니다. 지금은 이메일 발송 한도에 도달해 재설정 링크를 보내지 못했습니다. 발송 한도가 초기화된 뒤 다시 로그인해 주세요.';

const RESET_TEXT: Readonly<Record<ResetDelivery, string>> = {
  accepted: RESET_SENT,
  held: RESET_NOT_SENT,
  over_allowance: RESET_OVER_ALLOWANCE,
};

export function ResetRequiredNotice({ delivery }: { delivery: ResetDelivery }) {
  return (
    <p role="status" className="status" data-testid="reset-required">
      {RESET_TEXT[delivery] ?? RESET_NOT_SENT}
    </p>
  );
}

export function AdminMfaPrompt({
  client,
  policy,
  mode,
  onSignInAgain,
}: {
  client: Transport;
  policy: PolicyRef;
  mode: 'setup' | 'reverify';
  onSignInAgain: () => void;
}) {
  const heading = useRef<HTMLHeadingElement | null>(null);
  useEffect(() => {
    heading.current?.focus();
  }, []);
  return (
    <Panel title="관리자 추가 인증" titleRef={heading} testId="admin-mfa-prompt">
      {mode === 'setup' ? (
        <>
          <p>
            관리자 계정은 추가 인증(MFA)을 등록해야 운영 기능을 사용할 수 있습니다. 등록을 마치면
            다시 로그인해 주세요.
          </p>
          <MfaControls client={client} policy={policy} />
        </>
      ) : (
        <p>운영 화면을 보려면 추가 인증을 다시 완료해야 합니다. 다시 로그인해 주세요.</p>
      )}
      <button type="button" onClick={onSignInAgain} data-testid="admin-mfa-sign-in-again">
        다시 로그인
      </button>
    </Panel>
  );
}

/**
 * ProviderStateNotice (BR7.2, BR5.9): a feature that depends on a provider shows that
 * provider's state from the capability list. Signed out, the list is the public
 * projection: states and reason keys only.
 */
import React from 'react';
import { MAIL_HELD_TEXT } from '../api';
import styles from './shell.module.css';

export type CapabilityStateMap = Readonly<Record<string, { state: string; reasonKey?: string }>>;

const PROVIDER_NAMES = { google: 'Google', orcid: 'ORCID' } as const;
export type IdentityProvider = keyof typeof PROVIDER_NAMES;

/** A provider serves only while its capability is available or degraded. */
export function serves(states: CapabilityStateMap, capability: string): boolean {
  const state = states[capability]?.state;
  return state === 'available' || state === 'degraded';
}

export function signInUnavailableText(provider: IdentityProvider): string {
  return `지금은 ${PROVIDER_NAMES[provider]} 로그인을 사용할 수 없습니다. 비밀번호로 로그인해 주세요.`;
}

// The notice and the up-front refusal say one sentence (L1-53); it lives in api.ts so that
// ui.tsx still imports no U8 module.
export { MAIL_HELD_TEXT };
export const ASSISTANCE_PENDING_TEXT = '요약·번역 기능을 준비 중입니다';

/** The sign-in buttons for Google and ORCID, each disabled with its reason while its
 * provider does not serve. */
export function ProviderSignInButtons({
  states,
  busy,
  onBegin,
}: {
  states: CapabilityStateMap;
  busy: boolean;
  onBegin: (provider: IdentityProvider) => void;
}) {
  return (
    <section aria-label="다른 방법으로 로그인" data-testid="provider-sign-in">
      {(Object.keys(PROVIDER_NAMES) as IdentityProvider[]).map((provider) => {
        const available = serves(states, `provider.${provider}`);
        const reasonId = `provider-${provider}-reason`;
        return (
          <div key={provider} className={styles.entry}>
            <button
              type="button"
              disabled={busy || !available}
              aria-describedby={available ? undefined : reasonId}
              onClick={() => onBegin(provider)}
              data-testid={`provider-${provider}`}
            >
              {PROVIDER_NAMES[provider]}로 로그인
            </button>
            {available ? null : (
              <span id={reasonId} className={styles.reason}>
                {signInUnavailableText(provider)}
              </span>
            )}
          </div>
        );
      })}
    </section>
  );
}

/** The notice a mail-sending flow or paper assistance shows while its provider waits. */
export function ProviderStateNotice({
  states,
  feature,
}: {
  states: CapabilityStateMap;
  feature: 'mail' | 'assistance';
}) {
  // Signed out, the realm gives the mail provider as serving or not serving alone
  // (`readiness.py`'s `public_mail`), so the mail notice shows exactly while it reads
  // `unavailable`, and never for a state the realm does not send.
  const waiting =
    feature === 'mail'
      ? states['provider.resend']?.state === 'unavailable'
      : states['assistance.summary'] !== undefined && !serves(states, 'assistance.summary');
  if (!waiting) return null;
  // No role of its own: it re-renders on every capability change, and capability changes
  // are announced only through the shell's region (L1-26).
  return (
    <p className={styles.notice} data-testid={`provider-notice-${feature}`}>
      {feature === 'mail' ? MAIL_HELD_TEXT : ASSISTANCE_PENDING_TEXT}
    </p>
  );
}

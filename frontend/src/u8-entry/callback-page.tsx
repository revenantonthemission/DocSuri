/**
 * The identity arrival page, `/sign-in/callback/{provider}` (A8, D3). Before anything
 * renders it removes the whole query from the address with `history.replaceState`. It
 * reads `state` and `code` from the address, and the flow from it or from the flow this
 * tab kept when the sign-in began (`keepFlow`, which the entry panel calls before the
 * browser leaves for the provider). It reads `error` to tell a refusal, and ignores every
 * other key a provider adds (RFC 6749 § 4.1.2; R-09). It then sends only `flow`, `state`
 * and `code` to the API route with a same-site request. An `error` return, a repeated
 * `flow`, `state`, `code` or `error`, or a missing `state`, `code` or flow shows
 * "로그인이 취소되었습니다" with a way back and calls no API route. While admission is
 * maintainer-only, the page shows the maintenance notice with its 관리자 로그인, which
 * leaves for the sign-in form, and a late arrival answer after that is ignored (NFR1.3).
 */
import React, { useEffect, useRef, useState } from 'react';
import type { Transport } from '../api';
import { describeError, Panel, StatusLine, type Notice } from '../ui';
import { MaintenanceBanner } from '../u8-shell/maintenance-banner';
import type { CapabilityStateMap } from '../u8-shell/provider-notice';

export const FLOW_KEY = 'docsuri.private.identity-flow';
export const CANCELLED = '로그인이 취소되었습니다';
const PROVIDERS = ['google', 'orcid'] as const;
export type ArrivalProvider = (typeof PROVIDERS)[number];
// The keys of the provider's answer the page reads. It ignores every other key: Google's
// success redirect adds `scope`, `authuser` and `prompt`, often `hd` and `iss`, answering
// the `scope` `openid email` and `prompt` `select_account` the Google adapter asks for.
const ANSWER_KEYS = ['flow', 'state', 'code', 'error'] as const;

export type Arrival =
  | { kind: 'answer'; provider: ArrivalProvider; flow: string; state: string; code: string }
  | { kind: 'cancelled' };

/** Keep the begun flow for this tab only, for the arrival page to send back. */
export function keepFlow(provider: ArrivalProvider, flowId: string): void {
  try {
    window.sessionStorage.setItem(FLOW_KEY, JSON.stringify({ provider, flowId }));
  } catch {
    // Without storage the arrival cannot name its flow; it reads as cancelled.
  }
}

function takeFlow(provider: ArrivalProvider): string | null {
  try {
    const raw = window.sessionStorage.getItem(FLOW_KEY);
    window.sessionStorage.removeItem(FLOW_KEY);
    const value = raw ? (JSON.parse(raw) as { provider?: string; flowId?: string }) : null;
    return value?.provider === provider && typeof value.flowId === 'string' ? value.flowId : null;
  } catch {
    return null;
  }
}

// The answer read for this address, so a second read of the same render (StrictMode)
// sees what the first one removed.
let taken: { href: string; arrival: Arrival } | null = null;

/** Read and remove the provider's answer from the address (call before rendering). */
export function takeArrival(provider: string): Arrival {
  const href = window.location.href;
  if (taken && (taken.href === href || href === stripped(taken.href))) return taken.arrival;
  const arrival = readArrival(provider);
  taken = { href, arrival };
  return arrival;
}

// The identity arrival page the complete assembly serves (C13 /sign-in/callback/{provider}).
const CALLBACK_PATH = /^\/sign-in\/callback\/([a-z]+)$/;

/** On the arrival page, take the provider's answer out of the address and keep it for
 * CallbackPage, and name the provider; elsewhere `null`. App calls it in its first render,
 * so the answer leaves the address before the shell's capability, session and navigation
 * reads (L1-15). */
export function takeCallbackArrival(): string | null {
  const provider = CALLBACK_PATH.exec(window.location.pathname)?.[1] ?? null;
  if (provider === null) return null;
  takeArrival(provider);
  return provider;
}

/** Once the page has mounted, the next arrival is read afresh. */
export function forgetArrival(): void {
  taken = null;
}

function stripped(href: string): string {
  const address = new URL(href);
  return `${address.origin}${address.pathname}`;
}

function readArrival(provider: string): Arrival {
  const params = new URLSearchParams(window.location.search);
  window.history.replaceState(null, '', window.location.pathname);
  if (!(PROVIDERS as readonly string[]).includes(provider)) return { kind: 'cancelled' };
  const known = provider as ArrivalProvider;
  const stored = takeFlow(known);
  if (params.has('error')) return { kind: 'cancelled' };
  if (ANSWER_KEYS.some((key) => params.getAll(key).length > 1)) return { kind: 'cancelled' };
  const state = params.get('state');
  const code = params.get('code');
  const flow = params.get('flow') ?? stored;
  if (!state || !code || !flow) return { kind: 'cancelled' };
  return { kind: 'answer', provider: known, flow, state, code };
}

export function CallbackPage({
  client,
  provider,
  onArrived,
  onBack,
  states,
  onAdministratorSignIn,
}: {
  client: Transport;
  provider: string;
  onArrived: (answer: unknown) => void;
  onBack: () => void;
  states: CapabilityStateMap;
  onAdministratorSignIn: () => void;
}) {
  const [arrival] = useState(() => takeArrival(provider));
  const [failure, setFailure] = useState<Notice | null>(null);
  const sent = useRef(false);
  // Set at the 관리자 로그인 click, never by an effect's cleanup: StrictMode's repeated
  // effect run is held off by `sent`, so a cleanup flag would drop the one answer.
  const left = useRef(false);
  useEffect(forgetArrival, []);
  useEffect(() => {
    if (arrival.kind !== 'answer' || sent.current) return;
    sent.current = true;
    const query = new URLSearchParams({
      flow: arrival.flow,
      state: arrival.state,
      code: arrival.code,
    });
    client
      .get<unknown>(`/api/v2/identity/callback/${arrival.provider}?${query}`)
      .then((answer) => {
        if (!left.current) onArrived(answer);
      })
      .catch((error) => {
        if (!left.current) setFailure(describeError(error));
      });
  }, [arrival, client, onArrived]);
  const leaveForSignIn = () => {
    left.current = true;
    onAdministratorSignIn();
  };
  const notice = <MaintenanceBanner states={states} onAdministratorSignIn={leaveForSignIn} />;
  if (arrival.kind === 'cancelled') {
    return (
      <Panel title="로그인" testId="callback-cancelled">
        {notice}
        <p role="alert">{CANCELLED}</p>
        <button type="button" onClick={onBack} data-testid="callback-back">
          로그인 화면으로 돌아가기
        </button>
      </Panel>
    );
  }
  return (
    <Panel title="로그인" testId="callback-page">
      {notice}
      {failure ? (
        <>
          <StatusLine value={failure} />
          <button type="button" onClick={onBack} data-testid="callback-back">
            로그인 화면으로 돌아가기
          </button>
        </>
      ) : (
        <p role="status">로그인을 확인하고 있습니다</p>
      )}
    </Panel>
  );
}

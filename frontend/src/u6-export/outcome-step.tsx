/** The outcome step: follows the effect by polling its read (reads never export, BR2.2).

Each state change is announced once through the view's polite live region. Every
status shows text and an icon. The success link is named by the page title; an
owner-settled success is labelled "직접 확인됨" and links only when the owner gave a
link (BR4.7). "취소" is offered while the export is accepted (BR3.6); an unknown
export shows its next check (BR4.4); before the export starts, the step notes that
signing out stops it (BR3.3). */

import React, { useEffect, useRef, useState } from 'react';
import useSWR from 'swr';
import { ApiError, type Transport } from '../api';
import { effectEnded, exportCall, type Effect } from './api';
import {
  EFFECT_STATE_COPY,
  formatTime,
  OUTCOME_REASON_COPY,
  OWNER_CONFIRMED,
  REFUSAL_HINTS,
  SIGN_OUT_NOTE,
} from './copy';
import { refusalText, StatusBadge, type Announce } from './status';

/** How often an export that has not ended is read again. */
export const OUTCOME_POLL_MS = 3_000;

/** The sentence announced for one effect state. */
export function outcomeAnnouncement(effect: Effect): string {
  const status = EFFECT_STATE_COPY[effect.state].text;
  const reason = effect.outcomeReason ? ` · ${OUTCOME_REASON_COPY[effect.outcomeReason]}` : '';
  return `내보내기 상태: ${status}${reason}`;
}

function SuccessLink({ effect, pageTitle }: { effect: Effect; pageTitle: string }) {
  const ownerSettled = effect.settledBy === 'owner';
  return (
    <>
      {ownerSettled ? (
        <p className="export-note" data-testid="outcome-owner-confirmed">
          {OWNER_CONFIRMED}
        </p>
      ) : null}
      {effect.remoteUrl ? (
        <a
          href={effect.remoteUrl}
          target="_blank"
          rel="noopener noreferrer"
          data-testid="outcome-page-link"
        >
          {pageTitle}
          {ownerSettled ? ` (${OWNER_CONFIRMED})` : ''} · Notion에서 열기
        </a>
      ) : null}
    </>
  );
}

export function OutcomeStep({
  client,
  initial,
  pageTitle,
  onFreshPreview,
  announce,
  pollMs = OUTCOME_POLL_MS,
}: {
  client: Transport;
  initial: Effect;
  /** The created page's title, which names the success link. */
  pageTitle: string;
  onFreshPreview: () => void;
  announce: Announce;
  pollMs?: number;
}) {
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const lastAnnounced = useRef<string | null>(null);
  const { data, mutate } = useSWR<Effect>(
    ['u6-export-effect', client, client.generation, initial.effectId],
    () => exportCall(client, 'read-export-effect', { effectId: initial.effectId }),
    {
      fallbackData: initial,
      revalidateOnMount: false,
      revalidateOnFocus: false,
      shouldRetryOnError: false,
      refreshInterval: (latest) => (latest && effectEnded(latest.state) ? 0 : pollMs),
    },
  );
  const effect = data ?? initial;

  // A change is what the owner hears, so a poll that reads the same words again (for
  // example accepted, then executing: both "내보내는 중") announces nothing.
  const announcement = outcomeAnnouncement(effect);
  useEffect(() => {
    if (lastAnnounced.current === announcement) return;
    lastAnnounced.current = announcement;
    announce(announcement);
  }, [announce, announcement]);

  const requestCancel = (expectedRevision: string) =>
    exportCall(client, 'cancel-export-approval', {
      approvalId: effect.approvalId,
      expectedRevision,
    });

  // The lane records internal facts on an accepted export (for example that its check
  // must wait), which advances the revision without changing the state. When the export
  // read again is still accepted, the owner's cancel still applies: it is sent once more
  // at that revision, and the compare-and-set still refuses an export that has started.
  const cancelAtLatest = async (failure: unknown) => {
    if (!(failure instanceof ApiError && failure.envelope.code === 'CONFLICT')) throw failure;
    const latest = await mutate();
    if (!latest || latest.state !== 'accepted' || latest.revision === effect.revision)
      throw failure;
    await requestCancel(latest.revision);
  };

  const cancel = async () => {
    setBusy(true);
    try {
      await requestCancel(effect.revision).catch(cancelAtLatest);
      setNotice(null);
    } catch (failure) {
      const text =
        failure instanceof ApiError && failure.envelope.code === 'CONFLICT'
          ? '이미 내보내는 중이거나 상태가 바뀌어 취소할 수 없습니다'
          : refusalText(failure);
      setNotice(text);
      announce(text);
    } finally {
      setBusy(false);
      void mutate();
    }
  };

  const hint = effect.outcomeReason ? REFUSAL_HINTS[effect.outcomeReason] : undefined;
  return (
    <div className="export-step" data-testid="outcome-step" data-effect-state={effect.state}>
      <p className="export-outcome">
        <StatusBadge status={EFFECT_STATE_COPY[effect.state]} testId="outcome-status" />
      </p>
      {effect.outcomeReason ? (
        <p data-testid="outcome-reason">{OUTCOME_REASON_COPY[effect.outcomeReason]}</p>
      ) : null}
      {hint ? <p className="export-hint">{hint}</p> : null}
      {effect.state === 'succeeded' ? <SuccessLink effect={effect} pageTitle={pageTitle} /> : null}
      {effect.state === 'unknown' ? (
        <p className="export-note" data-testid="outcome-next-check">
          {effect.nextCheckAt
            ? `확인 중 · 다음 확인 ${formatTime(effect.nextCheckAt)}`
            : '확인 중 · 자동 확인으로 정할 수 없으면 내보내기 기록에서 직접 확인할 수 있습니다'}
          . 결과가 정해질 때까지 같은 내보내기를 다시 할 수 없습니다.
        </p>
      ) : null}
      {effect.state === 'accepted' ? (
        <p className="export-note" data-testid="outcome-signout-note">
          {SIGN_OUT_NOTE}
        </p>
      ) : null}
      {notice ? (
        <p className="export-notice" data-testid="outcome-notice">
          {notice}
        </p>
      ) : null}
      <div className="export-actions">
        {effect.state === 'accepted' ? (
          <button
            type="button"
            disabled={busy}
            onClick={() => void cancel()}
            data-testid="outcome-cancel"
          >
            취소
          </button>
        ) : null}
        {effect.state === 'invalidated' ? (
          <button type="button" onClick={onFreshPreview} data-testid="outcome-fresh-preview">
            미리보기 다시 만들기
          </button>
        ) : null}
      </div>
    </div>
  );
}
